from xl30serial.scanningelectronmicroscope import ScanningElectronMicroscope
from xl30serial.scanningelectronmicroscope import ScanningElectronMicroscope_ScanMode, ScanningElectronMicroscope_ImageFilterMode
from xl30serial.scanningelectronmicroscope import ScanningElectronMicroscope_NotConnectedException, ScanningElectronMicroscope_CommunicationError
from xl30serial.scanningelectronmicroscope import ScanningElectronMicroscope_SpecimenCurrentDetectorMode

import atexit
import serial
import logging
import struct
import math

from time import sleep


# Decorators used in this file

class onlyconnected:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if args[0]._port is None:
                args[0]._logger.error(f"[XL30] Called {func} but microscope is not connected")
                raise ScanningElectronMicroscope_NotConnectedException()
            return func(*args, **kwargs)
        return wrapper

class retrylooped:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            retryCountState = args[0]._retryCount
            reconnectCountState = args[0]._reconnectCount

            while True:
                try:
                    retValue = func(*args, **kwargs)
                    return retValue
                except Exception as e:
                    # We have encountered an exception - if we retry we ignore it
                    args[0]._logger.error(f"[XL30] Encountered communication error:\n{e}")
                    if retryCountState > 0:
                        args[0]._logger.warning(f"[XL30] Retrying request (retry {args[0]._retryCount - retryCountState + 1}/{args[0]._retryCount})")
                        # We can simply retry ...
                        retryCountState = retryCountState - 1
                        sleep(args[0]._retryDelay)
                        continue
                    else:
                        # We have to reconnect if we have reconnections available
                        if reconnectCountState > 0:
                            args[0]._logger.warning(f"[XL30] Reconnect to XL30 (attempt {args[0]._reconnectCount - reconnectCountState + 1}/{args[0]._reconnectCount})")
                            args[0]._reconnect()
                            reconnectCountState = reconnectCountState - 1
                        else:
                            self._logger.error(f"[XL30] {args[0]._reconnectCount} reconnection attempts with {args[0]._retryCount} retries each exceeded")
                            raise
        return wrapper


class tested:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

class untested:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            args[0]._logger.warning(f"[XL30] Calling untested function {func} / function with possibly known bugs")
            return func(*args, **kwargs)
        return wrapper
class buggy:
    def __init__(self, *args, **kwargs):
        if 'bugs' in kwargs:
            self._bugs = kwargs['bugs']
        else:
            self._bugs = "Unknown"
        pass
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            args[0]._logger.warning(f"[XL30] Calling function {func} with known bugs ({self._bugs})!")
            return func(*args, **kwargs)
        return wrapper

class XL30(ScanningElectronMicroscope):
    def __init__(self):
        super().__init__(
            highTension = (100, 30e3),
            spotSize = (1, 10),
            magnification = (10, 100000),
            supportedScanModes = [
                ScanningElectronMicroscope_ScanMode.FULL_FRAME,
                ScanningElectronMicroscope_ScanMode.SELECTED_AREA,
                ScanningElectronMicroscope_ScanMode.SPOT,
                ScanningElectronMicroscope_ScanMode.LINE_X,
                ScanningElectronMicroscope_ScanMode.LINE_Y,
                ScanningElectronMicroscope_ScanMode.EXT_XY
            ],
            stigmatorCount = 1
        )
        pass

class XL30Serial(XL30):
    def __init__(self, port, logger = None, debug = False, loglevel = "ERROR", detectorsAutodetect = False, retryCount = 3, reconnectCount = 3, retryDelay = 5, reconnectDelay = 5):
        super().__init__()

        self._retryCount = retryCount
        self._reconnectCount = reconnectCount

        self._retryCountState = retryCount
        self._reconnectCountState = reconnectCount

        self._retryDelay = retryDelay
        self._reconnectDelay = reconnectDelay

        loglvls = {
            "DEBUG"     : logging.DEBUG,
            "INFO"      : logging.INFO,
            "WARNING"   : logging.WARNING,
            "ERROR"     : logging.ERROR,
            "CRITICAL"  : logging.CRITICAL
        }
        self._detectorsAuto = detectorsAutodetect
        self._detectorTypes = {
            0 : { 'short' : 'SSD', 'long' : 'Solid State Detector' },
            1 : { 'short' : 'PMT', 'long' : 'Photo Multiplier' },
            2 : { 'short' : 'SED', 'long' : 'Photo Multiplier, grid, 10 kV' },
            3 : { 'short' : 'XAIB', 'long' : 'eXternal Analog Interface Board' },
            4 : { 'short' : 'MULTIPLE', 'long' : 'Multiple, mixed detector id' }
        }
        self._detectorIds = {
                0 : { 'name' : 'No detector connected',         'type' : None,  'shortname' : None, 'supported' : False },
                1 : { 'name' : 'Specimen current detector',     'type' : 0,     'shortname' : 'SC', 'supported' : False },
                2 : { 'name' : 'Cathode Luminescence',          'type' : 1,     'shortname' : 'CL', 'supported' : False },
                3 : { 'name' : 'Secondary Electron 1',          'type' : 2,     'shortname' : 'SE', 'supported' : False },
                4 : { 'name' : 'Backscatter Electron',          'type' : 0,     'shortname' : 'BSE', 'supported' : False },
                5 : { 'name' : 'Robinson Detector',             'type' : 1,     'shortname' : 'RBS', 'supported' : False },
                6 : { 'name' : 'Secondary Electron 2',          'type' : 2,     'shortname' : 'SE2', 'supported' : False },
                7 : { 'name' : 'Auxiliary 1',                   'type' : None,  'shortname' : None,  'supported' : False },
                8 : { 'name' : 'CCD',                           'type' : 0,     'shortname' : 'CCD', 'supported' : False },
                9 : { 'name' : 'EDX Standard',                  'type' : 3,     'shortname' : 'EDX', 'supported' : False },
                10 : { 'name' : 'WDX',                          'type' : 3,     'shortname' : 'WDX', 'supported' : False },
                11 : { 'name' : 'External video',               'type' : 3,     'shortname' : 'EXT', 'supported' : False },
                12 : { 'name' : 'Phax PV9900',                  'type' : 3,     'shortname' : 'HAX', 'supported' : False },
                13 : { 'name' : 'EDX Imaging',                  'type' : 3,     'shortname' : 'IMG', 'supported' : False },
                14 : { 'name' : 'GW Backscatter Electron 1',    'type' : 0,     'shortname' : 'BS1', 'supported' : False },
                15 : { 'name' : 'GW Backscatter Electron 2',    'type' : 0,     'shortname' : 'BS2', 'supported' : False },
                16 : { 'name' : 'GW Backscatter Electron 3',    'type' : 0,     'shortname' : 'BS3', 'supported' : False },
                17 : { 'name' : 'GW Backscatter Electron 4',    'type' : 0,     'shortname' : 'BS4', 'supported' : False },
                18 : { 'name' : 'Econ 3',                       'type' : 3,     'shortname' : 'EDX', 'supported' : False },
                19 : { 'name' : 'Econ 4',                       'type' : 3,     'shortname' : 'EDX', 'supported' : False },
                20 : { 'name' : 'EDX Free',                     'type' : 3,     'shortname' : 'EDX', 'supported' : False },
                21 : { 'name' : 'MCP_1',                        'type' : 2,     'shortname' : 'MCP', 'supported' : False },
                22 : { 'name' : 'MCP_2',                        'type' : 2,     'shortname' : 'MCP_1', 'supported' : False },
                23 : { 'name' : 'Channel Electron Det CED',     'type' : 2,     'shortname' : 'CED', 'supported' : False },
                24 : { 'name' : 'Electron BackScatter Pattern', 'type' : 2,     'shortname' : 'EBSP', 'supported' : False },
                25 : { 'name' : 'Gaseous Secondary Electron',   'type' : 2,     'shortname' : 'GSE', 'supported' : False },
                26 : { 'name' : 'Centaurus',                    'type' : 1,     'shortname' : 'CEN', 'supported' : False },
                27 : { 'name' : 'STEM Transmission Electron',   'type' : 0,     'shortname' : 'TED', 'supported' : False },
                28 : { 'name' : 'TLD (SFEG)',                   'type' : 0,     'shortname' : 'TLD', 'supported' : False },
                29 : { 'name' : 'GBSD (gaseous backscatter)',   'type' : 0,     'shortname' : 'GSE', 'supported' : False },
                256 : { 'name' : 'Mixed',                       'type' : 4,     'shortname' : 'MIX', 'supported' : False }
        }

        if loglevel not in loglvls:
            raise ValueError(f"Unknown log level {loglevel}")

        if isinstance(port, serial.Serial):
            self._port = port
            self._portName = None
            self._initialRequests()
        else:
            self._port = None
            self._portName = port

        self._debug = debug
        if logger is not None:
            self._logger = logger
            # we don't set the loglevel in case the logger has been passed from the outside
        else:
            self._logger = logging.getLogger()
            self._logger.setLevel(loglvls[loglevel])

        self._usedConnect = False
        self._usedContext = False

        self._machine_type = None
        self._machine_serial = None

        atexit.register(self._close)

    def __enter__(self):
        if self._usedConnect:
            self._logger.error("[XL30] Enter called on connected microscope")
            raise ValueError("Cannot use context management on connected microscope")

        if (self._port is None) and (self._portName is not None):
            self._logger.debug(f"[XL30] Connecting to XL30 on serial port {self._portName}")
            self._port = serial.Serial(
                    self._portName,
                    baudrate = 9600,
                    bytesize = serial.EIGHTBITS,
                    parity = serial.PARITY_NONE,
                    stopbits = serial.STOPBITS_ONE,
                    timeout = 60
            )
            self._initialRequests()
        else:
            self._logger.debug("[XL30] Not executing connect - either port already passed or no name present")

        self._usesContext = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._logger.debug("[XL30] Exiting XL30 context")
        self._close()
        self._usesContext = False

    def _close(self):
        self._logger.debug("[XL30] Close called")
        atexit.unregister(self._close)
        if (self._port is not None) and (self._portName is not None):
            self._logger.debug("[XL30] Closing serial port")
            self._port.close()
            self._port = None

    def _connect(self):
        self._logger.debug("[XL30] Connect called")
        if (self._port is None) and (self._portName is not None):
            self._logger.debug(f"[XL30] Connecting to serial port {self._portName}")
            self._port = serial.Serial(
                    self._portName,
                    baudrate = 9600,
                    bytesize = serial.EIGHTBITS,
                    parity = serial.PARITY_NONE,
                    stopbits = serial.STOPBITS_ONE,
                    timeout = 60
            )
            self._initialRequests()
        else:
            self._logger.debug("[XL30] Not opening serial port - either port has been passed or no port name present")
        return True

    def _disconnect(self):
        self._logger.debug("[XL30] Disconnect called")
        if (self._port is not None):
            self._close()
        return True

    def _reconnect(self):
        self._logger.debug("[XL30] Trying to reconenct")
        if (self._port is not None):
            try:
                self._port.close()
            except:
                pass
            self._port = None

        # Short sleep
        sleep(2)

        # Reconnect
        try:
            self._connect()
            return True
        except:
            return False

    @onlyconnected()
    def _msg_tx(
        self,
        opCode,
        payload = None,
        fill = None
    ):
        if (opCode < 0) or (opCode > 255):
            self._logger.error(f"[XL30] Requested to transmit OpCode {opCode} out of range 0-255")
            raise ValueError("Command not transmitable")

        if fill is not None:
            payload = b''
            for i in range(fill):
                payload = payload + bytes([0])

        if payload is not None:
            if len(payload) > 255-5:
                self._logger.error(f"[XL30] Requested amount of data ({len(payload)} bytes) out of range for single message block")
                raise ValueError("Payload exceeds single message size")
            payloadSize = len(payload)
        else:
            payloadSize = 0

        msg = b''
        msg = bytes([0x05, payloadSize + 5, opCode, 0x00])
        if payload is not None:
            msg += bytes(payload)

        # Checksum calculation
        chksum = 0
        for b in msg:
            chksum = (chksum + b) % 256

        msg += bytes([chksum])

        # Transmit message
        self._logger.debug(f"[XL30] TX: {msg}")
        self._port.write(msg)

        return True

    @onlyconnected()
    def _msg_rx(
        self,
        fmt = None
    ):
        msg = self._port.read(2)
        if msg == b'':
            # Timeout indicates no message has been received
            self._logger.warning("[XL30] Timeout during RX")
            return None

        if len(msg) != 2:
            # Communication error, not enough bytes received in one timeout - no valid message received
            self._logger.warning("[XL30] Incomplete message during RX")
            return None

        if msg[0] != 0x05:
            self._logger.error(f"[XL30] Invalid message response. Expecting ID 0x05, got {msg[0]}")
            raise ScanningElectronMicroscope_CommunicationError("Invalid message response")

        msgLen = msg[1]
        toRead = msgLen - 2

        while toRead > 0:
            b = self._port.read(1)
            if b == b'':
                # Timeout - no valid message received
                self._logger.error(f"[XL30] Invalid message response. Partial message: {msg}")
                raise ScanningElectronMicroscope_CommunicationError("Invalid message response: Timeout, partial message")
            toRead = toRead - 1
            msg += b

        # Checksum verification
        chksum = 0
        for i in range(len(msg) - 1):
            chksum = (chksum + msg[i]) % 256

        if chksum != msg[-1]:
            self._logger.error(f"[XL30] Communication error: RX invalid checksum: {msg}")
            raise ScanningElectronMicroscope_CommunicationError(f"Invalid checksum on message {msg}")

        # Verify status bits
        if int(msg[3]) & 0x3F != 0:
            self._logger.error(f"[XL30] Invalid status bits set on RX: {msg[3]}")
            raise ScanningElectronMicroscope_CommunicationError(f"Invalid status bits set {msg[3]}")

        self._logger.debug(f"RX: {msg}")

        isError = False
        if int(msg[3]) & 0x80 != 0:
            isError = True

        payload = None
        if msgLen > 5:
            payload = msg[4 : -1]

        # If requested parse payload according to specification string
        # Allowed entries are:
        #   b   Sequence of 4 bytes
        #   i   Two 16 bit integer values
        #   f   Single 32 bit float
        #
        #   e   Error Code (assumed automatically if error bit is set)

        # Valid checksum - parse message
        msgp = {
            'id' : int(msg[0]),
            'lengthTotal' : int(msg[1]),
            'lengthPayload' : int(msg[1]) - 5,
            'op' : int(msg[2]),
            'status' : int(msg[3]),
            'error' : isError,
            'errorcode' : None,
            'payload' : payload
        }

        if fmt is not None:
            data = []
            if not isError:
                # Parse as requested
                if (int(msg[1]) - 5) < (len(fmt)*4):
                    self._logger.error(f"[XL30] Requested parsing according to {fmt} ({len(fmt) * 4} bytes) but got only {int(msg[1])-5} payload bytes")
                    raise ValueError(f"Requested parsing according to {fmt} ({len(fmt) * 4} bytes) but got only {int(msg[1])-5} payload bytes")
                idx = 0
                for c in fmt:
                    if c == "b":
                        data.append(msg[4 + idx*4 : 4 + (idx+1)*4])
                    if c == "i":
                        data.append(int(msg[4 + idx*4 + 0]) + int(msg[4 + idx*4 + 1]) * 256)
                        data.append(int(msg[4 + idx*4 + 2]) + int(msg[4 + idx*4 + 3]) * 256)
                    if c == "f":
                        data.append(struct.unpack('f', msg[4 + idx*4 : 4 + (idx+1) * 4])[0])
                msgp['data'] = data
        if isError:
            if (int(msg[1]) - 5) < 4:
                self._logger.error(f"[XL30] Expected error code - but got {int(msg[1]) - 5} bytes instead of 4")
                raise ScanningElectronMicroscope_CommunicationError(f"Expected error code - but got {int(msg[1]) - 5} bytes instead of 4")
            msgp['errorcode'] = int(msg[4]) + int(msg[5]) * 256 + int(msg[6]) * 65536 + int(msg[7]) * 16777216

        self._logger.debug(f"[XL30] RX: {msgp}")
        return msgp

    @onlyconnected()
    def _initialRequests(self):
        # First clear serial buffer (short timeout)
        self._port.timeout = 1
        while self._port.read() != b'':
            pass
        self._port.timeout = 60

        # Requesting machine type and serial
        mid = self._get_id()
        self._machine_type = mid['type']
        self._machine_serial = mid['serial']

        # Determine which detectors are supported
        if self._detectorsAuto:
            for detid in self._detectorIds:
                if (self._detectorIds[detid]['type'] is None) or (self._detectorIds[detid]['type'] == 4):
                    self._detectorIds[detid]['supported'] = False
                    continue
                if self._set_detector(detid):
                    self._logger.info(f"[XL30] Supported detector {detid}: {self._detectorIds[detid]}")
                    self._detectorIds[detid]['supported'] = True
                else:
                    self._detectorIds[detid]['supported'] = False

        # Query current state:
        #   High tension (current)
        #   High tension status
        #   XL software version
        #   Check if TMP or ODP system
        #   Check if we are in service mode
        #   Check which type of gun (Tungsten, FEG, LaB6, SFEG)

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_id(self):
        self._logger.debug("[XL30] Requesting ID")

        self._msg_tx(0, fill = 4)
        resp = self._msg_rx(fmt = "i")

        knownTypes = {
            2 : "XL20",
            3 : "XL30",
            4 : "XL40"
        }

        if resp['data'][0] in knownTypes:
            return {
                'type' : knownTypes[resp['data'][0]],
                'serial' : resp['data'][1]
            }
        else:
            self._logger.error(f"[XL30] Unknown response to ID request: {resp}")
            raise ScanningElectronMicroscope_CommunicationError(f"Unknown response to ID reqeuest: {resp}")

    @tested()
    @retrylooped()
    def _get_hightension(self):
        if self._port is None:
            raise ScanningElectronMicroscope_NotConnectedException()

        # First get status
        self._msg_tx(4, fill = 4)
        resp = self._msg_rx(fmt = "i")

        if resp['data'][0] == 0:
            self._logger.debug("[XL30] High tension is currently disabled")
            return False
        self._logger.debug("[XL30] High tension enabled")

        self._msg_tx(2, fill = 4)
        resp = self._msg_rx(fmt = "f")
        return resp['data'][0]

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_hightension(self, voltage):
        if ((voltage < 200) or (voltage > 30000)) and (voltage != 0):
            raise ValueError("High tension voltage has to be in range 200V-30kV")

        if voltage != 0:
            self._logger.info("[XL30] Enabling high tension")
            self._msg_tx(5, bytes([1,0,0,0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error(f"[XL30] Enabling high tension failed. Error code {resp['errorcode']}")
                return False

            self._logger.info(f"[XL30] Setting high tension to {voltage}")
            self._msg_tx(3, struct.pack('<f', float(voltage)))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error(f"[XL30] Enabling high tension failed. Error code {resp['errorcode']}")
                self._set_hightension(0)
                return False

            # Wait till ramp up ...
            ht = 0
            for wit in range(90*2):
                sleep(0.5)
                ht = self._get_hightension()
                if abs(ht - voltage) < 100:
                    break
                self._logger.info(f"[XL30] Waiting for high tension to reach {voltage}V, currently at {ht}")

            if abs(ht - voltage) > 100:
                # If we raise an IOError we will trigger our retry loop that will use reconnect ...
                self._logger.error("[XL30] Failed to set high tension in 90 seconds")
                raise IOError("[XL30] Failed to set high tension in 90 seconds")

            return True
        else:
            self._logger.info("[XL30] Disabling high tension")
            self._msg_tx(5, bytes([0,0,0,0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error(f"[XL30] Failed to disable high tension. Error code {resp['errorcode']}")
                return False
            return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _vent(self, stop = False):
        self._logger.debug(f"[XL30] Request venting (stop: {stop})")

        if not stop:
            self._msg_tx(113, bytes([1, 0, 0, 0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error("[XL30] Failed to execute venting command. Error code {resp['errorcode']}")
                return False
            self._logger.info("[Xl30] Venting")
            return True
        else:
            self._msg_tx(113, bytes([2, 0, 0, 0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error("[XL30] Failed to stop venting command. Error code {resp['errorcode']}")
                return False
            self._logger.info("[XL30] Stop venting")
            return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _pump(self):
        self._logger.debug("[XL30] Request pumping")

        self._msg_tx(113, bytes([0, 0, 0, 0]))
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error("[XL30] Failed to start pumping")
            return False
        self._logger.info("[XL30] Pumping")
        return True
      
    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_spotsize(self):
        self._msg_tx(6, fill = 4)
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error("[XL30] Failed to query spotsize")
            return False
        self._logger.info(f"[XL30] Queried spot size {resp['data'][0]}")
        return resp['data'][0]

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_spotsize(self, spotsize):
        if (spotsize < 1.0) or (spotsize > 10.0):
            raise ValueError("Valid spotsizes (probe currents) in the range of 1.0 to 10.0")
        self._msg_tx(7, struct.pack("<f", float(spotsize)))
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error(f"[XL30] Failed to set spotsize to {spotsize}")
            return False
        else:
            self._logger.info(f"[XL30] New spotsize {spotsize}")
            return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_magnification(self):
        self._msg_tx(12, fill = 4)
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error("[XL30] Failed to query magnification")
            return False
        self._logger.info(f"[XL30] Queried magnification {resp['data'][0]}")
        return resp['data'][0]

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_magnification(self, magnification):
        if (magnification < 20) or (magnification > 4e5):
            raise ValueError("Valid magnification values range from 20 to 400000")

        self._msg_tx(13, struct.pack("<f", magnification))
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error("[XL30] Failed to set magnification")
            return False

        self._logger.info(f"[XL30] New magnification {magnification}")
        return True

    @untested()
    @onlyconnected()
    @retrylooped()
    def _get_stigmator(self, stigmatorindex = 0):
        if stigmatorindex != 0:
            raise ValueError("This device only offers a signle stigmator")

        self._msg_tx(70, fill = 8)
        resp = self._msg_rx(fmt = "ff")
        if resp['error']:
            self._logger.error("[XL30] Failed to read stigmator setting")
            return None, None

        return (resp['data'][0], resp['data'][1])

    @untested()
    @onlyconnected()
    @retrylooped()
    def _set_stigmator(self, x = None, y = None, stigmatorindex = 0):
        if stigmatorindex != 0:
            raise ValueError("This device only offers a single stigmator")

        if (x is None) and (y is None):
            return True

        if (x is None) or (y is None):
            oldx, oldy = self._get_stigmator()
            if oldx is None:
                self._logger.error("[XL30] Failed to query old stigmator setting")
                return False
            if x is None:
                x = oldx
            if y is None:
                y = oldy

        self._msg_tx(71, struct.pack("<ff", x, y))
        resp = self._msg_rx(fmt = "ff")
        if resp['error']:
            self._logger.error(f"[XL30] Failed to set stigmator setting to {x} and {y}")
            return False

        self._logger.info(f"[XL30] New stigmator settings: {x}, {y}")
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_detector(self):
        self._msg_tx(14, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error("[XL30] Failed to query current selected detector")
            return False

        # Got detector ID and type ... translate
        r = {
                'raw_id' : resp['data'][0],
                'raw_type' : resp['data'][1]
        }

        if resp['data'][0] in self._detectorIds:
            r['name'] = self._detectorIds[resp['data'][0]]['name']
            r['shortname'] = self._detectorIds[resp['data'][0]]['shortname']
        if resp['data'][1] in self._detectorTypes:
            r['shorttype'] = self._detectorTypes[resp['data'][1]]['short']
            r['type'] = self._detectorTypes[resp['data'][1]]['long']

        return r

    # Currently able to set CCD and BSE but not SE?!?!?
    @untested()
    @buggy(bugs="Currently not able to set SE detector")
    @onlyconnected()
    @retrylooped()
    def _set_detector(self, detectorId):
        if detectorId not in self._detectorIds:
            raise ValueError(f"Unknown detector {detectorId}")

        self._logger.info(f"[XL30] Requesting change to detector {detectorId} ({self._detectorIds[detectorId]['shortname']}: {self._detectorIds[detectorId]['name']})")

        self._msg_tx(15, bytes([ detectorId, self._detectorIds[detectorId]['type'], 0, 0]))
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error(f"[XL30] Failed to set detector to {detectorId}")
            return False

        self._logger.info(f"[XL30] New detector: {detectorId} ({self._detectorIds[detectorId]['shortname']}: {self._detectorIds[detectorId]['name']})")
        return True

    @onlyconnected()
    @retrylooped()
    def _set_linetime(self, lt):
        supportedLts = {
            0 : 1.25,
            1 : 1.87,
            2 : 3.43,
            3 : 6.86,
            4 : 20.0,
            5 : 40.0,
            6 : 60.0,
            7 : 120.0,
            8 : 240.0,
            9 : 360.0,
            10 : 1020.0,
            100 : "TV"
        }

        setval = None
        for l in supportedLts:
            if lt == supportedLts[l]:
                setval = l
                break
        if setval is None:
            raise ValueError("Unsupported line time {lt} ms, only supporting {supportedLts}")

        self._msg_tx(21, bytes([ setval, 0, 0, 0 ]))
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error("[XL30] Failed to set line time {lt} ms")
            return False
        self._logger.info("[XL30] Set line time {lt} ms")
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_linetime(self):
        supportedLts = {
            0 : 1.25,
            1 : 1.87,
            2 : 3.43,
            3 : 6.86,
            4 : 20.0,
            5 : 40.0,
            6 : 60.0,
            7 : 120.0,
            8 : 240.0,
            9 : 360.0,
            10 : 1020.0,
            100 : "TV"
        }

        self._msg_tx(21, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error("[XL30] Failed to query line time from XL30")
            return None
        v = resp['data'][0]

        for lt in supportedLts:
            if lt == v:
                rv = supportedLts[v]
                self._logger.info(f"[XL30] Queried line time {rv} ms")
                return rv
        self._logger.error(f"[XL30] Unknown queried line time value {v}")
        return None





    @onlyconnected()
    @retrylooped()
    def _set_linesperframe(self, lines):
        supportedLines = {
            0 : 121,
            1 : 242,
            2 : 484,
            3 : 968,
            4 : 1452,
            5 : 1936,
            6 : 2420,
            7 : 2904,
            8 : 3388,
            9 : 3872,
            10 : 180,
            11 : 360,
            12 : 720,
            100 : "TV"
        }

        setValue = None
        for l in supportedLines:
            if lines == supportedLines[l]:
                setValue = l
                break
        if setValue is None:
            raise ValueError(f"Unspported number of lines {lines}, supporting only {supportedLines}")

        self._msg_tx(19, bytes([ setValue, 0, 0, 0 ]))
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error(f"[XL30] Failed to set number of lines to {lines} (value {setValue})")
            return False
        else:
            self._logger.info(f"[XL30] Set number of lines to {lines}")
            return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_linesperframe(self):
        supportedLines = {
            0 : 121,
            1 : 242,
            2 : 484,
            3 : 968,
            4 : 1452,
            5 : 1936,
            6 : 2420,
            7 : 2904,
            8 : 3388,
            9 : 3872,
            10 : 180,
            11 : 360,
            12 : 720,
            100 : "TV"
        }

        self._msg_tx(18, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error("[XL30] Failed to query number of lines per frame")
            return None
        v = resp['data'][0]

        for l in supportedLines:
            if v == l:
                self._logger.info(f"[XL30] Queried {supportedLines[l]} per frame")
                return supportedLines[l]

        self._logger.error(f"[XL30] Unknown value for lines per frame: {v}")
        return None

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_scanmode(self, mode):
        if not isinstance(mode, ScanningElectronMicroscope_ScanMode):
            raise ValueError("Scan mode has to be a ScanningElectronMicroscope_ScanMode")

        self._msg_tx(17, bytes([ mode.value, 0, 0, 0 ]))
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error(f"[XL30] Failed to set scan mode to {mode}")

        self._logger.info(f"[XL30] Scan mode set to {mode}")
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_scanmode(self):
        self._msg_tx(16, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error("[XL30] Failed to query scan mode")
            return None

        v = resp['data'][0]
        venum = None

        try:
            venum = ScanningElectronMicroscope_ScanMode(v)
        except:
            venum = None

        if venum is None:
            self._logger.error(f"[XL30] Microscope reported unknown scan mode {v}")
            return None

        r = {
            'mode' : venum,
            'name' : venum.name
        }
        return r

    @onlyconnected()
    @untested()
    @retrylooped()
    def _make_photo(self):
        self._msg_tx(37)
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error("[XL30] Failed to make photo")
            return False
        else:
            self._logger.info("[XL30] Stored photo")
            return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _write_tiff_image(self, fname, printmagnification = False, graphicsbitplane = False, databar = True, overwrite = False):
        # Note: This function requires an absolute path such as "C:\\TEMP\\PYIMAGE". This image can
        # then be fetched via SMB

        #if len(fname) > 8+4:
        #    raise ValueError("Microscope only supports 8 character filenames")

        fnamebin = fname.encode('ascii')
        fnamebin = fnamebin + bytes([0])
        while len(fnamebin) % 4 != 0:
            fnamebin = fnamebin + bytes([0])

        flagbyteL = 0
        flagbyteH = 0
        if printmagnification:
            flagbyteH = flagbyteH | 0x80
        if graphicsbitplane:
            flagbyteH = flagbyteH | 0x40
        if databar:
            flagbyteH = flagbyteH | 0x20
        if overwrite:
            flagbyteL = flagbyteL | 0x10

        flagbytes = bytes([flagbyteL, flagbyteH, 0, 0])

        self._msg_tx(84, flagbytes + fnamebin)
        resp = self._msg_rx()
        return resp

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_contrast(self):
        self._msg_tx(48, fill = 4)
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("[XL30] Failed to query contrast")
            return None

        return res['data'][0]

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_contrast(self, contrast):
        if (contrast < 0) or (contrast > 100):
            raise ValueError("Contrast has to be in range 0 to 100")

        self._msg_tx(49, struct.pack("<f", contrast))
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("[XL30] Failed to set contrast")
            return False

        self._logger.info(f"[XL30] New contrast: {contrast}")
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_brightness(self):
        self._msg_tx(50, fill = 4)
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("[XL30] Failed to query brightness")
            return None

        return res['data'][0]

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_brightness(self, brightness):
        if (brightness < 0) or (brightness > 100):
            raise ValueError("Brightness has to be in range 0 to 100")

        self._msg_tx(51, struct.pack("<f", brightness))
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("[XL30] Failed to set brightness")
            return False

        self._logger.info(f"[XL30] New brightness: {brightness}")
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _auto_contrastbrightness(self):
        self._msg_tx(53, fill = 4)
        res = self._msg_rx()
        if res['error']:
            self._logger.error("[XL30] Auto contrast and brightness did not execute")
            return False

        self._logger.info("[XL30] Auto contrast an brightness did execute")
        # ACB takes some time
        sleep(30)
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _auto_focus(self):
        #self._msg_tx(55, bytes([1,0,0,0]))

        # Set timeout to wait for autofocus to complete
        tout = self._port.timeout
        self._port.timeout = 240

        self._msg_tx(111, fill = 4)
        res = self._msg_rx()

        # Restore timeout
        self._port.timeout = tout

        if res['error']:
            self._logger.error("[XL30] Auto focus did not execute")
            return False
        self._logger.info("[XL30] Auto focus executed")

        return True

    @onlyconnected()
    @tested()
    @retrylooped()
    def _set_databar_text(self, newtext):
        if len(newtext) > 39:
            self._logger.error("[XL30] User requested more than 40 characters in data bar")
            raise ValueError("Can only show up to 40 characters in data bar")

        txtbin = bytes([0,0,0,0]) + newtext.encode('ascii')
        txtbin += bytes([0])
        while len(txtbin) % 4 != 0:
            txtbin += bytes([0])

        self._msg_tx(101, txtbin)
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error("[XL30] Failed to set databar text")
            return False

        self._logger.info(f"[XL30] New databar text {newtext}")
        return True

    @onlyconnected()
    @tested()
    @retrylooped()
    def _get_databar_text(self):
        self._msg_tx(100, fill = 44)
        resp = self._msg_rx()

        txt = (resp['payload'][4:]).decode('ascii')
        return txt


    # ===========
    # Positioning
    # ===========

    @tested()
    @buggy(bugs="Will ask for confirmation on the device control PC")
    @onlyconnected()
    @retrylooped()
    def _stage_home(self):
        self._logger.info("[XL30] Started homing")

        # Increase timeout to 2 min 30 secs + 15 secs grace timeout
        tout = self._port.timeout
        self._port.timeout = 2*60 + 30 + 15

        self._msg_tx(175, fill = 4)
        resp = self._msg_rx()

        # Restore old timeout
        self._port.timeout = tout

        if resp['error']:
            self._logger.error("[XL30] Homing failed")
            return False
        self._logger.info("[XL30] Homed stage")
        return True

    @onlyconnected()
    @retrylooped()
    def _get_stage_position(self):
        # Queries the stage position ...
        self._msg_tx(190, fill = 20)
        resp = self._msg_rx(fmt = "fffff")
        if resp['error']:
            self._logger.error("[XL30] Failed to query stage position")
            return None

        self._logger.debug(f"[XL30] Queried stage position: X:{resp['data'][0]}mm, Y:{resp['data'][1]}mm, Z:{resp['data'][2]}mm, Tilt:{resp['data'][3]}mm, Rot:{resp['data'][4]}mm")

        return {
            'x' : resp['data'][0],
            'y' : resp['data'][1],
            'z' : resp['data'][2],
            'tilt' : resp['data'][3],
            'rot' : resp['data'][4]
        }

    @onlyconnected()
    @buggy(bugs = "Does not check boundaries! Ignores error when setting z position. Sets tilt before z position ...? Maybe implement here moving down before changing tilt ...")
    @retrylooped()
    def _set_stage_position(self, x = None, y = None, z = None, tilt = None, rot = None):
        self._logger.debug(f"[XL30] Starting move to x:{x}, y:{y}, z:{z}, tilt:{tilt}, rot:{rot}")
        ox,oy,oz,otilt,orot = x,y,z,tilt,rot

        # Get current position (required for some of the methods)
        currentPosition = self._get_stage_position()

        if (x is not None) or (y is not None):
            if x is None:
                x = currentPosition['x']
            if y is None:
                y = currentPosition['y']

            # Execute Command 177 SetPosition (synchronous)
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"[XL30] Moving to position x:{x} mm, y:{y} mm")
            self._msg_tx(177, struct.pack("<ff", x, y))
            rep = self._msg_rx(fmt = "ff")
            self._port.timeout = tout
            if rep['error']:
                self._logger.error(f"[XL30] Failed moving to x:{x}mm, y:{y}mm")
                return False
            self._logger.info(f"[XL30] New position x:{x}mm, y:{y}mm")

        if rot is not None:
            # Execute Command 179 SetRotation (synchronous)
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"[XL30] Moving to position rot:{rot} deg")
            self._msg_tx(179, struct.pack("<f", rot))
            rep = self._msg_rx(fmt = "f")
            self._port.timeout = tout
            if rep['error']:
                self._logger.error(f"[XL30] Failed to rotate to {rot} deg")
                return False
            self._logger.info(f"[XL30] New rotation rot:{rot} deg")

        if z is not None:
            # Set z position ...
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"[XL30] Moving to position z:{z} mm")
            self._msg_tx(187, struct.pack("<f", z))
            rep = self._msg_rx(fmt = "f")
            self._port.timeout = tout
            if rep['error']:
                self._logger.error(f"[XL30] Failed to set z position to {z} mm")
                #return False
            self._logger.info(f"[XL30] New z position: {z} mm")

        if tilt is not None:
            # Set tilt
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"[XL30] Moving to tilt {tilt} deg")
            self._msg_tx(189, struct.pack("<f", tilt))
            rep = self._msg_rx(fmt = "f")
            if rep['error']:
                self._logger.error(f"[XL30] Failed to set tilt position to {tilt} mm")
                return False
            self._logger.info(f"[XL30] New tilt position: {tilt} deg")

        self._logger.info(f"[XL30] New position set: x:{ox}, y:{oy}, z:{oz}, rot:{orot}, tilt: {otilt}")
        return True

    @onlyconnected()
    @tested()
    @retrylooped()
    def _get_beamshift(self):
        self._msg_tx(80, fill = 2*4)
        resp = self._msg_rx(fmt = "ff")
        if resp['error']:
            self._logger.error("[XL30] Failed to query beam shift")
            return None
        self._logger.debug(f"[XL30] Queried beamshift x: {resp['data'][0]} mm, y: {resp['data'][1]} mm")
        return {
            'x' : resp['data'][0],
            'y' : resp['data'][1]
        }

    @onlyconnected()
    @buggy(bugs = "Currently not checking x and y bounds")
    @tested()
    @retrylooped()
    def _set_beamshift(self, x = None, y = None):
        if (x is None) and (y is None):
            self._logger.debug("[XL30] Not setting beam shift, no data supplied")
            return True
        if (x is None) or (y is None):
            # First query shift so we can do a complete set
            currentPos = self._get_beamshift()
            if currentPos is None:
                self._logger.debug("[XL30] Failed to query current position, cannot set only single component")
                return False
            if x is None:
                x = currentPos['x']
            if y is None:
                y = currentPos['y']

        print(struct.pack('<ff', x, y))
        self._msg_tx(81, struct.pack('<ff', x, y,))
        resp = self._msg_rx(fmt = "ff")
        if resp['error']:
            self._logger.error("[XL30] Failed to set beamshift")
            return False

        self._logger.info(f"[XL30] New beamshift x={x}mm, y={y}mm")
        return True

    @onlyconnected()
    @untested()
    @retrylooped()
    def _get_scanrotation(self):
        self._msg_tx(98, fill = 1*4)
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error("[XL30] Failed to query scan rotation")
            return None
        self._logger.debug(f"[XL30] Queried scan rotation: {resp['data'][0]} deg")
        return resp['data'][0]

    @onlyconnected()
    @untested()
    @retrylooped()
    def _set_scanrotation(self, rot = None):
        rot = float(rot)
        if (rot < 90) or (rot > 90):
            self._logger.error("[XL30] Scan rotation has to be in range +- 90 deg")
            return False
        self._msg_tx(99, struct.pack('<f', rot))
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error("[XL30] Failed to set scan rotation")
            return False

        self._logger.info(f"[XL30] New scan rotation rot={rot}deg")
        return True

    @tested()
    @onlyconnected()
    @retrylooped()
    def _get_area_or_dot_shift(self):
        self._msg_tx(26, fill = 4)
        res = self._msg_rx(fmt = 'f')
        if res['error']:
            self._logger.error("[XL30] Failed to query SA/dot shift along X axis")
            return None
        xshift = res['data'][0]

        self._msg_tx(28, fill = 4)
        res = self._msg_rx(fmt = 'f')
        if res['error']:
            self._logger.error("[XL30] Failed to query SA/dot shift along Y axis")
            return None
        yshift = res['data'][0]

        return (xshift, yshift)

    @tested()
    @onlyconnected()
    @retrylooped()
    def _set_area_or_dot_shift(self, xshift = None, yshift = None):
        if isinstance(xshift, list) or isinstance(xshift, tuple):
            if (len(xshift) == 2) and (yshift is None):
                yshift = xshift[1]
                xshift = xshift[0]
            else:
                raise ValueError("xshift and yshift have to be specied as float or first argument has to be a 2-tuple or 2-list")

        if xshift is not None:
            xshift = float(xshift)
            if (xshift < -100) or (xshift > 100):
                raise ValueError("X shift has to be in range [-100...100%]")

        if yshift is not None:
            yshift = float(yshift)
            if (yshift < -100) or (yshift > 100):
                raise ValueError("Y shift has to be in range [-100...100%]")

        if xshift is not None:
            self._msg_tx(27, struct.pack("<f", xshift))
            res = self._msg_rx(fmt = 'i')
            if res['error']:
                self._logger.error("[XL30] Failed to set X shift")
                return False

        if yshift is not None:
            self._msg_tx(29, struct.pack("<f", yshift))
            res = self._msg_rx(fmt = 'i')
            if res['error']:
                self._logger.error("[XL30] Failed to set Y shift")
                return False

        self._logger.info(f"[XL30] Set X and Y shift to {xshift} and {yshift}")
        return True

    @onlyconnected()
    @untested()
    @retrylooped()
    def _get_selected_area_size(self):
        self._msg_tx(22, fill = 4)
        res = self._msg_rx(fmt = 'f')
        if res['error']:
            self._logger.error("[XL30] Failed to query X area size")
            return None
        xsize = res['data'][0]

        self._msg_tx(24, fill = 4)
        if res['error']:
            self._logger.error("[XL30] Failed to query Y area size")
            return None
        ysize = res['data'][0]

        self._logger.debug(f"[XL30] Queried selected area size: {xsize}%, {ysize}%")
        return (xsize, ysize)

    @onlyconnected()
    @untested()
    @retrylooped()
    def _set_selected_area_size(self, sizex = None, sizey = None):
        if sizex is not None:
            if isinstance(sizex, tuple) or isinstance(sizex, list):
                if len(sizex) == 2:
                    sizey = sizex[1]
                    sizex = sizex[0]
                else:
                    raise ValueError("Either supply two floats or a 2-list or 2-tuple as first argument")

        if sizex is not None:
            sizex = float(sizex)
            if (sizex < 0) or (sizex > 100):
                raise ValueError("SizeX is out of range from [0...100%] (requested {sizex})")
        if sizey is not None:
            sizey = float(sizey)
            if (sizey < 0) or (sizey > 100):
                raise ValueError("SizeY is out of range from [0...100%] (requested {sizey})")

        self._msg_tx(23, struct.pack("<f", sizex))
        r = self._msg_rx(fmt = 'i')
        if r['error']:
            self._logger.error("[XL30] Failed to set selected area X")
            return False

        self._msg_tx(25, struct.pack("<f", sizey))
        r = self._msg_rx(fmt = 'i')
        if r['error']:
            self._logger.error("[XL30] Failed to set selected area Y")
            return False

        self._logger.info(f"[XL30] Set selected area size to {sizex}, {sizey}")
        return True
        


    @onlyconnected()
    @tested()
    @retrylooped()
    def _get_imagefilter_mode(self):
        self._msg_tx(74, fill = 4)
        res = self._msg_rx(fmt = 'i')
        if res['error']:
            self._logger.error("[XL30] Failed to query filter mode")
            return None

        fmode = None
        try:
            fmode = ScanningElectronMicroscope_ImageFilterMode(res['data'][0])
        except:
            self._logger.error(f"[XL30] Unknown image filter mode {res['data'][0]} reported")
            return None

        return {
                'mode' : fmode,
                'frames' : 2**int(res['data'][1])
        }


    @onlyconnected()
    @buggy(bugs="Cannot set average with != 2 frames")
    @untested()
    @retrylooped()
    def _set_imagefilter_mode(self, filtermode, frames):
        # Note that setting average for frames != 2 currently does not work
        if frames < 1:
            raise ValueError("At least one frame has to be gathered")
        if math.ceil(math.log10(frames)/math.log10(2)) != math.floor(math.log10(frames)/math.log10(2)):
            raise ValueError("Frame count has to be a power of two")
        if int(math.log10(frames)/math.log10(2)) > 255:
            raise ValueError("Frame count exceedes 2**255")

        if not isinstance(filtermode, ScanningElectronMicroscope_ImageFilterMode):
            raise ValueError("Filter mode has to be a ScanningElectronMicroscope_ImageFilterMode instance")

        self._msg_tx(75, bytes([filtermode.value, int(math.log10(frames) / math.log10(2)), 0, 0]))
        rep = self._msg_rx(fmt = "i")
        if rep['error']:
            self._logger.error(f"[XL30] Failed to set filter mode {filtermode} with {frames} frames")
            return False
        self._logger.info(f"[XL30] New filtermode {filtermode} with {frames} frames")
        return True

    @untested()
    @onlyconnected()
    @retrylooped()
    def _get_specimen_current_detector_mode(self):
        self._msg_tx(58, fill = 4)
        rep = self._msg_rx(fmt = "i")
        if rep['error']:
            self._logger.error("[XL30] Failed to query speciment current detector mode")
            return None
        mode = rep['data'][0]

        knownModes = {
            0 : ScanningElectronMicroscope_SpecimenCurrentDetectorMode.TOUCH_ALARM,
            1 : ScanningElectronMicroscope_SpecimenCurrentDetectorMode.IMAGING,
            2 : ScanningElectronMicroscope_SpecimenCurrentDetectorMode.MEASURING
        }

        if mode in knownModes:
            self._logger.debug(f"[XL30] Queried speciment current detector mode {knownModes[mode]} (raw: {mode})")
            return knownModes[mode]
        else:
            self._logger.error(f"[XL30] Received unknown speciment current detector mode {mode}")
            return None

    @buggy(bugs="Does not work on our XL30 ESEM")
    @onlyconnected()
    @retrylooped()
    def _set_specimen_current_detector_mode(self, mode):
        if not isinstance(mode, ScanningElectronMicroscope_SpecimenCurrentDetectorMode):
            raise ValueError("Mode has to be a ScanningElectronMicroscope_SpecimentCurrentDetectorMode, is {mode}")

        knownModes = {
            ScanningElectronMicroscope_SpecimenCurrentDetectorMode.TOUCH_ALARM : 0,
            ScanningElectronMicroscope_SpecimenCurrentDetectorMode.IMAGING : 1,
            ScanningElectronMicroscope_SpecimenCurrentDetectorMode.MEASURING : 2
        }

        if mode not in knownModes:
            raise ValueError("Unknown or unspported SCD mode {mode}")

        md = knownModes[mode]

        self._msg_tx(59, bytes([md, 0, 0, 0]))
        resp = self._msg_rx(fmt = "i")
        if resp["error"]:
            self._logger.error("[XL30] Failed to blank beam")
            return False
        return True

    @buggy(bugs="Does not work on our XL30 ESEM")
    @onlyconnected()
    @retrylooped()
    def _get_specimen_current(self):
        # Note this only works in measure mode ...
        self._msg_tx(60, fill = 4)
        resp = self._msg_rx(fmt = "f")
        if resp["error"]:
            self._logger.error(f"[XL30] Failed to query speciment current (errorcode: {resp['errorcode']})")
            return None

        return resp["data"][0]

    @untested()
    @onlyconnected()
    @retrylooped()
    def _is_beam_blanked(self):
        self._msg_tx(62, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp["error"]:
            self._logger.error("[XL30] Failed to query beam blanking error code")
            return None

        if resp["data"][0] == 0:
            return False
        else:
            return True

    @untested()
    @onlyconnected()
    @retrylooped()
    def _blank(self):
        self._msg_tx(63, bytes([1, 0, 0, 0]))
        resp = self._msg_rx(fmt = "i")
        if resp["error"]:
            self._logger.error("[XL30] Failed to blank beam")
            return False
        return True

    @untested()
    @onlyconnected()
    @retrylooped()
    def _unblank(self):
        self._msg_tx(63, bytes([0, 0, 0, 0]))
        resp = self._msg_rx(fmt = "i")
        if resp["error"]:
            self._logger.error("[XL30] Failed to unblank beam")
            return False
        return True

    @untested()
    @onlyconnected()
    @retrylooped()
    def _oplock(self, lock = True):
        if lock:
            self._msg_tx(39, bytes([1, 0, 0, 0]))
        else:
            self._msg_tx(39, bytes([0, 0, 0, 0]))
        resp = self._msg_rx(fmt = 'i')
        if resp["error"]:
            self._logger.error("[XL30] Failed to lock/unlock the system")
            return False
        return True

    @untested()
    @onlyconnected()
    @retrylooped()
    def _isOplocked(self):
        self._msg_tx(38, fill = 4)
        resp = self._msg_rx(fmt = 'i')
        if resp["error"]:
            self._logger.error("[XL30] Failed to query lock state")
            return None

        if resp["data"][0] == 0:
            return False
        else:
            return True




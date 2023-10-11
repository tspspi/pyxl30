from scanningelectronmicroscope import ScanningElectronMicroscope
from scanningelectronmicroscope import ScanningElectronMicroscope_ScanMode, ScanningElectronMicroscope_ImageFilterMode
from scanningelectronmicroscope import ScanningElectronMicroscope_NotConnectedException, ScanningElectronMicroscope_CommunicationError

import atexit
import serial
import logging
import struct
import math

# Decorators used in this file

class onlyconnected:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if args[0]._port is None:
                args[0]._logger.error(f"Called {func} but microscope is not connected")
                raise ScanningElectronMicroscope_NotConnectedException()
            return func(*args, **kwargs)
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
            args[0]._logger.warning(f"Calling untested function {func} / function with possibly known bugs")
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
            args[0]._logger.warning(f"Calling function {func} with known bugs ({self._bugs})!")
            return func(*args, **kwargs)
        return wrapper

class XL30(ScanningElectronMicroscope):
    pass

class XL30Serial(XL30):
    def __init__(self, port, logger = None, debug = False, loglevel = "ERROR", detectorsAutodetect = False):
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
            self._logger.error("Enter called on connected microscope")
            raise ValueError("Cannot use context management on connected microscope")

        if (self._port is None) and (self._portName is not None):
            self._logger.debug(f"Connecting to XL30 on serial port {self._portName}")
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
            self._logger.debug("Not executing connect - either port already passed or no name present")

        self._usesContext = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._logger.debug("Exiting XL30 context")
        self._close()
        self._usesContext = False

    def _close(self):
        self._logger.debug("Close called")
        atexit.unregister(self._close)
        if (self._port is not None) and (self._portName is not None):
            self._logger.debug("Closing serial port")
            self._port.close()
            self._port = None

    def _connect(self):
        self._logger.debug("Connect called")
        if (self._port is None) and (self._portName is not None):
            self._logger.debug(f"Connecting to serial port {self._portName}")
            self._port = serial.Serial(
                    self._portName,
                    baudrate = 9600,
                    bytesize = serial.EIGHTBYTES,
                    parity = serial.PARITY_NONE,
                    stopbits = serial.STOPBITS_ONE,
                    timeout = 60
            )
            self._initialRequests()
        else:
            self._logger.debug("Not opening serial port - either port has been passed or no port name present")
        return True

    def _disconnect(self):
        self._logger.debug("Disconnect called")
        if (self._port is not None):
            self._close()
        return True

    @onlyconnected()
    def _msg_tx(
        self,
        opCode,
        payload = None,
        fill = None
    ):
        if (opCode < 0) or (opCode > 255):
            self._logger.error(f"Requested to transmit OpCode {opCode} out of range 0-255")
            raise ValueError("Command not transmitable")

        if fill is not None:
            payload = b''
            for i in range(fill):
                payload = payload + bytes([0])

        if payload is not None:
            if len(payload) > 255-5:
                self._logger.error(f"Requested amount of data ({len(payload)} bytes) out of range for single message block")
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
        self._logger.debug(f"TX: {msg}")
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
            self._logger.warning("Timeout during RX")
            return None

        if len(msg) != 2:
            # Communication error, not enough bytes received in one timeout - no valid message received
            self._logger.warning("Incomplete message during RX")
            return None

        if msg[0] != 0x05:
            self._logger.error(f"Invalid message response. Expecting ID 0x05, got {msg[0]}")
            raise ScanningElectronMicroscope_CommunicationError("Invalid message response")

        msgLen = msg[1]
        toRead = msgLen - 2

        while toRead > 0:
            b = self._port.read(1)
            if b == b'':
                # Timeout - no valid message received
                self._logger.error(f"Invalid message response. Partial message: {msg}")
                raise ScanningElectronMicroscope_CommunicationError("Invalid message response: Timeout, partial message")
            toRead = toRead - 1
            msg += b

        # Checksum verification
        chksum = 0
        for i in range(len(msg) - 1):
            chksum = (chksum + msg[i]) % 256

        if chksum != msg[-1]:
            self._logger.error(f"Communication error: RX invalid checksum: {msg}")
            raise ScanningElectronMicroscope_CommunicationError(f"Invalid checksum on message {msg}")

        # Verify status bits
        if int(msg[3]) & 0x3F != 0:
            self._logger.error(f"Invalid status bits set on RX: {msg[3]}")
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
                    self._logger.error(f"Requested parsing according to {fmt} ({len(fmt) * 4} bytes) but got only {int(msg[1])-5} payload bytes")
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
                self._logger.error(f"Expected error code - but got {int(msg[1]) - 5} bytes instead of 4")
                raise ScanningElectronMicroscope_CommunicationError(f"Expected error code - but got {int(msg[1]) - 5} bytes instead of 4")
            msgp['errorcode'] = int(msg[4]) + int(msg[5]) * 256 + int(msg[6]) * 65536 + int(msg[7]) * 16777216

        self._logger.debug(f"RX: {msgp}")
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
                    self._logger.info(f"Supported detector {detid}: {self._detectorIds[detid]}")
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
    def _get_id(self):
        self._logger.debug("Requesting ID")

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
            self._logger.error(f"Unknown response to ID request: {resp}")
            raise ScanningElectronMicroscope_CommunicationError(f"Unknown response to ID reqeuest: {resp}")

    @tested()
    def _get_hightension(self):
        if self._port is None:
            raise ScanningElectronMicroscope_NotConnectedException()

        # First get status
        self._msg_tx(4, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['data'][0] == 0:
            self._logger.debug("High tension is currently disabled")
            return False
        self._logger.debug("High tension enabled")

        self._msg_tx(2, fill = 4)
        resp = self._msg_rx(fmt = "f")
        return resp['data'][0]

    @tested()
    @onlyconnected()
    def _set_hightension(self, voltage):
        if ((voltage < 200) or (voltage > 30000)) and (voltage != 0):
            raise ValueError("High tension voltage has to be in range 200V-30kV")

        if voltage != 0:
            self._logger.info("Enabling high tension")
            self._msg_tx(5, bytes([1,0,0,0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error(f"Enabling high tension failed. Error code {resp['errorcode']}")
                return False

            self._logger.info(f"Setting high tension to {voltage}")
            self._msg_tx(3, struct.pack('<f', float(voltage)))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error(f"Enabling high tension failed. Error code {resp['errorcode']}")
                self._set_hightension(0)
                return False

            return True
        else:
            self._logger.info("Disabling high tension")
            self._msg_tx(5, bytes([0,0,0,0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error(f"Failed to disable high tension. Error code {resp['errorcode']}")
                return False
            return True

    @tested()
    @onlyconnected()
    def _vent(self, stop = False):
        self._logger.debug(f"Request venting (stop: {stop})")

        if not stop:
            self._msg_tx(113, bytes([1, 0, 0, 0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error("Failed to execute venting command. Error code {resp['errorcode']}")
                return False
            self._logger.info("Venting")
            return True
        else:
            self._msg_tx(113, bytes([2, 0, 0, 0]))
            resp = self._msg_rx()
            if resp['error']:
                self._logger.error("Failed to stop venting command. Error code {resp['errorcode']}")
                return False
            self._logger.info("Stop venting")
            return True

    @tested()
    @onlyconnected()
    def _pump(self):
        self._logger.debug("Request pumping")

        self._msg_tx(113, bytes([0, 0, 0, 0]))
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error("Failed to start pumping")
            return False
        self._logger.info("Pumping")
        return True
      
    @tested()
    @onlyconnected()
    def _get_spotsize(self):
        self._msg_tx(6, fill = 4)
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error("Failed to query spotsize")
            return False
        self._logger.info(f"Queried spot size {resp['data'][0]}")
        return resp['data'][0]

    @tested()
    @onlyconnected()
    def _set_spotsize(self, spotsize):
        if (spotsize < 1.0) or (spotsize > 8.0):
            raise ValueError("Valid spotsizes (probe currents) in the range of 1.0 to 8.0")
        self._msg_tx(7, struct.pack("<f", float(spotsize)))
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error(f"Failed to set spotsize to {spotsize}")
            return False
        else:
            self._logger.info(f"New spotsize {spotsize}")
            return True

    @tested()
    @onlyconnected()
    def _get_magnification(self):
        self._msg_tx(12, fill = 4)
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error(f"Failed to query magnification")
            return False
        self._logger.info(f"Queried magnification {resp['data'][0]}")
        return resp['data'][0]

    @tested()
    @onlyconnected()
    def _set_magnification(self, magnification):
        if (magnification < 20) or (magnification > 4e5):
            raise ValueError("Valid magnification values range from 20 to 400000")

        self._msg_tx(13, struct.pack("<f", magnification))
        resp = self._msg_rx(fmt = "f")
        if resp['error']:
            self._logger.error(f"Failed to set magnification")
            return False

        self._logger.info(f"New magnification {magnification}")
        return True

    @tested()
    @onlyconnected()
    def _get_detector(self):
        self._msg_tx(14, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error("Failed to query current selected detector")
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
    def _set_detector(self, detectorId):
        if detectorId not in self._detectorIds:
            raise ValueError(f"Unknown detector {detectorId}")

        self._logger.info(f"Requesting change to detector {detectorId} ({self._detectorIds[detectorId]['shortname']}: {self._detectorIds[detectorId]['name']})")

        self._msg_tx(15, bytes([ detectorId, self._detectorIds[detectorId]['type'], 0, 0]))
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error(f"Failed to set detector to {detectorId}")
            return False

        self._logger.info(f"New detector: {detectorId} ({self._detectorIds[detectorId]['shortname']}: {self._detectorIds[detectorId]['name']})")
        return True

    @tested()
    @onlyconnected()
    def _set_scanmode(self, mode):
        if not isinstance(mode, ScanningElectronMicroscope_ScanMode):
            raise ValueError("Scan mode has to be a ScanningElectronMicroscope_ScanMode")

        self._msg_tx(17, bytes([ mode.value, 0, 0, 0 ]))
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error(f"Failed to set scan mode to {mode}")

        self._logger.info(f"Scan mode set to {mode}")
        return True

    @tested()
    @onlyconnected()
    def _get_scanmode(self):
        self._msg_tx(16, fill = 4)
        resp = self._msg_rx(fmt = "i")
        if resp['error']:
            self._logger.error(f"Failed to query scan mode")
            return None

        v = resp['data'][0]
        venum = None

        try:
            venum = ScanningElectronMicroscope_ScanMode(v)
        except:
            venum = None

        if venum is None:
            self._logger.error(f"Microscope reported unknown scan mode {v}")
            return None

        r = {
            'mode' : venum,
            'name' : venum.name
        }
        return r

    @onlyconnected()
    @untested()
    def _make_photo(self):
        self._msg_tx(37)
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error("Failed to make photo")
            return False
        else:
            self._logger.info("Stored photo")
            return True

    @tested()
    @onlyconnected()
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
    def _get_contrast(self):
        self._msg_tx(48, fill = 4)
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("Failed to query contrast")
            return None

        return res['data'][0]

    @tested()
    @onlyconnected()
    def _set_contrast(self, contrast):
        if (contrast < 0) or (contrast > 100):
            raise ValueError("Contrast has to be in range 0 to 100")

        self._msg_tx(49, struct.pack("<f", contrast))
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("Failed to set contrast")
            return False

        self._logger.info(f"New contrast: {contrast}")
        return True

    @tested()
    @onlyconnected()
    def _get_brightness(self):
        self._msg_tx(50, fill = 4)
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("Failed to query brightness")
            return None

        return res['data'][0]

    @tested()
    @onlyconnected()
    def _set_brightness(self, brightness):
        if (brightness < 0) or (brightness > 100):
            raise ValueError("Brightness has to be in range 0 to 100")

        self._msg_tx(51, struct.pack("<f", brightness))
        res = self._msg_rx(fmt = "f")
        if res['error']:
            self._logger.error("Failed to set brightness")
            return False

        self._logger.info(f"New brightness: {brightness}")
        return True

    @tested()
    @onlyconnected()
    def _auto_contrastbrightness(self):
        self._msg_tx(53, fill = 4)
        res = self._msg_rx()
        if res['error']:
            self._logger.error("Auto contrast and brightness did not execute")
            return False

        self._logger.info("Auto contrast an brightness did execute")
        # ACB takes some time
        sleep(30)
        return True

    @tested()
    @onlyconnected()
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
            self._logger.error("Auto focus did not execute")
            return False
        self._logger.info("Auto focus executed")

        return True

    @onlyconnected()
    @tested()
    def _set_databar_text(self, newtext):
        if len(newtext) > 39:
            self._logger.error("User requested more than 40 characters in data bar")
            raise ValueError("Can only show up to 40 characters in data bar")

        txtbin = bytes([0,0,0,0]) + newtext.encode('ascii')
        txtbin += bytes([0])
        while len(txtbin) % 4 != 0:
            txtbin += bytes([0])

        self._msg_tx(101, txtbin)
        resp = self._msg_rx()
        if resp['error']:
            self._logger.error("Failed to set databar text")
            return False

        self._logger.info(f"New databar text {newtext}")
        return True

    @onlyconnected()
    @tested()
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
    def _stage_home(self):
        self._logger.info("Started homing")

        # Increase timeout to 2 min 30 secs + 15 secs grace timeout
        tout = self._port.timeout
        self._port.timeout = 2*60 + 30 + 15

        self._msg_tx(175, fill = 4)
        resp = self._msg_rx()

        # Restore old timeout
        self._port.timeout = tout

        if resp['error']:
            self._logger.error("Homing failed")
            return False
        self._logger.info("Homed stage")
        return True

    @onlyconnected()
    def _get_stage_position(self):
        # Queries the stage position ...
        self._msg_tx(190, fill = 20)
        resp = self._msg_rx(fmt = "fffff")
        if resp['error']:
            self._logger.error("Failed to query stage position")
            return None

        self._logger.debug(f"Queried stage position: X:{resp['data'][0]}mm, Y:{resp['data'][1]}mm, Z:{resp['data'][2]}mm, Tilt:{resp['data'][3]}mm, Rot:{resp['data'][4]}mm")

        return {
            'x' : resp['data'][0],
            'y' : resp['data'][1],
            'z' : resp['data'][2],
            'tilt' : resp['data'][3],
            'rot' : resp['data'][4]
        }

    @onlyconnected()
    @buggy(bugs = "Does not check boundaries! Ignores error when setting z position. Sets tilt before z position ...? Maybe implement here moving down before changing tilt ...")
    def _set_stage_position(self, x = None, y = None, z = None, tilt = None, rot = None):
        self._logger.debug(f"Starting move to x:{x}, y:{y}, z:{z}, tilt:{tilt}, rot:{rot}")
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
            self._logger.debug(f"Moving to position x:{x} mm, y:{y} mm")
            self._msg_tx(177, struct.pack("<ff", x, y))
            rep = self._msg_rx(fmt = "ff")
            self._port.timeout = tout
            if rep['error']:
                self._logger.error(f"Failed moving to x:{x}mm, y:{y}mm")
                return False
            self._logger.info(f"New position x:{x}mm, y:{y}mm")

        if rot is not None:
            # Execute Command 179 SetRotation (synchronous)
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"Moving to position rot:{rot} deg")
            self._msg_tx(179, struct.pack("<f", rot))
            rep = self._msg_rx(fmt = "f")
            self._port.timeout = tout
            if rep['error']:
                self._logger.error(f"Failed to rotate to {rot} deg")
                return False
            self._logger.info(f"New rotation rot:{rot} deg")

        if z is not None:
            # Set z position ...
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"Moving to position z:{z} mm")
            self._msg_tx(187, struct.pack("<f", z))
            rep = self._msg_rx(fmt = "f")
            self._port.timeout = tout
            if rep['error']:
                self._logger.error(f"Failed to set z position to {z} mm")
                #return False
            self._logger.info(f"New z position: {z} mm")

        if tilt is not None:
            # Set tilt
            tout = self._port.timeout
            self._port.timeout = 60
            self._logger.debug(f"Moving to tilt {tilt} deg")
            self._msg_tx(189, struct.pack("<f", tilt))
            rep = self._msg_rx(fmt = "f")
            if rep['error']:
                self._logger.error(f"Failed to set tilt position to {tilt} mm")
                return False
            self._logger.info(f"New tilt position: {tilt} deg")

        self._logger.info(f"New position set: x:{ox}, y:{oy}, z:{oz}, rot:{orot}, tilt: {otilt}")
        return True

    @onlyconnected()
    @tested()
    def _get_beamshift(self):
        self._msg_tx(80, fill = 2*4)
        resp = self._msg_rx(fmt = "ff")
        if resp['error']:
            self._logger.error("Failed to query beam shift")
            return None
        self._logger.debug(f"Queried beamshift x: {resp['data'][0]} mm, y: {resp['data'][1]} mm")
        return {
            'x' : resp['data'][0],
            'y' : resp['data'][1]
        }

    @onlyconnected()
    @buggy(bugs = "Currently not checking x and y bounds")
    @tested()
    def _set_beamshift(self, x = None, y = None):
        if (x is None) and (y is None):
            self._logger.debug("Not setting beam shift, no data supplied")
            return True
        if (x is None) or (y is None):
            # First query shift so we can do a complete set
            currentPos = self._get_beamshift()
            if currentPos is None:
                self._logger.debug("Failed to query current position, cannot set only single component")
                return False
            if x is None:
                x = currentPos['x']
            if y is None:
                y = currentPos['y']

        print(struct.pack('<ff', x, y))
        self._msg_tx(81, struct.pack('<ff', x, y,))
        resp = self._msg_rx(fmt = "ff")
        if resp['error']:
            self._logger.error("Failed to set beamshift")
            return False

        self._logger.info(f"New beamshift x={x}mm, y={y}mm")
        return True




    @onlyconnected()
    @tested()
    def _get_imagefilter_mode(self):
        self._msg_tx(74, fill = 4)
        res = self._msg_rx(fmt = 'i')
        if res['error']:
            self._logger.error("Failed to query filter mode")
            return None

        fmode = None
        try:
            fmode = ScanningElectronMicroscope_ImageFilterMode(res['data'][0])
        except:
            self._logger.error(f"Unknown image filter mode {res['data'][0]} reported")
            return None

        return {
                'mode' : fmode,
                'frames' : 2**int(res['data'][1])
        }


    @onlyconnected()
    @buggy(bugs="Cannot set average with != 2 frames")
    @untested()
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
            self._logger.error(f"Failed to set filter mode {filtermode} with {frames} frames")
            return False
        self._logger.info(f"New filtermode {filtermode} with {frames} frames")
        return True



if __name__ == "__main__":
    import sys
    from time import sleep

    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG)

    with XL30Serial("/dev/ttyU0", logger, debug = True) as xl:
        #sleep(60)
        print(xl._get_id())

        #print(xl._stage_home())

        ##xl._set_hightension(10000)
        ##sleep(30)
        #xl._auto_contrastbrightness()
        #xl._auto_focus()
        #xl._write_tiff_image("C:\\XL\\USR\\SUPERVSR\\REM\\PYTST.TIF", overwrite = True)
        #sleep(10)
        ##xl._set_brightness(20)
        #xl._set_hightension(0)

        #print(xl._get_beamshift())
        #xl._set_beamshift(1e-3, 2e-3)
        #print(xl._get_beamshift())
        #xl._set_beamshift(0,0)

        import numpy as np
        n = 0
        for ixpos, xpos in enumerate(np.linspace(-3000e-3, 3000e-3, 7)):
            for iypos, ypos in enumerate(np.linspace(-1000e-3, 1000e-3, 100)):
                fname = f"C:\\XL\\USR\\SUPERVSR\\REM\\PYT{n}.TIF"
                xl._set_stage_position(x = xpos, y = ypos)
                sleep(0.5)
                xl._write_tiff_image(fname, overwrite = True)
                print(fname)
                n = n + 1

        xl._set_hightension(0)

        #xl._stage_home()
        #xl._get_stage_position()
        #xl._set_stage_position(x = 2, y = 2, z = 38)
        #sleep(10)
        #xl._set_stage_position(x = 0, y = 0, z = 39)
        #sleep(10)
        #xl._set_stage_position(x = -2, y = -2, z = 38)
        #sleep(10)
        #xl._set_stage_position(x = 0, y = 0, z = 39)
        #xl._set_stage_position(x = 2, y = 2, z = 40, rot = 2, tilt = 2)
        #sleep(10)
        #xl._set_stage_position(x = 10, y = 10, z = 40, rot = 0, tilt = 0)
        #sleep(10)
        #xl._set_stage_position(x = 0, y = 0, z = 0, rot = 0, tilt = 0)
        #xl._get_stage_position()

from abc import abstractmethod
from enum import Enum

class ScanningElectronMicroscope_NotConnectedException(Exception):
    pass
class ScanningElectronMicroscope_CommunicationError(Exception):
    pass

class ScanningElectronMicroscope_ScanMode(Enum):
        FULL_FRAME      = 7
        SELECTED_AREA   = 6
        SPOT            = 5
        LINE_X          = 4
        LINE_Y          = 3
        EXT_XY          = 1

class ScanningElectronMicroscope_ImageFilterMode(Enum):
        LIVE            = 0
        AVERAGE         = 1
        INTEGRATE       = 2
        FREEZE          = 3

class ScanningElectronMicroscope:


    # Overriden abstract methods
    @abstractmethod
    def _connect(self):
        raise NotImplementedError()
    @abstractmethod
    def _disconnect(self):
        raise NotImplementedError()
    @abstractmethod
    def _close(self):
        raise NotImplementedError()


    @abstractmethod
    def _get_id(self):
        raise NotImplementedError()
    @abstractmethod
    def _get_hightension(self):
        raise NotImplementedError()

    @abstractmethod
    def _vent(self, stop = False):
        raise NotImplementedError()
    def _pump(self):
        raise NotImplementedError()

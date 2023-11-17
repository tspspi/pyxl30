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

class ScanningElectronMicroscope_SpecimenCurrentDetectorMode(Enum):
    TOUCH_ALARM     = 0
    IMAGING         = 1
    MEASURING       = 2

class ScanningElectronMicroscope:
    def __init__(
            self,

            highTension = ( None, None )
    ):
        if not isinstance(highTension, list) and not isinstance(highTension, tuple):
            raise ValueError("High tension range has to be a 2-list or 2-tuple")
        if len(highTension) != 2:
            raise ValueError("High tension range has t obe a 2-list or 2-tuple")
        if highTension[0] > highTension[1]:
            raise ValueError("High tension maximum has to be larger than high tension minimum")

        self._p_highTensionRange = highTension

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
    def _set_hightension(self):
        raise NotImplementedError()

    @abstractmethod
    def _vent(self, stop = False):
        raise NotImplementedError()
    @abstractmethod
    def _pump(self):
        raise NotImplementedError()

    @abstractmethod
    def _get_spotsize(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_spotsize(self, spotsize):
        raise NotImplementedError()
    @abstractmethod
    def _get_magnification(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_magnification(self, magnification):
        raise NotImplementedError()
    @abstractmethod
    def _get_detector(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_detector(self, detectorId):
        raise NotImplementedError()
    @abstractmethod
    def _get_scanmode(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_scanmode(self, mode):
        raise NotImplementedError()

    @abstractmethod
    def _make_photo(self):
        raise NotImplementedError()
    @abstractmethod
    def _write_tiff_image(self, fname, printmagnification = False, graphicsbitplane = False, databar = True, overwrite = False):
        raise NotImplementedError()

    @abstractmethod
    def _get_imagefilter_mode(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_imagefilter_mode(self, filtermode, frames):
        raise NotImplementedError()

    @abstractmethod
    def _get_contrast(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_contrast(self, contrast):
        raise NotImplementedError()
    @abstractmethod
    def _get_brightness(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_brightness(self, brightness):
        raise NotImplementedError()

    @abstractmethod
    def _auto_contrastbrightness(self):
        raise NotImplementedError()
    @abstractmethod
    def _auto_focus(self):
        raise NotImplementedError()

    @abstractmethod
    def _set_databar_text(self, newtext):
        raise NotImplementedError()
    @abstractmethod
    def _get_databar_text(self):
        raise NotImplementedError()

    @abstractmethod
    def _stage_home(self):
        raise NotImplementedError()
    @abstractmethod
    def _get_stage_position(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_stage_position(self, x = None, y = None, z = None, tilt = None, rot = None):
        raise NotImplementedError()
    @abstractmethod
    def _get_beamshift(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_beamshift(self, x = None, y = None):
        raise NotImplementedError()


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

            highTension = ( None, None ),
            spotSize = ( None, None),
            magnification = ( None, None),
            supportedScanModes = [],
            stigmatorCount = None,
    ):
        if not isinstance(highTension, list) and not isinstance(highTension, tuple):
            raise ValueError("High tension range has to be a 2-list or 2-tuple")
        if len(highTension) != 2:
            raise ValueError("High tension range has t obe a 2-list or 2-tuple")
        if highTension[0] > highTension[1]:
            raise ValueError("High tension maximum has to be larger than high tension minimum")

        if not isinstance(spotSize, list) and not isinstance(spotSize, tuple):
            raise ValueError("Spot size range has to be a 2-list or 2-tuple")
        if len(spotSize) != 2:
            raise ValueError("Spot size range has to be a 2-list or 2-tuple")
        if spotSize[0] > spotSize[1]:
            raise ValueError("Spot size maxmium has to be larger or equal than spot size minimum")

        if not isinstance(magnification, list) and not isinstance(magnification, tuple):
            raise ValueError("Magnification range has to be a 2-list or 2-tuple")
        if len(magnification) != 2:
            raise ValueError("Magnification range has to be a 2-list or 2-tuple")
        if magnification[0] > magnification[1]:
            raise ValueError("Magnification maximum has to be larger or equal to minimum")

        if not isinstance(supportedScanModes, list) and not isinstance(supportedScanModes, tuple):
            raise ValueError("Supported scan modes has to be a list or tuple")
        if len(supportedScanModes) < 1:
            raise ValueError("At least one scan mode has to be supported")
        for sm in supportedScanModes:
            if not isinstance(sm, ScanningElectronMicroscope_ScanMode):
                raise ValueError(f"Scan mode {sm} is not an ScanningElectronMicroscope_ScanMode")

        if (stigmatorCount < 0) or (stigmatorCount is None):
            raise ValueError("Stigmator count has to be 0 or a positive integer")
        if int(stigmatorCount) != stigmatorCount:
            raise ValueError("Stigmator count has to be an integer")

        self._p_highTensionRange = highTension
        self._p_spotSizeRange = spotSize
        self._p_magnificationRange = magnification
        self._p_scanModes = supportedScanModes
        self._p_stigmatorCount = stigmatorCount

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
    def _set_hightension(self, ht):
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
    def _get_stigmator(self, stigmatorindex = 0):
        raise NotImplementedError()
    def _set_stigmator(self, x = None, y = None, stigmatorindex = 0):
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



    @abstractmethod
    def _get_area_or_dot_shift(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_area_or_dot_shift(self, xshift = None, yshift = None):
        raise NotImplementedError()
    @abstractmethod
    def _get_selected_area_size(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_selected_area_size(self, sizex = None, sizey = None):
        raise NotImplementedError()



    @abstractmethod
    def _get_specimen_current_detector_mode(self):
        raise NotImplementedError()
    @abstractmethod
    def _set_specimen_current_detector_mode(self, mode):
        raise NotImplementedError()
    @abstractmethod
    def _get_specimen_current(self):
        raise NotImplementedError()


    @abstractmethod
    def _is_beam_blanked(self):
        raise NotImplementedError()
    @abstractmethod
    def _blank(self):
        raise NotImplementedError()
    @abstractmethod
    def _unblank(self):
        raise NotImplementedError()


    # Exposed methods (public API)
    def get_id(self):
        return self._get_id()

    def get_hightension(self):
        return self._get_hightension()
    def set_hightension(self, ht):
        if (ht < self._p_highTensionRange[0]) and (ht != 0):
            raise ValueError("High tension has to be set to minimum of {self._p_highTensionRange[0]} or 0")
        if (ht > self._p_highTensionRange[1]):
            raise ValueError("High tension can be set to a maximum of {self._p_highTensionRange[1]}")
        return self._set_hightension(ht)

    def vent(self, stop = False):
        return self._vent(stop)
    def pump(self):
        return self._pump()

    def get_spotsize(self):
        return self._get_spotsize()
    def set_spotsize(self, spotsize):
        if spotsize < self._p_spotSizeRange[0]:
            raise ValueError("Mimimum supported spot size is {self._p_spotSizeRange[0]}")
        if spotsize > self._p_spotSizeRange[1]:
            raise ValueError("Maximum supported spot size is {self._p_spotSizeRange[1]}")

        return self._set_spotsize(spotsize)

    def get_magnification(self):
        return self._get_magnification()
    def set_magnification(self, mag):
        if mag < self._p_magnificationRange[0]:
            raise ValueError("Minimum supported magnification is {self._p_magnificationRange[0]}")
        if mag > self._p_magnificationRange[1]:
            raise ValueError("Maximum supported magnification is {self._p_magnificationRange[1]}")
        return self._set_magnification(mag)

    def get_detector(self):
        return self._get_detector()
    def set_detector(self, detectorId):
        # ToDo: Translate to generic detector type enum
        return self._set_detector()

    def get_scanmode(self):
        return self._get_scanmode()
    def set_scanmode(self, mode):
        if not isinstance(mode, ScanningElectronMicroscope_ScanMode):
            raise ValueError("Scan mode has to be one of the ScanningElectronMicroscope_ScanMode instances")
        if mode not in self._p_scanModes:
            raise ValueError(f"Mode {mode} not supported by this device")

        return self._set_scanmode(mode)

    def get_stigmator(self, stigmatorIndex = 0):
        return self._get_stigmator(stigmatorIndex)
    def set_stigmator(self, x = None, y = None, stigmatorIndex = 0):
        return self._set_stigmator(x = x, y = y, stigmatorIndex = stigmatorIndex)


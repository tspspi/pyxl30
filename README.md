# Philips XL30 Environmental Scanning Electron Microscope (ESEM) control libraries and utilities (unofficial)

_Under development_

This repository contains a small set of utilities and control libraries for
the Philips XL30 environmental scanning electron microscope (ESEM). __This
code is not associated with Philips or FEI in any way__.

Current available components:

* The ```xl30serial.xl30serial``` module provides a simple interface
  to the XL30 using it's serial console server. Remote control via the
  serial interface has to be enabled on the console. This route of control
  has been chosen since DDE and shared memory via flat thunking is not
  working since the Windows 2K update. Unfortunately not all parameters
  like chamber pressure are available via the serial port - and transfer
  of images has to work via files. __This library is under development
  and may change at any point in future__. It only implements a small
  subset of the supported commands.

## Installation

This package is available as PyPi package and automatically build on each
tag by an automated build system.

```
pip install pyxl30-tspspi
```

## Usage

### Simple sample with internal methods

This simple sample currently uses private methods of the class. Usually
one should access the microscope via it's base class from
the [pylabdevs](https://github.com/tspspi/pylabdevs/tree/master) project.
This base class is currently under development.

```
from xl30serial import XL30Serial
from time import sleep

with XL30Serial("/dev/ttyU0", logger, debug = True) as xl:
   print(xl._get_id())
   xl._set_hightension(30e3)
   sleep(120)
   xl._set_scanmode(ScanningElectronMicroscope_ScanMode.FULL_FRAME)
   xl._set_imagefilter_mode(ScanningElectronMicroscope_ImageFilterMode.INTEGRATE, 1)
   while(xl._get_imagefilter_mode()['mode'] != ScanningElectronMicroscope_ImageFilterMode.FREEZE):
      sleep(0.5)
   xl._write_tiff_image("c:\\temp\\IMAGE.TIF")

   xl._set_scanmode(ScanningElectronMicroscope_ScanMode.FULL_FRAME)
   xl._set_hightension(0)

```

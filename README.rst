pymodaq_plugins_princeton_instruments (Princeton Instruments Cameras and Monochromators)
########################################################################################

PyMoDAQ plugin for Princeton Instruments Cameras and monochromators.

Relies on Alexey Shkarin's pylablib hardware control python module for the control of cameras
The picam library produced by Princeton Instruments has to be installed to use this plugin with cameras (used to be freely downloadable at https://www.princetoninstruments.com/products/software-family/pi-cam).
If pylablib is not able to find the existing picam installation (.dll file), it is easy to solve. See: https://pylablib.readthedocs.io/en/latest/devices/Picam.html#cameras-picam)

Relies on pyserial for the control of monochromators.

You can help in the development of this plugin by testing it with your hardware and reporting issues and successes in this repository. I will update the list of tested hardware hardware accordingly.

Authors
=======

* Nicolas Tappy

Instruments
===========
Should support all cameras using picam through adaptative parameters parsing.

Tested on Princeton Instrument PYLon BR eXcelon cameras.

Support Princeton Instrument Acton SpectraPro SP2500i spectrometer. Limited functionalities are expected  work with other monochromators of the same family (sp2150i, sp2300i) but I advise caution
as some hard-to-anticipate differences exist between these models that will induce unexpected behaviour.

Viewer2D
++++++++

* **picam**: Control of cameras using the picam library.

Move
++++

* **spectrapro2500i**: Control of Spectra Pro Monochromator using pyserial

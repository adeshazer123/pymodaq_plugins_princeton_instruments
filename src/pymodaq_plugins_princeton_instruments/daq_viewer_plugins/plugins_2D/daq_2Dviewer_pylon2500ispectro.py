import numpy as np
from serial.tools.list_ports import comports
from easydict import EasyDict as edict
from pymodaq.daq_utils.daq_utils import ThreadCommand, getLineInfo, DataFromPlugins, Axis
from pymodaq.daq_viewer.utility_classes import DAQ_Viewer_base, comon_parameters, main

from qtpy import QtWidgets, QtCore

from ...hardware.picam_utils import define_pymodaq_pyqt_parameter, sort_by_priority_list, remove_settings_from_list

from .daq_2Dviewer_picam import DAQ_2DViewer_picam
from ...hardware.Serial_SpectraPro2500i import SpectraPro2500i

import pylablib.devices.PrincetonInstruments as PI


class DAQ_2DViewer_pylon2500ispectro(DAQ_2DViewer_picam):
    """
        Base class for Princeton Instruments CCD camera controlled with the picam c library.

        =============== ==================
        **Attributes**   **Type**
        Nothing to see here...
        =============== ==================

        See Also
        --------
        utility_classes.DAQ_Viewer_base
    """
    _dvcs = PI.list_cameras()
    serialnumbers = [dvc.serial_number for dvc in _dvcs]

    _dvc_mono = comports()
    comports_mono = [d.device for d in _dvc_mono]
    val = comports_mono[-1]

    params = comon_parameters + [
        {'title': 'Controller ID:', 'name': 'controller_id', 'type': 'str', 'value': '', 'readonly': True},
        {'title': 'Serial number:', 'name': 'serial_number', 'type': 'list', 'limits': serialnumbers},
        {'title': 'COM Port Mono:', 'name': 'com_port_mono', 'type': 'list', 'limits': comports_mono, 'value': val},
        {'title': 'Simple Settings', 'name': 'simple_settings', 'type': 'bool', 'value': True}
    ]

    callback_signal = QtCore.Signal()

    hardware_averaging = False

    def __init__(self, parent=None, params_state=None):
        super().__init__(parent, params_state)

        # Axes are not dealt with at the moment.
        self.x_axis = None
        self.y_axis = None

        self.data_shape = 'Data2D'
        self.callback_thread = None

        self.monochromator = SpectraPro2500i(port='None')

    def commit_settings(self, param):
        """Commit setting changes to the device."""
        # Parameter from these groups are handled by the camera plugin
        if param.parent().name() in ['settable_camera_parameters', 'read_only_camera_parameters']:
            super().commit_settings(param)
        #ROi parameters as well but require re-computing the wavelength axis
        elif param.parent().name() == "rois":
            super().commit_settings(param)
            self._compute_wavelength_axis()
        #The rest we make it custom
        elif param.name() == 'wavelength':
            #First set position
            self.monochromator.set_position(param.value())
            #Then update the "real" value (which is not needed but still)
            self.settings.child('monochromator_parameters', 'physical_parameters', 'central_wavelength').setValue(self.monochromator.get_position())
            #Then update the wavelength axis
            self._compute_wavelength_axis()
        elif param.name() == "grating":
            # Here we must extract the correct index from the gratings string.
            grating_index = int(param.value().replace('->', '')[0])
            # Then set
            self.monochromator.set_grating(value=grating_index)
            # Then update the list as the arrow moves place and it's nice
            all_gratings = self.monochromator.get_all_gratings()
            self.settings.child('monochromator_parameters', 'grating').setLimits(all_gratings)
            self.settings.child('monochromator_parameters', 'grating').setValue(all_gratings[grating_index - 1])
            # Then update the wavelength axis
            self._compute_wavelength_axis()
        elif param.name() == 'exit_mirror':
            #This basically kills the signal.
            self.monochromator.ensure_mirror_is_set_to_exit()
            self.monochromator.set_mirror_position(param.value())

    def _compute_wavelength_axis(self) -> None:
        """ Compute the wavelength axis of the spectrometer"""

        x_start = self.settings.child('settable_camera_parameters', 'rois', 'x').value()
        x_width = self.settings.child('settable_camera_parameters', 'rois', 'width').value()
        x_binning = self.settings.child('settable_camera_parameters', 'rois', 'x_binning').value()
        # Indices object
        axis_indices = np.arange(x_start, x_width, x_binning)

        # Detector pixel size
        pix_size = self.controller.get_attribute_value('Pixel Width')*1000  # *1000 to get in nm
        self.emit_status(ThreadCommand('Update_Status', [f'pixel size {pix_size}']))
        # Centre channel
        Pc = int(self.controller.get_attribute_value('Active Width')/2) - 1  # minus 1 for 0 start indexing
        self.emit_status(ThreadCommand('Update_Status', [f'centre channel {Pc}']))

        # Focal length in nm
        f = self.settings.child('monochromator_parameters', 'physical_parameters', 'focal_length').value()*1e6
        self.emit_status(ThreadCommand('Update_Status', [f'f nm {f}']))

        # Centre wavelength in nm
        lambda_centre = self.settings.child('monochromator_parameters', 'physical_parameters', 'central_wavelength').value()
        self.emit_status(ThreadCommand('Update_Status', [f'l centre {lambda_centre}']))

        # Angles in radian
        K = self.settings.child('monochromator_parameters', 'physical_parameters', 'dv_angle').value() * np.pi/180.0
        gamma = self.settings.child('monochromator_parameters', 'physical_parameters', 'det_angle').value() * np.pi/180.0

        #Grating density in lines per nm
        current_grating = self.settings.child('monochromator_parameters', 'grating').value().replace('->', '')
        G = [s for s in current_grating.split(' ') if s]
        G = float(G[1])*1e-6 #in lines per nm
        self.emit_status(ThreadCommand('Update_Status', [f'g in nm-1 {G}']))

        #Axis computation
        beta_c = np.arcsin(G * lambda_centre / (2 * np.cos(K))) - K
        beta_n = beta_c + gamma - np.arctan(np.tan(gamma) - pix_size*(axis_indices-Pc)/(f*np.cos(gamma)))
        lambda_n = 1 / G * (np.sin(2 * K + beta_c) + np.sin(beta_n))

        self.emit_status(ThreadCommand('Update_Status', [f'updated axis of length {len(lambda_n)}: {lambda_n}']))
        self.x_axis = lambda_n
        # return lambda_n

    def _prepare_view(self):
        """Preparing a data viewer by emitting temporary data. Typically, needs to be called whenever the
        ROIs are changed"""
        wx = self.settings.child('settable_camera_parameters', 'rois', 'width').value()
        wy = self.settings.child('settable_camera_parameters', 'rois', 'height').value()
        bx = self.settings.child('settable_camera_parameters', 'rois', 'x_binning').value()
        by = self.settings.child('settable_camera_parameters', 'rois', 'y_binning').value()

        sizex = wx // bx
        sizey = wy // by

        mock_data = np.zeros((sizey, sizex))

        if sizey != 1 and sizex != 1:
            data_shape = 'Data2D'
            if data_shape != self.data_shape:
                self.data_shape = data_shape
                xax = Axis(label='Wavelength', units= "nm", data = self.x_axis)
                yax = Axis(data=np.arange(sizey))
                data_obj = DataFromPlugins(name='Picam - spectro', data=[np.squeeze(mock_data)], dim=self.data_shape,
                                x_axis=xax, y_axis=yax, labels=[f'Picam_{self.data_shape}'])
                self.data_grabed_signal_temp.emit([data_obj])
        else:
            data_shape = 'Data1D'
            if data_shape != self.data_shape:
                self.data_shape = data_shape
                xax = Axis(label='Wavelength', units= "nm", data = self.x_axis)
                data_obj = DataFromPlugins(name='Picam - spectro', data=[np.squeeze(mock_data)], dim=self.data_shape,
                                x_axis=xax, labels=[f'Picam_{self.data_shape}'])
                self.data_grabed_signal_temp.emit([data_obj])

        # if data_shape != self.data_shape:
        #     self.data_shape = data_shape
        #     # init the viewers
        #     self.data_grabed_signal_temp.emit([DataFromPlugins(name='Picam',
        #                                                        data=[np.squeeze(mock_data)],
        #                                                        dim=self.data_shape,
        #                                                        labels=[f'Picam_{self.data_shape}'])])
            QtWidgets.QApplication.processEvents()

    def emit_data(self):
        """
            Fonction used to emit data obtained by callback.
            See Also
            --------
            daq_utils.ThreadCommand
        """
        try:
            # Get  data from buffer
            frame = self.controller.read_newest_image()
            # Emit the frame.
            self.data_grabed_signal.emit([DataFromPlugins(name='Picam',
                                                          data=[np.squeeze(frame)],
                                                          dim=self.data_shape,
                                                          labels=[f'Picam_{self.data_shape}'],
                                                          x_axis= self.x_axis,
                                                          )])
            # To make sure that timed events are executed in continuous grab mode
            QtWidgets.QApplication.processEvents()

        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [str(e), 'log']))

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object) custom object of a PyMoDAQ plugin (Slave case).
        None if only one detector by controller (Master case)

        Returns
        -------
        self.status (edict): with initialization status: three fields:
            * info (str)
            * controller (object) initialized controller
            *initialized: (bool): False if initialization failed otherwise True
        """
        _ = super().ini_detector(controller)

        if self.status.initialized == False:
            self.emit_status(
                ThreadCommand('Update_Status', ["Leaving DAQ_2DViewer_pylon2500ispectro.ini_detector", "log"]))
            return self.status

        mono_params_list = [
            {'title': 'Wavelength', 'name': 'wavelength', 'type': 'float', 'values': 000.000},
            {'title': 'Grating', 'name': 'grating', 'type': 'list', 'values': []},
            {'title': 'Exit mirror', 'name': 'exit_mirror', 'type': 'list', 'value': 'front',
             'limits': ['front', 'side']},
            {'title': 'Monochromator ID:', 'name': 'monochromator_id', 'type': 'str', 'value': '', 'readonly': True},
            {'title': 'Physical parameters:', 'name': 'physical_parameters', 'type': 'group', 'children': [
                {'title': 'Central Wavelength:', 'name': 'central_wavelength', 'type': 'float', 'value': 0.0, 'readonly': True},
                {'title': 'Focal Length:', 'name': 'focal_length', 'type': 'float', 'value': 0.0, 'readonly': True},
                {'title': 'Dv angle:', 'name': 'dv_angle', 'type': 'float', 'value': 0.0, 'readonly': True},
                {'title': 'Det angle:', 'name': 'det_angle', 'type': 'float', 'value': 0.0, 'readonly': True},
            ]}]

        self.settings.addChild({'title': 'Monochromator Parameters',
                                'name': 'monochromator_parameters',
                                'type': 'group',
                                'children': mono_params_list,
                                })

        self.settings.child('com_port_mono').setReadonly()

        self.monochromator = SpectraPro2500i(port=self.settings.child('com_port_mono').value())
        self.monochromator.open()

        fl = self.monochromator.get_focal_length()
        self.settings.child('monochromator_parameters', 'physical_parameters', 'focal_length').setValue(fl)

        half_angle = self.monochromator.get_half_angle()
        self.settings.child('monochromator_parameters', 'physical_parameters', 'dv_angle').setValue(half_angle)

        detector_angle = self.monochromator.get_detector_angle()
        self.settings.child('monochromator_parameters', 'physical_parameters', 'det_angle').setValue(detector_angle)

        self.monochromator.ensure_mirror_is_set_to_exit()

        exitmirror = self.monochromator.get_mirror_position()
        self.settings.child('monochromator_parameters', 'exit_mirror').setValue(exitmirror)

        gratinglist = self.monochromator.get_all_gratings()
        self.settings.child('monochromator_parameters', 'grating').setLimits(gratinglist)
        for g in gratinglist:
            if g.startswith('->'):
                self.settings.child('monochromator_parameters', 'grating').setValue(g)

        spectroname = self.monochromator.get_mono_model()
        self.settings.child('monochromator_parameters', 'monochromator_id').setValue(spectroname)

        self.status.info = "Initialised Spectrometer"
        self.status.initialized = True
        self.status.controller = self.controller
        return self.status

    def close(self):
        """
        Terminate the communication protocol
        """
        super().close()
        self.settings.child('com_port_mono').setWritable()
        self.monochromator.close()

if __name__ == '__main__':
    main(__file__)

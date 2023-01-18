# common set of parameters for all actuators
from pymodaq.control_modules.move_utility_classes import DAQ_Move_base, comon_parameters_fun, main
from pymodaq.daq_utils.daq_utils import ThreadCommand  # object used to send info back to the main thread
from pymodaq.daq_utils.parameter import Parameter

from pymodaq_plugins_princeton_instruments.hardware.Serial_SpectraPro2500i import SpectraPro2500i
from serial.tools.list_ports import comports


class DAQ_Move_spectrapro2500i(DAQ_Move_base):
	"""Plugin for the Template Instrument

	This object inherits all functionality to communicate with PyMoDAQ Module through inheritance via DAQ_Move_base
	t then implements the particular communication with the instrument

	Attributes:
	-----------
	controller: object
		The particular object that allow the communication with the hardware, in general a python wrapper around the
		 hardware library
	"""
	_dvc = comports()
	com = [d.device for d in _dvc]
	_controller_units = 'nm'
	is_multiaxes = False
	axes_names = ['Wavelength']

	params = [{'title': 'Monochromator ID:', 'name': 'monochromator_id', 'type': 'str', 'value': '', 'readonly': True},
			  {'title': 'COM Port:', 'name': 'com_port', 'type': 'list', 'values': com},
			  {'title': 'Grating', 'name': 'grating', 'type': 'list', 'values': []},
			  {'title': 'Exit mirror', 'name': 'exit_mirror', 'type': 'list', 'value': 'front',
			   'limits': ['front', 'side']},
			  {'title': 'Spectrometer Parameters:', 'name': 'spectrometer_parameters', 'type': 'group', 'children': [
				  {'title': 'Focal Length:', 'name': 'focal_length', 'type': 'float', 'value': 0.0, 'readonly': True},
				  {'title': 'Dv angle:', 'name': 'dv_angle', 'type': 'float', 'value': 0.0, 'readonly': True},
				  {'title': 'Det angle:', 'name': 'det_angle', 'type': 'float', 'value': 0.0, 'readonly': True},
			  ]}
			  ] + comon_parameters_fun(is_multiaxes, axes_names)

	def ini_attributes(self):
		self.controller: SpectraPro2500i

	def get_actuator_value(self):
		"""Get the current value from the hardware with scaling conversion.

		Returns
		-------
		float: The position obtained after scaling conversion.
		"""
		pos = self.controller.get_position()  # when writing your own plugin replace this line
		pos = self.get_position_with_scaling(pos)
		return pos

	def commit_settings(self, param: Parameter):
		"""Apply the consequences of a change of value in the detector settings

		Parameters
		----------
		param: Parameter
			A given parameter (within detector_settings) whose value has been changed by the user
		"""
		if param.name() == "grating":
			# Here we must extract the correct index from the gratings string. This means removing the arrow and
			# Replacing the number by a zero-starting index.
			grating_index = int(param.value().replace('->', '')[0])
			self.controller.set_grating(value=grating_index)
			all_gratings = self.controller.get_all_gratings()
			self.settings.child('grating').setLimits(all_gratings)
			self.settings.child('grating').setValue(all_gratings[grating_index-1])
		elif param.name() == 'exit_mirror':
			self.controller.ensure_mirror_is_set_to_exit()
			self.controller.set_mirror_position(param.value())
		else:
			pass

	def ini_stage(self, controller=None):
		"""Actuator communication initialization

		Parameters
		----------
		controller: (object)
			custom object of a PyMoDAQ plugin (Slave case). None if only one actuator by controller (Master case)

		Returns
		-------
		info: str
		initialized: bool
			False if initialization failed otherwise True
		"""
		com = self.settings.child('com_port').value()
		self.settings.child('com_port').setReadonly(readonly=True)

		self.ini_stage_init(old_controller=controller,
							new_controller=SpectraPro2500i(port=com))

		self.controller.open()

		fl = self.controller.get_focal_length()
		self.settings.child('spectrometer_parameters', 'focal_length').setValue(fl)

		half_angle = self.controller.get_half_angle()
		self.settings.child('spectrometer_parameters', 'dv_angle').setValue(half_angle)

		detector_angle = self.controller.get_detector_angle()
		self.settings.child('spectrometer_parameters', 'det_angle').setValue(detector_angle)

		self.controller.ensure_mirror_is_set_to_exit()

		exitmirror = self.controller.get_mirror_position()
		self.settings.child('exit_mirror').setValue(exitmirror)

		gratinglist = self.controller.get_all_gratings()
		self.settings.child('grating').setLimits(gratinglist)
		for g in gratinglist:
			if g.startswith('->'):
				self.settings.child('grating').setValue(g)

		spectroname = self.controller.get_mono_model()
		self.settings.child('monochromator_id').setValue(spectroname)

		info = f"Initialization successful: Monochromator model {spectroname} at com port {com}"
		initialized = True
		return info, initialized

	def move_abs(self, value):
		""" Move the actuator to the absolute target defined by value

		Parameters
		----------
		value: (float) value of the absolute target positioning
		"""

		value = self.check_bound(value)  # if user checked bounds, the defined bounds are applied here
		self.target_value = value
		value = self.set_position_with_scaling(value)  # apply scaling if the user specified one
		self.controller.set_position(value)  # when writing your own plugin replace this line
		self.emit_status(ThreadCommand('Update_Status', [f'New position: {value}']))

	def move_rel(self, value):
		""" Move the actuator to the relative target actuator value defined by value

		Parameters
		----------
		value: (float) value of the relative target positioning
		"""
		value = self.check_bound(self.current_position + value) - self.current_position
		self.target_value = value + self.current_position
		value = self.set_position_relative_with_scaling(value)

		self.controller.set_position(value + self.current_position)  # when writing your own plugin replace this line
		self.emit_status(ThreadCommand('Update_Status', [f'New position: {value}']))

	def move_home(self):
		"""Call the reference method of the controller"""
		self.controller.set_position(0.0)  # when writing your own plugin replace this line
		self.emit_status(ThreadCommand('Update_Status', [f'Moving home: {0.0}']))

	def stop_motion(self):
		"""Stop the actuator and emits move_done signal"""

		self.controller.stop_moving()  # when writing your own plugin replace this line
		self.emit_status(ThreadCommand('Update_Status', ['Motion stopped']))

	def close(self):
		"""Terminate the communication protocol"""
		self.settings.child('com_port').setReadonly(readonly=False)
		self.settings.child('com_port').setWritable()

		self.controller.close()  # when writing your own plugin replace this line


if __name__ == '__main__':
	main(__file__)

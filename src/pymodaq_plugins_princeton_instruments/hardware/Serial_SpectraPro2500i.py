"""
Wrapper to communicate with a Princeton Instruments Acton SpectraPro 2500i monochromator. Is expected to work with
little adjustment on many spectrometers of the same series (2150i, 2300i)

Largely, this wrapper is adapted from the piezosystem Jena wrapper.
"""

import serial
import warnings
import threading
from typing import List, Union

class SpectraPro2500i:

    """Class for wrapping SpectraPro CLE commands"""
    def __init__(self, port: str):
        self.ser = serial.Serial()
        self.ser.baudrate = 9600
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        # self.ser.xonxoff = True
        self.ser.timeout = None
        self.ser.write_timeout = None
        self.ser.port = port

        self.lock = threading.Lock()

        self.setup_calibration: Union[List[str], None] = None
        self.grating_list: Union[List[str], None] = None


    def open(self) -> None:
        """
        Open communication.
        """
        self.ser.open()

    def reset_buffer(self) -> str:
        """Check if the buffer of serial communication has bytes waiting inside.
        If that's the case, read it and log it as some kind of warning."""
        dumped = ""
        if self.ser.in_waiting != 0:
            #Maybe raise a warning?
            dumped = self.ser.read_all().decode()
            warnings.warn(f'Dumped IO-buffer content: {dumped}', RuntimeWarning)

        return dumped

    def get_position(self) -> float:
        """
        Get the current Monochromator position in nm
        Returns
        -------
        float: The current value
        """
        # Encode command for communication with Monochromator
        cmd = f'?NM\r'.encode()

        with self.lock:
            #Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 4:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        #Convert value to float
        pos = float(reply[1:6])

        return pos

    def get_scanning_speed(self) -> float:
        """
        Get the current Monochromator scanning speed in nm/min
        Returns
        -------
        float: The current value
        """
        # Encode command for communication with Monochromator
        cmd = f'?NM/MIN\r'.encode()

        with self.lock:
            #Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 8:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Convert value to float
        pos = float(reply[1:8])

        return pos

    def get_grating(self) -> int:
        """
        Get the currently installed grating
        Returns
        -------
        grating_num: The current value
        """
        # Encode command for communication with Monochromator
        cmd = f'?GRATING\r'.encode()

        with self.lock:
            #Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 9:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        #Convert value to int
        grating_num = int(reply[1:3])

        return grating_num

    def get_turret(self) -> int:
        """
        Get the currently installed grating turret
        Returns
        -------
        turret_num: The current value
        """
        # Encode command for communication with Monochromator
        cmd = f'?TURRET\r'.encode()

        with self.lock:
            #Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 8:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        #Convert value to float
        turret_num = int(reply[1:3])

        return turret_num

    def get_all_gratings(self) -> List[str]:
        """
        Get the list of all installed grating turrets. Currently used grating is indicated with an arrow.
        Returns
        -------
        all_gratings: The list of gratings with a description.
        """
        # Encode command for communication with Monochromator
        cmd = f'?GRATINGS\r'.encode()

        with self.lock:
            #Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 10:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')
            #Convert value to float
            all_gratings = reply.decode().replace('\x1a', '->').splitlines()[1:-1]
            all_gratings = [s.strip() for s in all_gratings]

        return all_gratings

    def ensure_mirror_is_set_to_exit(self) -> None:
        """Ensure the Monochromator firmware is set to accept commands to the exit mirror and not entrance"""

        # Encode command for communication with Monochromator
        cmd = f'EXIT-MIRROR\r'.encode()

        with self.lock:
            # Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 12:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        mirror_ok = reply.decode().strip()

        if not mirror_ok.startswith('ok'):
            raise ValueError(f'Mirror not ok: received {mirror_ok}')

    def get_mirror_position(self) -> str:
        """
        Get the exit mirror position. In the 2500i spectrometer there is no entrance mirror so no ambiguity
        Returns
        -------
        exit_position: The currently set exit position
        """
        # Encode command for communication with Monochromator
        cmd = f'?MIRROR\r'.encode()

        with self.lock:
            # Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 8:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        mirror_position = reply.decode().strip().split(' ')[0]

        if mirror_position not in ['front', 'side']:
            raise ValueError(f'Mirror position currently set to {mirror_position}. '
                             f'Ensure that the monochromator is currently set to receive commands for '
                             f'exit diverter mirror.')

        return mirror_position

    def get_mono_model(self) -> str:
        """
        Get the monochromator model
        Returns
        -------
        exit_position: The currently set exit position
        """
        # Encode command for communication with Monochromator
        cmd = f'MODEL\r'.encode()

        with self.lock:
            # Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 6:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        model = reply.decode().strip().split(' ')[0]

        return model

    def get_setup_and_calibration(self) -> List[str]:
        """
        Get the monochromator calibration information
        Returns
        -------
        setup_calibration: The setup and calibration information
        """
        # Encode command for communication with Monochromator
        cmd = f'MONO-EESTATUS\r'.encode()

        with self.lock:
            # Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 14:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        self.setup_calibration = reply.decode().splitlines()[1:-1]

        return self.setup_calibration

    def get_focal_length(self) -> float:
        """
        Get the focal length from  calibration information
        Returns
        -------
        f: The instrument focal length
        """
        if self.setup_calibration is None:
            _ = self.get_setup_and_calibration()

        f = None

        for line in self.setup_calibration:
            if line.startswith('focal length'):
                f = float(line.strip().split(' ')[-1])

        if f is None:
            raise ValueError('focal length information not found in calibration information')
        else:
            return f

    def get_half_angle(self) -> float:
        """
        Get the half deviation angle (named half angle) of the spectrometer
        Returns
        -------
        alpha: The instrument half angle
        """
        if self.setup_calibration is None:
            _ = self.get_setup_and_calibration()

        alpha = None

        for line in self.setup_calibration:
            if line.startswith('half angle'):
                alpha = float(line.strip().split(' ')[-1])

        if alpha is None:
            raise ValueError('half angle information not found in calibration information')
        else:
            return alpha

    def get_detector_angle(self) -> float:
        """
        Get the detector plane angle of the monochromator
        Returns
        -------
        delta: The instrument detector plane angle
        """
        if self.setup_calibration is None:
            _ = self.get_setup_and_calibration()

        delta = None

        for line in self.setup_calibration:
            if line.startswith('detector angle'):
                delta = float(line.strip().split(' ')[-1])

        if delta is None:
            raise ValueError('detector angle information not found in calibration information')
        else:
            return delta

    def set_position(self, value: float) -> None:
        """
        Send a call to the actuator to move at the given value
        Parameters
        ----------
        value: (nm) the target value in nm
        """
        #Encode it for communication with stage controller
        cmd = f'{value:3.3f} GOTO\r'.encode()
        #write
        with self.lock:
            self.ser.write(cmd)
            reply = self.ser.read_until(expected=b'ok\r\n')
        # Format reply.
        grating_set = reply.decode().strip()

        if not grating_set.startswith('ok'):
            raise ValueError(f'Grating failed to set: received {grating_set}')

    def set_grating(self, value: int) -> None:
        """
        Send a call to the actuator to select the correct grating
        Parameters
        ----------
        value: the grating number
        """
        if value>8 or value<0:
            raise ValueError(f'Grating number {value} out of 0-8 range')
        #Encode it for communication with stage controller
        cmd = f'{value:d} GRATING\r'.encode()
        #write
        with self.lock:
            self.ser.write(cmd)

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        grating_set = reply.decode().strip()

        if not grating_set.startswith('ok'):
            raise ValueError(f'Grating failed to set: received {grating_set}')

    def set_mirror_position(self, value: str) -> None:
        """
        Set the exit mirror position. In the 2500i spectrometer there is no entrance mirror so no ambiguity.
        Must either receive 'front' or 'side' as input string.
        """
        if value == 'front':
            # Encode command for communication with Monochromator
            cmd = f'FRONT\r'.encode()
        elif value == 'side':
            # Encode command for communication with Monochromator
            cmd = f'SIDE\r'.encode()
        else:
            raise ValueError(f'Invalid input {value} received by the function. Valid inputs are "front" or "side".')

        with self.lock:
            # Send command and read reply
            ret = self.ser.write(cmd)
            if ret not in [5, 6]:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        mirror_position = reply.decode().strip()

        if not mirror_position.startswith('ok'):
            raise ValueError(f'Mirror position currently set to {mirror_position}. '
                             f'Ensure that the monochromator is currently set to receive commands for '
                             f'exit mirror.')

    def stop_moving(self) -> None:
        """
        Get the monochromator model
        Returns
        -------
        exit_position: The currently set exit position
        """
        # Encode command for communication with Monochromator
        cmd = f'MONO-STOP\r'.encode()

        with self.lock:
            # Send command and read reply
            ret = self.ser.write(cmd)
            if ret != 10:
                warnings.warn(f'Unsuccessful command: {cmd.decode()}\n')

            reply = self.ser.read_until(expected=b'ok\r\n')

        # Format reply.
        stop_confirm = reply.decode().strip()

        if not stop_confirm.startswith('ok'):
            raise ValueError(f'Motion stop failed to execute. received string: {stop_confirm}.')


    def close(self):
        """
        Close communication.
        """
        self.ser.close()
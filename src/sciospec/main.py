import serial
# pip install pyserial
import sys
import struct
from deepdiff import DeepDiff, model as dd_model
import json


DEFAULT_INDENT_IN_JSON = 2

ACK_DICT = {
    "01": "Frame-Not-Acknowledge: Incorrect syntax",
    "02": "Timeout: Communication-timeout (less data than expected)",
    "04": "Wake-Up Message: System boot ready",
    "11": "TCP-Socket: Valid TCP client-socket connection",
    "81": "Not-Acknowledge: Command has not been executed",
    "82": "Not-Acknowledge: Command could not be recognized",
    "83": "Command-Acknowledge: Command has been executed successfully",
    "84": "System-Ready Message: System is operational and ready to receive data"
}


# tags
SET_SETUP_TAG = "B6"


RESPONSE_LENGTH_DICT = {
    "Ack": 4,
    "D1": 7,
    # "B6": ??,
}


HARDCODED_LENS = {
    SET_SETUP_TAG: 16
}


# config consts
FREQ_LIST_KEY = "freq_list_params"
AMPLITUDE_KEY = "amplitude"
PRECISION_KEY = "precision"
START_FREQ_KEY = "start_freq"
END_FREQ_KEY = "end_freq"
FREQ_COUNT_KEY = "freq_count"
FREQ_SCALE_KEY = "freq_scale"
DUMMY_CONFIG = {
    FREQ_LIST_KEY: {
        "start_freq": 100,
        "end_freq": 1000,
        "freq_count": 80,
        "freq_scale": 1 # Log
    },
    PRECISION_KEY: 1,
    AMPLITUDE_KEY: 0.1, # V
}

def to_byte(hex_str):
    # hex_str = "D1"
    byte_value = int(hex_str, 16)
    return byte_value


def decode_bytes(data):
    res = []
    for byte in data:
        res.append(f"{byte:02X}")
    return res


def make_cmd(cmd_tag, data_bytes, hardcoded_len=None):
    if hardcoded_len is not None:
        data_len = hardcoded_len
    else:
        data_len = len(data_bytes)
    cmd_tag_byte = to_byte(cmd_tag)
    return bytes(
            [
                cmd_tag_byte,
                to_byte(str(data_len))
            ]
        +
            [to_byte(byte) for byte in data_bytes]
        +
            [cmd_tag_byte]
    )


def float_as_bytes(float_val):
    # bytes_as_list = []
    packed_value = struct.pack('>f', float_val)  # '>f' is for big-endian float
    # for byte in packed_value:
    #     bytes_as_list.append(byte)
    return decode_bytes(packed_value)
    # return bytes_as_list


def get_with_assert(container, key, error_msg=None):

    if isinstance(key, list):
        assert len(key) > 0
        next_key = key[0]
        rest_key = key[1:]
        next_container = get_with_assert(container, next_key, error_msg)
        if len(rest_key) == 0:
            return next_container
        else:
            return get_with_assert(next_container, rest_key, error_msg)
    else:
        if error_msg is None:
            error_msg = f"Key \"{key}\" not in container: {container}"
        assert key in container, error_msg
        return container[key]


# from: https://stackoverflow.com/questions/8230315/how-to-json-serialize-sets
class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (set, dd_model.PrettyOrderedSet)):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


# from: https://www.tensorflow.org/tensorboard/text_summaries
def pretty_json(hp, cls=SetEncoder, default=str):

    json_hp = json.dumps(
        hp,
        indent=DEFAULT_INDENT_IN_JSON,
        cls=cls,
        default=default
    )
    return "".join("\t" + line for line in json_hp.splitlines(True))


class Device:

    def __init__(self):
        self.connection = self._get_connection()

    def read_ack(self, verbose=True):
        # Read 4 bytes from the serial port
        read_buffer = self.read_data_buffer(RESPONSE_LENGTH_DICT["Ack"])

        # Print the ACK frame in hexadecimal format
        print("ACK-Frame: ", end="")
        # for byte in read_buffer:
        #     print(f"{byte:02X} ", end="")
        # print()
        # print(decode_bytes(read_buffer))
        decoded_buffer = decode_bytes(read_buffer)
        if len(read_buffer) == 0:
            print("No acknowledgement received")
            ack_id = None
        else:
            # print()
            assert len(decoded_buffer) == 4
            ack_id = str(decoded_buffer[2])
            if verbose:
                print(ACK_DICT[ack_id])
        return ack_id

        # # Check if the third byte (index 2) is 0x83
        # if ack_id == "83":
        #     return True  # ACK
        # else:
        #     return False  # Not ACK

    def assert_execution(self):
        ack_id = self.read_ack()
        if ack_id != "83":
            raise Exception("Command has not been executed")
        # assert ack_id == "83", "Command has not been executed"

    def exec_cmd(
        self,
        cmd_tag,
        data_bytes,
        has_response=True,
        hardcoded_len=None
    ):
        # data_bytes = ["00"]
        # ??
        # 0xD1 0x00 0x00 0xD1
        # D1 00 D1
        # Command to send, as a byte array (example: [0x01, 0x02, 0x03])
        # cmd = bytes([tag_byte, 0x00, tag_byte]) ??
        cmd = make_cmd(cmd_tag, data_bytes, hardcoded_len=hardcoded_len)
        # cmd = bytearray([tag_byte, 0x00, tag_byte])
        # self.read_ack()

        # Write the data to the device
        self.write_data_to_device(cmd)
        # get ack
        self.assert_execution()
        # ack = self.read_ack()
        # assert ack
        # get response
        if has_response:
            response = decode_bytes(
                self.read_data_buffer(RESPONSE_LENGTH_DICT[cmd_tag])
            )
        else:
            response = None
        return response


    def get_device_id(self):
        # cmd_tag = "D1"
        # # tag_byte = to_byte(cmd_tag)
        # data_bytes = ["00"]
        # # ??
        # # 0xD1 0x00 0x00 0xD1
        # # D1 00 D1
        # # Command to send, as a byte array (example: [0x01, 0x02, 0x03])
        # # cmd = bytes([tag_byte, 0x00, tag_byte]) ??
        # cmd = make_cmd(cmd_tag, data_bytes)
        # # cmd = bytearray([tag_byte, 0x00, tag_byte])
        # # self.read_ack()

        # # Write the data to the device
        # self.write_data_to_device(cmd)
        # # get ack
        # self.assert_execution()
        # # ack = self.read_ack()
        # # assert ack
        # # get response
        # device_id = decode_bytes(
        #     self.read_data_buffer(RESPONSE_LENGTH_DICT[cmd_tag])
        # )
        # return device_id
        return self.exec_cmd("D1", ["00"])

    def get_firmware_id(self):
        return self.exec_cmd("D2", ["00"])

    # get freqeuncy list: Syntax get: [CT] 01 04 [CT] - response is split in 252 byte packages

    def get_device_id(self):

        self.exec_cmd("D1", ["00"])

    def reset_setup(self):
        '''
        This option resets the currently configured setup
        and an empty setup is initialized.
        '''

        self.exec_cmd(SET_SETUP_TAG, ["01"], has_response=False)

    def set_setup(self, config):

        def parse_setup_config(setup_config):
            freq_list_params = get_with_assert(
                config,
                [FREQ_LIST_KEY],
                cfg_not_found(FREQ_LIST_KEY, config)
            )

            amplitude = get_with_assert(
                config,
                [AMPLITUDE_KEY],
                cfg_not_found(AMPLITUDE_KEY, config)
            )

            precision = get_with_assert(
                config,
                [PRECISION_KEY],
                cfg_not_found(PRECISION_KEY, config)
            )

            return freq_list_params, amplitude, precision

        def cfg_not_found(cfg_key, config):
            return (
                f"Key \"{cfg_key}\" not found in "
                f"the given config:\n{pretty_json(config)}"
            )

        def set_freq_list(
            freq_list_params,
            precision,
            amplitude
        ):

            def parse_freq_list(freq_list_params):

                start_freq = get_with_assert(
                    freq_list_params,
                    [START_FREQ_KEY],
                    cfg_not_found(START_FREQ_KEY, freq_list_params)
                )

                end_freq = get_with_assert(
                    freq_list_params,
                    [END_FREQ_KEY],
                    cfg_not_found(END_FREQ_KEY, freq_list_params)
                )

                freq_count = get_with_assert(
                    freq_list_params,
                    [FREQ_COUNT_KEY],
                    cfg_not_found(FREQ_COUNT_KEY, freq_list_params)
                )

                freq_scale = get_with_assert(
                    freq_list_params,
                    [FREQ_SCALE_KEY],
                    cfg_not_found(FREQ_SCALE_KEY, freq_list_params)
                )

                return start_freq, end_freq, freq_count, freq_scale

            start_freq, stop_freq, count, scale = parse_freq_list(freq_list_params)

            data_bytes = (
                    ["03"]
                +
                    float_as_bytes(start_freq)
                +
                    float_as_bytes(stop_freq)
                +
                    float_as_bytes(count)
                # +
                #     float_as_bytes(scale)
                +
                    [str(scale)]
                +
                    float_as_bytes(precision)
                +
                    float_as_bytes(amplitude)
            )
            self.exec_cmd(
                SET_SETUP_TAG,
                data_bytes,
                has_response=False,
                hardcoded_len=HARDCODED_LENS[SET_SETUP_TAG]
            )

        print(
            f"Setting up the device with the following configuration:"
            f"\n{pretty_json(config)}"
        )

        freq_list_params, amplitude, precision = parse_setup_config(config)

        if freq_list_params is not None:
            set_freq_list(freq_list_params, precision, amplitude)

    def read_data_buffer(self, bytes_to_read):
        buffer = bytearray()  # Create a buffer to store the incoming data

        for _ in range(bytes_to_read):
            # Read one byte at a time
            ch = self.connection.read(1)  # This blocks until a byte is available
            if ch:  # If a byte is read, append it to the buffer
                buffer.append(ord(ch))

        return buffer

    def write_data_to_device(self, cmd):
        # Print the command bytes in hexadecimal format
        # for byte in cmd:
        #     print(f"{byte:02X} ", end="")
        # print()  # Newline after printing all bytes
        print("Writing this cmd as bytes to device", cmd)
        print("Its decoded version", decode_bytes(cmd))

        # Write the bytes to the serial port
        self.connection.write(cmd)

    def _get_connection(self):

        def get_com_number():
            return 5 # TODO: Implement logic to get COM number

        try:
            com_number = get_com_number()
            # Open serial port
            ser = serial.Serial(f'COM{com_number}', baudrate=9600, timeout=1)

            if ser.is_open:
                print("Serial port opened successfully")
            else:
                print("Failed to open serial port")
                # sys.exit(0)

        except serial.SerialException as e:
            print(f"Error: {e}")
            sys.exit(0)
            # with open("\\\\.\\COM6", "r") as f:
        return ser


# def get_device_id():
#     # ??
#     # 0xD1 0x00 0x00 0xD1
#     # D1 00 D1
#     # Command to send, as a byte array (example: [0x01, 0x02, 0x03])
#     cmd = bytes([0x01, 0x02, 0x03])

#     # Write the data to the device
#     write_data_to_device(ser, cmd)


# def write_data_to_device(ser, cmd):
#     # Print the command bytes in hexadecimal format
#     for byte in cmd:
#         print(f"{byte:02X} ", end="")
#     print()  # Newline after printing all bytes

#     # Write the bytes to the serial port
#     ser.write(cmd)


# def get_connection():
#     try:
#         com_number = get_com_number()
#         # Open serial port
#         ser = serial.Serial(f'COM{com_number}', baudrate=9600, timeout=1)

#         if ser.is_open:
#             print("Serial port opened successfully")
#         else:
#             print("Failed to open serial port")
#             # sys.exit(0)

#     except serial.SerialException as e:
#         print(f"Error: {e}")
#         sys.exit(0)
#         # with open("\\\\.\\COM6", "r") as f:
#     return ser


def main():
    device = Device()
    # device_id = device.get_device_id()
    # print("Device ID: ", device_id)
    # device_firmware_id = device.get_firmware_id()
    # print("Firmware ID: ", device_firmware_id)
    device.reset_setup()
    device.set_setup(DUMMY_CONFIG)


if __name__ == "__main__":
    main()

#get device id
# get ack



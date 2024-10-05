import serial
# pip install pyserial
import sys
import struct
from deepdiff import DeepDiff, model as dd_model
# pip install deepdiff
import json


DEFAULT_INDENT_IN_JSON = 2
MAX_COUNT_IN_ONE_FRAME = 62

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
SET_FE_TAG = "B0"
SET_SETUP_TAG = "B6"
GET_SETUP_TAG = "B7"


RESPONSE_LENGTH_DICT = {
    "Ack": 4,
    "D1": 7
}


HARDCODED_LENS = {
    SET_SETUP_TAG: 16 # they require 16 in manual, even though there are at least 21 bytes by default: 5 floats + 1 bool
}
RESULT_FRAME_SIZE = 14


# config consts
SETUP_KEY = "setup"
FREQ_LIST_KEY = "freq_list_params"
AMPLITUDE_KEY = "amplitude"
PRECISION_KEY = "precision"
START_FREQ_KEY = "start_freq"
END_FREQ_KEY = "end_freq"
FREQ_COUNT_KEY = "freq_count"
FREQ_SCALE_KEY = "freq_scale"
FE_KEY = "frontend_settings"
MES_MODE_KEY = "measurement_mode"
MES_CHNL_KEY = "measurement_channel"
CURR_RANGE_KEY = "current_range"
VOL_RANGE_KEY = "voltage_range"
DUMMY_CONFIG = {
    SETUP_KEY: {
        FREQ_LIST_KEY: {
            "start_freq": 100,
            "end_freq": 1000,
            "freq_count": 80,
            "freq_scale": "Lin"
        },
        PRECISION_KEY: "medium",
        AMPLITUDE_KEY: 0.25, # V
    },
    FE_KEY:
        {
            MES_MODE_KEY: "2PT",
            MES_CHNL_KEY: "BNC",
            CURR_RANGE_KEY: "auto",
            VOL_RANGE_KEY: "1"
        }
}


PRECISION_DICT = {
    # "low": "00",
    # "medium": "01",
    # "high": "02",
    # "very_high": "03"
    "low": 0,
    "medium": 1,
    "high": 2,
    "very_high": 3
}


# TODO(Alex | 05.10.2024): add option for excitation type
EXCITATION_DICT = {
    "voltage": "01",
    "current": "02"
}


# writeDataToDevice(handle, cmd, numberOfBytes);
#     readAck(handle);
# printf("\n");
# cmd[3] = 0x02;
# cmd[4] = 0x01;
# cmd[5] = 0x01;
# writeDataToDevice(handle, cmd, numberOfBytes);
# readAck(handle);
# printf("\n");

# $/ /$ mode $=4 \mathrm{Pt}$ measurement
# //add channel: Channel 1 (BNC),
# //1000hm Range,

FREQ_SCALE_DICT = {
    "Lin": "00",
    "Log": "01"
}


MEASUREMENT_MODE_DICT = {
    "2PT": "01",  # 2 point configuration
    "3PT": "03",  # 3 point configuration
    "4PT": "02",  # 4 point configuration
}


MEASUREMENT_CHANNEL_DICT = {
    "BNC": "01",  # BNC Port (ISX-3mini: Port 1)
    "EXT1": "02",  # ExtensionPort
    "EXT2": "03",  # ExtensionPort2 (ISX-3mini: Port 2, ISX-3: optional, InternalMux)
}


CURRENT_RANGE_SETTINGS_DICT = {
    "auto": "00",  # autoranging
    "100": "01",  # ± 10 mA
    "10k": "02",  # ± 100 μA
    "1M": "04",  # ± 1 μA
    "100M": "06"  # ± 10 nA
}


VOLTAGE_RANGE_SETTINGS_DICT = {
    "auto": "00",  # autoranging
    "1": "01",  # ± 1V (default)
    "0.09": "02",  # ± 0.09V
}


def to_byte(hex_str):
    # hex_str = "D1"
    byte_value = int(hex_str, 16)
    return byte_value


def bytes_list_to_bytes(bytes_list):
    return [to_byte(byte) for byte in bytes_list]


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
    all_bytes = (
            [
                cmd_tag_byte,
                to_byte(str(data_len))
            ]
        +
            [to_byte(byte) for byte in data_bytes]
        +
            [cmd_tag_byte]
    )
    return bytes(all_bytes)


def float_as_byte_list(float_val):
    # bytes_as_list = []
    packed_value = struct.pack('>f', float_val)  # '>f' is for big-endian float
    # for byte in packed_value:
    #     bytes_as_list.append(byte)
    return decode_bytes(packed_value)
    # return bytes_as_list


# def read_ui_from_byte_list(byte_list):
#     as_bytes = bytes(byte_list)
#     n, r = divmod(len(as_bytes), struct.calcsize('I'))
#     assert r == 0, "Data length not a multiple of int size"
#     unsigned_data = struct.unpack('I' * n, as_bytes)[0]
#     return unsigned_data


def read_from_byte_list(byte_list, fmt):
    as_bytes = bytes(byte_list)
    return struct.unpack(fmt, as_bytes)[0]


def read_uchar_from_byte_list(byte_list):
    return read_from_byte_list(byte_list, 'B')


def read_ushort_from_byte_list(byte_list):
    return read_from_byte_list(byte_list, 'H')


def read_float_from_byte_list(byte_list):
    # return struct.unpack('>f', bytes(byte_list))[0]
    return read_from_byte_list(byte_list, '>f')


def cfg_not_found(cfg_key, config):
    return (
        f"Key \"{cfg_key}\" not found in "
        f"the given config:\n{pretty_json(config)}"
    )


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
        self.connection = self._get_connection() # uncomment when testing on real device
        self.freq_count = None

    def close(self):
        self.connection.close()

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

        if ack_id is None:
            raise Exception("No acknowledgement received")

        ack = ACK_DICT[ack_id]

        if ack_id not in ["81", "83"]:
            raise Exception(f"Command has not been executed, reason: {ack}")
        # assert ack_id == "83", "Command has not been executed"

    def exec_cmd(
        self,
        cmd_tag,
        data_bytes,
        has_response=False,
        hardcoded_len=None
    ):
        # data_bytes = ["00"]
        # 0xD1 0x00 0x00 0xD1
        # D1 00 D1
        # Command to send, as a byte array (example: [0x01, 0x02, 0x03])
        # cmd = bytes([tag_byte, 0x00, tag_byte])
        cmd = make_cmd(cmd_tag, data_bytes, hardcoded_len=hardcoded_len)
        # cmd = bytearray([tag_byte, 0x00, tag_byte])
        # self.read_ack()

        # Write the data to the device
        self.write_data_to_device(cmd)
        # get ack
        # ack = self.read_ack()
        # assert ack
        # get response
        if has_response:
            response = decode_bytes(
                self.read_data_buffer(RESPONSE_LENGTH_DICT[cmd_tag])
            )
        else:
            response = None

        self.assert_execution()
        return response

    # TODO(Alex | 03.10.2024): make function below working
    def get_firmware_id(self):
        return self.exec_cmd("D2", ["00"], has_response=True)

    # get freqeuncy list: Syntax get: [CT] 01 04 [CT] - response is split in 252 byte packages

    # TODO(Alex | 03.10.2024): make function below working
    def get_device_id(self):

        self.exec_cmd("D1", [], has_response=True)

    def reset_setup(self):
        '''
        This option resets the currently configured setup
        and an empty setup is initialized.
        '''

        self.exec_cmd(SET_SETUP_TAG, ["01"])

    def set_setup(self, config):

        def parse_setup_config(setup_config):

            # setup_config = get_with_assert(
            #     config,
            #     [SETUP_KEY],
            #     cfg_not_found(SETUP_KEY, config)
            # )

            freq_list_params = get_with_assert(
                setup_config,
                [FREQ_LIST_KEY],
                cfg_not_found(FREQ_LIST_KEY, setup_config)
            )

            amplitude = get_with_assert(
                setup_config,
                [AMPLITUDE_KEY],
                cfg_not_found(AMPLITUDE_KEY, setup_config)
            )

            precision_kw = get_with_assert(
                setup_config,
                [PRECISION_KEY],
                cfg_not_found(PRECISION_KEY, setup_config)
            )

            precision = get_with_assert(
                PRECISION_DICT,
                precision_kw,
                cfg_not_found(precision_kw, PRECISION_DICT)
            )

            return freq_list_params, amplitude, precision

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

                freq_scale = get_with_assert(
                    FREQ_SCALE_DICT,
                    freq_scale,
                    f"Frequency scale \"{freq_scale}\" not supported; "
                    f"allowed values are: {list(FREQ_SCALE_DICT.keys())}"
                )

                return start_freq, end_freq, freq_count, freq_scale

            start_freq, stop_freq, count, scale = parse_freq_list(freq_list_params)

            assert count < MAX_COUNT_IN_ONE_FRAME, \
                f"Frequency count must be less than {MAX_COUNT_IN_ONE_FRAME}, " \
                f"but it is {count}"
            self.freq_count = count

            data_bytes = (
                    ["03"]
                +
                    float_as_byte_list(start_freq)
                +
                    float_as_byte_list(stop_freq)
                +
                    float_as_byte_list(count)
                # +
                #     float_as_byte_list(scale)
                +
                    [str(scale)]
                +
                    float_as_byte_list(precision)
                +
                    float_as_byte_list(amplitude)
            )
            self.exec_cmd(
                SET_SETUP_TAG,
                data_bytes,
                hardcoded_len=HARDCODED_LENS[SET_SETUP_TAG]
            )

        print(
            f"Setting up the device with the following configuration:"
            f"\n{pretty_json(config)}"
        )

        setup_config = get_with_assert(
            config,
            [SETUP_KEY],
            cfg_not_found(SETUP_KEY, config)
        )

        freq_list_params, amplitude, precision = parse_setup_config(setup_config)

        self.reset_setup() # uncomment when testing on real device
        set_freq_list(freq_list_params, precision, amplitude) # uncomment when testing on real device

    # TODO(Alex | 03.10.2024): test function below
    def set_frontend_settings(self, config):

        def clear_channel():
            self.exec_cmd(
                SET_FE_TAG,
                # ["03", "FF", "FF", "FF"],
                ["FF", "FF", "FF"],
                # hardcoded_len=3
            )

        def parse_frontend_config(fe_settings):
            mes_mode_kw = get_with_assert(
                fe_settings,
                [MES_MODE_KEY],
                cfg_not_found(MES_MODE_KEY, fe_settings)
            )
            mes_mode = get_with_assert(
                MEASUREMENT_MODE_DICT,
                mes_mode_kw,
                cfg_not_found(mes_mode_kw, MEASUREMENT_MODE_DICT)
            )
            mes_chl_kw = get_with_assert(
                fe_settings,
                [MES_CHNL_KEY],
                cfg_not_found(MES_CHNL_KEY, fe_settings)
            )
            mes_chl = get_with_assert(
                MEASUREMENT_CHANNEL_DICT,
                mes_chl_kw,
                cfg_not_found(mes_chl_kw, MEASUREMENT_CHANNEL_DICT)
            )
            curr_range_kw = get_with_assert(
                fe_settings,
                [CURR_RANGE_KEY],
                cfg_not_found(CURR_RANGE_KEY, fe_settings)
            )
            curr_range = get_with_assert(
                CURRENT_RANGE_SETTINGS_DICT,
                curr_range_kw,
                cfg_not_found(curr_range_kw, CURRENT_RANGE_SETTINGS_DICT)
            )
            vol_range_kw = get_with_assert(
                fe_settings,
                [VOL_RANGE_KEY],
                cfg_not_found(VOL_RANGE_KEY, fe_settings)
            )
            vol_range = get_with_assert(
                VOLTAGE_RANGE_SETTINGS_DICT,
                vol_range_kw,
                cfg_not_found(vol_range_kw, VOLTAGE_RANGE_SETTINGS_DICT)
            )
            return mes_mode, mes_chl, curr_range, vol_range

        clear_channel() # uncomment when testing on real device

        fe_settings = get_with_assert(
            config,
            [FE_KEY],
            cfg_not_found(FE_KEY, config)
        )

        mes_mode, mes_chl, curr_range, vol_range = parse_frontend_config(fe_settings)
        data_bytes = [mes_mode, mes_chl, curr_range]
        if vol_range is not None:
            data_bytes.append(vol_range)
            self.exec_cmd(
                SET_FE_TAG,
                data_bytes,
                # hardcoded_len=3
            )
        # if vol_range is None:
        #     self.exec_cmd(
        #         SET_FE_TAG,
        #         ["03", mes_mode, mes_chl, curr_range],
        #         has_response=False,
        #         # hardcoded_len=3
        #     )
        # else:
        #     self.exec_cmd(
        #         SET_FE_TAG,
        #         ["04", mes_mode, mes_chl, curr_range, vol_range],
        #         has_response=False,
        #         # hardcoded_len=3
        #     )

        # self.set_channel()

    # TODO(Alex | 03.10.2024): test function below
    def start_measurement(self):
        self.exec_cmd("B8", ["01", "00", "00"])

    # TODO(Alex | 03.10.2024): test function below
    def stop_measurement(self):
        self.exec_cmd("B8", ["00", "00", "00"])

    # TODO(Alex | 03.10.2024): test function below
    def read_measurement_result(self):
        """
        Format of the measurement result frame:

        If time stamp and current range are disabled (see command 0x97 and 0x98):
            [CT] 0A [ID] [Real part] [Imaginary part] [CT]
        Else if time stamp in ms is enabled (see command 0x97 and 0x98):
            [CT] 0E [ID] [Time stamp] [Real part] [Imaginary part] [CT]
        Else if time stamp in μs is enabled (see command 0x97 and 0x98)
            [CT] 0F [ID] [Time stamp] [Real part] [Imaginary part] [CT]
        Else if current range is enabled (see command 0x97 and 0x98)
            [CT] 0B [ID] [Current Range] [Real part] [Imaginary part] [CT]
        Else if time stamp and current range are enabled (see command 0x97 and 0x98)
            [CT] 0F [ID] [Time stamp] [Current Range] [Real part] [Imaginary part] [CT]
        """

        def parse_result_frame(frame):

            # [CT] 0B [ID] [Current Range] [Real part] [Imaginary part] [CT]
            frame = bytes_list_to_bytes(frame)
            # ['B8',  'B8']
            # '0B', '00', '00', '01', '49', '44', '06', '7C', 'C6', '24', '98', '41',
            # [184, 11, 0, 0, 1, 73, 68, 6, 124, 198, 36, 152, 65, 184]

            # TODO(Alex | 03.10.2024): check correctness in practice, because manual and example contradict to each other
            assert len(frame) == RESULT_FRAME_SIZE
            frame_type = frame[1]
            # ch = frame[2]
            # id_ = (frame[3] << 8) + frame[4]
            # id_ = read_ui_from_byte_list(frame[2:4])
            id_ = read_ushort_from_byte_list(frame[2:4])

            # cur_range = read_ui_from_byte_list([frame[5]])
            cur_range = read_uchar_from_byte_list([frame[5]])

            # TODO(Alex | 03.10.2024): avoid double conversions from bytes to string and back
            re = read_float_from_byte_list(frame[5:9])
            im = read_float_from_byte_list(frame[9:13])
            return cur_range, id_, re, im

        # self.freq_count = 3 # comment when testing on real device
        assert self.freq_count is not None, \
            "Called read_measurement_result before set_setup"

        for _ in range(self.freq_count):
            cur_frame = decode_bytes(self.read_data_buffer(RESULT_FRAME_SIZE))
            print("cur_frame", cur_frame) # tmp
            parsed_frame = parse_result_frame(cur_frame)
            print(parsed_frame)
        # assert RESULT_FRAME_SIZE * self.frec_count < MAX_BYTE_RESULT * 8
        # readBuffer = malloc(14);

# 4Byte Im
# //3Byte Framing, 2Byte idNumber, 4Byte RE,
# byte j;
# byte i;
# UINT8 ch;
# UINT16 id;
# UINT32 tmp32;
# float re, im;
# for(j=0; j<numberOfSpecs; j++){
# printf("Spec#%i:\n", j+1); printf("ch\tid\tre\tim\n"); for(i=0; i<frequencyCount;i++){
#             readData(handle, readBuffer, 14);
#             ch = readBuffer[2];
#             id = (readBuffer[3]<<8) + readBuffer[4];
#             tmp32 = (readBuffer[5]<<24) + (readBuffer[6]<<16) +
# (readBuffer[7]<<8) + (readBuffer[8]);
#             re = *(float*)&tmp32;
#             tmp32 = (readBuffer[9]<<24) + (readBuffer[10]<<16) +
# (readBuffer[11]<<8) + (readBuffer[12]);
#             im = *(float*)&tmp32;
#             printf("%i\t%i\t%f\t%f\n", ch, id, re, im);
# }
#         printf("\n");
#     }

    # TODO(Alex | 03.10.2024): test function below
    def run_measurement(self):
        self.start_measurement() # uncomment when testing on real device
        try:
            result = self.read_measurement_result()
        # result = self.read_measurement_result()
        finally:
            self.stop_measurement() # uncomment when testing on real device
        return result

    def read_data_buffer(self, bytes_to_read):
        buffer = bytearray()  # Create a buffer to store the incoming data

        for _ in range(bytes_to_read):
            # Read one byte at a time
            ch = self.connection.read(1)  # This blocks until a byte is available
            if ch:  # If a byte is read, append it to the buffer
                buffer.append(ord(ch))

        return buffer

    # TODO(Alex | 05.10.2024): test function below
    def get_freq_list(self):

        def parse_bytes_list(bytes_list, group_by, parse_func):
            return [
                parse_func[i:i + group_by]
                    for i in range(0, len(bytes_list), group_by)
            ]

        # [CT] 01 04 [CT]
        self.exec_cmd(GET_SETUP_TAG, ["04"])

        # TODO(Alex | 05.10.2024): avoid unneeded decoding from bytes to string and back
        first_two_bytes = self.read_data_buffer(2)
        assert decode_bytes(first_two_bytes)[0] == GET_SETUP_TAG
        length = read_uchar_from_byte_list([first_two_bytes[1]])
        rest_bytes = self.read_data_buffer(length + 1)

        decoded_rest_bytes = decode_bytes(rest_bytes)
        assert decoded_rest_bytes[-1] == GET_SETUP_TAG
        freq_list = parse_bytes_list(
            decoded_rest_bytes,
            group_by=4,
            parse_func=read_float_from_byte_list
        )
        return freq_list
        # decoded_buffer = decode_bytes(read_buffer)
        # assert


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

    # device.reset_setup()

    # TODO(Alex | 03.10.2024): read config from given yaml path
    device.set_setup(DUMMY_CONFIG)
    device.set_frontend_settings(DUMMY_CONFIG) # uncomment when testing on real device
    freq_list = device.get_freq_list()
    print("Freq list: ", freq_list)
    result = device.run_measurement()

    # TODO(Alex | 03.10.2024): save result in output csv specified in args
    pass # saving code

    # debug_result_frame = ['B8', '0B', '00', '00', '01', '49', '44', '06', '7C', 'C6', '24', '98', '41', 'B8']
    # result = parse_result_frame(debug_result_frame)
    print("Result: ", result)
    device.close()


# def parse_result_frame(frame):

#     # [CT] 0B [ID] [Current Range] [Real part] [Imaginary part] [CT]
#     frame = bytes_list_to_bytes(frame)
#     # ['B8',  'B8']
#     # '0B', '00', '00', '01', '49', '44', '06', '7C', 'C6', '24', '98', '41',
#     # [184, 11, 0, 0, 1, 73, 68, 6, 124, 198, 36, 152, 65, 184]

#     # TODO(Alex | 03.10.2024): check correctness in practice, because manual and example contradict to each other
#     assert len(frame) == RESULT_FRAME_SIZE
#     frame_type = frame[1]
#     # ch = frame[2]
#     # id_ = (frame[3] << 8) + frame[4]
#     # id_ = read_ui_from_byte_list(frame[2:4])
#     id_ = read_ushort_from_byte_list(frame[2:4])

#     # cur_range = read_ui_from_byte_list([frame[5]])
#     cur_range = read_uchar_from_byte_list([frame[5]])

#     # TODO(Alex | 03.10.2024): avoid double conversions from bytes to string and back
#     re = read_float_from_byte_list(frame[5:9])
#     im = read_float_from_byte_list(frame[9:13])
#     return cur_range, id_, re, im



if __name__ == "__main__":
    main()

import serial
# pip install pyserial
import sys


# def get_com_number():
#     return 5 # TODO: Implement logic to get COM number


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


def decode_bytes(data):
    res = []
    for byte in data:
        res.append(f"{byte:02X}")
    return res


class Device:

    def __init__(self):
        self.connection = self._get_connection()

    def read_ack(self, verbose=True):
        # Read 4 bytes from the serial port
        read_buffer = self.read_data_buffer(4)

        # Print the ACK frame in hexadecimal format
        print("ACK-Frame: ", end="")
        # for byte in read_buffer:
        #     print(f"{byte:02X} ", end="")
        # print()
        # print(decode_bytes(read_buffer))
        decoded_buffer = decode_bytes(read_buffer)
        # print()
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
        assert ack_id == "83", "Command has not been executed"

    def get_device_id(self):
        # ??
        # 0xD1 0x00 0x00 0xD1
        # D1 00 D1
        # Command to send, as a byte array (example: [0x01, 0x02, 0x03])
        cmd = bytes([0x01, 0x02, 0x03])

        # Write the data to the device
        self.write_data_to_device(cmd)
        # get ack
        self.assert_execution()
        # ack = self.read_ack()
        # assert ack
        # get response
        device_id = decode_bytes(self.read_data_buffer(4))
        return device_id

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
        for byte in cmd:
            print(f"{byte:02X} ", end="")
        print()  # Newline after printing all bytes

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
    device_id = device.get_device_id()
    print("Device ID: ", device_id)


if __name__ == "__main__":
    main()

#get device id
# get ack

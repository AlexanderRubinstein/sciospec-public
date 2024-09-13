import serial
import sys


def get_com_number():
    return 5 # TODO: Implement logic to get COM numbe)


def get_connection():
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


def main():
    connection = get_connection()


if __name__ == "__main__":
    main()

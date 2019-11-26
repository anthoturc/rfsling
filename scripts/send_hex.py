#!/bin/python3
"""
When run in main, the script will record and send over the raw hex and file extension
of a previously specified file to a connected Arduino for RF file transfers.

Params: 
    sys.argv[1]:
        Absolute path of Serial port

    sys.argv[2]: 
        Baudrate of Serial port

    sys.argv[3]: 
        Filepath of file to send

    sys.argv[4]: 
        Plain raw-hex string of file to send

Sends:
    file_extension_bytes:
        File extension of our sent file
    
    raw_hex_bytes:
        Raw-hex of our file
    
"""
import sys
import serial
import time

    
# We are going to store the configured integers in our Arduino in a Union, 
# by sending over our individal bytes and storing them in memory.  
# Thus, we need to consider the endianess of our Arduino
ENDIANESS = 'little'

# size of char array in union representing extension on Arduino
EXTENSION_LEN = 10

# Max amount of time to wait duing our handshakeTX before we throw and exception
MAX_HANDSHAKE_SEC = 10

# used to communicate state changes between the Arduino and Computer
HANDSHAKE_CHAR = '\t'

# byte to send to Arduino to signal that we are about to send a file
HANDSHAKE_CHAR_BYTE = 9

# tell Arduino to switch to transmit state
HANDSHAKE_BYTE = bytearray()
HANDSHAKE_BYTE.extend([HANDSHAKE_CHAR_BYTE])

# Max bytes to send over to the Arduino at one time. We send 224 bytes because it is
# a multiple of 32, the size of our our FIFO buffer on the nRF24L01+ chip, and it still
# fits within our serial's buffer, which has a capacity of 224 hex chars.
MAX_HEX_CHUNK_BYTES = 224

# used to debug communication
DEBUG = 1


def handshakeTX(ser):
    """
    Sends to the Arduino HANDSHAKE_BYTE, telling it we are about to send over data.
    Then, we wait for a confimation from Arduino that it is ready via HANDSHAKE_CHAR
    at which point we break, signifying a successful handshakeTX.  This funciton relies
    on handshakeTX function included in the serial_io class on the Arduino's side of 
    communication.

    We throw an error if handshakeTX takes more than MAX_HANDSHAKE_SEC

    Params:
        ser:
            Our initiallized pyserial serial port

    Outputs:
        None
    """
    ser.write(HANDSHAKE_BYTE)
    config_string = ""

    start_time = time.time()
    # time.sleep(1)


   # We need two while loops because we need to remain in our
   # hanshake state until the Arduino sends over data, but that
   # may not happen instantly.  We also want to break out of
   # the innermost loop the second that we have the confirmation
   # of our handshakeTX from the Arduino's side
    while config_string != HANDSHAKE_CHAR:
        while config_string != HANDSHAKE_CHAR and ser.in_waiting:
            config_string = ser.read(1).decode("utf-8")            
            if (time.time() - start_time) > MAX_HANDSHAKE_SEC:
                raise Exception('Handshake time limit of {0} sec exceeded'.format(MAX_HANDSHAKE_SEC))
        
        if (time.time() - start_time) > MAX_HANDSHAKE_SEC:
            raise Exception('Handshake time limit of {0} sec exceeded'.format(MAX_HANDSHAKE_SEC))
        

def chunkGenerator(data):
    """
    Generator to split data into chunks to be sent over serial.  We cannot fit
    all the data on the Arduino at once, which is why we have to split it up
    like this.  Data is read over serial on the Arduino's side and fills the
    file_chunk buffer via the setFromSerial function (both within serial_io).

    Params:
        data:
            string: hex data to be sent to Arduino
    
    Yields:
        string: next chunk of data with size <= MAX_HEX_CHUNK_BYTES
    """
    i = -MAX_HEX_CHUNK_BYTES
    j = 0
    for _ in range(len(data) // MAX_HEX_CHUNK_BYTES):
        i += MAX_HEX_CHUNK_BYTES
        j += MAX_HEX_CHUNK_BYTES
        yield data[i:j]
    yield data[i + MAX_HEX_CHUNK_BYTES:len(data)]


def printData(ser, end_char='\n'):
    """
    Prints data sent to the computer from the Arduino over seral.
    Transmissions are seperated by the HANDSHAKE_CHAR.

    Params:
        ser:
            Our initiallized pyserial serial port
        end_char:
            String: End line character after print statement


    Outputs:
        None
    """
    data = ""
    curr = ""
    # time.sleep(1) # wait for the Arduino
    while curr !=  HANDSHAKE_CHAR:
        while curr !=  HANDSHAKE_CHAR and ser.in_waiting:
            data += curr
            curr = ser.read(1).decode("utf-8")
        
    print(data, end=end_char)
 

if __name__ == "__main__":

    # TODO: send over size of hex as checksum if have time
    raw_hex_bytes = bytearray()  # our file to be sent
    file_extension_bytes = bytearray()  # file extension being sent over, used for decoding
    file_extension = []

    # configuring our serial
    ser = serial.Serial()
    ser.port = sys.argv[1]
    ser.baudrate = int(sys.argv[2])
    ser.open()
    
    # Translation:
    #   1) .split('.')[1] means take everything after the . of our file path
    #   2) ord converts characters to bytes
    file_extension.extend(map(ord, sys.argv[3].split('.')[1]))

    # Fill in unused chars with spaces (as bytes), ensuring that our file extension to
    # be sent over has EXTENSION_LEN bytes total
    space_pad = [ord(" ") for _ in range(EXTENSION_LEN - len(file_extension))]
    file_extension.extend(space_pad)

    # populating our byte arrays
    file_extension_bytes.extend(file_extension)
    raw_hex_bytes.extend(map(ord, sys.argv[4]))
    
    # initialte communication with the Arduino
    handshakeTX(ser)

    # send over the extension and its contents one byte at a time
    ser.write(file_extension_bytes)   
    
    # precaution to make sure we are only sending file data over Serial
    chunks = chunkGenerator(raw_hex_bytes)
    for c in chunks:
 
        # Shake between every transaction to make sure that the Arduino
        # is ready for our next chunk of data
        handshakeTX(ser)
        # time.sleep(1)
        total = len(c) 
        total = total.to_bytes(1, byteorder=ENDIANESS)
        ser.write(total)
        # time.sleep(1)
        ser.write(c)
        
        if DEBUG:
            printData(ser, '') #output our received file
    
    ser.close()

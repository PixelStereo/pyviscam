#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import glob
import serial
import argparse
from time import sleep

parser = argparse.ArgumentParser()
parser.add_argument("-p","--port",type=str, help="port to send visca commands")
parser.add_argument("-l", "--list", help="list available serial ports",
                    action="store_true")
parser.add_argument("-v", "--verbose", help="increase output verbosity",
                    action="store_true")
args = parser.parse_args()


def ports_list():
    """Lists serial ports
    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports
    """
    if sys.platform.startswith('win'):
        ports = ['COM' + str(i + 1) for i in range(256)]

    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this is to exclude your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')

    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')

    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def test(port):
    global viscam
    #create a serial object
    viscam  = serial.Serial()
    #fix correct baudrate
    viscam.baudrate = 9600
    viscam.port = port
    print viscam
    #open the serial port
    viscam.open()
    print viscam
    #close the serial port
    viscam.close()
    print viscam

if args.verbose:
    print "verbosity turned on"
if not args.port:
    print ports_list()
else:
    test(args.port)
    ########################### main loop ##################################    
    try:
        while True:
            sleep(0.1)  
    except KeyboardInterrupt:
        #close the serial port if one is opened
        if viscam.isOpen():
            print "closing"
            viscam.close()



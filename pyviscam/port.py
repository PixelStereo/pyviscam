#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import glob
import serial
try:
    # python 2
    from thread import allocate_lock
except:
    # python 3
    from _thread import allocate_lock

debug = 1

class Serial(object):
    def __init__(self):
        self.mutex = allocate_lock()
        self.port = None

    def listports(self):
        """ Lists serial port names
            :exit 1 (error code 11)
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            if debug:
                print('ERROR 11 - Unsupported platform')
            sys.exit(1)
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

    def open(self, portname):
        self.mutex.acquire()
        self.portname = portname
        if (self.port == None):
            try:
                self.port = serial.Serial(self.portname, 9600, timeout=None, stopbits=1, \
                						  bytesize=8, rtscts=False, dsrdtr=False)
                self.port.flushInput()
                self.mutex.release()
                return True
            except:
                self.port = None
                self.mutex.release()
                return False

    def recv_packet(self, extra_title=None):
        if self.port:
            # read up to 16 bytes until 0xff
            packet=''
            count=0
            while count<16:
                s=self.port.read(1)
                if s:
                    byte = ord(s)
                    count+=1
                    packet=packet+chr(byte)
                else:
                    print("ERROR: Timeout waiting for reply")
                    break
                if byte==0xff:
                    break
            return packet
        else:
            return False

    def _write_packet(self, packet):
        if self.port:
            if not self.port.isOpen():
                if debug:
                    print("ERROR 14 - no serial port cannot be opened")
                return False
            # lets see if a completion message or someting
            # else waits in the buffer. If yes dump it.
            elif self.port.inWaiting():
                self.recv_packet("ignored")
            self.port.write(packet)
            return True
        else:
            if debug:
                print("ERROR 15 - no serial port")
            return False

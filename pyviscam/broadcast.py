#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
# imports from pyviscam lib
from port import Serial
from camera import Camera
from convert import hex_to_int
from pan_tilt_utils import degree_to_visca, visca_to_degree

debug = 1


class Viscam(object):
    """
    Viscam is a chain of Visca camera
    Viscam is a broadcast command relative to a Serial port
    Viscam initialisation call _cmd_address_set and _if_clear
    """
    def __init__(self, port=None):
        super(Viscam, self).__init__()
        # create a serial port communication
        serial = Serial()
        # make it available from everywhere
        self.serial = serial
        self.port = port
        if port:
            self.reset(port)
        else:
            # please make a simulation in case you don't have
            # a serial port with a visca camera available
            if debug:
                print("ERROR 34 - no serial port selected")

    def get_instances(self):
        return self.viscams

    def reset(self, port):
        """
        Reset the visca communication
        Notice that it release and re-create Visca objects
        """
        # if there is a port, open it
        self.serial.open(port)
        # Give me the list of available cameras
        self.viscams = self._cmd_adress_set()
        # Clear the buffers from any packet stuck anywhere
        self._if_clear()

    def _send_broadcast(self, data):
        """
        shortcut to broadcast commands
        """
        return self._send_packet(data, -1)

    def _cmd_adress_set(self):
        """
        starts enumerating devices, sends the first adress to use on the bus
        reply is the same packet with the next free adress to use

        Create Visca Instances for each device found on the serial bus
        """
        #address of first device. should be 1:
        first=1

        reply = self._send_broadcast('\x30'+chr(first)) # set address
        if isinstance(reply,type(None)):
            if debug:
                print("ERROR 35 - No reply from the bus")
            sys.exit(1)
        if len(reply)!=4 or reply[-1:]!='\xff':
            if debug:
                print("ERROR 36 - enumerating devices")
            sys.exit(1)
        if reply[0] != '\x88':
            if debug:
                print("ERROR 37 - expecting broadcast answer to an enumeration request")
            sys.exit(1)
        address = ord(reply[2])

        devices_count = address - first
        if devices_count == 0:
            if debug:
                print('ERROR 38 - unexpected answer : someone reply, but no Camera found')
            sys.exit(1)
        else:
            if debug:
                print("found %i devices on the bus" % devices_count)
            device = 1
            viscams = []
            while device <= devices_count:
                device = device + 1
                cam = Camera(self)
                viscams.append(cam)
                # Turn off digital zoom aka zoom_digital
                cam.zoom_digital = False
                # Turn off datascreen display
                cam.menu_off()
                cam.info_display = False
            return viscams

    def _if_clear(self):
        """
        clear the interfaces on the bys
        """
        # interface clear all
        reply = self._send_broadcast('\x01\x00\x01') 
        if not reply[1:] == '\x01\x00\x01\xff':
            print("ERROR 39 - when clearing interfaces on the bus!")
            sys.exit(1)
        if debug:
            print("all interfaces clear")
        return reply

    def _send_packet(self, data, recipient=1):
        """
        according to the documentation:

        |------packet (3-16 bytes)---------|

         header     message      terminator
         (1 byte)  (1-14 bytes)  (1 byte)

        | X | X . . . . .  . . . . . X | X |

        header:                  terminator:
        1 s2 s1 s0 0 r2 r1 r0     0xff

        with r,s = recipient, sender msb first

        for broadcast the header is 0x88!

        we use -1 as recipient to send a broadcast!
        """
        # we are the controller with id=0
        sender = 0
        if recipient==-1:
            #broadcast:
            rbits=0x8
        else:
            # the recipient (address = 3 bits)
            rbits=recipient & 0b111

        sbits=(sender & 0b111)<<4
        header=0b10000000 | sbits | rbits
        terminator=0xff
        packet = chr(header)+data+chr(terminator)
        self.serial.mutex.acquire()
        self.serial._write_packet(packet)
        reply = self.serial.recv_packet()
        if reply:
            if reply[-1:] != '\xff':
                if debug:
                    print("received packet not terminated correctly: %s" % reply.encode('hex'))
                reply=None
            self.serial.mutex.release()
            return reply
        else:
            return None

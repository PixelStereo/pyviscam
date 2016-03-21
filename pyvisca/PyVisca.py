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

from pan_tilt_utils import degree_to_visca, visca_to_degree
# import constants
from pyvisca import shutter_val, iris_val, expo_compensation_val, \
					gain_val, gain_limit_val, video_val

debug = 1

class Serial(object):
    def __init__(self):
        self.mutex = allocate_lock()
        self.port = None

    def listports(self):
        """ Lists serial port names

            :raises EnvironmentError:
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

    def open(self, portname):
        self.mutex.acquire()
        self.portname=portname
        if (self.port == None):
            try:
                self.port = serial.Serial(self.portname, 9600, timeout=2, stopbits=1, \
                						  bytesize=8, rtscts=False, dsrdtr=False)
                self.port.flushInput()
            except Exception as e:
                pass
                #raise e
                self.port = None
        self.mutex.release()    

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
        print('no reply from serial because there is no connexion')

    def _write_packet(self,packet):
        if self.port:
            if not self.port.isOpen():
                pass
                #sys.exit(1)

            # lets see if a completion message or someting
            # else waits in the buffer. If yes dump it.
            if self.port.inWaiting():
                self.recv_packet("ignored")

            self.port.write(packet)
            #self.dump(packet,"sent")
        else:
            print("message hasn't be send because no serial port is open")


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
			print("please make a simulation in case you don't have \
				  a serial port with a visca camera available")

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
		# shortcut to broadcast commands
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

		if not reply or type(reply) == None:
			if debug:
				print("No reply from the bus.")
			sys.exit(1)
		if len(reply)!=4 or reply[-1:]!='\xff':
			if debug:
				print("ERROR enumerating devices")
			sys.exit(1)
		if reply[0] != '\x88':
			if debug:
				print("ERROR: expecting broadcast answer to an enumeration request")
			sys.exit(1)
		address = ord(reply[2])

		d=address-first
		if d==0:
			if debug:
				print('unexpected ERROR, someone reply, but no Camera found')
			sys.exit(1)
		else:
			print("found %i devices on the bus" % d)
			z = 1
			viscams = []
			while z <= d:
				z = z + 1
	        	v = Visca(self.serial)
	        	viscams.append(v)
	        	# Turn off digital zoom aka zoom_digital
	        	v.zoom_digital = False
	        	# Turn off datascreen display
	        	v.menu_off()
	        	v.info_display = False
			return viscams

	def _if_clear(self):
		"""
		clear the interfaces on the bys
		"""
		# interface clear all
		reply = self._send_broadcast('\x01\x00\x01') 
		if not reply[1:] == '\x01\x00\x01\xff':
			print("ERROR clearing all interfaces on the bus!")
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


class Visca(object):
	"""create a visca device object"""
	def __init__(self, serial=None):
		"""the constructor"""
		self.serial = serial
		self.pan_speedy = 0x01
		self.tilt_speedy = 0x01
		print("CREATING A VISCA INSTANCE")

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
		if recipient == -1:
			# broadcast
			rbits = 0x8
		else:
			# the recipient (address = 3 bits)
			rbits = recipient & 0b111

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

	def _i2v(self,value):
		"""
		return word as dword in visca format
		packets are not allowed to be 0xff
		so for numbers the first nibble is 0000
		and 0xfd gets encoded into 0x0f 0x0xd
		"""
		if type(value) == unicode:
			value = int(value)
		ms = (value &  0b1111111100000000) >> 8
		ls = (value &  0b0000000011111111)
		p=(ms&0b11110000)>>4
		r=(ls&0b11110000)>>4
		q=ms&0b1111
		s=ls&0b1111
		return chr(p)+chr(q)+chr(r)+chr(s)

	def _cmd_cam_alt(self, subcmd):
		"""
		shortcut to send command with alternative prefix
		"""
		prefix = '\x01\x06'
		self._cmd_cam(subcmd, prefix)

	def _cmd_cam(self, subcmd, prefix='\x01\x04'):
		packet = prefix + subcmd
		reply = self._send_packet(packet)
		if reply == '\x90'+'\x41'+'\xFF':
			if debug == 4:
				print('-----------ACK 1-------------------')
			reply = self.serial.recv_packet()
			if reply == '\x90'+'\x51'+'\xFF':
				if debug == 4:
					print('--------COMPLETION 1---------------')
				return True
		elif reply == '\x90'+'\x42'+'\xFF':
			if debug == 4:
				print('-----------ACK 2-------------------')
			reply = self.serial.recv_packet()
			if reply == '\x90'+'\x52'+'\xFF':
				if debug == 4:
					print('--------COMPLETION 2---------------')
				return True
		elif reply == '\x90'+'\x60'+'\x02'+'\xFF':
			if debug:
				print('--------Syntax Error------------')
			return False
		elif reply == '\x90'+'\x61'+'\x41'+'\xFF':
			if debug:
				print('-----------ERROR 1------------------')
			return False
		elif reply == '\x90'+'\x62'+'\x41'+'\xFF':
			if debug:
				print('-----------ERROR 2------------------')
			return False
		
	def _come_back(self,query):
		""" Send a query and wait for (ack + completion + answer)
			Accepts a visca query (hexadeciaml)
			Return a visca answer if ack and completion (hexadeciaml)"""
		# send the query and wait for feedback
		reply = self._send_packet(query)
		#reply = reply.encode('hex')
		if reply == '\x90'+'\x60'+'\x03'+'\xFF':
			if debug:
				print('-------- FULL BUFFER ---------------')
			self._come_back(query)
		elif reply.startswith('\x90'+'\x50'):
			if debug == 4:
				print('-------- QUERY COMPLETION ---------------')
			return reply
		elif reply == '\x90'+'\x60'+'\x02'+'\xFF':
			if debug:
				print('-------- QUERY SYNTAX ERROR ---------------')
			return

	def _query(self, function=None):
		"""
		Query method needs a parameter as argument
			:Return False if no parameter is provided
			:Return False if parameter provided does not exist
			:Return 
		"""
		if not function:
			return False
		if debug == 4:
			print('QUERY', function)
		if function == 'power':
			subcmd = "\x04\x00"
		elif function == 'zoom':
			subcmd = "\x04\x47"
		elif function == 'zoom_digital':
			subcmd = "\x04\x06"
		elif function == 'focus_auto':
			subcmd = "\x04\x38"
		elif function == 'focus':
			subcmd = "\x04\x48"			
		elif function == 'focus_nearlimit':
			subcmd = "\x04\x28"
		elif function == 'focus_auto_sensitivity':
			subcmd = "\x04\x58"
		elif function == 'focus_auto_mode':
			subcmd = "\x04\x57"
		elif function == 'focus_ir':
			subcmd = "\x04\x11"
		elif function == 'WB':
			subcmd = "\x04\x35"
		elif function == 'gain_red':
			subcmd = "\x04\x43"
		elif function == 'gain_blue':
			subcmd = "\x04\x44"
		elif function == 'AE':
			subcmd = "\x04\x39"
		elif function == 'slowshutter':
			subcmd = "\x04\x5A"
		elif function == 'shutter':
			subcmd = "\x04\x4A"
		elif function == 'iris':
			subcmd = "\x04\x4B"
		elif function == 'gain':
			subcmd = "\x04\x4C"
		elif function == 'gain_limit':
			subcmd = "\x04\x2C"
		elif function == 'bright':
			subcmd = "\x04\x4D"
		elif function == 'expo_compensation':
			subcmd = "\x04\x3E"
		elif function == 'expo_compensation_amount':
			subcmd = "\x04\x4E"
		elif function == 'backlight':
			subcmd = "\x04\x33"
		elif function == 'WD':
			subcmd = "\x04\x3D"
		elif function == 'aperture':
			subcmd = "\x04\x42"
		elif function == 'HR':
			subcmd = "\x04\x52"
		elif function == 'NR':
			subcmd = "\x04\x53"
		elif function == 'gamma':
			subcmd = "\x04\x5B"
		elif function == 'high_sensitivity':
			subcmd = "\x04\x5E"
		elif function == 'FX':
			subcmd = "\x04\x63"
		elif function == 'IR':
			subcmd = "\x04\x01"
		elif function == 'IR_auto':
			subcmd = "\x04\x51"
		elif function == 'IR_auto_threshold':
			subcmd = "\x04\x21"
		# FIXME : create the ID property
		elif function == 'ID':
			subcmd = "\x04\x22"
		elif function == 'version':
			subcmd = "\x00\x02"
		elif function == 'chroma_supress':
			subcmd = "\x04\x5F"
		elif function == 'color_gain':
			subcmd = "\x04\x49"
		elif function == 'color_hue':
			subcmd = "\x04\x4F"
		elif function == 'info_display':
			subcmd = "\x7E\x01\x18"
		elif function == 'video':
			subcmd = "\x06\x23"
		elif function == 'video_next':
			subcmd = "\x06\x33"
		elif function == 'IR_receive':
			subcmd = "\x06\x08"
		# FIXME : create condition ??
		elif function == 'condition':
			subcmd = "\x06\x34"
		elif function == 'pan_tilt_speed':
			subcmd = "\x06\x11"
		elif function == 'pan_tilt':
			subcmd = "\x06\x12"
		elif function == 'pan_tilt_mode':
			subcmd = "\x06\x10"
		elif function == 'fan':
			subcmd = "\x7E\x01\x38"
		else:
			if debug:
				dbg = 'function {function} has not yet been implemented'
				print(dbg.format(function=function))
			return False
		# make the packet with the dedicated query
		query='\x09' + subcmd
		reply = self._come_back(query)
		if debug == 4:
			dbg = '{function} is {reply}'
			print dbg.format(function=function, reply=reply.encode('hex'))
		if reply:
			#packet = reply
			#header=ord(packet[0])
			#term=ord(packet[-1:])
			#qq=ord(packet[1])
			#sender = (header&0b01110000)>>4
			#broadcast = (header&0b1000)>>3
			#recipient = (header&0b0111)
			reply=reply[2:-1].encode('hex')
#			if len(reply)>3 and ((qq & 0b11110000)>>4)==5:
#				socketno = (qq & 0b1111)
#			elif len(reply)==3 and ((qq & 0b11110000)>>4)==5:
#				socketno = (qq & 0b1111)
			def hex_unpack(zoom,L,size=2):
				part = zoom[:size]
				zoom=zoom[size:]
				L.append(part)
				if zoom:
					hex_unpack(zoom,L)
					return L
			if len(reply) > 2:
				reply = hex_unpack(reply,[])
			elif not type(reply):
				reply = None
			elif type(reply) == hex:
				reply = int(reply,16)
			elif type(reply) == str:
				reply = int(reply,16)
			else:
				reply = None
			if function == 'focus_auto' or function == 'zoom_digital' or function == 'WD' \
			or function == 'focus_ir' or function == 'power' or function == 'expo_compensation' \
			or function == 'IR' or function == 'info_display' or function == 'backlight' \
			or function == 'IR_auto' or function == 'HR' or function == 'high_sensitivity' \
			or function == 'IR_receive':
				if reply == 2:
					reply = True
				elif reply == 3:
					reply = False
			elif function == 'focus_auto_sensitivity':
				if reply == 2:
					reply = 'normal'
				else:
					reply = 'low'
			elif function == 'focus_auto_mode':
				if reply == 0:
					reply = 'normal'
				elif reply == 1:
					reply = 'interval'
				elif reply == 2:
					reply = 'zoom_trigger'
			elif function == 'WB':
				if reply == 0:
					reply = 'auto'
				if reply == 1:
					reply = 'indoor'
				if reply == 2:
					reply = 'outdoor'
				if reply == 3:
					reply = 'trigger'
				if reply == 5:
					reply = 'manual'
			elif function == 'AE':
				if reply == 0:
					reply = 'auto'
				if reply == 3:
					reply = 'manual'
				if reply == 10:
					reply = 'shutter'
				if reply == 11:
					reply = 'iris'
				if reply == 13:
					reply = 'bright'
			elif function == 'slowshutter':
				if reply == 2:
					reply = 'auto'
				else:
					reply = 'manual'
			elif function == 'shutter':
				reply = int(reply[3], 16)
				reply = shutter_val.get(reply)
			elif function == 'iris':
				reply = int(reply[3], 16)
				reply = iris_val.get(reply)
			elif function == 'gain':
				reply = int(reply[3], 16)
				reply = gain_val.get(reply)
			elif function == 'gain_limit':
				reply = int(reply[3], 16)
				reply = gain_limit_val.get(reply)
			elif function == 'bright':
				reply = int(reply[3], 16)
				print('bright feedback need some love')
			elif function == 'expo_compensation_amount':
				reply = int(reply[3], 16)
				reply = expo_compensation_val.get(reply)
			elif function == 'NR':
				reply = reply
			elif function == 'gamma':
				reply = reply
			elif function == 'chroma_supress':
				reply = reply
			elif function == 'FX':
				if reply == 0:
					reply = 'normal'
				if reply == 2:
					reply = 'negart'
				if reply == 4:
					reply = 'BW'
			elif function == 'color_gain':
				reply = int(reply[3], 16)
				reply = ( (reply - 0) / (14 - 0) ) * (200 - 60) + 60
				reply = str(reply)+'%'
			elif function == 'color_hue':
				reply = int(reply[3], 16)
				reply = ( (reply - 0) / (14 - 0) ) * (14 - -14) + -14
				reply = str(reply)+'°'
			elif function == 'video':
				reply = video_val.get(reply)
			elif function == 'video_next':
				reply = video_val.get(reply)
			elif function == 'pan_tilt':
				a=int(reply[7],16)
				b=int(reply[6],16)
				c=int(reply[5],16)
				d=int(reply[4],16)
				e=int(reply[3],16)
				f=int(reply[2],16)
				g=int(reply[1],16)
				h=int(reply[0],16)
				pan = (((((16*h)+g)*16)+f)*16)+e
				tilt = (((((16*d)+c)*16)+b)*16)+a
				pan = visca_to_degree(pan, 'pan')
				tilt = visca_to_degree(tilt, 'tilt')
				reply = [pan, tilt]
			elif function == 'fan':
				if reply == 0:
					reply = True
				else:
					reply = False
			else:
				if debug == 4:
					print('generic translation for function :', function)
				if len(reply) == 4:
					a=int(reply[3],16)
					b=int(reply[2],16)
					c=int(reply[1],16)
					d=int(reply[0],16)
					reply = ((((((16*d)+c)*16)+b)*16)+a)
				else:
					print("don't understand this reply - this have to be implemented")
			if debug:
				dbg = '{function} is {reply}'
				print dbg.format(function=function, reply=reply)
			return reply

	#FIXME: IR_Receive_Return
	#FIXME: Pan-tiltLimitSet
	# ----------------------------------------------------
	# ---------------------- POWER -----------------------
	# ----------------------------------------------------
	@property
	def power(self):
		"""
		State of the power (0/1)
		"""
		return self._query('power')
	@power.setter
	def power(self, state):
		if debug:
			print('power', state)
		if state:
			subcmd = '\x00\x02'
		else:
			subcmd = '\x00\x03'
		return self._cmd_cam(subcmd)

	@property
	def power_auto(self):
		"""
		Return the state of the power_auto param
		time = minutes without command until standby
		0: disable
		0xffff: 65535 minutes (approximatly 45 days)
		"""
		return self._query('power_auto')
	@power.setter
	def power_auto(self, time):
		subcmd = '\x40' + self._i2v(time)
		if debug:
			print('power_auto',time)
		return self._cmd_cam(subcmd)

	# ----------------------------------------------------
	# ---------------------- ZOOM ------------------------
	# ----------------------------------------------------
	def zoom_stop(self):
		"""
		Stop the zoom movement
		"""
		if debug:
			print('zoom_stop')
		subcmd = "\x07\x00"
		return self._cmd_cam(subcmd)

	def zoom_tele(self, speed=3):
		"""
		Zoom In
			:speed is from 0 to 7 (default=3)
		"""
		if speed == 3:
			subcmd = "\x07\x02"
		else:
			self.zoom_tele_speed = speed
			sbyte = 0x20 + (speed&0b111)
			subcmd = "\x07" + chr(sbyte)
		if debug:
			print('zoom_tele', speed)
		return self._cmd_cam(subcmd)

	def zoom_wide(self, speed=3):
		"""
		Zoom Out
			:speed is from 0 to 7 (default=3)
		"""
		if speed == 3:
			subcmd = "\x07\x03"
		else:
			self.zoom_tele_speed = speed
			sbyte = 0x30 + (speed&0b111)
			subcmd = "\x07" + chr(sbyte)
		if debug:
			print('zoom_wide', speed)
		return self._cmd_cam(subcmd)

	@property
	def zoom(self):
		"""
		Return the actual value of the zoom
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		return self._query('zoom')
	@zoom.setter
	def zoom(self, value):
		if debug:
			print('zoom', value)
		subcmd = "\x47" + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	@property
	def zoom_digital(self):
	    return self._query('zoom_digital')
	@zoom_digital.setter
	def zoom_digital(self, state):
		"""
		Digital zoom ON/OFF
		"""
		if debug:
			print('zoom_digital', state)
		if state:
			subcmd = "\x06\x02"
		else:
			subcmd = "\x06\x03"
		return self._cmd_cam(subcmd)

	# ----------------------------------------------------
	# ---------------------- FOCUS -----------------------
	# ----------------------------------------------------
	def focus_stop(self):
		if debug:
			print('focus_stop')
		subcmd = "\x08\x00"
		return self._cmd_cam(subcmd)

	def focus_far(self, speed=3):
		"""
		Focus In with speed = 0..7
		default is 3
		"""
		if speed == 3:
			subcmd = "\x08\x03"
		else:
			sbyte = 0x30 + (value&0b111)
			subcmd = "\x08" + chr(sbyte)
		if debug:
			print('focus_far', speed)
		return self._cmd_cam(subcmd)

	def focus_near(self, speed=3):
		"""
		Focus Out with speed = 0..7
		default = 3
		"""
		if speed == 3:
			subcmd = "\x08\x02"
		else:
			sbyte = 0x20 + (value&0b111)
			subcmd = "\x08" + chr(sbyte)
		if debug:
			print('focus_near', speed)
		return self._cmd_cam(subcmd)

	@property
	def focus(self):
		"""
		focus to value
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		return self._query('focus')

	@focus.setter
	def focus(self, value):
		if debug:
			print('focus',value)
		subcmd = "\x48" + self._i2v(value)
		return self._cmd_cam(subcmd)

	@property
	def focus_auto(self):
		"""
		AF ON/OFF
		"""
		return self._query('focus_auto')
	@focus_auto.setter
	def focus_auto(self, state):
		if debug:
			print('focus_auto', state)
		if state:
			return self._cmd_cam("\x38\x02")
		else:
			return self._cmd_cam("\x38\x03")

	def focus_trigger(self):
		"""
		One Push AF Trigger
		"""
		if debug:
			print('focus_trigger')
		return self._cmd_cam("\x18\x01")

	def focus_infinity(self):
		"""
		Forced infinity
		"""
		if debug:
			print('focus_infinity')
		return self._cmd_cam("\x18\x02")

	@property
	def focus_nearlimit(self):
	    return self._query('focus_nearlimit')
	
	def focus_nearlimit(self, value):
		"""
		Can be set in a range from 1000 (∞) to F000 (10 mm)
		"""
		if debug:
			print('focus_nearlimit',value)
		subcmd = "\x28" + self._i2v(value)
		return self._cmd_cam(subcmd)

	def focus_auto_sensitivity(self, state):
		"""
		AF Sensitivity High/Low
		'normal or low'
		"""
		if debug:
			print('focus_auto_sensitivity', state)
		if state == 'normal':
			return self._cmd_cam("\x58\x02")
		elif state == 'low':
			return self._cmd_cam("\x58\x03")

	def focus_auto_mode(self, state):
		"""
		AF Movement Mode
			:state = normal / interval / zoom trigger / active-interval
		"""
		if debug:
			print('focus_movement_mode', state)
		if state == 'normal':
			subcmd = "\x57\x00"
		elif state == 'interval':
			subcmd = "\x57\x01"
		elif state == 'zoom_trigger':
			subcmd = "\x57\x02"
		return self._cmd_cam(subcmd)

	def focus_auto_active(self, value):
		"""
		pq: Movement Time, rs: Interval
		"""
		if debug:
			print('focus_auto_active', value)
			print('this function has never been tested')
		subcmd = "\x27" + self._i2v(value)
		return self._cmd_cam(subcmd)

	def focus_ir(self, state):
		"""
		FOCUS IR compensation data switching
		0/1
		"""
		if debug:
			print('IR', state)
		if state:
			subcmd = "\x11" + "\x00"
		else:
			subcmd = "\x11" + "\x01"
		return self._cmd_cam(subcmd)

	def zoom_focus(self, zoom, focus):
		"""
		Zoom & Focus in the same command
		"""
		print('Needs to be done')

	# ----------------------------------------------------
	# ---------------- WHITE BALANCE ---------------------
	# ----------------------------------------------------
	@property
	def WB(self):
	    return self._query('WB')
	@WB.setter
	def WB(self, mode):
		if debug:
			print('WB', mode)
		prefix = '\x35'
		if mode == 'auto':
			subcmd = '\x00'
		elif mode == 'indoor':
			subcmd = '\x01'
		elif mode == 'outdoor':
			subcmd = '\x02'
		elif mode == 'trigger':
			subcmd = '\x03'
		elif mode == 'manual':
			subcmd = '\x05'
		subcmd = prefix + subcmd
		return self._cmd_cam(subcmd)

	def WB_trigger(self):
		return self._cmd_cam('\x10\x05')

	@property
	def gain_red(self):
	    return self._query('gain_red')
	@gain_red.setter
	def gain_red(self, value):
		"""
		Manual Control of R Gain
			:0..255 set the red gain
		"""
		if debug:
			print('gain_red', value)
		subcmd = "\x43\x00\x00" + self._i2v(value)
		return self._cmd_cam(subcmd)

	def gain_red_reset(self):
		"""
		Reset the Red Gain
		"""
		return self._cmd_cam('\x03\x00')

	@property
	def gain_blue(self):
	    return self._query('gain_blue')
	@gain_blue.setter
	def gain_blue(self, value):
		"""
		Manual Control of B Gain
			:0..255 set the blue gain
		"""
		if debug:
			print('gain_blue', value)
		subcmd = "\x44\x00\x00" + self._i2v(value)
		return self._cmd_cam(subcmd)

	def gain_blue_reset(self):
		"""
		Reset the Blue Gain
		"""
		return self._cmd_cam('\x04\x00')

	# ----------------------------------------------------
	# ----------------------  EXPOSURE -------------------
	# ----------------------------------------------------
	@property
	def AE(self):
		"""
		define exposure mode :
			:auto = Automatic Exposure mode
			:manual = Manual Control mode
			:shutter = Shutter Priority Automatic Exposure mode
			:iris = Iris Priority Automatic Exposure mode
			:bright = Bright Mode (Manual control)
			Bright can be set only in Full Auto mode or Shutter Priority mode.
		"""
		return self._query('AE')
	@AE.setter
	def AE(self, mode):
		if debug:
			print('AE',mode)
		if mode == 'auto':
			subcmd = "\x39\x00"
		elif mode == 'shutter':
			subcmd = "\x39\x0A"
		elif mode == 'manual':
			subcmd = "\x39\x03"
		elif mode == 'iris':
			subcmd = "\x39\x0B"
		elif mode == 'bright':
			subcmd = "\x39\x0D"
		return self._cmd_cam(subcmd)
	
	@property
	def slowshutter(self):
		"""
		Auto Slow Shutter ON/OFF
		"""
		return self._query('slowshutter')
	@slowshutter.setter
	def slowshutter(self, mode):
		if debug:
			print('slowshutter', mode)
		if mode == 'auto':
			subcmd = "\x5A\x02"
		if mode == 'manual':
			subcmd = "\x5A\x03"
		return self._cmd_cam(subcmd)		

	@property
	def shutter(self):
	    return self._query('shutter')
	@shutter.setter
	def shutter(self, value):
		"""
		Set shutter speed
		"""
		if debug:
			print('shutter', value)
		subcmd = '\x4A' + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	@property
	def iris(self):
	    return self._query('iris')
	@iris.setter
	def iris(self, value):
		"""
		Set iris aperture
		"""
		if debug:
			print('iris',value)
		subcmd = '\x4B' + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	@property
	def gain(self):
		"""
		Set Gain in dB
		"""
		return self._query('gain')
	@gain.setter
	def gain(self, value):
		if debug:
			print('gain',value)
		subcmd = '\x4C' + self._i2v(value)
		return self._cmd_cam(subcmd)

	def gain_limit(self, value):
		"""
		AE Gain Limit (4-F)
		"""
		if debug:
			print('gain_limit', value)
		subcmd = '\x2C' + value
		return self._cmd_cam(subcmd)

	@property
	def bright(self):
		"""
		Set brightness
		"""
		return self._query('bright')
	@bright.setter
	def bright(self, value):
		if debug:
			print('bright',value)
		subcmd = '\x4D\x00\x00' + self._i2v(value)
		return self._cmd_cam(subcmd)

	@property
	def expo_compensation(self):
		"""
		exposure compensation on/off
		"""
		return self._query('expo_compensation')
	@expo_compensation.setter
	def expo_compensation(self, state):
		if debug:
			print('expo_compensation', state)
		if state:
			subcmd = "\x3E\x02"
		else:
			subcmd = "\x3E\x03"
		return self._cmd_cam(subcmd)

	@property
	def expo_compensation_amount(self):
		"""
		exposure compensation amount
		"""
		return self._query('expo_compensation_amount')
	@expo_compensation_amount.setter
	def expo_compensation_amount(self, value):
		if debug:
			print('expo_compensation_amount', value)
		subcmd = '\x4E\x00\x00' + self._i2v(value)
		return self._cmd_cam(subcmd)

	@property
	def backlight(self):
	    return self._query('backlight')
	@backlight.setter
	def backlight(self, state):
		if debug:
			print('backlight', state)
		if state:
			subcmd = "\x33\x02"
		else:
			subcmd = "\x33\x03"
		return self._cmd_cam(subcmd)

	@property
	def WD(self):
		"""
		Wide Dynamic ON/OFF
		"""
		return self._query('WD')
	@WD.setter
	def WD(self, state):
		if debug:
			print('WD', state)
		if state:
			subcmd = "\x3D\x02"
		else:
			subcmd = "\x3D\x03"
		return self._cmd_cam(subcmd)

	# todo : implement WD params

	@property
	def aperture(self):
		"""
		Set aperture
		0 means no enhancement
		0 to 15
		"""
		return self._query('aperture')
	@aperture.setter
	def aperture(self, value):
		if debug:
			print('aperture',value)
		subcmd = '\x42' + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	@property
	def HR(self):
		"""
		High-Resolution Mode ON/OFF
		"""
		return self._query('HR')
	@HR.setter
	def HR(self, state):
		if debug:
			print('HR', state)
		if state:
			subcmd = "\x52\x02"
		else:
			subcmd = "\x52\x03"
		return self._cmd_cam(subcmd)

	@property
	def NR(self):
		"""
		Noise Reduction
			:0 is OFF
		 	:level 1..5
		"""
		return self._query('NR')
	@NR.setter
	def NR(self, value):
		if debug:
			print('NR', value)
		subcmd = "\x53" + value
		return self._cmd_cam(subcmd)

	@property
	def gamma(self):
		"""
		Gamma setting (0: Standard, 1 to 4)
		"""
		return self._query('gamma')
	@gamma.setter
	def gamma(self, value):
		if debug:
			print('gamma', value)
		subcmd = "\x5B" + value
		return self._cmd_cam(subcmd)

	@property
	def high_sensitivity(self):
		"""
		High-Sensitivity Mode ON/OFF
		"""
		return self._query('high_sensitivity')
	@high_sensitivity.setter
	def high_sensitivity(self, state):
		if debug:
			print('high_sensitivity', state)
		if state:
			subcmd = "\x5E\x02"
		else:
			subcmd = "\x5E\x03"
		return self._cmd_cam(subcmd)

	@property
	def FX(self):
		"""
		Picture Effect Setting
			:normal / negart / BW
		"""
		return self._query('FX')
	@FX.setter
	def FX(self, mode):
		if debug:
			print('FX', mode)
		if mode == 'normal':
			subcmd = "\x63" + "\x00"
		if mode == 'negart':
			subcmd = "\x63" + "\x02"
		if mode == 'BW':
			subcmd = "\x63" + "\x04"
		return self._cmd_cam(subcmd)

	@property
	def IR(self):
		"""
		Infrared Mode ON/OFF
		"""
		return self._query('IR')
	@IR.setter
	def IR(self, state):
		if debug:
			print('IR', state)
		if state:
			subcmd = "\x01" + "\x02"
		else:
			subcmd = "\x01" + "\x03"
		return self._cmd_cam(subcmd)

	@property
	def IR_auto(self):
		"""
		Auto dark-field mode On/Off
		"""
		return self._query('IR_auto')
	@IR_auto.setter
	def IR_auto(self, state):
		if debug:
			print('IR_auto', state)
		if state:
			subcmd = "\x51" + "\x02"
		else:
			subcmd = "\x51" + "\x03"
		return self._cmd_cam(subcmd)

	@property
	def IR_auto_threshold(self):
		"""
		ICR ON → OFF Threshold Level
			:0..15
		"""
		return self._query('IR_auto_threshold')
	@IR_auto_threshold.setter
	def IR_auto_threshold(self, level):
		if debug:
			print('IR_auto_threshold', level)
		subcmd = '\x21\x00\x00' + self._i2v(value)
		return self._cmd_cam(subcmd)

	# ----------- MEMORY -------------
	def _memory(self,func,num):
		if debug:
			print('memory', func, num)
		if num > 5:
			num = 5
		if func < 0 or func > 2:
			return
		if debug:
			print("memory")
		subcmd = "\x3f" + chr(func) + chr( 0b0111 & num)
		return self._cmd_cam(subcmd)

	def memory_reset(self, num):
		return self._memory(0x00, num)
	
	def memory_set(self, num):
		return self._memory(0x01, num)

	def memory_recall(self, num):
		return self._memory(0x02, num)

	# todo id_write

	@property
	def chroma_supress(self):
		"""
		pp: Chroma Suppress setting level
		00: OFF
		1 to 3: ON (3 levels)
		Effect increases as the level number increases.
		"""
		return self._query('chroma_supress')
	@chroma_supress.setter
	def chroma_supress(self, level):
		if debug:
			print('chroma_supress', level)
		subcmd = "\x5F" + level
		return self._cmd_cam(subcmd)
		
	@property
	def color_gain(self):
		"""
		Color Gain setting 0h (60%) to Eh (200%)
		"""
		return self._query('color_gain')
	@color_gain.setter
	def color_gain(self, value):
		if debug:
			print('color_gain', value)
		subcmd = "\x49\x00\x00\x00" + value
		return self._cmd_cam(subcmd)
	

	@property
	def color_hue(self):
		"""
		Color Hue setting 0h (− 14 degrees) to Eh (+14 degrees)
		"""
		return self._query('color_hue')
	@color_hue.setter
	def color_hue(self, value):
		if debug:
			print('color_hue', value)
		subcmd = "\x4F\x00\x00\x00" + value
		return self._cmd_cam(subcmd)

	# ----------------------------------------------------
	# ------------------ SYSTEM --------------------------
	# ----------------------------------------------------
	def menu_off(self):
		"""
		Turns off the menu screen
		"""
		if debug:
			print('menu_off')
		subcmd = '\x06' + '\x03'
		return self._cmd_cam_alt(subcmd)

	@property
	def video(self):
		"""
		Return the state of the video (resolution + frequency)
		720:50
		"""
		return self._query('video')
	@video.setter
	def video(self, resfreq):
		res = resfreq[0]
		freq = resfreq[1]
		if debug:
			print('video', str(res) + str(freq))
		if res == 720:
			if freq == 50:
				subcmd = '\x35\x00\x09'
		return self._cmd_cam_alt(subcmd)

	@property
	def IR_receive(self):
		"""
		IR(remote commander) receive ON/OFF
		"""
		return self._query('IR_receive')
	@IR_receive.setter
	def IR_receive(self, state):
		if debug:
			print('IR_receive', state)
		if state:
			subcmd = "\x02"
		else:
			subcmd = "\x03"
			prefix = '\x01\x06\x08'
		return self._cmd_cam(subcmd, prefix)

	# ----------- INFO DISPLAY-------------
	@property
	def info_display(self):
		"""
		ON/OFF of the Operation status display
		of One Push Trigger of CAM_Memory and CAM_WB
		"""
		return self._query('info_display')
	@info_display.setter
	def info_display(self, state):
		if debug:
			print('info_display', state)
		if state:
			subcmd = '\x02'
		else:
			subcmd = '\x03'
		prefix = '\x01\x7E\x01\x18'
		return self._cmd_cam(subcmd, prefix)

	# ----------------------------------------------------
	# ----------------------  PAN TILT -------------------
	# ----------------------------------------------------
	def _cmd_ptd(self, lr, ud):
		"""
		simple shortcut to send _cmd_cam with pan_tilt_speed
		"""
		subcmd = '\x01'+chr(self.pan_speedy)+chr(self.tilt_speedy)+chr(lr)+chr(ud)
		return self._cmd_cam_alt(subcmd)

	@property
	def pan_speed(self):
		return self._query('pan_tilt_speed')
	@pan_speed.setter
	def pan_speed(self, pan_speed):
		if debug:
			print('pan_speed', pan_speed)
		self.pan_speedy = pan_speed

	@property
	def tilt_speed(self):
		return self._query('pan_tilt_speed')
	@tilt_speed.setter
	def tilt_speed(self, tilt_speed):
		if debug:
			print('tilt_speed', tilt_speed)
		self.tilt_speedy = tilt_speed

	def up(self):
		if debug:
			print('up')
		return self._cmd_ptd(0x03,0x01)

	def down(self):
		if debug:
			print('down')
		return self._cmd_ptd(0x03,0x02)
	
	def left(self):
		if debug:
			print('left')
		return self._cmd_ptd(0x01,0x03)
	
	def right(self):
		if debug:
			print('right')
		return self._cmd_ptd(0x02,0x03)
	
	def upleft(self):
		if debug:
			print('upleft')
		return self._cmd_ptd(0x01,0x01)

	def upright(self):
		if debug:
			print('upright')
		return self._cmd_ptd(0x02,0x01)
	
	def downleft(self):
		if debug:
			print('downleft')
		return self._cmd_ptd(0x01,0x02)
	
	def downright(self):
		if debug:
			print('downright')
		return self._cmd_ptd(0x02,0x02)

	def stop(self):
		if debug:
			print('stop')
		return self._cmd_ptd(0x03,0x03)

	@property
	def pan(self):
		"""
		pan
			:between -170 & 170
		"""
		return self._query('pan_tilt')
	@pan.setter
	def pan(self, pan):
		if debug:
			print('pan', pan)
		pan = degree_to_visca(pan, 'pan')
		pan = self._i2v(pan)
		subcmd = '\x02' + chr(self.pan_speedy) + chr(self.tilt_speedy) + pan + chr(0)

	@property
	def tilt(self):
		"""
		tilt
			:between -20 & 90 if flip == False
			:between -20 & 90 if flip == True
			: default flip is False
		"""
		return self._query('pan_tilt')
	@tilt.setter
	def tilt(self, tilt):
		if debug:
			print('tilt', tilt)
		tilt = degree_to_visca(tilt, 'tilt')
		tilt = self._i2v(tilt)
		subcmd = '\x02' + chr(self.pan_speedy) + chr(self.tilt_speedy) + tilt + chr(0)

	# FIX ME : not sur this one is need. Separate pan / tilt might be enough
	def pan_tilt(self, pan, tilt):
		if debug:
			print('pan_tilt',pan,tilt)
		pan = self._i2v(pan)
		tilt = self._i2v(tilt)
		subcmd = '\x02'+chr(self.pan_speedy)+chr(self.tilt_speedy)+pan+tilt

	def home(self):
		if debug:
			print('home')
		subcmd = '\x04'
		return self._cmd_cam_alt(subcmd)

	def reset(self):
		if debug:
			print('reset')
		subcmd = '\x05'
		return self._cmd_cam_alt(subcmd)

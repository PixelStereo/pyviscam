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
                self.port = serial.Serial(self.portname, 9600, timeout=2, stopbits=1, bytesize=8, rtscts=False, dsrdtr=False)
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
			print("please make a simulation in case you don't have a serial port with a visca camera available")

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
		
	def _cmd_pt(self,subcmd,device=1):
		packet='\x01\x06'+subcmd
		reply = self._send_packet(packet)
		#FIXME: check returned data here and retransmit?
		return reply
	
	def _cmd_ptd(self,lr,ud):
		subcmd = '\x01'+chr(self.pan_speedy)+chr(self.tilt_speedy)+chr(lr)+chr(ud)
		return self._cmd_pt(subcmd)
		
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

	def _query(self,function):
		if debug == 4:
			print('QUERY', function)
		if function == 'zoom':
			subcmd = "\x04"+"\x47"
		elif function == 'focus':
			subcmd = "\x04"+"\x48"
		elif function == 'focus_mode':
			subcmd = "\x04"+"\x38"
		elif function == 'pan_tilt':
			subcmd = "\x06"+"\x12"
		elif function == 'nearlimit':
			subcmd = "\x04"+"\x28"
		elif function == 'AE':
			subcmd = "\x04"+"\x39"
		elif function == 'shutter':
			subcmd = "\x04"+"\x4A"
		elif function == 'iris':
			subcmd = "\x04"+"\x4B"
		elif function == 'gain':
			subcmd = "\x04"+"\x4C"
		elif function == 'aperture':
			subcmd = "\x04"+"\x42"
		elif function == 'power':
			subcmd = "\x04"+"\x00"
		elif function == 'IR':
			subcmd = "\x04"+"\x01"
		elif function == 'display':
			subcmd = "\x04"+"\x7E"+"\x01"+"\x18"
		elif function == 'video':
			subcmd = "\x06"+"\x23"+"\xFF"
		# make the packet with the dedicated query
		query='\x09'+subcmd
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
			if function == 'focus_mode' or function == 'power' or function == 'IR':
				if reply == 2:
					reply=True
				elif reply == 3:
					reply = False
			elif function == 'video':
				if reply == 9:
					reply = (720, 50)
			elif function == 'AE':
				if reply == 0:
					reply = 'auto'
				if reply == 3:
					reply = 'manual'
				if reply == 10:
					reply = 'shutter'
				if reply == 11:
					reply = 'iris'
			elif function == 'pan_tilt':
				a=int(reply[7],16)
				b=int(reply[6],16)
				c=int(reply[5],16)
				d=int(reply[4],16)
				e=int(reply[3],16)
				f=int(reply[2],16)
				g=int(reply[1],16)
				h=int(reply[0],16)
				reply = (((((16*h)+g)*16)+f)*16)+e , (((((16*d)+c)*16)+b)*16)+a
				print('pan_tilt need some love (and scaling)',reply)
			else:
				a=int(reply[3],16)
				b=int(reply[2],16)
				c=int(reply[1],16)
				d=int(reply[0],16)
				reply = ((((((16*d)+c)*16)+b)*16)+a)
			if debug:
				dbg = '{function} is {reply}'
				print dbg.format(function=function, reply=reply)
			return reply

	#FIXME: CAM_Bright
	#FIXME: CAM_ExpComp
	#FIXME: CAM_BackLight
	#FIXME: IR_Receive
	#FIXME: IR_Receive_Return
	#FIXME: Pan-tiltLimitSet

	# ----------------------------------------------------
	# ---------------------- POWER -----------------------
	# ----------------------------------------------------
	@property
	def power(self):
		"""
		Return the state of the power
		"""
		return self._query('power')

	@power.setter
	def power(self, state):
		"""
		Set the power on or off (boolean)
		"""
		if debug:
			print('power', state)
		if state:
			subcmd = '\x00\x02'
		else:
			subcmd = '\x00\x03'
		return self._cmd_cam(subcmd)

	# ----------- POWER AUTO -------------
	@property
	def power_auto(self):
		"""
		Return the state of the power_auto param
		"""
		return self._query('power_auto')

	@power.setter
	def power_auto(self, time):
		"""
		time = minutes without command until standby
		0: disable
		0xffff: 65535 minutes (approximatly 45 days)
		"""
		subcmd = '\x40' + self._i2v(time)
		if debug:
			print('power_auto',time)
		return self._cmd_cam(subcmd)

	# ----------------------------------------------------
	# ---------------------- VIDEO -----------------------
	# ----------------------------------------------------
	@property
	def video(self):
		"""
		Return the state of the video (resolution + frequency)
		720:50
		"""
		return self._query('video')

	@video.setter
	def video(self, res, freq):
		if debug:
			print('video', str(res) + str(freq))
		if res == 720:
			if freq == 50:
				subcmd = '\x35\x00\x09'
		prefix = '\x01\x06'
		return self._cmd_cam(subcmd, prefix)

	# ----------------------------------------------------
	# ----------------------  EXPOSURE -------------------
	# ----------------------------------------------------
	@property
	def AE(self):
		return self._query('AE')

	@AE.setter
	def AE(self, mode):
		"""
		define exposure mode :
		auto
		shutter
		manual
		iris
		"""
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
		return self._cmd_cam(subcmd)
	
	# ----------- SHUTTER -------------
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
	
	# ----------- IRIS -------------
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
	
	# ----------- GAIN -------------
	@property
	def gain(self):
	    return self._query('gain')
	
	@gain.setter
	def gain(self, value):
		"""
		Set Gain in dB
		"""
		if debug:
			print('gain',value)
		subcmd = '\x4C' + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	# ----------- APERTURE -------------
	@property
	def aperture(self):
	    return self._query('aperture')

	@aperture.setter
	def aperture(self, value):
		"""
		Set aperture
		0 means no enhancement
		0 to 15
		"""
		if debug:
			print('aperture',value)
		subcmd = '\x42' + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	# ----------- SLOW SHUTTER -------------
	@property
	def slowshutter(self):
	    return self._query('slowshutter')
	
	@slowshutter.setter
	def slowshutter(self, mode):
		"""
		Set the slowshutter auto or manual
		"""
		if debug:
			print('slowshutter',mode)
		if mode == 'auto':
			subcmd = "\x5A\x02"
		if mode == 'manual':
			subcmd = "\x5A\x03"
		return self._cmd_cam(subcmd)		
	
	# ----------------------------------------------------
	# ---------------------- ZOOM ------------------------
	# ----------------------------------------------------
	@property
	def zoom_direct(self):
		"""
		Return the actual value of the zoom
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		return self._query('zoom')

	@zoom_direct.setter
	def zoom_direct(self, value):
		"""
		zoom to value
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		if debug:
			print('zoom_direct', value)
		subcmd = "\x47" + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def zoom_stop(self):
		"""
		Stop the zoom movement
		"""
		if debug:
			print('zoom_stop')
		subcmd = "\x07\x00"
		return self._cmd_cam(subcmd)

	def zoom_tele(self, speed=None):
		"""
		Zoom in
		accepts 
		"""
		if speed != None:
			self.zoom_tele_speed = speed
		if debug:
			print('zoom_tele')
		subcmd = "\x07\x02"
		return self._cmd_cam(subcmd)
	
	def zoom_wide(self, speed=None):
		"""
		Zoom Out
		"""
		if speed != None:
			self.zoom_wide_speed = speed
		if debug:
			print('zoom_wide')
		subcmd = "\x07\x03"
		return self._cmd_cam(subcmd)
	
	@property
	def zoom_tele_speed(self):
		"""
		Returns zoom in speed
		from 0 to 7
		"""
		return self._query('zoom_tele_speed')

	@zoom_tele_speed.setter
	def zoom_tele_speed(self,speed):
		"""
		Set Zoom In speed
		from 0 to 7
		"""
		if debug:
			print('zoom_tele_speed',speed)
		sbyte=0x20+(speed&0b111)
		subcmd = "\x07"+chr(sbyte)
		return self._cmd_cam(subcmd)

	@property
	def zoom_wide_speed(self):
		"""
		Returns Zoom Out speed
		from 0 to 7
		"""
		return self._query('zoom_wide_speed')

	@zoom_wide_speed.setter
	def zoom_wide_speed(self,speed):
		"""
		Set Zoom Out speed
		from 0 to 7
		"""
		if debug:
			print('zoom_wide_speed',speed)
		sbyte=0x30+(speed&0b111)
		subcmd = "\x07"+chr(sbyte)
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
	def focus_nearlimit(self,value):
		if debug:
			print('focus_nearlimit',value)
		subcmd = "\x28"+self._i2v(value)
		return self._cmd_cam(subcmd)

	# ----------- FOCUS MODE -------------
	def focus_mode(self,mode):
		if debug:
			print('focus_mode',mode)
		if mode == 'auto':
			return self._cmd_cam("\x38\x02")
		elif mode == 'manual':
			return self._cmd_cam("\x38\x03")
	
	# ----------- FOCUS STOP -------------
	def focus_stop(self):
		if debug:
			print('focus_stop')
		subcmd = "\x08\x00"
		return self._cmd_cam(subcmd)
	
	# ----------- FOCUS NEAR -------------
	def focus_near(self):
		if debug:
			print('focus_near')
		subcmd = "\x08\x02"
		return self._cmd_cam(subcmd)

	# ----------- FOCUS FAR -------------
	def focus_far(self):
		if debug:
			print('focus_far')
		subcmd = "\x08\x03"
		return self._cmd_cam(subcmd)
	
	# ----------- FOCUS NEAR SPEED -------------
	def focus_near_speed(self,value):
		"""
		focus in with speed = 0..7
		"""
		if debug:
			print('focus_near_speed',value)
		sbyte = 0x20 + (value&0b111)
		subcmd = "\x08" + chr(sbyte)
		return self._cmd_cam(subcmd)
	
	# ----------- FOCUS FAR SPEED -------------
	def focus_far_speed(self,value):
		"""
		focus in with speed = 0..7
		"""
		if debug:
			print('focus_far_speed',value)
		sbyte = 0x30 + (value&0b111)
		subcmd = "\x08" + chr(sbyte)
		return self._cmd_cam(subcmd)

	# ----------- FOCUS DIRECT -------------
	def focus_direct(self,value):
		"""
		focus to value
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		if debug:
			print('focus_direct',value)
		subcmd = "\x48" + self._i2v(value)
		return self._cmd_cam(subcmd)
	
	# ----------- FOCUS IR -------------
	def IR(self,state):
		if debug:
			print('IR',state)
		if state:
			subcmd = "\x01" + "\x02"
		else:
			subcmd = "\x01" + "\x03"
		return self._cmd_cam(subcmd)
	
	# ----------- FOCUS FX -------------
	def FX(self,mode):
		if debug:
			print('FX',mode)
		if mode == 'normal':
			subcmd = "\x63" + "\x00"
		if mode == 'negart':
			subcmd = "\x63" + "\x02"
		if mode == 'BW':
			subcmd = "\x63" + "\x04"
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

	# ----------------------------------------------------
	# ---------------------- OSD -----------------------
	# ----------------------------------------------------

	# ----------- MENU OFF -------------
	def menu_off(self):
		"""
		Turns off the menu screen
		"""
		if debug:
			print('menu_off')
		subcmd = '\x06' + '\x03'
		prefix='\x01\x06'
		return self._cmd_cam(subcmd, prefix)

	# ----------- INFO DISPLAY-------------
	@property
	def info_display(self):
	    return self._query('info_display')

	@info_display.setter
	def info_display(self, state):
		"""
		ON/OFF of the Operation status display
		of One Push Trigger of CAM_Memory and CAM_WB
		"""
		if debug:
			print('info_display', state)
		if state:
			subcmd = '\x02'
		else:
			subcmd = '\x03'
		prefix = '\x01\x7E\x01\x18'
		return self._cmd_cam(subcmd, prefix)
	
	# ----------- WHITE BALANCE -------------
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

	# ----------- PAN -------------
	def pan(self, pan):
		if debug:
			print('pan', pan)
		pan = self._i2v(pan)
		subcmd = '\x02' + chr(self.pan_speedy) + chr(self.tilt_speedy) + pan + chr(0)

	# ----------- TILT -------------
	def tilt(self, tilt):
		if debug:
			print('tilt', tilt)
		tilt = self._i2v(tilt)
		subcmd = '\x02' + chr(self.pan_speedy) + chr(self.tilt_speedy) + tilt + chr(0)

	# ----------- PAN TILT -------------
	def pan_tilt(self,pan,tilt):
		if debug:
			print('pan_tilt',pan,tilt)
		pan=self._i2v(pan)
		tilt=self._i2v(tilt)
		subcmd = '\x02'+chr(self.pan_speedy)+chr(self.tilt_speedy)+pan+tilt

	# ----------- PAN SPEED -------------
	def pan_speed(self,pan_speed):
		if debug:
			print('pan_speed',pan_speed)
		self.pan_speedy = pan_speed

	# ----------- TILT SPEED -------------
	def tilt_speed(self,tilt_speed):
		if debug:
			print('tilt_speed',tilt_speed)
		self.tilt_speedy = tilt_speed
	
	# ----------- UP -------------
	def up(self):
		if debug:
			print('up')
		return self._cmd_ptd(0x03,0x01)

	# ----------- DOWN -------------
	def down(self):
		if debug:
			print('down')
		return self._cmd_ptd(0x03,0x02)
	
	# ----------- LEFT -------------
	def left(self):
		if debug:
			print('left')
		return self._cmd_ptd(0x01,0x03)
	
	# ----------- RIGHT -------------
	def right(self):
		if debug:
			print('right')
		return self._cmd_ptd(0x02,0x03)
	
	# ----------- UPLEFT -------------
	def upleft(self):
		if debug:
			print('upleft')
		return self._cmd_ptd(0x01,0x01)

	# ----------- UPRIGHT-------------
	def upright(self):
		if debug:
			print('upright')
		return self._cmd_ptd(0x02,0x01)
	
	# ----------- DOWNLEFT -------------
	def downleft(self):
		if debug:
			print('downleft')
		return self._cmd_ptd(0x01,0x02)
	
	# ----------- DOWNRIGHT -------------
	def downright(self):
		if debug:
			print('downright')
		return self._cmd_ptd(0x02,0x02)

	# ----------- STOP -------------
	def stop(self):
		if debug:
			print('stop')
		return self._cmd_ptd(0x03,0x03)
	
	# ----------- HOME -------------
	def home(self):
		if debug:
			print('home')
		subcmd = '\x04'
		return self._cmd_pt(subcmd)
	
	# ----------- RESET -------------
	def reset(self):
		if debug:
			print('reset')
		subcmd = '\x05'
		return self._cmd_pt(subcmd)

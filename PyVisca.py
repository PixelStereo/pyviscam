#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import serial
from thread import allocate_lock
import glob

debug=False

class Serial(object):
    def __init__(self):
        self.mutex = allocate_lock()
        self.port=None

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

    def open(self,portname):
        self.mutex.acquire()
        self.portname=portname
        if (self.port == None):
            try:
                self.port = serial.Serial(self.portname,9600,timeout=2,stopbits=1,bytesize=8,rtscts=False, dsrdtr=False)
                self.port.flushInput()
            except Exception as e:
                pass
                #raise e
                self.port = None
        self.mutex.release()    

    def recv_packet(self,extra_title=None):
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
                    print "ERROR: Timeout waiting for reply"
                    break
                if byte==0xff:
                    break
            return packet
        print 'no reply from serial because there is no connexion'

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


class Visca():
	"""create a visca device object"""
	def __init__(self,serial=None):
		"""the constructor"""
		self.serial=serial
		self.pan_speedy = 0x01
		self.tilt_speedy = 0x01
		print "CREATING A VISCA INSTANCE"

	def _send_packet(self,data,recipient=1):
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
				if debug:print "received packet not terminated correctly: %s" % reply.encode('hex')
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
			if debug : print reply.encode('hex') , '####### ACK __ buffer 1-------------------'
			reply = self.serial.recv_packet()
			if reply == '\x90'+'\x51'+'\xFF':
				if debug : print reply.encode('hex') , '####### COMPLETION __ buffer 1-------------------'
				return reply
		elif reply == '\x90'+'\x42'+'\xFF':
			if debug : print reply.encode('hex') , '####### ACK __ buffer 2-------------------'
			reply = self.serial.recv_packet()
			if reply == '\x90'+'\x60'+'\x02'+'\xFF':
				if debug : print reply.encode('hex') , '####### Syntax Error-------------------'
				return reply
		elif reply == '\x90'+'\x61'+'\x41'+'\xFF':
			if debug : print reply.encode('hex') , '####### NOT IN THIS MODE   -------------------'
			return 'ERROR'
		elif reply == '\x90'+'\x62'+'\x41'+'\xFF':
			if debug : print reply.encode('hex') , '####### NOT IN THIS MODE   -------------------'
			return 'ERROR'
		
	def _memory(self,func,num):
		if debug :print 'function from viscalib triggered','memory',func,num
		if num>5:
			num=5
		if func<0 or func>2:
			return
		if debug:print "memory"
		subcmd="\x3f"+chr(func)+chr( 0b0111 & num)
		return self._cmd_cam(subcmd)
		
	def _cmd_pt(self,subcmd,device=1):
		packet='\x01\x06'+subcmd
		reply = self._send_packet(packet)
		#FIXME: check returned data here and retransmit?
		return reply
	
	def _cmd_ptd(self,lr,ud):
		subcmd='\x01'+chr(self.pan_speedy)+chr(self.tilt_speedy)+chr(lr)+chr(ud)
		return self._cmd_pt(subcmd)
		
	def _come_back(self,query):
		""" Send a query and wait for (ack + completion + answer)
			Accepts a visca query (hexadeciaml)
			Return a visca answer if ack and completion (hexadeciaml)"""
		# send the query and wait for feedback
		reply = self._send_packet(query)
		#reply = reply.encode('hex')
		if reply == '\x90'+'\x60'+'\x03'+'\xFF':
			if debug : print reply.encode('hex') , '####### Command Buffer Full-------------------'
			self._come_back(query)
		elif reply.startswith('\x90'+'\x50'):
			if debug : print reply.encode('hex') , '####### Completion to query-------------------'
			return reply
		elif reply == '\x90'+'\x60'+'\x02'+'\xFF':
			if debug : print reply.encode('hex') , '####### Syntax Error to query-------------------'
			return

	def _query(self,function):
		if debug :print 'function from viscalib triggered QUERY',function
		if function == 'zoom':
			subcmd="\x04"+"\x47"
		elif function == 'focus':
			subcmd="\x04"+"\x48"
		elif function == 'focus_mode':
			subcmd="\x04"+"\x38"
		elif function == 'pan_tilt':
			subcmd="\x06"+"\x12"
		elif function == 'nearlimit':
			subcmd="\x04"+"\x28"
		elif function == 'AE':
			subcmd="\x04"+"\x39"
		elif function == 'shutter':
			subcmd="\x04"+"\x4A"
		elif function == 'iris':
			subcmd="\x04"+"\x4B"
		elif function == 'gain':
			subcmd="\x04"+"\x4C"
		elif function == 'aperture':
			subcmd="\x04"+"\x42"
		elif function == 'power':
			subcmd="\x04"+"\x00"
		elif function == 'IR':
			subcmd="\x04"+"\x01"
		elif function == 'display':
			subcmd="\x04"+"\x7E"+"\x01"+"\x18"
		elif function == 'video':
			subcmd="\x06"+"\x23"+"\xFF"
		# make the packet with the dedicated query
		query='\x09'+subcmd
		reply = self._come_back(query)
		if debug : print '---REPLY FROM THE CAMERA---',function, reply.encode('hex'),type(reply.encode('hex')),'----'
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
				print '--------', reply
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
				print 'pan_tilt need some love (and scaling)',reply
			else:
				a=int(reply[3],16)
				b=int(reply[2],16)
				c=int(reply[1],16)
				d=int(reply[0],16)
				reply = ((((((16*d)+c)*16)+b)*16)+a)
			return reply

	#FIXME: CAM_Bright
	#FIXME: CAM_ExpComp
	#FIXME: CAM_BackLight
	#FIXME: IR_Receive
	#FIXME: IR_Receive_Return
	#FIXME: Pan-tiltLimitSet

	def power(self,state):
		""" set the power on or off (boolean) """
		if debug :print 'function from viscalib triggered','power',state
		if state:
			subcmd='\x00\x02'
		else:
			subcmd='\x00\x03'
		return self._cmd_cam(subcmd)

	def power_auto(self,time=0):
		""" time = minutes without command until standby
		0: disable
		0xffff: 65535 minutes
		"""
		subcmd='\x40'+self._i2v(time)
		if debug :print 'function from viscalib triggered','power_auto',time
		return self._cmd_cam(subcmd)

	def AE(self,mode):
		""" define exposure mode
		auto
		shutter
		manual
		iris
		"""
		if debug :print 'function from viscalib triggered','AE',mode
		if mode == 'auto':
			subcmd="\x39\x00"
		elif mode == 'shutter':
			subcmd="\x39\x0A"
		elif mode == 'manual':
			subcmd="\x39\x03"
		elif mode == 'iris':
			subcmd="\x39\x0B"
		return self._cmd_cam(subcmd)

	def video(self, res, freq):
		if debug:
			print 'function from viscalib triggered', 'video', str(res) + str(freq)
		if res == 720:
			if freq == 50:
				subcmd = '\x35\x00\x09'
		prefix = '\x01\x06'
		return self._cmd_cam(subcmd, prefix)
	
	def shutter(self,value):
		if debug :print 'function from viscalib triggered', 'shutter', value
		subcmd='\x4A'+self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def iris(self,value):
		if debug :print 'function from viscalib triggered','iris',value
		subcmd='\x4B'+self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def gain(self,value):
		if debug :print 'function from viscalib triggered','gain',value
		subcmd='\x4C'+self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def aperture(self,value):
		if debug :print 'function from viscalib triggered','aperture',value
		subcmd='\x42'+self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def slowshutter(self,mode):
		if debug :print 'function from viscalib triggered','slowshutter',mode
		if mode == 'auto':
			subcmd="\x5A\x02"
		if mode == 'manual':
			subcmd="\x5A\x03"
		return self._cmd_cam(subcmd)		
	
	def zoom_stop(self):
		if debug :print 'function from viscalib triggered','zoom_stop'
		subcmd="\x07\x00"
		return self._cmd_cam(subcmd)

	def zoom_tele(self):
		if debug :print 'function from viscalib triggered','zoom_tele'
		subcmd="\x07\x02"
		return self._cmd_cam(subcmd)
	
	def zoom_wide(self):
		if debug :print 'function from viscalib triggered','zoom_wide'
		subcmd="\x07\x03"
		return self._cmd_cam(subcmd)
	
	def zoom_tele_speed(self,speed):
		if debug :print 'function from viscalib triggered','zoom_tele_speed',speed
		"""
		zoom in with speed = 0..7
		"""
		sbyte=0x20+(speed&0b111)
		subcmd="\x07"+chr(sbyte)
		return self._cmd_cam(subcmd)
	
	def zoom_wide_speed(self,speed):
		"""
		zoom in with speed = 0..7
		"""
		if debug :print 'function from viscalib triggered','zoom_wide_speed',speed
		sbyte=0x30+(speed&0b111)
		subcmd="\x07"+chr(sbyte)
		return self._cmd_cam(subcmd)
	
	def zoom_direct(self,value):
		"""
		zoom to value
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		if debug :print 'function from viscalib triggered','zoom_direct',value
		subcmd="\x47"+self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def zoom_digital(self,state):
		if debug :print 'function from viscalib triggered','zoom_digital',state
		if state:
			subcmd="\x06\x02"
		else:
			subcmd="\x06\x03"
		return self._cmd_cam(subcmd)
	
	def focus_nearlimit(self,value):
		if debug :print 'function from viscalib triggered','focus_nearlimit',value
		subcmd="\x28"+self._i2v(value)
		return self._cmd_cam(subcmd)

	def focus_mode(self,mode):
		if debug :print 'function from viscalib triggered','focus_mode',mode
		if mode == 'auto':
			return self._cmd_cam("\x38\x02")
		elif mode == 'manual':
			return self._cmd_cam("\x38\x03")
	
	def focus_stop(self):
		if debug :print 'function from viscalib triggered','focus_stop'
		subcmd="\x08\x00"
		return self._cmd_cam(subcmd)
	
	def focus_near(self):
		if debug :print 'function from viscalib triggered','focus_near'
		subcmd="\x08\x02"
		return self._cmd_cam(subcmd)

	def focus_far(self):
		if debug :print 'function from viscalib triggered','focus_far'
		subcmd="\x08\x03"
		return self._cmd_cam(subcmd)
	
	def focus_near_speed(self,value):
		"""
		focus in with speed = 0..7
		"""
		if debug :print 'function from viscalib triggered','focus_near_speed',value
		sbyte=0x20+(value&0b111)
		subcmd="\x08"+chr(sbyte)
		return self._cmd_cam(subcmd)
	
	def focus_far_speed(self,value):
		"""
		focus in with speed = 0..7
		"""
		if debug :print 'function from viscalib triggered','focus_far_speed',value
		sbyte=0x30+(value&0b111)
		subcmd="\x08"+chr(sbyte)
		return self._cmd_cam(subcmd)

	def focus_direct(self,value):
		"""
		focus to value
		optical: 0..4000
		digital: 4000..7000 (1x - 4x)
		"""
		if debug :print 'function from viscalib triggered','focus_direct',value
		subcmd="\x48"+self._i2v(value)
		return self._cmd_cam(subcmd)
	
	def IR(self,state):
		if debug :print 'function from viscalib triggered','IR',state
		if state:
			subcmd="\x01"+"\x02"
		else:
			subcmd="\x01"+"\x03"
		return self._cmd_cam(subcmd)
	
	def FX(self,mode):
		if debug :print 'function from viscalib triggered','FX',mode
		if mode == 'normal':
			subcmd="\x63"+"\x00"
		if mode == 'negart':
			subcmd="\x63"+"\x02"
		if mode == 'BW':
			subcmd="\x63"+"\x04"
		return self._cmd_cam(subcmd)

	def memory_reset(self,num):
		return self._memory(0x00,num)
	
	def memory_set(self,num):
		return self._memory(0x01,num)

	def memory_recall(self,num):
		return self._memory(0x02,num)
	
	def noOSD(self):
		""" Datascreen control """
		if debug :print 'function from viscalib triggered','noOSD'
		subcmd='\x01'+'\x06'+'\x06'+'\x03'
		self.info_display(False)
		return self._send_packet(subcmd)

	def info_display(self,state):
		if debug :print 'function from viscalib triggered','info_display',state
		if state:
			packet = '\x01\x7E\x01\x18\x02'
		else:
			packet = '\x01\x7E\x01\x18\x03'
		return self._send_packet(packet)
	
	def WB(self,mode):
		if debug :print 'function from viscalib triggered','WB',mode
		prefix = '\x35'
		if mode == 'auto':
			subcmd='\x00'
		elif mode == 'indoor':
			subcmd='\x01'
		elif mode == 'outdoor':
			subcmd='\x02'
		elif mode == 'trigger':
			subcmd='\x03'
		elif mode == 'manual':
			subcmd='\x05'
		subcmd = prefix+subcmd
		return self._cmd_cam(subcmd)

	def pan(self,pan):
		if debug :print 'function from viscalib triggered','pan',pan
		pan=self._i2v(pan)
		subcmd='\x02'+chr(self.pan_speedy)+chr(self.tilt_speedy)+pan+chr(0)

	def tilt(self,tilt):
		if debug :print 'function from viscalib triggered','tilt',tilt
		tilt=self._i2v(tilt)
		subcmd='\x02'+chr(self.pan_speedy)+chr(self.tilt_speedy)+tilt+chr(0)

	def pan_tilt(self,pan,tilt):
		if debug :print 'function from viscalib triggered','pan_tilt',pan,tilt
		pan=self._i2v(pan)
		tilt=self._i2v(tilt)
		subcmd='\x02'+chr(self.pan_speedy)+chr(self.tilt_speedy)+pan+tilt

	def pan_speed(self,pan_speed):
		if debug :print 'function from viscalib triggered','pan_speed',pan_speed
		self.pan_speedy = pan_speed

	def tilt_speed(self,tilt_speed):
		if debug :print 'function from viscalib triggered','tilt_speed',tilt_speed
		self.tilt_speedy = tilt_speed
	
	def up(self):
		if debug :print 'function from viscalib triggered','up'
		return self._cmd_ptd(0x03,0x01)

	def down(self):
		if debug :print 'function from viscalib triggered','down'
		return self._cmd_ptd(0x03,0x02)
	
	def left(self):
		if debug :print 'function from viscalib triggered','left'
		return self._cmd_ptd(0x01,0x03)
	
	def right(self):
		if debug :print 'function from viscalib triggered','right'
		return self._cmd_ptd(0x02,0x03)
	
	def upleft(self):
		if debug :print 'function from viscalib triggered','upleft'
		return self._cmd_ptd(0x01,0x01)

	def upright(self):
		if debug :print 'function from viscalib triggered','upright'
		return self._cmd_ptd(0x02,0x01)
	
	def downleft(self):
		if debug :print 'function from viscalib triggered','downleft'
		return self._cmd_ptd(0x01,0x02)
	
	def downright(self):
		if debug :print 'function from viscalib triggered','downright'
		return self._cmd_ptd(0x02,0x02)

	def stop(self):
		if debug :print 'function from viscalib triggered','stop'
		return self._cmd_ptd(0x03,0x03)
	
	def home(self):
		if debug :print 'function from viscalib triggered','home'
		subcmd='\x04'
		return self._cmd_pt(subcmd)
	
	def reset(self):
		if debug :print 'function from viscalib triggered','reset'
		subcmd='\x05'
		return self._cmd_pt(subcmd)

# The following functions are used for broadcast. It will be nice to have a better orgnaisation, maybe a class Visca_Init?
def _send_broadcast(data,serial=None):
	# shortcut
	return _send_packet(data,-1,serial)

def _if_clear(serial):
	reply=_send_broadcast( '\x01\x00\x01',serial) # interface clear all
	if not reply[1:]=='\x01\x00\x01\xff':
		print "ERROR clearing all interfaces on the bus!"
		sys.exit(1)
	if debug:print "all interfaces clear"
	return reply

def _send_packet(data,recipient=1,serial=None):
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

	serial.mutex.acquire()

	serial._write_packet(packet)
	reply = serial.recv_packet()
	if reply:
		if reply[-1:] != '\xff':
			if debug:print "received packet not terminated correctly: %s" % reply.encode('hex')
			reply=None
		serial.mutex.release()

		return reply
	else:
		return None


def _cmd_adress_set(serial):
	"""
	starts enumerating devices, sends the first adress to use on the bus
	reply is the same packet with the next free adress to use
	"""

	#address of first device. should be 1:
	first=1

	reply = _send_broadcast('\x30'+chr(first),serial) # set address

	if not reply :
		print "No reply from the bus."
		sys.exit(1)

	if type(reply) == None:
		print "No reply from the bus."
		sys.exit(1)

	if len(reply)!=4 or reply[-1:]!='\xff':
		print "ERROR enumerating devices"
		sys.exit(1)

	if reply[0] != '\x88':
		print "ERROR: expecting broadcast answer to an enumeration request"
		sys.exit(1)
	address = ord(reply[2])

	d=address-first
	if d==0:
		sys.exit(1)
		pass
	else:
		print "found %i devices on the bus" % d
		z = 1
		viscams = []
		while z <= d:
			viscams.append('v'+`z`)
			z = z + 1
		return viscams


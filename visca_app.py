#! /usr/bin/env python
# -*- coding: utf-8 -*-
import threading
from time import sleep
from PyVisca.PyVisca import _cmd_adress_set , Visca , _if_clear
from PyVisca.PyVisca import Serial as serial
from pydevicemanager.devicemanager import OSCServer

debug = True

if debug : print '-----serial port initialisation-----'
# create a serial object
serial = serial()
# get a list of serial ports available and select the last one
port = serial.listports()[-1]
if debug : print 'serial port opening : ' + port
# open a connection on the serial object
serial.open(portname=port)
# broadcase a address set command
if debug : print '-----pyvisca module initialisation-----'
viscams = _cmd_adress_set(serial)
if debug : print '-----clearing all buffers-----'
_if_clear(serial)

# this part is ugly but I don't know how to do. the following commented code does'nt work
"""for v in viscams:
	print v
	v = Visca(serial)"""
if len(viscams) == 1:
	v1 = Visca(serial)
if len(viscams) == 2:
	v1 = Visca(serial)
	v2 = Visca(serial)
if len(viscams) == 3:
	v1 = Visca(serial)
	v2 = Visca(serial)
	v3 = Visca(serial)
if len(viscams) > 3:
	print 'only 3 cameras are working for now'
	sys.exit(1)

if debug : print 'Turn off digital zoom aka zoom_digital(False)'
if debug : print v1.zoom_digital(False).encode('hex')
if debug : print 'trig from APP :','datascreen off'
if debug : print v1.noOSD().encode('hex')
#print 'power off'
#v1.power(0)
#sleep(1)
#print 'power on'
#v1.power(1)
#sleep(10)
sleep(2)
print 'home'
v1.home()

# create OSC server
osc = OSCServer(22222,'span')
osc = osc.serverThread.oscServer
# it will be nice to do next lines in devicemanager
# create multi-thread server
#st = threading.Thread(target=osc.serve_forever)
#st.daemon = True
#st.start()
#if debug :print  "Server loop running in thread:", st.name
if debug :print  '----------- VISCA APP LOADED AND RUNNING----------------'

print '---------registering osc callback-----------------'
parameters =  dir(Visca)
for parameter in parameters:
	if not parameter.startswith('_'):
		old = parameter.split('_')
		new = ''
		for item in old:
			new = new+'/'+item
			handler = parameter+'_handler'
		# some commands doesn't need arguments, but it's more simple to send all and ignore these after
		function = 'def '+handler+'(addr, tags, args, source):v1.'+parameter+'(args)'
		exec(function)
		osc.addMsgHandler(parameter,eval(handler))
		#print new , '->' , parameter
print '---------end of registering osc callback----------'
#! /usr/bin/env python
# -*- coding: utf-8 -*-

from time import sleep
#from PyDeviceManager.devicemanager import Serial as serial
from PyVisca.PyVisca import _cmd_adress_set , Visca , _if_clear
from PyVisca.PyVisca import Serial as serial

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


print
print 'POWER :' , v1._query('power') 
print 'ZOOM :' , v1._query('zoom') 
print 'FOCUS :' , v1._query('focus') 
print 'IRIS :' , v1._query('iris') 
print 'IRIS :' , v1._query('AE') 
print 'IR :' , v1._query('IR') 
print 'DISPLAY :' , v1._query('display') 

"""

print 'power off'
v1.power(0)
sleep(1)
print 'power on'
v1.power(1)
sleep(10)
print 'left'
v1.left()
sleep(4)
print ('stop')
v1.stop()
sleep(0.2)
print 'home'
v1.home()
sleep(10)"""
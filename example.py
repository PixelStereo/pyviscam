#! /usr/bin/env python
# -*- coding: utf-8 -*-

from time import sleep
from pyvisca.PyVisca import Viscam, Visca

print '----- visca bus initialisation -----'
# create a visca bus object
cams = Viscam()
# get a list of serial ports available and select the last one
ports = cams.serial.listports()
port = None
for item in ports:
	if 'usbserial' in item:
		port = item
if not port:
	port = ports[0]
print('serial port opening : ' + port)
# open a connection on the serial object
cams.reset(port)
v1 = cams.get_instances()[0]

print('available parameters : ')
print('-------------------------')
prop_list = [p for p in dir(Visca) if isinstance(getattr(Visca, p),property)]
for prop in prop_list:
	v1._query(prop)


"""
v1.power = False
sleep(1)
v1.power = True
sleep(10)
v1.left()
sleep(4)
v1.stop()
sleep(0.2)
v1.home()
sleep(1)"""
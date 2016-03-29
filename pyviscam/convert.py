#! /usr/bin/env python
# -*- coding: utf-8 -*-

def hex_to_int(value):
    if len(value) == 4:
        a=int(value[3],16)
        b=int(value[2],16)
        c=int(value[1],16)
        d=int(value[0],16)
        value = ((((((16*d)+c)*16)+b)*16)+a)
    elif len(value) == 8:
        a=int(value[7],16)
        b=int(value[5],16)
        c=int(value[3],16)
        d=int(value[1],16)
        value = ((((((16*d)+c)*16)+b)*16)+a)
    else:
        print 'error length is :', len(value)
        print("don't understand this reply - this have to be implemented")
    return value

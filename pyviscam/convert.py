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

def i2v(value):
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
    p = (ms&0b11110000)>>4
    r = (ls&0b11110000)>>4
    q = ms&0b1111
    s = ls&0b1111
    return chr(p)+chr(q)+chr(r)+chr(s)

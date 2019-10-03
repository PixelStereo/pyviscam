#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file contains the constants value for camera
For now, these are EVI H 100, but we need a better system
to choose the model of camera, and the constants and features only for this one
"""

queries = {'power':"\x04\x00", 'zoom':"\x04\x47", 'zoom_digital':"\x04\x06",'focus_auto':"\x04\x38", 'focus':"\x04\x48", \
           'focus_nearlimit':"\x04\x28", 'focus_auto_sensitivity':"\x04\x58", 'focus_auto_mode':"\x04\x57", 'focus_ir':"\x04\x11", \
           'WB':"\x04\x35", 'gain_red':"\x04\x43", 'gain_blue':"\x04\x44", 'AE':"\x04\x39", 'slowshutter':"\x04\x5A", \
           'shutter':"\x04\x4A", 'iris':"\x04\x4B", 'gain':"\x04\x4C", 'gain_limit':"\x04\x2C", 'bright':"\x04\x4D", \
           'expo_compensation':"\x04\x3E", 'expo_compensation_amount':"\x04\x4E", 'backlight':"\x04\x33", 'WD':"\x04\x3D", \
           'aperture':"\x04\x42", 'HR':"\x04\x52", 'NR':"\x04\x53", 'gamma':"\x04\x5B", 'high_sensitivity':"\x04\x5E", \
           'FX':"\x04\x63", 'IR':"\x04\x01", 'IR_auto':"\x04\x51", 'IR_auto_threshold':"\x04\x21", 'ID':"\x04\x22", 'version':"\x00\x02", \
           'chromasuppress':"\x04\x5F", 'color_gain':"\x04\x49", 'color_hue':"\x04\x4F", 'info_display':"\x7E\x01\x18", \
           'video':"\x06\x23", 'video_next':"\x06\x33", 'IR_receive':"\x06\x08", 'condition':"\x06\x34",'pan_tilt_speed':"\x06\x11", \
           'pan_tilt':"\x06\x12", 'pan_tilt_mode':"\x06\x10", 'fan':"\x7E\x01\x38"}

answers = {'focus_auto':{2:True,3:False}, 'zoom_digital':{2:True,3:False}, 'WD':{2:True,3:False}, 'focus_ir':{2:True,3:False}, \
           'power':{2:True,3:False}, 'expo_compensation':{2:True,3:False}, 'IR':{2:True,3:False}, 'info_display':{2:True,3:False}, \
           'backlight':{2:True,3:False}, 'IR_auto':{2:True,3:False}, 'HR':{2:True,3:False}, 'high_sensitivity':{2:True,3:False}, \
           'IR_receive':{2:True,3:False}, 'focus_auto_sensitivity':{2:'normal', 3:'low'}, \
           'focus_auto_mode':{0:'normal', 1:'interval', 2:'zoom_trigger'}, 'WB':{0:'auto', 1:'indoor', 2:'outdoor', 3:'trigger', 5:'manual'}, \
           'AE':{0:'auto', 3:'manual', 10:'shutter', 11:'iris', 13:'bright'}, 'slowshutter':{2:'auto', 3:'manual'}, \
           'FX':{0:'normal', 2:'negart', 4:'BW'}, 'fan':{0:True, 1:False}, 'shutter':{21:10000, 20:6000, 19:3500, 18:2500, \
           17:1750, 16:1250 , 15:1000, 14:600, 13:425, 12:300, 11:215, 10:150, 9:120, 8:100, 7:75, 6:50, 5:25, 4:12, 3:6, 2:3, 1:2, 0:1}, \
           'iris':{17:1.6, 16:2, 15:2.4, 14:2.8, 13:3.4, 12:4, 11:4.8, 10:5.6, 9:6.8, 8:8, 7:9.6, 6:11, 5:14, 0:0}, \
           'expo_compensation_amount':{14:10.5, 13:9, 12:7.5, 11:6, 10:4.5, 9:3, 8:1.5, 7:0, 6:-1.5, 5:-3, 4:-4.5, 3:-6, 2:-7.5, 1:-9, 0:-10.5}, \
           'gain':{0:-3, 1:0, 2:+2, 3:+4, 4:+6, 5:+8, 6:+10, 7:+12, 8:+14, 9:+16, 10:+18, 11:+20, 12:+22, 13:+24, 14:+26, 15:+28}, \
           'gain_limit':{4:+6, 5:+8, 6:+10, 7:+12, 8:+14, 9:+16, 10:+18, 11:+20, 12:+22, 13:+24, 14:+26, 15:+28}, \
           'video':{0:'1080i59.95', 1:'1080p29.97', 2:'720p59.94', 3:'720p29.97', 4:'NTSC', 8:'1080i50', 9:'720p50', 10:'720p25', 11:'1080i50', 12:'PAL'}, \
           'video_next':{0:'1080i59.95', 1:'1080p29.97', 2:'720p59.94', 3:'720p29.97', 4:'NTSC', 8:'1080i50', 9:'720p50', 10:'720p25', 11:'1080i50', 12:'PAL'}}

high_res_params = ['shutter', 'iris', 'gain', 'gain_limit', 'gain_red', 'gain_blue', 'bright', 'expo_compensation_amount', 'aperture', 'IR_auto_threshold']

very_high_res_params = ['zoom', 'focus', 'focus_nearlimit', 'focus_auto_interval', 'ID']
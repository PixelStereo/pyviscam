#! /usr/bin/env python
# -*- coding: utf-8 -*-

from pyviscam.convert import scale

def degree_to_visca(value, what, flip=False):
    if what == 'pan':
        # value must be between -170 & 170
        if value >= 0:
            old_min = 0
            old_max = 170
            new_min = 0
            new_max = 7708
        else:
            old_min = -170
            old_max = 0
            new_min = 57829
            new_max = 65535
    elif what == 'tilt':
        # value must be between -20 & 90
        if value >= 0:
            old_min = 0
            old_max = 90
            new_min = 0
            new_max = 4080
        else:
            old_min = -20
            old_max = 0
            new_min = 61455
            new_max = 65535
        if flip:
            # value must be between -90 & 20
            pass
            print('flip function is not yet implemented for tilt')
    return int(scale(value, old_min, old_max, new_min, new_max))

def visca_to_degree(value, what, flip=False):
    if what == 'pan':
        # value must be between -170 & 170
        # value must be between -170 & 170
        if value <= 7708:
            old_min = 0
            old_max = 7708
            new_min = 0
            new_max = 170
        else:
            old_min = 57829
            old_max = 65535
            new_min = -170
            new_max = 0
    elif what == 'tilt':
        # value must be between -20 & 90
        if value <= 4080:
            old_min = 0
            old_max = 4080
            new_min = 0
            new_max = 90
        else:
            old_min = 61455
            old_max = 65535
            new_min = -20
            new_max = 0
        if flip:
            # value must be between -90 & 20
            print('flip function is not yet implemented for tilt')
    value = scale(value, old_min, old_max, new_min, new_max)
    return round(value, 1)


"""
# test
translation = degree_to_visca(22.2, 'pan')
print visca_to_degree(translation, 'pan')
translation = degree_to_visca(-20, 'tilt')
print visca_to_degree(translation, 'tilt')
"""
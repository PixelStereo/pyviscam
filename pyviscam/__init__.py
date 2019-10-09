#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module allows you to control video camera through Visca protocol

-------------------------------------------------------------------------------

    Copyright (c) 2016-2019 Pixel Stereo

-------------------------------------------------------------------------------
Changelog:
-------------------------------------------------------------------------------
- todo - 
	- Python 3 compatibility
	- Threading for ack / completion
	- a real pythonic debug system

- v0.0.5  - Oct. 9th 2019
    - Many Bug Fixes
    - Add Error codes for all serial operations
    - Shutter / Iris / Gain values are now string and no more integers
    - implement video settings properly (only for EVI H100 for now)

- v0.0.1  -  Mar. 26th 2016
    - First draft
"""

debug = 1

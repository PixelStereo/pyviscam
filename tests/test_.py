#! /usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os,sys
from time import sleep
# for 
lib_path = os.path.abspath('./../')
sys.path.append(lib_path)

# for Travis CI
lib_path = os.path.abspath('./../pyvisca')
sys.path.append(lib_path)


from pyvisca import Viscam


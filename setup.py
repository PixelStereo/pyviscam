#!/usr/bin/env python
# -*- coding: utf-8 -*-
from distutils.core import setup

setup(
  name = 'pyviscam',
  packages = ['pyviscam'], 
  version = '0.0.5',
  description = 'Control camera through Visca protocol',
  author = 'Pixel Stereo',
  url='https://github.com/PixelStereo/pyviscam', 
  download_url = 'https://github.com/PixelStereo/pyviscam/tarball/0.0.5.zip', 
  classifiers = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3.4',
    'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)

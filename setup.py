#!/usr/bin/env python

from setuptools import setup
import os
 
 
os.environ["PBR_VERSION"] = "0.1"

setup(
    setup_requires=['pbr'],
    pbr=True,
)

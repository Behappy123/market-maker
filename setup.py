#!/usr/bin/env python
from setuptools import setup, find_packages
from os.path import dirname, join

here = dirname(__file__)

setup(name='bitmex-market-maker',
      version='0.3',
      description='Market making bot for BitMEX API',
      long_description=open(join(here, 'README.md')).read(),
      author='Samuel Reed',
      author_email='sam@bitmex.com',
      url='',
      install_requires=[
          'requests'
      ]
     )

print "\n**** \nImportant!!!\nCopy settings.py.example to settings.py and edit before starting the bot.\n****"

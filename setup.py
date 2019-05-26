#!/usr/bin/env python3

import sys

from setuptools import setup

assert(sys.version_info > (3, 4))


setup(
    name='qospeedtest',
    description='Quick-and-Dirty OoklaServer Speed Test',
    license='GPLv2+',
    author='Ryan Finnie',
    author_email='ryan@finnie.org',
    package_dir={'': 'lib'},
    packages=['qospeedtest'],
    entry_points={
        'console_scripts': [
            'qospeedtest = qospeedtest.client:main',
            'qospeedtest-server = qospeedtest.server:main',
        ],
    },
)

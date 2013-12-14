#!/usr/bin/env python

from distutils.core import setup


setup(
    name='txhttpstream',
    version='1.0',
    packages=['txhttpstream'],
    install_requires=["Twisted", "nose"],
    data_files=[],
    zip_safe=False,
    test_suite='tests',
)


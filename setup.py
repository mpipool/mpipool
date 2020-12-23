#!/usr/bin/env python

import os
import sys

from setuptools import find_packages, setup

requires = ["schwimmbad", "mpi4py", "dill"]

with open("zwembad/__init__.py", "r") as f:
    for line in f.readlines():
        if "__version__ = " in line:
            exec(line.strip())
            break
    else:
        raise Exception("Missing version specification in __init__.py")

with open("README.md") as f:
    long_description = f.read()

setup(
    name="zwembad",
    version=__version__,
    description="MPI Pool similar to futures",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Uwe Schmitt",
    author_email="robingilbert.deschepper@unipv.it",
    maintainer="Robin De Schepper",
    url="https://github.com/Helveg/zwembad",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    keywords="mpipool zwembad",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)

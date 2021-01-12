#!/usr/bin/env python

import os
import sys

from setuptools import find_packages, setup

requires = ["mpi4py>=3.0.3", "dill>=0.3.3"]

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
    description="Parallel MPIPoolExecutor implementing the concurrent.futures interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Robin De Schepper",
    author_email="robingilbert.deschepper@unipv.it",
    url="https://github.com/Helveg/zwembad",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    keywords="mpi pool mpipool zwembad",
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

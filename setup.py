#!/usr/bin/env python

import os
import sys

from setuptools import find_packages, setup

REQUIRES = ["schwimmbad", "mpi4py", "dill"]


LONG_DESCRIPTION = ""

if sys.argv[1] == "sdist":
    LONG_DESCRIPTION = open("README.md").read()

VERSION = "0.1.0"


setup(
    name="mpipool",
    version=VERSION,
    description="MPI Pool similar to multiprocessing",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Uwe Schmitt",
    author_email="uwe.schmitt@id.ethz.ch",
    url="https://gitlab.com/uweschmitt/mpipool",
    packages=find_packages("mpipool"),
    package_dir={"mpipool": "mpipool"},
    include_package_data=True,
    install_requires=REQUIRES,
    license="Proprietary",
    zip_safe=False,
    keywords="mpipool",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)

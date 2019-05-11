#!/usr/bin/env python

import os
import sys

from setuptools import find_packages, setup

REQUIRES = ["schwimmbad", "mpi4py", "dill"]

LONG_DESCRIPTION = """

# About

`mpipool` offers a `Pool` class similar `multiprocessing.Pool`
from the standard library.

Currently `mpipool.Pool` only implements a `map` method.

# Example usage

```
from mpipool import Pool

def add(a, b):
    return a + b

p = Pool()

sums = p.map(add, [(ai, bi) for ai in range(10) for bi in range(10)])

assert len(sums) == 100
assert sums[0] == 0
assert sums[-1] == 18
```

The program must be run on the commandline like:

```
$ mpirun -n 4 python example.py
```

# Credits

`mpipool` uses of the `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/) library.
"""

VERSION = "0.0.1"


setup(
    name="mpipool",
    version=VERSION,
    description="MPI Pool similar to multiprocessing",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Uwe Schmitt",
    author_email="uwe.schmitt@id.ethz.ch",
    url="https://cosmo-docs.phys.ethz.ch/mpipool",
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

#! /usr/bin/env python

from mpipool import Pool


def divide(a, b):
    return a / (b - 3)


p = Pool()

sums = p.map(divide, [(ai, bi) for ai in range(10) for bi in range(10)])


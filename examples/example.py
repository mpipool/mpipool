
from mpipool import Pool


def add(a, b):
    return a + b


p = Pool()

sums = p.map(add, [(ai, bi) for ai in range(10) for bi in range(10)])

assert len(sums) == 100
assert sums[0] == 0
assert sums[-1] == 18

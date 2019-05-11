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


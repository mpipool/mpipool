# About

`mpipool` offers a `Pool` class similar `multiprocessing.Pool`
from the standard library.

`mpipool` uses `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/) library
and circumvents some of its limitations:

- A series of `mpipool.Pool.map` calls do not crash,
- In case a worker raises an exception, the MPI
  tasks are shut down properly so that the full program halts and does
  not hang.

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

sums = p.map(add, [(ai, bi) for ai in range(10) for bi in range(10)])

assert len(sums) == 100
assert sums[0] == 0
assert sums[-1] == 18
```

The program must be run on the commandline like:

```
$ mpirun -n 4 python example.py
```

Currently `mpipool.Pool` only implements a `map` method.

Contrary to the `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/)
the statements after `from mpipool import Pool` are only executed
by the task with rank `0`.


# Credits

`mpipool` uses of the `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/) library.


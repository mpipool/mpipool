# About

`mpipool` offers a `Pool` class similar `multiprocessing.Pool`
from the standard library.

`mpipool` `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/) library.

Currently `mpipool.Pool` only implements a `map` method.

The latest version of [schwimmbad](https://schwimmbad.readthedocs.io/en/latest/)
has some limitations, which `mpipool` avoids:

- Multiple `Pool.map` calls can crash.
- In case a worker raises an exception, the MPI
  tasks were not shut down properly, causing the full program to freeze.

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

Contrary to the `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/)
the statements after `from mpipool import Pool` are only executed
by the task with rank `0`. As such multiple `pool.map` can be used
without

`mpipool` also shuts down all MPI tasks if one of the workers throws
an exception.


# Credits

`mpipool` uses of the `MPIPool` implementation of
[schwimmbad](https://schwimmbad.readthedocs.io/en/latest/) library.


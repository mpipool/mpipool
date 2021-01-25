[![Documentation Status](https://readthedocs.org/projects/zwembad/badge/?version=latest)](https://zwembad.readthedocs.io/en/latest/?badge=latest)

# About

`zwembad` offers an `MPIPoolExecutor` class, an implementation of the
`concurrent.futures.Executor` class of the standard library.

# Example usage

```
from zwembad import MPIPoolExecutor
from mpi4py import MPI

pool = MPIPoolExecutor()

def menial_task(x):
    return x ** MPI.COMM_WORLD.Get_rank()

fs = [pool.submit(menial_task, i) for i in range(100)]

# Wait for all of the results and print them
print([f.result() for f in fs])

# A shorter notation to dispatch the same function with different args
# and to wait for all results is the `.map` method:
results = pool.map(menial_task, range(100))
```

You'll see that some results will have exponentiated either by 1, 2, ..., n depending on
which worker they were sent to.

Different from `mpi4py`s own `MPIPoolExecutor` zwembad is designed to function without
`MPI.Spawn()` for cases where this approach isn't feasible, like supercomputers where
`MPI.Spawn` is usually deliberatly not implemented (for example CrayMPI).

Therefor the pool can only use MPI processes that are spawned when the MPI world is
initialised and must be run from the command line using an MPI helper such as `mpirun`,
`mpiexec` or SLURM's `srun`:

```
$ mpirun -n 4 python example.py
```

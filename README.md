[![Documentation Status](https://readthedocs.org/projects/mpipool/badge/?version=latest)](https://mpipool.readthedocs.io/en/latest/?badge=latest)

# About

`mpipool` offers MPI based parallel execution of tasks through implementations of
Python's standard library interfaces such as `multiprocessing` and `concurrent.futures`.

# MPIExecutor

Executors are objects that return Futures when tasks are submitted. The `MPIExecutor` runs
each task on an MPI process and listens for its reply on a thread that controls the Future
object that was returned to the user.

## Example usage

```
from mpipool import MPIExecutor
from mpi4py import MPI

def menial_task(x):
  return x ** MPI.COMM_WORLD.Get_rank()

with MPIExecutor() as pool:
  pool.workers_exit()
  print("Only the master executes this code.")

  # Submit some tasks to the pool
  fs = [pool.submit(menial_task, i) for i in range(100)]

  # Wait for all of the results and print them
  print([f.result() for f in fs])

  # A shorter notation to dispatch the same function with different args
  # and to wait for all results is the `.map` method:
  results = pool.map(menial_task, range(100))

print("All MPI processes join again here.")
```

You'll see that some results will have exponentiated either by 1, 2, ..., n
depending on which worker they were sent to. It's also important to prevent your
workers from running the master code using the `pool.workers_exit()` call. As a
fail safe any attribute access on the `pool` object handed to workers will
result in an error.

**Note:** Use MPI helpers such as `mpirun`, `mpiexec` or SLURM's `srun`:

```
$ mpirun -n 4 python example.py
```

# MPIPool

Pools execute tasks using worker processes. Use `apply` or `map` to block for task results
or `apply_async` and `map_async` to obtain an `AsyncResult` that you can check or wait for
asynchronously.

## Example usage

```
from mpipool import MPIPool
from mpi4py import MPI

def menial_task(x):
  return x ** MPI.COMM_WORLD.Get_rank()

with MPIPool() as pool:
  pool.workers_exit()
  print("Only the master executes this code.")

  # Block for results
  results = pool.map(menial_task, range(100))

  # Async
  result = pool.map_async(menial_task, range(100))
  print("Done already?", result.ready())

print("All MPI processes join again here.")
```

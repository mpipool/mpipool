[![Documentation Status](https://readthedocs.org/projects/mpipool/badge/?version=latest)](https://mpipool.readthedocs.io/en/latest/?badge=latest)

# About

`mpipool` offers MPI based parallel execution of tasks through implementations of
Python's standard library interfaces such as `multiprocessing` and `concurrent.futures`.
`multiprocessing` is a slightly older library and its interface is not adapted to how
asynchronous programming has evolved in recent years. We advise
to use the `MPIExecutor` pool instead from the more recent `concurrent.futures` interface.

# MPIExecutor

`Executor`s are pool objects that return `Future`s when tasks are submitted. The `MPIExecutor` runs
each task on an MPI (worker) process and listens for its reply on a thread that controls the `Future`
object that was returned to the user. The user's program can continue asynchronously and inspect or
block for the `Future`s result.

## Control flow with pools

Pools usually have a single master script that spawns and controls additional workers who wait idly
for instructions. When using static process management under MPI this is not the case. `n` identical
scripts are started and execute the same code. Once they reach the pool constructor their flow diverges:

* The workers enter the constructor and enter into a loop where they idle for instructions or the 
  shutdown signal.
* The master enters the pool constructor and immediately exits it, code execution continues on the
  master process and it reads the pool instructions to dispatch to the workers.

Once the master process encounters the shutdown command (or when Python shuts down) it sends the
shutdown signal to the workers. These workers will now exit their work loop inside of the constructor,
exit the constructor and if control flow is not well managed they will also attempt, and fail, to
dispatch the pool instructions.

To prevent this using pool objects will usually follow these idioms:

```python
from mpipool import MPIExecutor
from mpi4py.MPI import COMM_WORLD

pool = MPIExecutor()
if pool.is_main():
  try:
    pool.map(len, ([],[]))
  finally:
    pool.shutdown()

# Wait for all the workers to finish and continue together
COMM_WORLD.Barrier()
print("All processes continue code execution")
```

We recommend using a context manager, which guarantees proper shutdown and makes things
slightly neater. The `workers_exit` makes the workers skip the instructions inside of
the `with` block:

```python
from mpipool import MPIExecutor
from mpi4py.MPI import COMM_WORLD

with MPIExecutor() as pool:
  pool.workers_exit()
  pool.map(len, ([], []))

# Wait for all the workers to finish and continue together
COMM_WORLD.Barrier()
print("All processes continue code execution"
```

**Note**: `mpipool` currently does not support dynamic process management, but `mpi4py` does. If
your MPI implementation supports `MPI_Spawn` you can use dynamic process management instead.

## Job submission

To submit a job to the pool use `future = pool.submit(fn, *args, **kwargs)` and `future.result()`
to block and wait for its result.

```python
from mpipool import MPIExecutor
from mpi4py import MPI

def menial_task(x):
  return x ** MPI.COMM_WORLD.Get_rank()

with MPIExecutor() as pool:
  pool.workers_exit()
  # Submit all the task and store their `future`s
  fs = [pool.submit(menial_task, i) for i in range(100)]
  # Wait for all of the `future` results and print them
  print([f.result() for f in fs])
```

### Batch submission

To launch a batch of jobs use the `submit_batch` or `map` function.
Both require the arguments to be given as iterables and will lazily
consume the iterators as previous jobs finish and the next set of arguments
is required.

Using `map` is a shorter notation to dispatch the same function with different args
and to wait for all results:

```python
  results = pool.map(menial_task, range(100))
```

**Note:** `submit_batch` and the `Batch` objects are not part of the
  standard library interfaces.

# MPIPool

Pools execute tasks using worker processes. Use `apply` or `map` to block for task results
or `apply_async` and `map_async` to obtain an `AsyncResult` that you can check or wait for
asynchronously.

## Example usage

```python
from mpipool import MPIPool
from mpi4py import MPI

def menial_task(x):
  return x ** MPI.COMM_WORLD.Get_rank()

with MPIPool() as pool:
  pool.workers_exit()

  # Sync
  results = pool.map(menial_task, range(100))

  # Async
  map_obj = pool.map_async(menial_task, range(100))
  print("Done already?", map_obj.ready())
  results = map_obj.get()
```

**Note:** Use MPI helpers such as `mpirun`, `mpiexec` or SLURM's `srun`:

```
$ mpirun -n 4 python example.py
```

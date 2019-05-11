#! /usr/bin/env python

import atexit
import os
import sys
import time
import traceback

import dill
from schwimmbad import MPIPool


def runs_with_mpi():
    return any(
        n.startswith(prefix)
        for n in os.environ.keys()
        for prefix in ("MPIEXEC_", "OMPI_COMM_WORLD_")
    )


if not runs_with_mpi():
    raise RuntimeError("you must run this programm using mpirun or mpiexec.")
else:
    from mpi4py import MPI


def eval_f(payload):
    f_serialised, args = payload
    if not isinstance(args, tuple):
        args = (args,)
    return dill.loads(f_serialised)(*args)


class Pool(MPIPool):
    def map(self, f, args):
        f_serialised = dill.dumps(f)
        return MPIPool.map(self, eval_f, [(f_serialised, arg) for arg in args])


pool = Pool()


def shutdown():
    pool.close()


atexit.register(pool.close)

if pool.rank > 0:
    try:
        pool.wait()
    except Exception as e:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        MPI.COMM_WORLD.Abort()
    sys.exit(0)

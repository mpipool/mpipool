import atexit
import os
import sys
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
    # put the import in the branch to avoid isort / black shuffling
    # of imports:
    from mpi4py import MPI


def eval_f(payload):
    """helper function to unpack the serialised function and its arguments"""
    f_serialised, args = payload
    if not isinstance(args, tuple):
        args = (args,)
    return dill.loads(f_serialised)(*args)


class Pool(MPIPool):
    def map(self, f, args):
        # we must serialise f, as the workers branch below, so that the
        # f supplied by the client is not defined in the workers global
        # namespace:
        f_serialised = dill.dumps(f)
        payloads = [(f_serialised, arg) for arg in args]
        return MPIPool.map(self, eval_f, payloads)


pool = Pool()

atexit.register(pool.close)

if pool.rank > 0:
    # workers branch here and wait for work
    try:
        pool.wait()
    except:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        # shutdown all mpi tasks:
        MPI.COMM_WORLD.Abort()
    # without the sys.exit below, programm execution would continue after the clients
    # 'import mpipool' instruction:
    sys.exit(0)

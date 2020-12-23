import atexit
import os
import sys
import traceback

import dill
from mpi4py import MPI
from schwimmbad import MPIPool


def eval_f(payload):
    """helper function to unpack the serialised function and its arguments"""
    f_serialised, args = payload
    return dill.loads(f_serialised)(*args)


class Pool(MPIPool):
    def __init__(self):
        if MPI.COMM_WORLD.Get_size() < 2:
            raise RuntimeError("At least 2 MPI processes are required to open a pool.")

        MPIPool.__init__(self)

        atexit.register(lambda: MPIPool.close(self))

        if self.rank > 0:
            # workers branch here and wait for work
            try:
                self.wait()
            except:
                print("worker with rank {} crashed".format(self.rank).center(80, "="))
                traceback.print_exc()
                sys.stdout.flush()
                sys.stderr.flush()
                # shutdown all mpi tasks:
                MPI.COMM_WORLD.Abort()
            # without the sys.exit below, programm execution would continue after the clients
            # 'import mpipool' instruction:
            sys.exit(0)

    def close(self):
        # noop close, would make client code hang, we finally close the pool
        # at exit of the Python interpreter, see __init__ above
        pass

    def map(self, f, *args):
        # we must serialise f, as the workers branch below, so that the
        # f supplied by the client is not defined in the workers global
        # namespace:
        f_serialised = dill.dumps(f)
        payloads = [(f_serialised, arg) for arg in zip(args)]
        return MPIPool.map(self, eval_f, payloads)

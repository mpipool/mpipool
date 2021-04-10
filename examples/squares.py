from mpipool import MPIExecutor
from mpi4py import MPI

pool = MPIExecutor()
# Return the worker ID and square of the input
print(pool.map(lambda x: (MPI.COMM_WORLD.Get_rank(), x ** 2), range(100)))

from mpi4py import MPI

from mpipool import MPIExecutor

pool = MPIExecutor()
# Return the worker ID and square of the input
print(pool.map(lambda x: (MPI.COMM_WORLD.Get_rank(), x**2), range(100)))

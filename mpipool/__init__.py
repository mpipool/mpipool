__author__ = "Robin De Schepper"
__email__ = "robingilbert.deschepper@unipv.it"
__all__ = ["MPIExecutor", "MPIPool", "WorkerExitSuiteSignal"]
__version__ = "1.0.0a1"

from ._futures import MPIExecutor, WorkerExitSuiteSignal
from ._multiprocessing import MPIPool

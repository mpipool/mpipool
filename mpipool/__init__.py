"""
Implementation of the futures and multiprocessing Pool interfaces based on MPI.
"""

__author__ = "Robin De Schepper"
__email__ = "robingilbert.deschepper@unipv.it"
__all__ = ["MPIExecutor", "MPIPool", "WorkerExitSuiteSignal", "enable_serde_logging"]
__version__ = "2.2.0"

from ._futures import MPIExecutor, WorkerExitSuiteSignal, enable_serde_logging
from ._multiprocessing import MPIPool

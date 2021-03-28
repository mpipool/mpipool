import threading
import concurrent.futures
import atexit
import sys
import traceback
import queue
import dill
import warnings
from mpi4py import MPI
from .exceptions import *

MPI.pickle.__init__(dill.dumps, dill.loads)

class _JobThread(threading.Thread):
    """
    Job threads run on the master process and wait for the result from the worker.
    """
    def __init__(self, future, task, args, kwargs):
        super().__init__()
        self._future = future
        self._task = task
        self._args = args
        self._kwargs = kwargs
        self._worker = None

    def run(self):
        if not self._future.set_running_or_notify_cancel():
            # If the future has been cancelled before we're placed on the queue we don't
            # do anything on this thread.
            return

        # If the future is still active we send the task to our assigned worker.
        MPI.COMM_WORLD.send((self._task, (self._args, self._kwargs)), dest=self._worker)
        # Execute a blocking wait on this thread, waiting for the result of the worker on
        # another MPI process
        result = MPI.COMM_WORLD.recv(source=self._worker)
        self._future.set_result(result)

    def assign_worker(self, worker):
        self._worker = worker


class MPIExecutor(concurrent.futures.Executor):
    """
    MPI based Executor. Will use all available MPI processes to execute submissions to the
    pool. The MPI process with rank 0 will continue while all other ranks halt and
    """
    def __init__(self, master=0, comm=None):
        if comm is None:
            comm = MPI.COMM_WORLD
        self._comm = comm
        self._master = master
        self._rank = self._comm.Get_rank()
        self._queue = queue.SimpleQueue()
        self._open = True

        atexit.register(lambda: MPIExecutor.shutdown(self))

        if not self.is_master():
            # The workers enter their workloop here.
            try:
                self._work()
            except Exception:
                traceback.print_exc()
                sys.stdout.flush()
                sys.stderr.flush()
                MPI.COMM_WORLD.Abort()
            # Workers who's been told to quit work resume code here and return out of the
            # pool constructor
            return

        # The master continues initialization here
        self._workers = set(range(self._comm.size))
        self._workers.discard(self._master)
        self._idle_workers = self._workers.copy()
        self._size = self._comm.Get_size() - 1

        if self._size == 0:
            raise MPIProcessError("MPIExecutor requires at least 2 MPI processes.")

    def _work(self):
        while True:
            task = self._comm.recv(source=self._master)
            if task is None:
                break
            func, (args, kwargs) = task
            result = func(*args, **kwargs)
            self._comm.ssend(result, self._master)

    def submit(self, fn, /, *args, **kwargs):
        """
        Submit a task to the MPIPool. ``fn(*args, **kwargs)`` will be called on an MPI
        process meaning that all data must be communicable over the MPI communicator,
        which by default uses pickle.

        :param fn: Function to call on the worker MPI process.
        :type fn: callable
        """
        # Create a future to hand to a new job thread and to return from the function
        # to the user
        f = concurrent.futures.Future()
        job = _JobThread(f, fn, args, kwargs)
        # Schedule the job to be executed on a worker
        self._schedule(job)
        return f

    def map(self, fn, *iterables):
        """
        Submits jobs for as long as all ``iterables`` provide values and places the
        results in a list. The iterables are consumed greedily.
        """
        # Submit all sets of parameters in the given iterables to the pool and collect
        # the results in a list.
        fs = [self.submit(fn, *args) for args in zip(*iterables)]
        return [f.result() for f in fs]

    def _schedule(self, job, handover=None):
        """
        Run a job on an open worker, or on the handover worker. Handover happens when a
        job finishes and another job is available on the queue.
        """
        if handover is None:
            worker = self._reserve_worker()
        else:
            worker = handover

        if worker is not None:
            job.assign_worker(worker)
            self._execute(job)
        else:
            self._queue.put(job, block=False)

    def _reserve_worker(self):
        # Pop a worker from the idle worker set
        try:
            return self._idle_workers.pop()
        except KeyError:
            # If there are no workers a KeyError is thrown and None is returned to signal
            # failure to reserve a worker.
            return None

    def _execute(self, j):
        # A callback is added so that when this job completes the next job should starts
        j._future.add_done_callback(self._job_finished(j))
        j.start()

    def _job_finished(self, job):
        # Create a callback with closure access to the job. The cb schedules the next job
        # from the queue on its worker, or if there's no jobs left in the queue it returns
        # its worker to the idle worker pool.
        def _job_finished_cb(f):
            try:
                # Schedule the next job
                self._schedule(self._queue.get(block=False), handover=job._worker)
            except queue.Empty:
                # No jobs waiting? Let the worker idle
                self._idle_workers.add(job._worker)

        return _job_finished_cb

    def shutdown(self):
        """
        Close the pool and tell all workers to stop their work loop
        """
        if self.is_worker():
            return

        if self._open:
            self._open = False
            for worker in self._workers:
                self._comm.send(None, worker, 0)

    def is_master(self):
        return self._rank == self._master

    def is_worker(self):
        return not self.is_master()

    @property
    def size(self):
        return self._size

    @property
    def idling(self):
        return len(self._idle_workers)

    def __enter__(self):
        if self.is_master():
            return self
        else:
            return ExitObject()

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is WorkerExitSuiteSignal and self.is_worker():
            return True

    def workers_exit(self):
        # The master shouldn't do anything when workers are asked to exit,
        # but workers should have been given an "exit" object by the context
        # manager, so raise an error if this function is called on by a worker.
        if self.is_master():
            return
        raise WorkerExitSuiteSignal()


class ExitObject:
    """
    Object returned from the context manager to all non-master processes. Any
    attribute access on this object will raise a ``WorkerExitSuiteSignal`` so
    that the context is exited.
    """
    def is_master(self):
        warnings.warn("Workers seem to have rejoined the main code, please properly fence off the master code.")
        return False

    def is_worker(self):
        warnings.warn("Workers seem to have rejoined the main code, please properly fence off the master code.")
        return True

    def workers_exit(self):
        raise WorkerExitSuiteSignal()

    def __getattr__(self, attr):
        raise PoolGuardError("Please use the `workers_exit` function at the start of the pool context.")


class WorkerExitSuiteSignal(Exception):
    """
    This signal is raised when a worker needs to exit before executing the suite
    of a ``with`` statement that only the master should execute.
    """
    pass

class PoolGuardError(Exception):
    """
    This error is raised if a user forgets to guard their pool context with a
    :method:`~.pool.MPIExecutor.workers_exit` call.
    """
    pass

import atexit
import collections
import concurrent.futures
import logging
import sys
import threading
import time
import typing
import warnings

import dill
import mpi4py.MPI
import tblib.pickling_support as tb_pickling
from mpi4py import MPI

from .exceptions import MPIProcessError

# Module level logger
_logger = logging.Logger(f"{__name__}:WORLD:{MPI.COMM_WORLD.Get_rank()}")
# Enable traceback pickling patch
tb_pickling.install()
# Set mpi4py to use `dill` as (de)serialization layer.


def _dill_dumps(obj, *args, **kwargs):
    if _logger.isEnabledFor(logging.DEBUG):
        size = sys.getsizeof(obj)
        _logger.debug(f"Serializing {type(obj)} of {size} bytes (arguments: {args}, keyword arguments: {kwargs})")
    ser = dill.dumps(obj, *args, **kwargs)
    if _logger.isEnabledFor(logging.DEBUG):
        _logger.debug(f"Serialized to {len(ser)} bytes.")
    return ser


def _dill_loads(ser, *args, **kwargs):
    if _logger.isEnabledFor(logging.DEBUG):
        _logger.debug(f"Deserializing {len(ser)} bytes (arguments: {args}, keyword arguments: {kwargs})")
    obj = dill.loads(ser, *args, **kwargs)
    if _logger.isEnabledFor(logging.DEBUG):
        size = sys.getsizeof(obj)
        _logger.debug(f"Deserialized to {type(obj)} of {size} bytes.")
    return obj


MPI.pickle.__init__(_dill_dumps, _dill_loads)


def enable_serde_logging():
    stream = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter("[%(asctime)s - %(levelname)s - %(name)s] %(message)s")
    stream.setFormatter(formatter)
    _logger.addHandler(stream)
    _logger.setLevel(logging.DEBUG)


# (func, (args, kwargs))
Task = typing.Tuple[typing.Callable, typing.Tuple[list, dict]]


class _JobThread(threading.Thread):
    """
    Job threads run on the main
     process and wait for the result from the worker.
    """

    def __init__(self, future: concurrent.futures.Future, task: typing.Callable, args, kwargs, logger: logging.Logger):
        # `daemon=True` prevents process from stalling (Python will more agressively kill this thread, which is good).
        super().__init__(daemon=True)
        self._future = future
        self._task = task
        self._args = args
        self._kwargs = kwargs
        self._worker: typing.Optional[int] = None
        self._logger = logger

    def run(self):
        """
        Send the job to the assigned worker and wait for the result on this thread.
        """
        if self._worker is None:
            raise RuntimeError(f"Attempt to run job without an assigned worker.")
        if not self._future.set_running_or_notify_cancel():
            # The future has been cancelled, we don't need to do anything.
            self._logger.debug(f"Bailing out of cancelled job {self}")
            return

        self._logger.info(f"Sending {self} MPI data to worker {self._worker}")
        # Send the task to the assigned worker.
        MPI.COMM_WORLD.send((self._task, (self._args, self._kwargs)), dest=self._worker)
        # Execute a non-blocking wait on this thread, waiting for the result of the worker on
        # another MPI process. Note: Blocking waits like `recv` prevent the threads from being
        # cleaned up and can stall the Python process indefinitively.
        request = MPI.COMM_WORLD.irecv(source=self._worker)
        while True:
            try:
                done, buffer = request.test()
            except Exception as e:
                self._logger.error(f"Unable to read {self} results from worker {self._worker}", exc_info=sys.exc_info())
                done = True
                buffer = (13, e)
            if done:
                break
            else:
                time.sleep(0.0001)

        exit_code, result = buffer
        if exit_code:
            self._logger.info(f"Received MPI exception from worker {self._worker}")
            self._future.set_exception(result)
        else:
            self._logger.info(f"Received MPI result from worker {self._worker}")
            self._future.set_result(result)

    def assign_worker(self, worker: int):
        self._worker = worker

    def cancel(self):
        self._future.cancel()


class MPIExecutor(concurrent.futures.Executor):
    """
    MPI based Executor. Will use all available MPI processes to execute submissions to the
    pool. The MPI process with rank 0 will continue while all other ranks halt and
    """

    def __init__(self, main=0, comm: mpi4py.MPI.Comm = None, rejoin=True, logger=None, loglevel=None):
        if comm is None:
            comm = MPI.COMM_WORLD
        self._comm = comm
        self._main = main
        self._rank = self._comm.Get_rank()
        self._queue = collections.deque()
        self._open = True
        self._rejoin = rejoin
        if logger is not None:
            self._logger = logger
        else:
            self._logger = logging.Logger(f"mpipool:{'main' if self.is_main() else 'worker'}:{self._rank}")
            if loglevel is not None:
                stream = logging.StreamHandler()
                formatter = logging.Formatter("[%(asctime)s - %(levelname)s - %(name)s] %(message)s")
                stream.setFormatter(formatter)
                self._logger.addHandler(stream)
                self._logger.setLevel(loglevel)
            else:
                self._logger.setLevel(logging.CRITICAL)

        atexit.register(lambda: MPIExecutor.shutdown(self))

        if not self.is_main():
            # The workers enter their workloop here.
            self._work()
            # Workers who've been told to quit work resume code here and return out of the
            # pool constructor, unless `rejoin=False`
            self.shutdown()
            if not rejoin:
                self._logger.info("Worker exiting (rejoin=False).")
                exit()
            self._logger.info("Worker rejoining normal code execution.")
            return

        # The master continues initialization here
        self._workers = set(range(self._comm.size))
        self._workers.discard(self._main)
        self._idle_workers = self._workers.copy()
        self._size = self._comm.Get_size() - 1

        if self._size == 0:
            raise MPIProcessError("MPIExecutor requires at least 2 MPI processes.")

    def _work(self):
        self._logger.info("Starting work loop")
        while True:
            try:
                task: Task = self._comm.recv(source=self._main)
                if task is None:
                    self._logger.info("Terminating work loop.")
                    break
                func, (args, kwargs) = task
                self._logger.info(f"Executing task: {func}")
                if self._logger.isEnabledFor(logging.DEBUG):
                    # Shield these logs by an effective check, because processing them into strings/streams is slow.
                    self._logger.debug(f"Task arguments: {args}")
                    self._logger.debug(f"Task keyword arguments: {kwargs}")
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    self._logger.error(f"Task execution error.", exc_info=sys.exc_info())
                    self._error(e)
                else:
                    self._logger.info(f"Task executed.")
                    if self._logger.isEnabledFor(logging.DEBUG):
                        self._logger.debug(f"Task result: {result}")
                    self._comm.ssend((0, result), self._main)
            except Exception as e:
                self._logger.critical(f"Work loop error.", exc_info=sys.exc_info())
                self._error(e)

    def _error(self, exc, exit_code=1):
        self._comm.ssend((exit_code, exc), self._main)

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
        job = _JobThread(f, fn, args, kwargs, self._logger)
        # Schedule the job to be executed on a worker
        self._schedule(job)
        return f

    def submit_batch(self, fn, *iterables):
        """
        Submits jobs lazily for as long as all ``iterables`` provide values.

        :return: A batch object
        :rtype: :class:`.Batch`
        """
        return Batch(self, fn, iterables)

    def map(self, fn, *iterables):
        """
        Submits jobs for as long as all ``iterables`` provide values and returns an
        iterator with the results. The iterables are consumed lazily.
        """
        yield from (f.result() for f in self.submit_batch(fn, *iterables).ordered)

    def _schedule(self, job, handover=None):
        """
        Run a job on an open worker, or on the handover worker. Handover happens when a
        job finishes and another job is available on the queue.
        """
        # Reserve or hand over a worker to the current job
        if handover is None:
            worker = self._reserve_worker()
        else:
            worker = handover

        # If we managed to reserve a worker, assign and execute the job, otherwise queue it for later.
        if worker is not None:
            self._logger.info(f"Executing {job} on worker {worker}.")
            job.assign_worker(worker)
            self._execute(job)
        else:
            self._logger.info(f"No workers available, queueing {job}.")
            self._queue.append(job)

    def _reserve_worker(self):
        # Pop a worker from the idle worker set
        try:
            return self._idle_workers.pop()
        except KeyError:
            # If there are no workers a KeyError is thrown and None is returned to signal
            # failure to reserve a worker.
            return None

    def _execute(self, j):
        # A callback is added so that when this job completes the next job starts
        j._future.add_done_callback(self._job_finished(j))
        j.start()

    def _job_finished(self, job):
        # Create a callback with closure access to the job. The cb schedules the next job
        # from the queue on its worker. If there's no jobs left in the queue it returns
        # its worker to the idle worker pool.
        def _job_finished_cb(f):
            self._logger.info(f"Job {job} finished.")
            try:
                next_job = self._queue.popleft()
            except IndexError:
                # No jobs waiting? Let the worker idle
                self._idle_workers.add(job._worker)
            else:
                # Schedule the next job
                self._schedule(next_job, handover=job._worker)

        return _job_finished_cb

    def shutdown(self, wait=True, *, cancel_futures=False):
        """
        Close the pool and tell all workers to stop their work loop
        """

        if self.is_worker():
            self._open = False
            return

        if self._open:
            self._open = False
            self._logger.info("Shutting down.")
            open_jobs = list(self._queue)
            if cancel_futures:
                self._logger.info(f"Cancelling {len(open_jobs)} jobs.")
                for job in open_jobs:
                    job.cancel()
            if wait:
                not_done = [job._future for job in open_jobs]
                while not_done:
                    self._logger.info(f"Waiting for shutdown of {len(open_jobs)} job threads.")
                    done, not_done = concurrent.futures.wait(not_done, return_when=concurrent.futures.ALL_COMPLETED)
            self._logger.info("Sending shutdown signal to workers.")
            for worker in self._workers:
                self._comm.send(None, worker, 0)
            self._logger.info("Shutdown complete.")

    def is_main(self):
        return self._rank == self._main

    def is_worker(self):
        return not self.is_main()

    @property
    def open(self):
        return self._open

    @property
    def size(self):
        return self._size

    @property
    def idling(self):
        return len(self._idle_workers)

    def __enter__(self):
        if self.is_main():
            return self
        else:
            return ExitObject()

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is WorkerExitSuiteSignal and self.is_worker():
            return True
        self.shutdown()

    def workers_exit(self):
        # The master shouldn't do anything when workers are asked to exit,
        # but workers should have been given an "exit" object by the context
        # manager, so raise an error if this function is called on by a worker.
        if self.is_main():
            return
        raise WorkerExitSuiteSignal()


class ExitObject:
    """
    Object returned from the context manager to all worker processes.
    """

    def is_main(self):
        warnings.warn("Pool object access from worker process. Please fence off the pool code.")
        return False

    def is_worker(self):
        warnings.warn("Pool object access from worker process. Please fence off the pool code.")
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


class PoolGuardError(Exception):
    """
    This error is raised if a user forgets to guard their pool context with a
    :method:`~.pool.MPIExecutor.workers_exit` call.
    """


class Batch:
    """
    A asynchronous interface to a collection of lazily submitted jobs. Can be used to
    check whether all jobs have been submitted already and whether all jobs have finished
    already. The batch can also be waited on, or a blocking call can be made to collect
    the result of the batch as a list.
    """

    def __init__(self, pool, fn, iterables):
        self._pool = pool
        self._fn = fn
        self._itr = enumerate(zip(*iterables))
        self._futures = []
        self._ordered = []
        self._order_queue = []
        self._submitted = False
        self._submit_count = 0
        self._finished = False
        self._finished_count = 0
        for _ in range(pool._size):
            self._submit_next()

    @property
    def submitted(self):
        return self._submitted

    @property
    def finished(self):
        return self._finished

    def _submit_next(self):
        try:
            id, args = next(self._itr)
            self._submit_count += 1
        except StopIteration:
            self._submitted = True
            if not len(self._futures):
                self._finished = True
        else:
            f = self._pool.submit(self._fn, *args)
            f.id = id
            self._futures.append(f)
            f.add_done_callback(self._future_done)

    def _future_done(self, completed_f):
        self._add_ordered(completed_f)
        self._submit_next()
        self._finished_count += 1
        self._finished = self._submitted and self._finished_count == self._submit_count

    def _add_ordered(self, f):
        if len(self._ordered) == f.id:
            # Is this future the next to be added to the ordered result?
            self._ordered.append(f)
            # Go over the queued results in id order to add the next results that might be
            # in the queue already.
            for qf in sorted(self._order_queue, key=lambda f: f.id):
                if len(self._ordered) == qf.id:
                    self._ordered.append(qf)
                    self._order_queue.remove(qf)
        else:
            self._order_queue.append(f)

    def wait(self, *args, **kwargs):
        if not self.submitted and kwargs.get("return_when", "") != "FIRST_COMPLETED":
            warnings.warn(
                "Returning when ALL_COMPLETED or FIRST_EXCEPTION on a not completely"
                + " submitted batch is unsupported and can lead to unexpected results."
            )
        return self._wait(*args, **kwargs)

    def _wait(self, *args, **kwargs):
        return concurrent.futures.wait(self._futures.copy(), *args, **kwargs)

    def result(self):
        while not self.finished:
            self._wait()
        return [f.result() for f in self._ordered]

    def __iter__(self):
        """
        Returns the futures of this batch as soon as they become available as the
        lazy consumption of the input iterables progresses.

        :return: futures iterator
        :rtype: generator
        """
        done = set()
        while not self.finished or len(done) < len(self._futures):
            fs = self._wait(return_when="FIRST_COMPLETED")
            newly_done = set(fs.done) - done
            done.update(fs.done)
            yield from newly_done

    @property
    def futures(self):
        """
        Returns the futures of this batch as soon as they become available as the
        lazy consumption of the input iterables progresses.

        :return: futures iterator
        :rtype: generator
        """
        return iter(self)

    @property
    def ordered(self):
        id = 0
        while not self.finished or id < len(self._ordered):
            if id < len(self._ordered):
                yield self._ordered[id]
                id += 1
            else:
                self._wait(return_when="FIRST_COMPLETED")

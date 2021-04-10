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
import tblib.pickling_support as tb_pickling

tb_pickling.install()
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
        exit_code, result = MPI.COMM_WORLD.recv(source=self._worker)
        if exit_code:
            self._future.set_exception(result)
        else:
            self._future.set_result(result)

    def assign_worker(self, worker):
        self._worker = worker


class MPIExecutor(concurrent.futures.Executor):
    """
    MPI based Executor. Will use all available MPI processes to execute submissions to the
    pool. The MPI process with rank 0 will continue while all other ranks halt and
    """

    def __init__(self, master=0, comm=None, rejoin=True):
        if comm is None:
            comm = MPI.COMM_WORLD
        self._comm = comm
        self._master = master
        self._rank = self._comm.Get_rank()
        self._queue = queue.SimpleQueue()
        self._open = True
        self._rejoin = rejoin

        atexit.register(lambda: MPIExecutor.shutdown(self))

        if not self.is_master():
            # The workers enter their workloop here.
            self._work()
            # Workers who've been told to quit work resume code here and return out of the
            # pool constructor, unless `rejoin=False`
            if not rejoin:
                exit()
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
            try:
                task = self._comm.recv(source=self._master)
                if task is None:
                    break
                func, (args, kwargs) = task
                result = func(*args, **kwargs)
                self._comm.ssend((0, result), self._master)
            except Exception as e:
                self._error(e)

    def _error(self, exc, exit_code=1):
        self._comm.ssend((exit_code, exc), self._master)

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
        warnings.warn(
            "Workers seem to have rejoined the main code, please properly fence off the master code."
        )
        return False

    def is_worker(self):
        warnings.warn(
            "Workers seem to have rejoined the main code, please properly fence off the master code."
        )
        return True

    def workers_exit(self):
        raise WorkerExitSuiteSignal()

    def __getattr__(self, attr):
        raise PoolGuardError(
            "Please use the `workers_exit` function at the start of the pool context."
        )


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

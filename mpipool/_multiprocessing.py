from .exceptions import *
from ._futures import MPIExecutor
import multiprocessing.pool

class MPIPool(multiprocessing.pool.Pool):
    def __init__(self):
        try:
            self._executor = MPIExecutor()
        except MPIProcessError as e:
            raise MPIProcessError("MPIPool requires at least 2 MPI processes.") from None

    def apply_async(self, fn, args=None, kwargs=None):
        if args is None:
            args = tuple()
        if kwargs is None:
            kwargs = dict()
        f = self._executor.submit(fn, *args, **kwargs)
        return AsyncResult(f)

    def map(self, fn, iterable):
        return self.map_async(fn, iterable).get()
    
    def map_async(self, fn, iterable):
        fs = [self._executor.submit(fn, arg) for arg in iter(iterable)]
        return MapAsyncResult(fs)

    def close(self):
        self._executor.shutdown()

    def workers_exit(self):
        self._executor.workers_exit()

    def __del__(self):
        # Check if __del__ has to close anything, if __init__ errored.
        if hasattr(self, "_executor"):
            self.close()

    def __enter__(self):
        return self._executor.__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._executor.__exit__(exc_type, exc, tb)


class AsyncResult(multiprocessing.pool.AsyncResult):
    def __init__(self, f):
        # Future handed to us by the Executor
        self._f = f

    def get(self, timeout=None):
        return self._f.result(timeout)

    def wait(self, timeout=None):
        self._f.result(timeout)

    def ready(self):
        return self._f.done()

    def succesful(self):
        if not self._f.done():
            raise ValueError("Call not finished yet.")
        try:
            # Raises CancelledError or the call exception if not sucessful.
            self._f.result()
        except:
            return False
        else:
            return True

class MapAsyncResult(AsyncResult):
    def __init__(self, fs):
        # List of futures handed to us by the Executor
        self._fs = fs

    def get(self, timeout=None):
        import time

        if timeout is not None:
            timeout = time.time() + timeout
            r = []
            for f in self._fs:
                r.append(f.result(timeout - time.time()))
        else:
            return [f.result() for f in self._fs]

    def wait(self, timeout=None):
        import time

        if timeout is not None:
            timeout = time.time() + timeout
            r = []
            for f in self._fs:
                f.result(timeout - time.time())
        else:
            [f.result() for f in self._fs]

    def ready(self):
        return all(f.done() for f in self._fs)

    def succesful(self):
        for f in self._fs:
            if not f.done():
                raise ValueError("Call not finished yet.")
            try:
                f.result()
            except:
                return False
        else:
            return True

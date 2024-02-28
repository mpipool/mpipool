import concurrent.futures
import time
import unittest
from concurrent.futures import CancelledError

import mpipool


def fx(x):
    return x * 2


def fxy(x, y):
    return x * y


def master(f):
    def master_only(self):
        try:
            self.pool.workers_exit()
            f(self)
        except mpipool.WorkerExitSuiteSignal:
            pass

    return master_only


class TestInterface(unittest.TestCase):
    def setUp(self):
        self.base = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.pool = mpipool.MPIExecutor()

    def tearDown(self):
        self.base.shutdown()
        self.pool.shutdown()

    @master
    def test_submit(self):
        self.compare("submit", fx, 5)
        self.compare_exc("submit", fx, 10, 2)

    @master
    def test_local_fn_submit(self):
        def fx(x):
            return x * 2

        self.compare("submit", fx, 5)
        self.compare_exc("submit", fx, 10, 2)

    @master
    def test_map(self):
        def map_equality(test, o, n):
            test.assertTrue(hasattr(n, "__next__"))
            test.assertEqual(list(o), list(n))

        self.compare("map", fx, (5, 10, 15), _assert=map_equality)
        self.compare("map", len, ([5, 10], [15], [2, 3, 5]), _assert=map_equality)

    def compare(self, attr, *args, _assert=None, **kwargs):
        with self.subTest(attr=attr, sig=(args, kwargs)):
            base_f = getattr(self.base, attr)(*args, **kwargs)
            pool_f = getattr(self.pool, attr)(*args, **kwargs)
            if _assert is None:
                self.assertEqual(base_f.result(), pool_f.result())
            else:
                _assert(self, base_f, pool_f)

    def compare_exc(self, attr, *args, _trigger=None, **kwargs):
        if _trigger is None:
            _trigger = lambda f: f.result()
        with self.subTest(attr=attr, sig=(args, kwargs)):
            with self.assertRaises(Exception) as cm:
                r = getattr(self.base, attr)(*args, **kwargs)
                _trigger(r)
            err = str(cm.exception)
            with self.assertRaises(TypeError) as cm_pool:
                r = getattr(self.pool, attr)(*args, **kwargs)
                _trigger(r)
            err2 = str(cm_pool.exception)
            self.assertEqual(type(err), type(err2))
            self.assertEqual(str(err), str(err2))


class TestNonlocal(unittest.TestCase):
    def setUp(self):
        self.base = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.pool = mpipool.MPIExecutor()

    def tearDown(self):
        self.base.shutdown()
        self.pool.shutdown()

    @master
    def test_nonlocal_fn_submit(self):
        i = 4

        def fx(x):
            nonlocal i
            return i + x * 2

        f = self.pool.submit(fx, 3)
        self.assertEqual(10, f.result())


class TestShutdown(unittest.TestCase):
    def test_wait_nocancel(self):
        t = time.time()
        with mpipool.MPIExecutor() as pool:
            pool.workers_exit()
            [pool.submit(lambda: time.sleep(0.1)) for _ in range(pool.size * 3)]
            pool.shutdown(wait=True, cancel_futures=False)
        self.assertGreater(time.time() - t, 0.2, "should wait all 5 job durations")

    def test_wait_cancel(self):
        t = time.time()
        with mpipool.MPIExecutor() as pool:
            pool.workers_exit()
            [pool.submit(lambda: time.sleep(0.1)) for _ in range(pool.size * 3)]
            pool.shutdown(wait=True, cancel_futures=True)
        self.assertLess(time.time() - t, 0.2, "should wait only 1 job duration")

    def test_nowait_nocancel(self):
        with mpipool.MPIExecutor() as pool:
            pool.workers_exit()
            futures = [pool.submit(lambda: time.sleep(0.01) or 1) for _ in range(pool.size * 5)]
            pool.shutdown(wait=False, cancel_futures=False)
            concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)
            self.assertEqual([1] * pool.size * 5, [f.result() for f in futures])

    def test_nowait_cancel(self):
        with mpipool.MPIExecutor() as pool:
            pool.workers_exit()
            futures = [pool.submit(lambda: time.sleep(0.01) or 1) for _ in range(pool.size * 5)]
            pool.shutdown(wait=False, cancel_futures=True)
            concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)
            with self.assertRaises(CancelledError):
                [f.result() for f in futures]

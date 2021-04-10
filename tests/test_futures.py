import unittest
import mpipool
import concurrent.futures


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
    def test_map(self):
        self.compare("map", fx, (5, 10, 15))
        self.compare("map", len, ([5, 10], [15], [2, 3, 5]))
        self.compare("map", zip, (1, 2, 3, 4), (1, 2, 3, 4))

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

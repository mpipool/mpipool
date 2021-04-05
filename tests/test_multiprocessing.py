import unittest
import mpipool
import multiprocessing

def fx(x):
    return x * 2

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
        self.base = multiprocessing.Pool(processes=4)
        self.pool = mpipool.MPIPool()

    def tearDown(self):
        self.base.close()
        self.pool.close()

    @master
    def test_apply(self):
        self.compare("apply", fx, (5,))
        self.compare_exc("apply", fx, (10, 2))

    @master
    def test_map(self):
        self.compare("map", fx, (5, 10, 15))
        self.compare("map", len, ([5, 10], [15], [2, 3, 5]))

    @master
    def test_apply_async(self):
        def _assert(base, pool):
            self.assertEqual(base.get(), pool.get())
        self.compare("apply_async", fx, (5,), _assert=_assert)
        self.compare_exc("apply_async", fx, (10, 2), _trigger=lambda r: r.get())

    @master
    def test_map_async(self):
        def _assert(base, pool):
            self.assertEqual(base.get(), pool.get())
        self.compare("map_async", fx, range(55), _assert=_assert)

    def compare(self, attr, *args, _assert=None, **kwargs):
        with self.subTest(attr=attr, sig=(args, kwargs)):
            base_r = getattr(self.base, attr)(*args, **kwargs)
            pool_r = getattr(self.pool, attr)(*args, **kwargs)
            if _assert is None:
                self.assertEqual(base_r, pool_r)
            else:
                _assert(base_r, pool_r)

    def compare_exc(self, attr, *args, _trigger=None, **kwargs):
        if _trigger is None:
            _trigger = lambda r: None
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

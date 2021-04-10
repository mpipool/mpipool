import unittest
import mpipool
import multiprocessing


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
    def test_apply_async(self):
        self.compare_async("apply_async", fx, (5,))
        self.compare_exc_async("apply_async", fx, (10, 2))

    @master
    def test_map(self):
        self.compare("map", fx, (5, 10, 15))
        self.compare("map", len, ([5, 10], [15], [2, 3, 5]))

    @master
    def test_map_async(self):
        self.compare_async("map_async", fx, range(55))

    @master
    def test_starmap(self):
        self.compare("starmap", fxy, [(i, i) for i in range(55)])

    @master
    def test_starmap_async(self):
        self.compare_async("starmap_async", fxy, [(i, i) for i in range(55)])

    def compare(self, attr, *args, _assert=None, **kwargs):
        with self.subTest(attr=attr, sig=(args, kwargs)):
            base_r = getattr(self.base, attr)(*args, **kwargs)
            pool_r = getattr(self.pool, attr)(*args, **kwargs)
            if _assert is None:
                self.assertEqual(base_r, pool_r)
            else:
                _assert(self, base_r, pool_r)

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

    def compare_async(self, attr, *args, **kwargs):
        return self.compare(attr, *args, _assert=_assert_async, **kwargs)

    def compare_exc_async(self, attr, *args, **kwargs):
        return self.compare_exc(attr, *args, _trigger=_trigger_async, **kwargs)


def _assert_async(self, base, pool):
    self.assertEqual(base.get(), pool.get())


def _trigger_async(r):
    return r.get()

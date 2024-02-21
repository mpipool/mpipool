import multiprocessing
import unittest

import mpi4py.MPI

import mpipool


def fx(x):
    return x * 2


def fxy(x, y):
    return x * y


class TestInterface(unittest.TestCase):
    """
    Test that the interface and results of the MPIPool match those of multiprocessing.Pool
    """

    def test_apply(self):
        self.compare("apply", fx, (5,))
        self.compare_exc("apply", fx, (10, 2))

    def test_apply_async(self):
        self.compare_async("apply_async", fx, (5,))
        # self.compare_exc_async("apply_async", fx, (10, 2))
        pass

    def test_map(self):
        self.compare("map", fx, (5, 10, 15))
        self.compare("map", len, ([5, 10], [15], [2, 3, 5]))

    def test_map_async(self):
        self.compare_async("map_async", fx, range(55))

    def test_starmap(self):
        self.compare("starmap", fxy, [(i, i) for i in range(55)])

    def test_starmap_async(self):
        self.compare_async("starmap_async", fxy, [(i, i) for i in range(55)])

    def compare(self, attr, *args, _await=None, **kwargs):
        with self.subTest(attr=attr, sig=(args, kwargs)):
            assert_on_this_rank = False
            with mpipool.MPIPool() as pool:
                pool.workers_exit()
                assert_on_this_rank = True
                pool_r = getattr(pool, attr)(*args, **kwargs)
                if _await:
                    pool_r = _await(pool_r)
            with multiprocessing.Pool(processes=4) as base:
                base_r = getattr(base, attr)(*args, **kwargs)
                if _await:
                    base_r = _await(base_r)
            if assert_on_this_rank:
                self.assertEqual(base_r, pool_r)

    def compare_exc(self, attr, *args, _await=None, **kwargs):

        with self.subTest(attr=attr, sig=(args, kwargs)):
            with multiprocessing.Pool(processes=4) as base:
                with self.assertRaises(Exception) as cm:
                    r = getattr(base, attr)(*args, **kwargs)
                    if _await:
                        _await(r)
            err = str(cm.exception)
            cm_pool = None
            with mpipool.MPIPool() as pool:
                pool.workers_exit()
                with self.assertRaises(TypeError) as cm_pool:
                    r = getattr(pool, attr)(*args, **kwargs)
                    if _await:
                        _await(r)
            cm_pool = mpi4py.MPI.COMM_WORLD.bcast(cm_pool)
            err2 = str(cm_pool.exception)
            self.assertEqual(type(err), type(err2))
            self.assertEqual(str(err), str(err2))

    def compare_async(self, attr, *args, **kwargs):
        return self.compare(attr, *args, _await=lambda r: r.get(), **kwargs)

    def compare_exc_async(self, attr, *args, **kwargs):
        return self.compare_exc(attr, *args, _await=lambda r: r.get(), **kwargs)

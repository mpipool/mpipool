import logging
import unittest

import mpipool


class TestErrorHandling(unittest.TestCase):
    def test_single_error(self):
        """
        Test that we propagate worker errors and have traceback info.
        """

        def razer():
            raise Exception("hmm")

        with mpipool.MPIExecutor() as pool:
            pool.workers_exit()
            e = pool.submit(razer).exception()
            self.assertEqual(Exception, type(e))
            self.assertEqual("hmm", str(e))
            self.assertIsNotNone(e.__traceback__, "Traceback wasn't pickled")

    def test_unpickling_error(self):
        """
        Test that we propagate unpickling errors. Regression test for a deadlock issue during unpickling.
        """
        records = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.Logger(__name__)
        logger.addHandler(TestHandler())
        logger.setLevel(logging.ERROR)
        with mpipool.MPIExecutor(logger=logger) as pool:
            pool.workers_exit()
            f = pool.submit(lambda: Ununpicklable())
            e = f.exception()
            self.assertEqual(TypeError, e.__class__)
            self.assertTrue(str(e).endswith("__setstate__() takes 1 positional argument but 2 were given"))


class Ununpicklable:
    def __init__(self):
        self.x = 5

    def __setstate__(self):
        pass

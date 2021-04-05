import unittest, time
import mpipool

class TestErrorHandling(unittest.TestCase):
    def test_single_error(self):
        def razer():
            raise Exception("hmm")

        with mpipool.MPIExecutor() as pool:
            pool.workers_exit()
            e = pool.submit(razer).exception()
            self.assertEqual(Exception, type(e))
            self.assertEqual("hmm", str(e))
            self.assertIsNotNone(e.__traceback__, "Traceback wasn't pickled")

.. mpipool documentation master file, created by
   sphinx-quickstart on Tue Jan 12 23:42:41 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to mpipool's documentation!
===================================

.. image:: https://readthedocs.org/projects/mpipool/badge/?version=latest
   :target: https://mpipool.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   mpipool

Both the package and the docs are pretty minimalistic: You create an
:class:`.MPIExecutor` and either :meth:`~.MPIExecutor.submit` jobs to it
or :meth:`~.MPIExecutor.map` a series of jobs to a list. There's also the
:class:`~.MPIPool` which follows the :class:`~multiprocessing.pool.Pool` interface.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

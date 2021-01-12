.. Zwembad documentation master file, created by
   sphinx-quickstart on Tue Jan 12 23:42:41 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Zwembad's documentation!
===================================

.. image:: https://readthedocs.org/projects/zwembad/badge/?version=latest
:target: https://zwembad.readthedocs.io/en/latest/?badge=latest
:alt: Documentation Status

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   zwembad

Both the package and the docs are pretty minimalistic: You create an
:class:`.pool.MPIPoolExecutor` and either :meth:`~.pool.MPIPoolExecutor.submit` jobs to it
or :meth:`~.pool.MPIPoolExecutor.map` a series of jobs to a list.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

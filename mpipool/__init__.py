__author__ = "Uwe Schmitt"
__email__ = "uwe.schmitt@id.ethz.ch"
__credits__ = "ETH Zurich, Scientific IT Services"


import pkg_resources

from .mpipool import Pool  # noqa

__version__ = pkg_resources.require(__package__)[0].version

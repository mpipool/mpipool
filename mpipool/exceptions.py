from errr.tree import make_tree as _t, exception as _e

_t(globals(), MPIPoolError=_e(
    MPIProcessError=_e()
))

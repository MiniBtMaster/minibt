from setuptools import setup
from Cython.Build import cythonize
import numpy as np

setup(
    ext_modules=cythonize("backtrader_from_signals.pyx"),
    include_dirs=[np.get_include()]
)
# -*- coding: utf-8 -*-
"""
MiniBT 构建脚本（方案 A：构建时现场编译 Cython 扩展）
========================================================

本文件只负责 ``ext_modules``；包发现、``package-data``、元数据等仍由
``pyproject.toml`` 统一管理。

- 构建 wheel / sdist 时会自动把这些 ``.pyx`` 编译成对应平台的扩展模块，
  因此最终 wheel 的平台标签会正确变为 ``cp3xx-cp3xx-<平台>``，不会再被
  误标成 ``py3-none-any``。
- 本地开发（不打包）时可单独执行::

      python setup.py build_ext --inplace

  在源码目录生成 ``.pyd`` / ``.so``，方便直接运行代码。
"""

import os

import numpy as np
from Cython.Build import cythonize
from setuptools import Extension, setup

CYTHON_FUNCTIONS = "minibt/cython_functions"
ZIGZAG = "minibt/zigzag"

# MSVC 用 /O2，其它编译器用 -O3
_extra_compile_args = ["/O2"] if os.name == "nt" else ["-O3"]


def _ext(name: str, source: str) -> Extension:
    """构造一个带 numpy 头文件路径的扩展模块定义。"""
    return Extension(
        name,
        [source],
        include_dirs=[np.get_include()],
        extra_compile_args=_extra_compile_args,
    )


# 需要编译的全部扩展模块（注意：不再包含已废弃的
# "backtrader_from_signals copy 2.pyx"）
_ext_modules = [
    _ext("minibt.cython_functions.backtest_engine",
         f"{CYTHON_FUNCTIONS}/backtest_engine.pyx"),
    _ext("minibt.cython_functions.backtrader_from_signals",
         f"{CYTHON_FUNCTIONS}/backtrader_from_signals.pyx"),
    _ext("minibt.cython_functions.backtrader_pair_from_signals",
         f"{CYTHON_FUNCTIONS}/backtrader_pair_from_signals.pyx"),
    _ext("minibt.cython_functions.signal_profit",
         f"{CYTHON_FUNCTIONS}/signal_profit.pyx"),
    _ext("minibt.zigzag.core",
         f"{ZIGZAG}/core.pyx"),
]


if __name__ == "__main__":
    setup(
        ext_modules=cythonize(
            _ext_modules,
            language_level=3,
            compiler_directives={"language_level": 3},
        ),
    )

# -*- coding: utf-8 -*-
"""
MiniBT 构建脚本（方案 A：构建时现场编译 Cython 扩展）
========================================================

本文件只负责 ``ext_modules``；包发现、``package-data``、元数据等仍由
``pyproject.toml`` 统一管理。

**打包前复位 ``LocalDatas`` 索引**（``minibt/data/utils.py``）**已自动化**：
build_py / sdist 命令会先调用 :func:`reset_local_datas_index`（并有“import 到的
必须是本目录源码”的守卫，绝不会去改 site-packages 里那份）。手动兜底::

    # 在 minibt/ 的**上一层**目录执行（保证 import 到的是源码）
    python -c "import minibt.data.tools as t; print(t.__file__); t.reset_index()"

它调用 ``tools.reset_index()``（＝ ``rewrite(base_only=True)``），把索引里
的用户名（``~/.minibt/datas``，即 C 盘那份）去掉，只留包内基础数据
（``minibt/data/test/*.csv``）—— 否则这些私人名字会被写进 wheel，而对应
CSV 不在 ``package-data`` 里，别人装完会看到一堆取不到数据的名字。
它**只改索引文件**，不会删任何数据；要让某个名字真正消失，得用
``LocalDatas.deleter('名字')`` / ``LocalDatas.keep('名字')`` 删真实文件。

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

# ★ 扩展源码一律用**绝对路径**（基于本文件位置 ✓）：
#   `setup.py` 就住在包里（`minibt/setup.py`），而 setuptools 把
#   ``Extension.sources`` 的**相对路径按“项目根”**解析 —— 也就是说
#   `cd minibt && python -m build --wheel`（pyproject.toml 里写的标准做法）
#   会把 `minibt/cython_functions/xx.pyx` 找成 `minibt/minibt/cython_functions/xx.pyx`
#   → 直接报 `ValueError: '...pyx' doesn't match any files`，**根本打不出包** ✗。
#   换成绝对路径后，在 `minibt/` 里 / 在上一层跑都能编译 ✓。
_HERE = os.path.dirname(os.path.abspath(__file__))
CYTHON_FUNCTIONS = os.path.join(_HERE, "cython_functions")
ZIGZAG = os.path.join(_HERE, "zigzag")

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


def _find_datas_utils() -> str:
    """定位包内 ``data/utils.py``（兼容 setup.py 在包内 / 在仓库根两种布局）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for relative in ("minibt/data/utils.py", "data/utils.py"):
        path = os.path.join(here, relative)
        if os.path.exists(path):
            return os.path.abspath(path)
    return ""


def reset_local_datas_index() -> None:
    """构建前复位 ``LocalDatas`` 索引（``minibt/data/utils.py``，**只列包内基础数据**）。

    为什么要做：本机 ``~/.minibt/datas`` 里的私人数据名会被 `rewrite()` 写进
    ``utils.py``；不打这个补丁，它们就会跟着 wheel 分发给别人（而对应 CSV 不在
    ``package-data`` 里，装完会看到一堆取不到数据的名字）。
    只改索引文件，**不删任何数据**；失败只提示、绝不中断构建。

    「解析到的必须是本目录源码」这道守卫很重要：如果 ``import minibt`` 命中的是
    **已安装的** site-packages，就会去改别人那份，而不是正在打包的源码。
    """
    import subprocess
    import sys

    target = _find_datas_utils()
    if not target:
        print("[minibt] 没找到 data/utils.py，跳过 LocalDatas 索引复位")
        return
    here = os.path.dirname(os.path.abspath(__file__))
    code = ("import minibt.data.tools as t; "
            "print(t.__file__); t.reset_index()")
    env = dict(os.environ)
    roots = [here, os.path.dirname(here)]
    env["PYTHONPATH"] = os.pathsep.join(
        roots + [env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    try:
        done = subprocess.run([sys.executable, "-c", code], cwd=here, env=env,
                              capture_output=True, text=True, timeout=180)
    except Exception as error:                      # 超时 / 没解释器
        print(f"[minibt] 跳过 LocalDatas 索引复位：{error}")
        return
    if done.returncode != 0 or not (done.stdout or "").strip():
        tail = (done.stderr or "").strip().splitlines()[-1:] or ["?"]
        print(f"[minibt] 跳过 LocalDatas 索引复位：{tail[0]}")
        return
    resolved = os.path.abspath((done.stdout or "").splitlines()[0].strip())
    # 比的是**目录**：`target` 是 utils.py，而 import 出来的是同目录下的 tools.py
    if os.path.dirname(resolved) != os.path.dirname(target):
        print(f"[minibt] 跳过 LocalDatas 索引复位（import 到的是 {resolved}）")
        return
    print(f"[minibt] LocalDatas 索引已复位（只列包内基础数据）：{target}")


class _ResetIndexBeforeBuild:
    """构建命令的 mixin：`run()` 之前先复位 `LocalDatas` 索引。"""

    def run(self, *args, **kwargs):
        reset_local_datas_index()
        return super().run(*args, **kwargs)


def _cmdclass() -> dict:
    """把复位钩子挂到 build_py / sdist 上（`python -m build` 会经过它们）。"""
    from setuptools.command.build_py import build_py
    from setuptools.command.sdist import sdist

    def _with(command):
        return type(f"_ResetIndex_{command.__name__}",
                    (_ResetIndexBeforeBuild, command), {})

    return {"build_py": _with(build_py), "sdist": _with(sdist)}


def _ext_modules_for_build():
    """要编译的扩展（`MINIBT_NO_CYTHON=1` → 跳过，纯 Python 也能跑 ✓）

    为什么需要跳过：
    * 没装 MSVC 的机器（全新环境）编译会失败；
    * **`.pyd` 正被运行中的 Python 占用**时会报
      ``could not delete '...core.cp312-win_amd64.pyd': 拒绝访问``
      （用户实测：开着 `minibt desk` 又去 `pip install -e .` ✗）
    * 仓库里已经带了编译好的 `.pyd`，editable 安装直接复用即可 ✓
    """
    flag = str(os.environ.get('MINIBT_NO_CYTHON') or '').strip().lower()
    if flag in ('1', 'true', 'yes', 'on'):
        print('[minibt] MINIBT_NO_CYTHON=1 → 跳过 Cython 扩展编译')
        return []
    from Cython.Build import cythonize as _cythonize
    return _cythonize(
        _ext_modules,
        language_level=3,
        compiler_directives={"language_level": 3},
    )


if __name__ == "__main__":
    setup(cmdclass=_cmdclass(), ext_modules=_ext_modules_for_build())

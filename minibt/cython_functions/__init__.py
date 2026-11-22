"""``minibt.cython_functions`` —— Cython 扩展的统一加载入口。

为什么需要这个模块
------------------
这 4 个扩展是**可选加速件**：编好了（``setup.py build_ext``）就用 C 版本，
没编（比如换了 Python 小版本、`.pyd` 的 ``cpXY`` 对不上）就退回纯 Python。
以前调用点写的是裸 ``from ..cython_functions.xxx import yyy`` —— 一旦 import
失败，用户看到的是

    ImportError: Module use of python312.dll conflicts with this version of Python.

完全看不出「我该干什么」。现在统一走 :func:`load`：

* 编好了 → 返回扩展模块（快）✓
* 没编、但有纯 Python 兜底（``signal_profit`` / ``zigzag.core``）→ 返回兜底 ✓
* 没编、也没有兜底（回测主循环两个）→ 抛 **可读的 RuntimeError**，里面写着
  该怎么编译 ✓

用法::

    from ..cython_functions import load
    from_signals = load('backtrader_from_signals').from_signals

    # 想要"能拿到就用、拿不到就 None"：
    module = load('signal_profit', fallback=False, required=False)
"""
from __future__ import annotations

import importlib

__all__ = ['EXTENSIONS', 'FALLBACKS', 'available', 'load', 'optional']

#: 扩展名 → 一句话说明（报错信息里会带上 ✓）
EXTENSIONS: dict[str, str] = {
    'backtest_engine': '回测主循环（`multi_bt`）',
    'backtrader_from_signals': '信号回测引擎（`signal_backtest` / `bt_from_signals`）',
    'backtrader_pair_from_signals': '配对信号回测引擎（`bt_pair_from_signals`）',
    'signal_profit': '信号持仓收益（`signal_profit`）',
}

#: 扩展名 → 纯 Python 兜底模块（同一个包里，命名 ``<name>_fallback``）✓
#:
#: `zigzag.core` 的兜底就写在 ``minibt/zigzag/core.py`` 里（扩展名优先于
#: ``.py``，所以两边共存不会打架），不在这里登记。
FALLBACKS: dict[str, str] = {
    'signal_profit': 'signal_profit_fallback',
}

#: 检查扩展是否真的可用（import 成功 = 可用；**不**触发兜底 ✓）
_COMPILED: dict[str, bool] = {}

_BUILD_HINT = (
    '请在 minibt 源码目录重新编译 Cython 扩展：\n'
    '    cd minibt\n'
    '    python setup.py build_ext --inplace\n'
    '（需要与当前解释器匹配的 Cython>=3.1.3 与 numpy；\n'
    '  已安装的 wheel 版本不匹配时，请安装对应 Python 小版本的 wheel）'
)


def _describe(name: str) -> str:
    return EXTENSIONS.get(str(name), str(name))


def available(name: str) -> bool:
    """这个扩展**编译版的**能不能 import（带缓存；不触发兜底 ✓）"""
    key = str(name)
    if key in _COMPILED:
        return _COMPILED[key]
    ok = True
    try:
        importlib.import_module(f'{__name__}.{key}')
    except Exception:                                          # noqa: BLE001
        ok = False
    _COMPILED[key] = ok
    return ok


def load(name: str, *, fallback: bool = True, required: bool = True):
    """加载一个 Cython 扩展（可选回退到纯 Python 兜底）。

    Args:
        name: 扩展名（``'signal_profit'`` / ``'backtrader_from_signals'`` …）
        fallback: 编译版加载失败时，是否尝试 ``<name>_fallback`` 纯 Python 版本
        required: 两者都拿不到时抛 ``RuntimeError``（False → 返回 ``None``）

    Returns:
        模块对象（扩展 / 兜底）；``required=False`` 且都拿不到时返回 ``None``

    Raises:
        RuntimeError: ``required=True`` 且既没有扩展也没有兜底
    """
    key = str(name)
    try:
        return importlib.import_module(f'{__name__}.{key}')
    except ImportError as error:
        compile_error: BaseException = error
    except Exception as error:               # noqa: BLE001
        # ABI 不匹配（`Module use of python312.dll conflicts`）不一定抛
        # ImportError，所以这里也要捕 ✓
        compile_error = error

    if fallback:
        target = FALLBACKS.get(key, f'{key}_fallback')
        try:
            return importlib.import_module(f'{__name__}.{target}')
        except Exception:                                      # noqa: BLE001
            ...

    if not required:
        return None

    raise RuntimeError(
        f'minibt 的 Cython 扩展 `{key}`（{_describe(key)}）不可用：'
        f'{compile_error}\n{_BUILD_HINT}'
    ) from compile_error


def optional(name: str):
    """:func:`load` 的简写：拿不到就 ``None``（不抛异常）✓"""
    return load(name, required=False)


def _reset_cache() -> None:
    """清掉 ``available()`` 的缓存（测试 / 热编译后用 ✓）"""
    _COMPILED.clear()

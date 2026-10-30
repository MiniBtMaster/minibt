"""Jupyter 环境自动切换到内联网页版（``Bt.run`` 的 gui 解析）。

历史 bug：``Bt.run(isplot=True)`` 默认 ``gui='pylightcharts'``（原生窗口），
在 Jupyter 里 ``chart.show(block=True)`` 会 ``asyncio.run()`` 嵌套事件循环，
报 ``RuntimeError: asyncio.run() cannot be called from a running event loop``。

现在在**真正的 notebook**（``ZMQInteractiveShell``）里，``pylightcharts`` /
``pylightcharts_web`` 都自动改用内联网页版；普通脚本不变；``Gui.Bokeh`` 仍走 bokeh。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

if not (ROOT / 'minibt' / 'bt.py').exists():
    pytest.skip('minibt 源码不存在（跳过 Jupyter gui 单测）',
                allow_module_level=True)

from minibt.bt import _use_jupyter_inline  # noqa: E402


def test_explicit_jupyter_always_inline(monkeypatch):
    """显式 ``gui='jupyter'`` —— 不管在不在 notebook 都内联。"""
    import minibt.strategy.strategy_window as sw
    monkeypatch.setattr(sw, '_in_notebook', lambda: False)
    assert _use_jupyter_inline('jupyter') is True


def test_notebook_auto_inlines_pylightcharts(monkeypatch):
    """notebook 里 ``pylightcharts`` / ``pylightcharts_web`` 都自动内联。"""
    import minibt.strategy.strategy_window as sw
    monkeypatch.setattr(sw, '_in_notebook', lambda: True)
    for gui in ('pylightcharts', 'light_chart', 'pylightcharts_web',
                'browser'):
        assert _use_jupyter_inline(gui) is True, gui


def test_plain_script_keeps_native_and_web(monkeypatch):
    """普通脚本不变：``pylightcharts`` 开原生窗口、``*_web`` 开浏览器。"""
    import minibt.strategy.strategy_window as sw
    monkeypatch.setattr(sw, '_in_notebook', lambda: False)
    assert _use_jupyter_inline('pylightcharts') is False
    assert _use_jupyter_inline('light_chart') is False
    assert _use_jupyter_inline('pylightcharts_web') is False

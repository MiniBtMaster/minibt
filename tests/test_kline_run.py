"""`KLine.run(...)` 快启动策略：并发 `.ta` 注册 + 默认 pylightcharts 出图。

历史 bug：`TPE.multi_run` 在多个线程里并发调 `multi_apply`
（`KLine.run(["ma1", Multiply(PandasTa.sma, ...)], ...)`），每个线程都会走
`ensure_core_loaded()`。它以前只做一次 ``"minibt.core" not in sys.modules``
判断，但 Python 在**执行模块体之前**就把模块放进 ``sys.modules`` —— 第一个线程
刚开始导入（pandas 的 ``.ta`` 访问器还没注册）时，其它线程看到“已在
sys.modules 里”就跳过，紧接着 ``getattr(df, "ta")`` 抛
``AttributeError: 'DataFrame' object has no attribute 'ta'``。
"""
import inspect

import pytest


def test_ensure_core_loaded_is_thread_safe():
    """`ensure_core_loaded` 必须是双重检查锁，不能只判断 sys.modules。"""
    from minibt import other
    src = inspect.getsource(other.ensure_core_loaded)
    assert '_core_loaded_lock' in src
    assert 'with _core_loaded_lock:' in src
    assert 'from . import core' in src


def _patch(monkeypatch):
    """替换真正开窗口 / 画 bokeh 的出口，记录分发结果。"""
    import minibt.bt as bt_mod
    import minibt.strategy.bokeh_plot as bokeh_mod
    import minibt.strategy.realtime as rt

    monkeypatch.setattr(bt_mod, '_force_browser_without_guard', lambda gui: gui)
    monkeypatch.setattr(bt_mod, '_use_jupyter_inline', lambda gui: False)
    captured = {}

    class FakeChart:
        def __init__(self, strategies, **kw):
            captured['strategies'] = strategies
            captured['kw'] = kw

        def set_backtest_from_strategy(self, strategy):
            captured['backtest'] = strategy

        def show(self, block=False):
            captured['block'] = block

    monkeypatch.setattr(rt, 'RealtimeChart', FakeChart)
    bokeh_calls = []
    monkeypatch.setattr(bokeh_mod, 'plot',
                        lambda *a, **k: bokeh_calls.append((a, k)))
    return captured, bokeh_calls


def test_kline_run_multiple_pandas_ta_indicators(monkeypatch):
    """多个 `Multiply(PandasTa.sma, ...)` 并发跑不能踩 `.ta` 竞态。"""
    pytest.importorskip('minibt')
    from minibt import LocalDatas, Multiply, PandasTa
    try:
        kline = LocalDatas.test.kline.iloc[:1000]
    except Exception:                    # pragma: no cover - 缺数据时跳过
        pytest.skip('拿不到本地测试 K 线')

    captured, bokeh_calls = _patch(monkeypatch)
    bt = kline.run(
        ["ma1", Multiply(PandasTa.sma, dict(length=20))],
        ["ma2", Multiply(PandasTa.sma, dict(length=30))],
        ["ma3", Multiply(PandasTa.sma, dict(length=60))],
        ["ma4", Multiply(PandasTa.sma, dict(length=120))],
        ["ebsw", Multiply(PandasTa.ebsw)],
        isreport=False)

    assert type(bt).__name__ == 'Bt'
    # 默认引擎 = pylightcharts（走 RealtimeChart，不走 bokeh）
    assert captured.get('strategies'), 'KLine.run 默认应走 pylightcharts'
    assert bokeh_calls == []

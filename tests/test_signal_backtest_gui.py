"""`IndFrame.signal_backtest(gui=...)` 的出图引擎分发。

默认引擎是 **pylightcharts**（原生窗口 / 浏览器 / Notebook 内联），只有显式
``gui='bokeh'`` 才走 bokeh —— 与 `Bt.run()` / `btplot` 同一套约定。
"""
import pytest


def _indicator():
    pytest.importorskip('minibt')
    from minibt import LocalDatas
    try:
        kline = LocalDatas.test.kline
    except Exception:                    # pragma: no cover - 缺数据时跳过
        pytest.skip('拿不到本地测试 K 线')
    return kline.tradingview.UT_Bot_Alerts()


def _patch(monkeypatch):
    """替换掉会真正开窗口 / 画 bokeh 的出口，记录分发结果。"""
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
            captured['backtest'] = None

        def set_backtest_from_strategy(self, strategy):
            captured['backtest'] = strategy

        def show(self, block=False):
            captured['block'] = block

    monkeypatch.setattr(rt, 'RealtimeChart', FakeChart)
    bokeh_calls = []
    monkeypatch.setattr(bokeh_mod, 'plot',
                        lambda *a, **k: bokeh_calls.append((a, k)))
    return captured, bokeh_calls


def test_default_gui_is_pylightcharts(monkeypatch):
    captured, bokeh_calls = _patch(monkeypatch)
    _indicator().signal_backtest(isreport=False)
    assert captured['kw']['browser'] is False
    assert captured['kw']['jupyter'] is False
    assert captured['backtest'] is not None      # 回测结果已登记
    assert captured['block'] is True             # 脚本里原生窗口要阻塞
    assert bokeh_calls == []


def test_gui_web_opens_a_browser(monkeypatch):
    captured, bokeh_calls = _patch(monkeypatch)
    _indicator().signal_backtest(gui='pylightcharts_web', isreport=False)
    assert captured['kw']['browser'] is True
    assert captured['kw']['jupyter'] is False
    assert bokeh_calls == []


def test_gui_jupyter_inlines(monkeypatch):
    captured, _ = _patch(monkeypatch)
    import minibt.bt as bt_mod
    monkeypatch.setattr(bt_mod, '_use_jupyter_inline',
                        lambda gui: gui == 'jupyter')
    _indicator().signal_backtest(gui='jupyter', isreport=False)
    assert captured['kw']['jupyter'] is True
    assert captured['kw']['browser'] is False
    assert captured['block'] is False            # 内联不阻塞


def test_gui_bokeh_uses_bokeh(monkeypatch):
    captured, bokeh_calls = _patch(monkeypatch)
    _indicator().signal_backtest(gui='bokeh', isreport=False)
    assert len(bokeh_calls) == 1
    assert captured == {}                        # 不走 RealtimeChart


def test_unknown_gui_raises(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(ValueError):
        _indicator().signal_backtest(gui='nope', isreport=False)

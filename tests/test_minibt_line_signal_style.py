"""``Line`` 的信号样式访问器（历史 bug：读到的是自身那份空配置）。

指标的列（``ind.long_signal`` / ``macd.macdx``）在构造时只建了**自己的**
``PlotInfo``，真正的 ``signalstyle`` 挂在**父级指标**上。以前这些访问器读
``self._plotinfo.signalstyle[sname]`` → 在空 ``Addict`` 上取到空字典：

* ``sig.signal_color`` / ``signal_marker`` / ``signal_size`` / ``signal_key``
  → 返回 ``{}``（不是配置值）✗
* ``sig.set_label('B')`` → ``TypeError: 'Dict' object is not callable`` ✗

现在统一走 ``_line_signal_style(line)``（父级优先，缺失补默认）✓
"""
import pytest


@pytest.fixture(scope='module')
def signal_line():
    from minibt import LocalDatas
    k = LocalDatas.test.kline
    ind = k.tradingview.SingleEMACross(ema1=10, ema2=20)
    return ind, ind.long_signal


def test_signal_accessors_return_real_values(signal_line):
    _, sig = signal_line
    assert isinstance(sig.signal_color, str), sig.signal_color
    assert isinstance(sig.signal_marker, str), sig.signal_marker
    assert isinstance(sig.signal_size, (int, float)), sig.signal_size
    assert isinstance(sig.signal_key, str), sig.signal_key
    assert sig.signal_show is True
    # 标签默认是 SignalLabel（有 text）
    assert getattr(sig.signal_label, 'text', None), sig.signal_label


def test_signal_style_entity_is_signalstyle(signal_line):
    import minibt.strategy.realtime as rt  # noqa: F401  （确保包可用）
    from minibt.indicators.core import _line_signal_style
    _, sig = signal_line
    style = _line_signal_style(sig)
    assert style is not None
    assert hasattr(style, 'set_label')


def test_set_label_works_and_syncs(signal_line):
    ind, sig = signal_line
    sig.set_label('B', size=12)
    assert sig.signal_label.text == 'B'
    assert int(float(sig.signal_label.size)) == 12
    # 父级（真正配置）也同步了
    parent = ind._plotinfo.signalstyle['long_signal']
    assert parent.label.text == 'B'


def test_setters_persist_to_parent(signal_line):
    from minibt import Colors

    ind, sig = signal_line
    sig.signal_color = Colors.blue
    sig.signal_show = False
    assert sig.signal_color == Colors.blue
    assert sig.signal_show is False
    # 重新取一条，读到的还是新值（说明写到了父级）
    fresh = ind.long_signal
    assert fresh.signal_color == Colors.blue
    assert fresh.signal_show is False
    sig.signal_show = True          # 还原，避免影响别的用例


def test_signal_style_setter_replaces_object(signal_line):
    from minibt import Colors, Markers, SignalStyle

    ind, sig = signal_line
    sig.signal_style = SignalStyle('low', Colors.red, Markers.triangle, size=17)
    assert float(sig.signal_size) == 17
    assert sig.signal_marker == Markers.triangle


def test_non_signal_line_returns_none():
    from minibt import LocalDatas
    k = LocalDatas.test.kline
    assert k.close.signal_color is None
    assert k.close.signal_size is None
    assert k.close.signal_label is None

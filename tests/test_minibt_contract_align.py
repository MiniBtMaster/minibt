"""回测结果页多合约 pane 的**时间轴对齐** ✓

问题（用户反馈 + `tradingview/时间刻度不一致的问题.png`）：一个策略里第一个合约
是主图，其它合约（周期不同 / 上市更晚）的数据会因为引擎用**全局时间轴**而整体
偏右 ✗。要求：其它合约的**开始位置与主图对齐** ✓。

修法：``StrategyWindow._contract_frame()`` 把该合约的 ``time`` 列换成主图**从头
开始**的同位置时间戳 ✓（根数不足只用前 N 个 ✓）。
"""
import pathlib

import pandas as pd

REPO = pathlib.Path(__file__).resolve().parents[1]


def _stub(main_times, contract_times):
    from minibt.strategy.strategy_window import StrategyWindow

    class _Stub:
        pass

    _Stub._contract_frame = StrategyWindow._contract_frame
    stub = _Stub()
    stub.chart = type('C', (), {
        'candle_data': pd.DataFrame({'time': list(main_times)})})()
    stub.strategy = 'S'
    stub.loader = lambda strategy, contract: pd.DataFrame({
        'time': list(contract_times), 'open': 1.0, 'high': 1.0,
        'low': 1.0, 'close': 1.0, 'volume': 1.0})
    return stub


def test_contract_frame_starts_where_main_starts():
    """★ 回归：起始更晚的合约，对齐后**第一根 == 主图第一根** ✓"""
    main = list(pd.date_range('2026-01-01', periods=6, freq='D'))
    late = list(pd.date_range('2026-06-01', periods=3, freq='D'))
    out = _stub(main, late)._contract_frame('B')
    assert list(out['time']) == main[:3], '没对齐到主图开头 ✗'
    assert len(out) == 3, '根数不该变 ✓'
    # OHLC 不能被改动 ✓
    assert list(out['close']) == [1.0, 1.0, 1.0]


def test_contract_frame_shorter_than_main_keeps_its_length():
    """副图根数比主图多时：只用主图前 N 个时间戳，**不额外造点** ✓"""
    main = list(pd.date_range('2026-01-01', periods=3, freq='D'))
    long_times = list(pd.date_range('2026-06-01', periods=5, freq='D'))
    out = _stub(main, long_times)._contract_frame('B')
    assert list(out['time'][:3]) == main
    assert len(out) == 5


def test_contract_frame_same_times_is_noop():
    """本来就对齐（同周期同区间）→ 时间列不变 ✓"""
    times = list(pd.date_range('2026-01-01', periods=4, freq='D'))
    out = _stub(times, times)._contract_frame('B')
    assert list(out['time']) == times


def test_contract_frame_handles_missing_main_frame():
    """主图还没就绪（空帧 / 没有 time 列）→ 原样返回，不报错 ✓"""
    from minibt.strategy.strategy_window import StrategyWindow

    class _Stub:
        pass

    _Stub._contract_frame = StrategyWindow._contract_frame
    times = list(pd.date_range('2026-01-01', periods=3, freq='D'))
    stub = _Stub()
    stub.strategy = 'S'
    stub.loader = lambda strategy, contract: pd.DataFrame({'time': times})
    result = _contract_frame = stub._contract_frame
    # chart 都没有
    stub.chart = type('C', (), {'candle_data': pd.DataFrame()})()
    assert list(_contract_frame('B')['time']) == times
    stub.chart = None
    assert list(_contract_frame('B')['time']) == times


def test_panes_use_the_aligned_frame():
    """源码约束：建/同步 pane 都必须走 ``_contract_frame`` ✓（不能直接用 loader）"""
    src = (REPO / 'minibt' / 'strategy' / 'strategy_window.py').read_text(
        encoding='utf-8')
    for name in ('def _build_contract_panes', 'def _sync_contract_panes'):
        start = src.index(name)
        body = src[start:start + 1500]
        assert 'self._contract_frame(contract)' in body, name
        assert 'self.loader(self.strategy, contract)' not in body, name


# --------------------------------------------------------------------------- #
# 副图蜡烛的图例行读数：要和主图一样是 `D|O|H|L|C|V|pct%` ✓
# --------------------------------------------------------------------------- #
def test_contract_frame_carries_volume_for_the_legend():
    """★ 副图蜡烛行要能显示 V（成交量）：LWC 只保留 ``customValues`` ✓

    （其它额外列会被引擎丢掉 ✗，所以把 volume 塞进 ``customValues`` ✓）
    """
    main = list(pd.date_range('2026-01-01', periods=3, freq='D'))
    stub = _stub(main, list(pd.date_range('2026-06-01', periods=3, freq='D')))
    out = stub._contract_frame('B')
    assert 'customValues' in out.columns, '没带上 customValues → 副图读不到成交量 ✗'
    assert out['customValues'].iloc[0] == {'volume': 1.0}


def test_js_bundle_has_candlestick_readout():
    """JS 侧：蜡烛行必须走 `candleReadout`（不再退化成 `low – high` ✗）"""
    bundle = (REPO / 'pylightcharts' / 'js' / 'bundle.js').read_text(
        encoding='utf-8', errors='ignore')
    assert 'candleReadout' in bundle, 'bundle 没重建 / 没有蜡烛读数 ✓'
    assert 'customValues' in bundle


def test_encode_series_data_keeps_dict_columns():
    """★ dict 列（customValues）必须走 JSON 路径 —— base64 路径会 ``str()`` 掉 ✗"""
    import numpy as np
    from pylightcharts.util import (_needs_json, encode_series_data,
                                    js_binary_data)

    n = 3000
    frame = pd.DataFrame({'time': np.arange(n, dtype='int64'),
                          'open': np.ones(n), 'high': np.ones(n) * 2,
                          'low': np.ones(n) * 0.5, 'close': np.ones(n),
                          'volume': np.arange(n, dtype=float)})
    assert _needs_json(frame) is False
    assert encode_series_data(frame) == js_binary_data(frame)   # 老行为 ✓

    frame['customValues'] = [{'volume': float(i)} for i in range(n)]
    assert _needs_json(frame) is True
    out = encode_series_data(frame)
    assert not out.startswith('Lib.decodeData'), 'dict 列走了 base64 → 会丢 ✗'
    assert '"customValues"' in out

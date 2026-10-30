# coding: utf-8
"""minibt 股票数据源：**富途 OpenD** + `kline_random` 瘦身回归测试。

用户需求：

* `get_kline(..., data_source="futu")` 支持富途；没有启动 FutuOpenD / 连不上
  → **直接报错**（而不是静默返回空数据）；
* 新增 `kline_from_futu()` 便捷函数；
* `kline_random` 原来 300+ 行太长 → 重写（行为等价、可复现）。

    pytest tests/test_minibt_futu_source.py
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = REPO / 'minibt' / 'strategy' / 'base.py'

pytestmark = pytest.mark.skipif(
    not BASE.exists(), reason='需要仓库里的 minibt 源码')


def _read() -> str:
    return BASE.read_text(encoding='utf-8')


# ------------------------------------------------------------ futu 数据源
def test_futu_source_is_registered():
    source = _read()
    assert "valid_sources = ['pytdx', 'baostock', 'akshare', 'futu']" in source
    assert 'def _get_futu_data' in source
    assert 'def kline_from_futu' in source
    # 非数字代码（HK.00700 / US.AAPL）也能走 futu 分支
    assert "== 'futu')):" in source
    # futu 自己 add_info（真实 price_tick），不能被 A 股 1e-2 覆盖
    assert "if data_source != 'futu':" in source


def test_futu_code_mapping():
    from minibt.strategy.base import StrategyBase

    assert StrategyBase._futu_code('600000') == 'SH.600000'
    assert StrategyBase._futu_code('000001') == 'SZ.000001'
    assert StrategyBase._futu_code('300750') == 'SZ.300750'
    assert StrategyBase._futu_code('00700') == 'HK.00700'
    assert StrategyBase._futu_code('AAPL') == 'US.AAPL'
    assert StrategyBase._futu_code('HK.00700') == 'HK.00700'
    assert StrategyBase._futu_code('600000.SH') == 'SH.600000'
    with pytest.raises(ValueError):
        StrategyBase._futu_code('1234')            # 4 位数字无法识别


def test_futu_raises_when_opend_is_not_running():
    """OpenD 没开 → RuntimeError（用户要求：直接报错终止 ✓）"""
    from minibt.strategy.base import StrategyBase

    obj = StrategyBase.__new__(StrategyBase)
    with pytest.raises(RuntimeError) as info:
        obj._get_futu_data('600000', 86400, 10, port=1, timeout=1)
    message = str(info.value)
    assert 'FutuOpenD' in message
    assert '127.0.0.1:1' in message


# ------------------------------------------------------- kline_random 重写
def _make_random_strategy():
    from minibt import Strategy

    sid = len(Strategy._strategy_instances)

    class Demo(Strategy):
        def __init__(self):
            self.data = self.kline_random('TEST', 86400, 200, base_price=50)

    strategy = Demo(_sid=sid)
    strategy._prepare_before_strategy_start()
    return strategy.data.pandas_object


def test_kline_random_is_compact():
    """重写后应该短很多（旧实现 300+ 行 ✗）"""
    source = _read()
    block = source[source.index('    def kline_random(self,'):]
    assert block.count('\n') < 150, f'kline_random 仍太长：{block.count(chr(10))} 行'


def test_kline_random_output_is_valid_and_reproducible():
    first = _make_random_strategy()
    second = _make_random_strategy()

    assert list(first.columns)[:6] == ['datetime', 'open', 'high', 'low',
                                       'close', 'volume']
    assert len(first) == 200
    # 可复现（默认 seed=42 ✓）
    assert (first['close'].to_numpy() == second['close'].to_numpy()).all()
    # OHLC 合法 + 无空值
    body_high = first[['open', 'close']].max(axis=1)
    body_low = first[['open', 'close']].min(axis=1)
    assert (first['high'] >= body_high).all()
    assert (first['low'] <= body_low).all()
    assert not first[['open', 'high', 'low', 'close', 'volume']].isna().any().any()
    # 价格不会复利到离谱（|对数偏移| 被限制 → 0.5x~2x 区间 ✓）
    ratio_max = float(first['close'].max()) / 50.0
    ratio_min = float(first['close'].min()) / 50.0
    assert 0.4 < ratio_max < 2.5
    assert 0.4 < ratio_min

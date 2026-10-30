"""指标 NaN 预热比较 / 短数据回归：不能刷 RuntimeWarning 或越界。"""
from __future__ import annotations

import threading
import warnings

from minibt import LocalDatas


def _compute_in_thread(func):
    """在**后台线程**里算指标（desk 的指标就是这么算的 ✓）

    ⚠ numpy 的 `errstate` 是**线程局部**的：`minibt/ta.py` 只在主线程里
    `np.seterr(divide='ignore', invalid='ignore')`，后台线程仍是默认的
    `warn` → 所以这类回归必须在子线程里跑才测得到 ✗
    """
    out = {}

    def work():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            out['result'] = func()
        out['runtime'] = [item for item in caught
                          if issubclass(item.category, RuntimeWarning)]

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    return out['result'], out['runtime']


def test_adaptive_trend_trail_does_not_warn_on_warmup():
    kline = LocalDatas.test.kline.iloc[:500]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = kline.tradingview.AdaptiveTrendTrail()
    runtime = [item for item in caught
               if issubclass(item.category, RuntimeWarning)]
    assert not runtime, [str(item.message) for item in runtime]
    assert result.shape[1] == 8


def test_adx_and_di_does_not_warn_in_worker_thread():
    """预热区间 0/0 与首根 `NaN <= NaN` 不能刷 RuntimeWarning ✓"""
    kline = LocalDatas.test.kline.iloc[:400]

    result, runtime = _compute_in_thread(
        lambda: kline.tradingview.ADX_and_DI())
    assert not runtime, [str(item.message) for item in runtime]
    assert result.shape[1] == 3

    # object dtype（Decimal / 没转换的 CSV）也不能刷 less_equal 警告 ✓
    obj = kline.astype(object)
    _, runtime = _compute_in_thread(
        lambda: obj.tradingview.ADX_and_DI())
    assert not runtime, [str(item.message) for item in runtime]


def test_twin_range_filter_short_history_does_not_index_error():
    kline = LocalDatas.test.kline.iloc[:400]
    result = kline.tradingview.Twin_Range_Filter()
    assert result.shape[1] == 3

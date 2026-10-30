"""`resample` / `replay` 与时区（历史 bug：tz-aware 数据会 ValueError）。

`Strategy.get_kline(..., data_length=…)` 读 CSV 时用
``pd.to_datetime(..., utc=True)``，返回的 ``datetime`` 是 **tz-aware(UTC)**；
而 ``kline_object`` / 重采样索引是 **naive**，于是：

* 在线分支：``df[df.datetime >= data.datetime.iloc[0]]`` → 比较失败
* 本地分支：``_resample`` 混用 → ``ValueError: Cannot mix tz-aware with tz-naive``

现在 ``resample`` / ``replay`` 里先统一去掉 tz（同为 UTC 语义，不影响先后顺序）✓
"""
import pytest


@pytest.fixture(scope='module')
def tz_kline():
    """一条 tz-aware（UTC）的 K 线 + 一个已初始化的策略。"""
    from minibt import LocalDatas, Strategy
    strategy = Strategy()
    kline = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                               data_length=1000)
    return strategy, kline


def test_kline_from_get_kline_is_tz_aware(tz_kline):
    _, kline = tz_kline
    assert kline.datetime.dt.tz is not None


def test_resample_on_tz_aware_kline(tz_kline):
    _, kline = tz_kline
    out = kline.resample(900)                 # 以前 ValueError
    assert out.cycle == 900
    assert 0 < len(out) < len(kline)
    assert out.datetime.dt.tz is None          # 结果统一成 naive


def test_strategy_resample_and_replay_on_tz_aware(tz_kline):
    strategy, kline = tz_kline
    rs = strategy.resample(900, data=kline)
    assert rs.cycle == 900 and len(rs) > 0
    rp = strategy.replay(900, data=kline)
    assert rp.cycle == 900 and len(rp) > 0


def test_resample_still_rejects_bad_cycle(tz_kline):
    _, kline = tz_kline
    for bad in (450, 60):                      # 非整数倍 / 低于主周期
        with pytest.raises(AssertionError):
            kline.resample(bad)


def test_resample_on_naive_kline_unchanged():
    """naive 的 K 线（LocalDatas 直接取的）行为不变。"""
    from minibt import LocalDatas
    kline = LocalDatas.test.kline
    assert kline.datetime.dt.tz is None
    out = kline.resample(900)
    assert out.cycle == 900 and len(out) > 0

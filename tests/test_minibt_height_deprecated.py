"""``PlotInfo.height`` **已废弃**（图表按 pane 比例布局，不再按固定像素高度）✓。

本版（第一步）做法：**保留字段与 `height=` 形参以兼容老脚本**，但
- 不再写进 `PlotInfo`（传了不生效 ✓）；
- `ind.height = 500` 打 `DeprecationWarning` ✓；
- `KLine(df, height=…)` / `upsample(height=…)` / `set_default_candles(…, height=…)`
  都**不报错** ✓。

下一版删字段（见仓库根目录 ``待办计划.md`` ✓）。
"""
import pathlib
import warnings

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _read(*parts):
    return REPO.joinpath(*parts).read_text(encoding='utf-8')


def test_height_kwarg_is_accepted_but_ignored():
    """★ `KLine(df, height=400)` 不报错，且**不生效**（字段保持默认 ✓）"""
    from minibt import KLine, LocalDatas
    from minibt.utils import PlotInfo

    df = LocalDatas.get_dataframe(LocalDatas.test)
    default = PlotInfo().height
    kline = KLine(df, height=400)               # 老脚本照旧能跑 ✓
    assert kline._plotinfo.height == default, 'height 竟然还生效了 ✗'


def test_indicator_height_kwarg_is_ignored():
    from minibt import LocalDatas
    from minibt.utils import PlotInfo

    ind = LocalDatas.test.kline.close.sma(5)
    assert ind._plotinfo.height == PlotInfo().height


def test_setting_indicator_height_warns_deprecated():
    from minibt import LocalDatas

    ind = LocalDatas.test.kline.close.sma(5)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        ind.height = 500
    assert any(issubclass(w.category, DeprecationWarning) for w in caught), \
        'setter 没打弃用警告 ✗'


def test_upsample_height_kwarg_still_accepted():
    from minibt import LocalDatas

    ind = LocalDatas.test.kline.close.sma(5)
    ind.upsample(height=400)                    # 不报错 ✓
    assert ind is not None


def test_set_default_candles_does_not_write_height():
    """蜡烛路径（`set_default_candles`）也不该再写 height ✓"""
    from minibt.utils import PlotInfo

    info = PlotInfo()
    before = info.height
    info.set_default_candles(8000.0, height=450)
    assert info.height == before, 'set_default_candles 还在写 height ✗'


def test_source_guards():
    """源码约束：`PlotInfo` 里已标注废弃、且不再把 height 传进 PlotInfo ✓"""
    utils = _read('minibt', 'utils.py')
    assert '已废弃' in utils
    assert 'self.height = height' not in utils

    core = _read('minibt', 'indicators', 'core.py')
    assert 'height=height,' not in core, '还在把 height 传进 PlotInfo ✗'
    assert 'set_default_candles(current_close[-1], self.height)' not in core

    base = _read('minibt', 'indicators', 'base.py')
    assert 'DeprecationWarning' in base


def test_height_kwarg_still_in_docstrings_but_marked_deprecated():
    """文档里提到 height 的地方要能看出“已废弃” ✓（避免用户继续抄 ✗）"""
    doc = _read('minibt', 'utils.py') + _read('minibt', 'indicators', 'base.py')
    index = doc.find('height')
    assert index >= 0
    # 至少有一处明确写了“已废弃”✓（更细的逐条文案在待办计划里继续清理 ✓）
    assert doc.count('已废弃') >= 2

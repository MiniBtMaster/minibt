"""图表主题统一：``Config.theme`` / ``Strategy.theme`` / ``resolve_theme``。

主题同时作用于 pylightcharts（``StrategyWindow``）与 bokeh（``btplot`` /
``bokeh_plot``）：默认 ``'light'``，可用 ``Config(theme=...)`` 或策略里的
``self.theme = 'light'`` 覆盖，旧参数 ``black_style`` 仍兼容。
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if not (ROOT / 'minibt' / 'utils.py').exists():
    # 从 sdist 运行、或只装了 pip 版 minibt 时没有这个文件，整份跳过
    pytest.skip('minibt/utils.py 不存在（跳过主题/Config 映射单测）',
                allow_module_level=True)

from minibt.utils import (Config, resolve_theme, theme_is_dark,   # noqa: E402
                          resolve_toolbox, resolve_grid, resolve_fullscreen,
                          normalise_y_margin, DEFAULT_Y_MARGIN)
from minibt.strategy.strategy import Strategy                    # noqa: E402


# ------------------------------------------------------------------ Config

def test_config_theme_defaults_to_light():
    assert Config().theme == 'light'
    assert Config(theme='light').theme == 'light'


def test_config_bokeh_fullscreen_defaults_to_none():
    assert Config().bokeh_fullscreen is None
    assert Config(bokeh_fullscreen=False).bokeh_fullscreen is False
    assert Config(bokeh_fullscreen=True).bokeh_fullscreen is True


def test_resolve_fullscreen_auto():
    class S:
        def __init__(self, cfg):
            self.config = cfg
    # None（未设置）：Jupyter → False，浏览器 → True
    assert resolve_fullscreen(None, jupyter=True) is False
    assert resolve_fullscreen(None, jupyter=False) is True
    assert resolve_fullscreen(S(Config(bokeh_fullscreen=False)),
                              jupyter=False) is False
    assert resolve_fullscreen(S(Config(bokeh_fullscreen=True)),
                              jupyter=True) is True


def test_config_grid_defaults_to_true():
    assert Config().grid is True
    assert Config(grid=False).grid is False


# ------------------------------------------------------- 价格轴上下余量

def test_y_margin_is_a_config_field():
    """价格轴余量：``Config.y_margin``（默认 None）+ ``run(y_margin=...)`` 临时覆盖。"""
    assert hasattr(Config(), 'y_margin')
    assert Config().y_margin is None            # None = 用 DEFAULT_Y_MARGIN
    assert Config(y_margin=0.02).y_margin == 0.02


def test_normalise_y_margin_accepts_float_and_pair():
    # 默认 0.1（LWC 自带 0.2/0.1 上下太空、图表被压）
    assert normalise_y_margin(None) == (0.1, 0.1)
    assert DEFAULT_Y_MARGIN == 0.1
    assert normalise_y_margin(0.1) == (0.1, 0.1)
    assert normalise_y_margin((0.02, 0.08)) == (0.02, 0.08)
    assert normalise_y_margin([0.05]) == (0.05, 0.05)
    assert normalise_y_margin(0.0) == (0.0, 0.0)        # 铺满
    assert normalise_y_margin((0.2, 0.1)) == (0.2, 0.1)  # 回到 LWC 原样
    assert normalise_y_margin(2.0) == (0.9, 0.9)        # 上限 0.9
    assert normalise_y_margin(-1.0) == (0.0, 0.0)       # 下限 0
    assert normalise_y_margin('x') == (0.1, 0.1)        # 非法 -> 默认
    assert normalise_y_margin(None, default=None) is None


def test_strategy_window_applies_y_margin_to_every_pane():
    """默认 0.1，主图 + 各指标副图的价格轴都下发 scaleMargins。

    ``y_margin=(0.2, 0.1)`` 可以回到 lightweight-charts 原样。
    """
    import minibt.strategy.strategy_window as sw
    from pylightcharts.headless import HeadlessChart
    original = sw.Chart
    sw.Chart = lambda *a, **kw: HeadlessChart(
        **{k: v for k, v in kw.items() if k != 'title'})
    try:
        for value, expect in ((None, '"top":0.1'),
                              ((0.2, 0.1), '"top":0.2')):
            window = sw.StrategyWindow(['S'], lambda n: ['C1'], browser=False,
                                       y_margin=value)
            pane = window.chart.add_pane()          # 主图 + 1 个副图
            window.chart.pane_add_series(pane, 'Line', name='ma')
            window.chart._scripts.clear()
            window._apply_y_margin()
            scripts = [s for s in window.chart._scripts
                       if 'scaleMargins' in s]
            # 2 个 pane x right/left = 4 条
            assert len(scripts) == 4, (value, scripts)
            assert all(expect in s for s in scripts), (value, scripts)
    finally:
        sw.Chart = original


def test_resolve_grid_reads_config():
    class S:
        def __init__(self, cfg):
            self.config = cfg
    assert resolve_grid(S(Config())) is True
    assert resolve_grid(S(Config(grid=False))) is False
    assert resolve_grid(None, default=True) is True


def test_rresolve_toolbox_priority():
    # 策略里显式 self.toolbox 优先，其次 config.toolbox，最后 default
    class S:
        def __init__(self, explicit=None, cfg=None):
            self.config = cfg if cfg is not None else Config()
            if explicit is not None:
                self.__dict__['_toolbox'] = explicit
    assert resolve_toolbox(S()) is False                    # config 默认 False
    assert resolve_toolbox(S(cfg=Config(toolbox=True))) is True
    assert resolve_toolbox(S(explicit=True)) is True        # self.toolbox=True 覆盖
    assert resolve_toolbox(S(explicit=False,
                             cfg=Config(toolbox=True))) is False
    assert resolve_toolbox(None, default=True) is True


# --------------------------------------------------------------- resolve_theme

def test_resolve_theme_default_is_light():
    assert resolve_theme() == 'light'
    assert theme_is_dark() is False


def test_resolve_theme_explicit_wins():
    assert resolve_theme('light') == 'light'
    assert theme_is_dark('light') is False
    # 大小写/空白归一化
    assert resolve_theme('  LIGHT ') == 'light'
    assert resolve_theme('Dark') == 'dark'


def test_resolve_theme_black_style_legacy_alias():
    # 显式 black_style 优先（旧参数兼容），True=深色 / False=浅色
    assert resolve_theme('light', True) == 'dark'
    assert resolve_theme('dark', False) == 'light'


class _FakeStrategy:
    def __init__(self, theme=None, cfg=None):
        self._theme = theme
        self.config = cfg

    @property
    def theme(self):
        if self._theme is not None:
            return self._theme
        return getattr(self.config, 'theme', 'light')


def test_resolve_theme_falls_back_to_strategy():
    assert resolve_theme(strategy=_FakeStrategy('light')) == 'light'
    assert resolve_theme(strategy=_FakeStrategy(cfg=Config(theme='light'))) \
        == 'light'
    assert resolve_theme(strategy=_FakeStrategy(cfg=Config())) == 'light'
    # 显式 theme 仍优先于策略
    assert resolve_theme('dark', strategy=_FakeStrategy('light')) == 'dark'


def test_resolve_theme_ignores_objects_without_theme():
    assert resolve_theme(strategy=object()) == 'light'


# ------------------------------------------------------------ Strategy.theme

def test_strategy_theme_falls_back_to_config():
    strategy = object.__new__(Strategy)
    strategy.config = Config()
    assert strategy.theme == 'light'

    strategy.config = Config(theme='light')
    assert strategy.theme == 'light'


def test_strategy_theme_can_be_overridden_via_self_theme():
    strategy = object.__new__(Strategy)
    strategy.config = Config()                  # 默认 light
    strategy.theme = 'light'                    # 等价于策略里 self.theme = 'light'
    assert strategy.theme == 'light'
    # 覆盖优先于 config
    strategy.config = Config(theme='dark')
    assert strategy.theme == 'light'
    # 大小写归一化 + 空白
    strategy.theme = '  LIGHT '
    assert strategy.theme == 'light'

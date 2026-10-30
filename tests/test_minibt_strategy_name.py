"""K 线上方的「策略名」在 pylightcharts / bokeh 里不再重复显示。

* pylightcharts：``StrategyWindow`` 页面顶栏已显示策略名 → 图例 ``text``
  不再放策略名；``bars != 'both'``（顶栏被隐藏，如 btplot）时保留 ✓。
* bokeh：单策略时不再套一层「策略名」外层标签页（btplot 走 ``btplot.py``，
  不受影响）✓。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
WINDOW = REPO / 'minibt' / 'strategy' / 'strategy_window.py'
BOKEH = REPO / 'minibt' / 'strategy' / 'bokeh_plot.py'


def test_pylightcharts_legend_name_gated_by_topbar():
    source = WINDOW.read_text(encoding='utf-8')
    assert "self._strategy_in_legend = str(bars) != 'both'" in source
    # 图例 text 按 flag 取（顶栏可见 → 空）
    assert 'text=self.strategy if self._strategy_in_legend else ' in source
    assert 'text=strategy if self._strategy_in_legend else ' in source
    # 至少 3 处（初始 / set_strategy / 恢复 K 线图例）
    assert source.count('self._strategy_in_legend') >= 4


def test_bokeh_single_strategy_drops_outer_tab():
    source = BOKEH.read_text(encoding='utf-8')
    assert 'if len(ts) == 1:' in source
    assert 'tabs = ts[0]' in source
    # 单策略时把内层 100% 换成 100vh（外层 fullscreen CSS）
    assert 'FULLSCREEN_TABS_INNER_CSS' in source
    assert 'styles.append(FULLSCREEN_TABS_CSS)' in source
    # 多策略仍然保留外层策略标签页（可切换）
    assert 'all_panels = [Panel(child=t, title=s_name[i])' in source

"""图表左上角「K 线信息 + 指标标签」的**默认字号 = 13** ✓

用户反馈字号过小 ✗（原样：初始图例硬编码 12、库默认 11）。minibt 本来就有一整套
字号机制（顶栏「设置 → 字号」、8~24、持久化到 ``setting.json``）✓，所以正确做法是：

* 把**默认值**从 12 改成 **13**（``LEGEND_FONT_SIZE``）✓；
* 各处 legend() 用**当前生效**的 ``self._font_size`` ✓ —— 而不是硬编码 ✗，
  否则 ``set_strategy`` / 切回测结果页时会把用户在设置里改过的字号**重置**掉 ✗。
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]


def _src() -> str:
    return (REPO / 'minibt' / 'strategy' / 'strategy_window.py').read_text(
        encoding='utf-8')


def test_default_legend_font_size_is_13():
    """★ 默认字号 = 13（契约 / 回测结果页都一样 ✓）"""
    from minibt.strategy import strategy_window as sw

    assert sw.LEGEND_FONT_SIZE == 13
    assert sw._DEFAULT_SETTINGS['font_size'] == sw.LEGEND_FONT_SIZE
    assert sw._DEFAULT_SETTINGS['font_size'] != 12, '还是老的 12 ✗'


def test_legend_calls_use_the_live_font_size():
    """★ 所有 legend() 都要用 ``self._font_size``（用户改过就用用户的 ✓）"""
    src = _src()
    calls = re.findall(r'chart\.legend\((.*?)\)', src, re.S)
    assert calls, '没找到 legend 调用 ✗'
    # 每个「可见」的 legend 调用都必须带 font_size=self._font_size ✓
    for call in calls:
        if 'visible=False' in call:
            continue
        if '**options' in call:
            continue      # `_apply_font` 用当前值重发 ✓（合法）
        assert 'font_size=self._font_size' in call, \
            f'legend() 没带当前字号（会被重置成硬编码值 ✗）：{call[:90]}'
    # 不能再有硬编码的 12/13 ✗（13 只允许出现在 LEGEND_FONT_SIZE 定义处 ✓）
    assert 'font_size=12' not in src
    assert 'font_size=13' not in src


def test_user_setting_still_wins_over_default():
    """持久化的用户设置优先于默认值 ✓（只是把兜底从 12 换成 13 ✓）"""
    src = _src()
    assert "_settings['user'].get('font_size', LEGEND_FONT_SIZE)" in src
    assert "_DEFAULT_SETTINGS.get('font_size'," in src
    # 改字号仍然会存盘 ✓；应用时同时改图例 ✓
    assert '_save_user_settings(font_size=self._font_size)' in src
    assert "self.chart.legend(**{**options, 'font_size': size})" in src
    assert "self.chart.apply_options(layout={'font_size': size})" in src


def test_legend_font_size_covers_contract_and_result_page():
    """合约页（set_strategy）与回测结果页（_show_info）都要套上 ✓"""
    src = _src()
    for name in ('def set_strategy', 'def _show_info', 'def _restore_legend'):
        start = src.index(name)
        body = src[start:start + 2200]
        assert 'font_size=self._font_size' in body, name

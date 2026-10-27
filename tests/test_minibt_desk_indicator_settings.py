"""指标设置卡（图例 ⚙）的行为回归：颜色 / 显示 / 位置 / 本地图表默认面板。

用户 2026-10-26 反馈的四点：

1. 指标线颜色（预留色块 + 最后的「＋」调色板）选了不生效；
2. 「显示该指标」应和图例 👁 一致（只隐藏线、不删指标标签），状态要同步；
3. 指标的 `overlap` 是 True/False 混合（主图 + 副图都有线）时，「位置」
   要显示「主副图」且不可改；其余情况可改，初始值 = 指标当前设置；
4. 本地图表打开时，交易 / 编辑器面板默认关闭。

前端逻辑已由 `jslib/test/indicator-settings.test.ts`（vitest）做行为用例；
这里再把**源码 / 构建产物**的关键约定钉住，避免回退。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


# ---------------------------------------------------------------- 1. 颜色
def test_settings_card_previews_colour_immediately():
    card = _read('jslib/src/desk/indicator-settings.ts')
    assert 'onColorPreview' in card
    # 色块点击 / 调色板 input 都要触发预览 ✓
    assert card.count('preview();') >= 2
    # 调色板按钮的 ＋ 号缺失时不能抛（Qt 里 querySelector 可能拿不到）
    assert 'if (plus) plus.style.opacity' in card


def test_pages_apply_style_and_refresh_legend_colour():
    chart = _read('jslib/src/desk/chart-page.ts')
    local = _read('jslib/src/desk/local-chart-page.ts')
    for source in (chart, local):
        assert 'onColorPreview: (color)' in source
        assert 'layer.applyStyle(item.key, currentState(color))' in source
        # 自定义图例的色点也要跟着改 ✓
        assert 'rememberColor(color)' in source
    # 副图序列在后端每次推送后重新套上颜色 / 线宽 / 线型 ✓
    layer = _read('jslib/src/desk/indicator.ts')
    assert 'private _paintLegend(' in layer
    assert 'color: item.color' in layer
    assert layer.count('crosshairMarkerVisible') >= 2


def test_line_data_has_no_per_point_colour():
    """★ LWC 会拿**逐点** `color` 覆盖序列 `color` → 设置卡改颜色就不生效了

    所以 `_gapLineData` 只给**缺口点**透明色，有效点不能带颜色。
    """
    layer = _read('jslib/src/desk/indicator.ts')
    assert 'void color;' in layer                 # 有效点不再写 color ✓
    assert "color: 'rgba(0,0,0,0)'" in layer      # 缺口点仍然透明 ✓
    assert 'private _lineDataFor(' in layer
    # 换颜色后要把已画的数据重设一遍（本地图表没有后续推送 ✓）
    assert 'target.setData(this._lineDataFor(item, state.color)' in layer


def test_legend_dot_uses_the_saved_colour():
    chart = _read('jslib/src/desk/chart-page.ts')
    local = _read('jslib/src/desk/local-chart-page.ts')
    for source in (chart, local):
        assert 'layer.styleOf(item.key).color' in source


# ---------------------------------------------------------------- 2. 显示
def test_visible_switch_uses_the_eye_path():
    chart = _read('jslib/src/desk/chart-page.ts')
    local = _read('jslib/src/desk/local-chart-page.ts')
    for source in (chart, local):
        # 「显示该指标」= 和图例 👁 同一条路径（toggleIndicator）✓
        assert 'this.toggleIndicator(item.key, !!state.visible, cell)' in source
        # ★ 眼睛 / 设置都只隐藏**指标线**：不能再按 hidden 过滤 items
        #   （过滤 = 指标标签跟着消失 ✗），也不再有 `_visibleItems`
        assert '_visibleItems' not in source
        assert 'layer.setVisible(key, show);' in source
        # 后端下一次全量推送时，隐藏状态用 `visible:false` 打标而不是删掉 ✓
        assert 'private _drawItems(' in source
        assert 'items: this._drawItems(cell' in source


def test_eye_icon_and_series_visibility_share_one_state():
    legend = _read('jslib/src/general/legend.ts')
    layer = _read('jslib/src/desk/indicator.ts')
    # 眼睛图标状态以 series.options().visible 为准（不再用闭包变量）✓
    assert 'setSeriesVisible(series: ISeriesApi<SeriesType>' in legend
    # 图层：设置卡 / 眼睛 → 只 applyOptions({visible})，标签不动 ✓
    assert 'legend?.setSeriesVisible?.(series, visible);' in layer
    assert 'if (saved.visible !== undefined) item.visible = saved.visible;' in layer
    assert 'visible: item.visible !== false' in layer


def test_settings_card_reads_current_visibility():
    page = _read('jslib/src/desk/chart-page.ts')
    # 打开卡片时「显示该指标」要反映当前状态（含 👁 隐藏过的）✓
    assert 'visible: saved.visible ?? !hidden.has(item.key)' in page


# ---------------------------------------------------------------- 3. 位置
def test_overlay_mixed_locks_the_position_select():
    card = _read('jslib/src/desk/indicator-settings.ts')
    assert 'overlayLocked' in card
    assert "'主副图'" in card
    assert 'areaSelect.disabled = locked' in card
    # 固定时不能把 'mixed' 当成“改成副图”✓
    assert 'overlay: locked ? state.overlay' in card

    chart = _read('jslib/src/desk/chart-page.ts')
    local = _read('jslib/src/desk/local-chart-page.ts')
    for source in (chart, local):
        assert 'private _overlayLocked(' in source
        assert 'overlayLocked,' in source
        # 位置可改时才发 add_indicator ✓
        assert 'if (!overlayLocked && !!state.overlay !== !!item.overlay)' in source


def test_card_initial_position_matches_indicator():
    card = _read('jslib/src/desk/indicator-settings.ts')
    # 选项值：1 = 主图、0 = 副图、mixed = 主副图 ✓
    assert "['1', '主图叠加'], ['0', '独立副图'], ['mixed', '主副图']" in card
    assert "const areaChoice = locked ? 'mixed' : (state.overlay ? '1' : '0');" in card


# ---------------------------------------------------------------- 4. 本地图表
def test_local_chart_dock_defaults_closed():
    local = _read('jslib/src/desk/local-chart-page.ts')
    assert 'this.dockVisible = false;' in local
    assert "this.dock.element.style.display = 'none';" in local
    # 分隔条也要跟着藏（不然底下留一条空条 ✓）
    assert ("if (this.dockSplitter) "
            "this.dockSplitter.style.display = 'none';") in local


def test_indicator_settings_passed_the_cell_index():
    chart = _read('jslib/src/desk/chart-page.ts')
    # 以前固定 `const cell = 0` → 第 2 格的设置会改到第 1 格 ✗
    assert 'this._openIndicatorSettings(item, anchor, index)' in chart
    assert 'const cell = 0;' not in chart.split(
        'private _openIndicatorSettings(')[1].split('openIndicatorSettings(')[0]


# ---------------------------------------------------------------- 构建产物
def test_built_bundle_contains_new_labels():
    js = _read('pylightcharts/js/desk.js')
    assert '主副图' in js
    assert 'overlayLocked' in js

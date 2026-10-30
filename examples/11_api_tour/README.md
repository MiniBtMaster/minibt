# API tour — 覆盖全部 Lightweight Charts v5.2 API 的可运行示例

本目录用 **19 个可运行脚本**逐类覆盖 `pylightcharts` 暴露的全部上游 API。每个文件都是
自包含的（用 numpy/pandas 合成数据），直接运行即可打开窗口肉眼验证。

```bash
python examples/11_api_tour/01_chart_and_data.py
```

## 每个文件的结构

```python
def make_data(rows=300) -> pd.DataFrame   # 自包含合成 OHLCV
def build(chart) -> None                  # 作用全部 API（不打开窗口）
def report(chart) -> None                 # 可选：读回类 API，需真实窗口
def main() -> None:                       # build → show(block=False) → report → show(block=True)
```

- `build(chart)` 只调用 API，适合在测试里用 `HeadlessChart` 驱动。
- 读回类 API（`chart_options()`、`get_visible_range()`、`price_lines()`、`options()`、
  `constants.verify()` …）必须在窗口加载后调用，因此统一放在 `report()`，由 `main()`
  在 `show(block=False)` 与 `show(block=True)` 之间执行并 `print` 结果。

## 文件与覆盖范围

| 文件 | 覆盖的 API |
|---|---|
| `01_chart_and_data.py` | `set` / `update` / `update_from_tick` / `batch`、`layout` / `style` / `grid` / `crosshair` / `watermark` / `legend` / `spinner` / `hotkey`、`candle_style` / `volume_config`、`price_scale` / `series_options` / `precision`、`hide_data`/`show_data`、`resize` / `fit`、`apply_options`、`time_scale` / `time_scale_options`、`set_price_formatter` / `set_time_formatter`、`create_line` / `create_histogram` |
| `02_series_types.py` | 全部序列类型（`create_line/area/bar/baseline/histogram`、`add_series`、`lines`）、逐序列 `set`/`update`/`apply_options`/`style`/`price_scale_options`/`set_price_scale_mode`/`set_scale_margins`/`price_line`/`precision`/`hide_data`/`show_data`/`delete`、`series_type`/`options`/`data_points`/`data_by_index`/`pop`/`last_value_data`/`bars_in_logical_range`/`price_to_coordinate`/`coordinate_to_price`、`get_pane_index`/`get_pane`/`move_to_pane`/`series_order`/`set_series_order`、`marker`/`marker_list`/`remove_marker`/`clear_markers`、`create_price_line`/`price_lines` + `PriceLine.apply_options/options/remove`、`legend_toggle`（隐藏图例行眼睛）、副图色带 `fill_between` / `horizontal_span`、条件上色（数据带 `color` 列）、每个序列独立命名并用不同指标线以便区分、`update_raw` |
| `03_scales_and_queries.py` | 时间轴滚动/范围/坐标换算/`time_scale_settings`、`PriceScale` 全部方法、`chart_options` / `chart_element` / `horz_behavior` / `auto_size_active` / `version`、十字线定位、`pane_size` |
| `04_events.py` | `events.click/dblclick/crosshair_move/range_change/visible_time_range_change/size_change/new_bar/search` + `unsubscribe`、`subscribe_data_changed`/`unsubscribe_data_changed`、`hotkey`、`create_table` + `Table` 方法、`topbar` 四种控件 |
| `05_drawings.py` | 全部 13 个交互式绘图工具 + `vertical_span`、`horizontal_span`（价格色带）、`fill_between`（指标线之间的色带），以及 `update`/`delete`/`options`/`set_offset`/`set_risk_ratio` |
| `06_panes.py` | `add_pane`/`remove_pane`/`swap_panes`、`pane_count`、pane 级建系列（`create_area`/`add_series`/`add_custom_series`/`pane_add_series`/`pane_add_custom_series`）、`set_pane_stretch`/`pane_stretch_factor`/`set_pane_height`/`pane_height`、`pane_get_htmlelement`/`pane_series_handle`/`pane_move_to`、`set_pane_preserve_empty`/`pane_preserve_empty`/`pane_size`/`pane_price_scale`/`pane_series_count`、pane primitive |
| `07_indicators.py` | 全部 17 个 `add_*` 指标、`add_indicator`、`add_computed_series`、原始 `indicators.*` 函数 |
| `08_custom_series.py` | `shapes.rect/band/line/circle/text/polyline/range_bar/box_plot/error_bar`、多面板 `add_custom_series`、`spec=` 自定义 pane view（`rendererDraw`/`priceValueBuilder`/`isWhitespace`/`defaultOptions`） |
| `09_plugins.py` | `markers_plugin`、`marker`/`marker_list`/`remove_marker`/`clear_markers`、`up_down_markers_plugin`、`text_watermark_plugin`、`image_watermark_plugin` 的完整生命周期 |
| `10_primitives.py` | `create_series_primitive`（全部 spec 字段：paneViews / axis pane views / axis views / autoscaleInfo / hitTest / attached / detached / updateAllViews）+ `attach_to`/`apply_options`/`options`/`request_update`/`detach_from`；`create_pane_primitive` |
| `11_callbacks.py` | `register_js_formatter`+`set_price_formatter(name=)`、`set_time_formatter`、`register_js_callback`、`set_tick_mark_formatter`、`set_price_formatter_callback`、`set_time_formatter_callback`、`set_price_format_formatter`、`set_autoscale_info_provider`、`set_option_callback`、`constants` 枚举 + `verify` |
| `12_numeric_and_scale.py` | `YieldCurveChart` / `OptionsChart` + `add_curve`、自定义水平轴 `MonthChart`（`_horz_scale_name`/`_horz_scale`） |
| `13_workspace.py` | `crosshair()`（十字线模式/线宽/颜色/标签底色）、`create_table`+`Table`+`Section`/`Row`、`topbar` 控件、`toolbox` 导入导出、`create_subchart`+`sync`、`screenshot`、`legend`、`chart.win.style`、`set_attribution_logo` |
| `14_multi_chart_layout.py` | `chart.win.page_topbar()`（横跨窗口的页面顶栏）、`chart.win.layout`（`pylightcharts.layout.Layout`：`vertical` / `horizontal` / `arrange` / `single` / `on_create` / `charts` / `register`）、`TopBar.menu` 做的布局下拉菜单 |
| `15_themes.py` | `chart.win.theme(...)` / `chart.theme(...)`（整站浅色 / 深色：根 CSS 变量 + 每张图的背景 / 网格 / 十字线 / K 线 / 成交量 / 分隔条 / 坐标轴）、`pylightcharts.themes` 的 `LIGHT` / `DARK` / `resolve`、顶栏 switcher 运行时切换、表格默认配色跟随主题 |
| `16_tooltips.py` | `series.tooltip(mode=...)` / `tracking_tooltip` / `magnifier_tooltip`（官方 tooltips 教程的追踪提示 + 放大镜提示：跟随光标 / 贴顶竖条、`fields='auto'` 显示 OHLC、`title` / `decimals` / `time_format` / `color_by_candle` / 尺寸与配色）、运行期 `apply_options` / `set_title` / `set_fields` / `set_mode` / `show` / `hide` / `visible` / `options` / `remove`，顶栏 switcher 切换，颜色跟随主题 |
| `17_two_symbols.py` | `chart.add_symbol(...)`（第二个标的 + 左侧价格刻度：`kind=` 蜡烛 / 线 等、`scale=`、`margins=`、`up_color` / `down_color` / `color` / `line_width`、蜡烛叠加）、`chart.scale_margins(right=, left=)`（两刻度叠加 / 上下分割）、`price_line(title=)` 给刻度最后一价命名、顶栏 switcher 切换标的形态与排布 |
| `19_indicator_legend.py` | 指标标签开关：`create_line` / `create_histogram` / `add_series` / `pane_add_series` 的 `legend=False`（只画线**不显示图例行**）、与 `legend_toggle=False`（行在、少一只眼睛）的区别；minibt 侧对应的指标属性 `legend = False` + `PlotInfo.legend` |
| `18_infinite_history.py` | 无限历史（官方 demos/infinite-history）：`chart.infinite_history(loader, page=, threshold=, spinner=, on_load=, on_exhausted=)`（`loader(count[, before])` 向左补更早数据、`events.range_change` 触发、`loaded` / `earliest` / `exhausted` / `load()` / `stop()`）、**主图与副图指标随历史一起延长**（SMA 50 + RSI 14 副图）、成交量重发、顶栏文本框显示已加载根数 |
| `19_indicator_panes.py` | 指标副图用 **pane**：`add_pane(preserve_empty=)` / `pane_add_series(index, kind, ...)` / `set_pane_height` / `remove_pane(index)` / `pane_count` / `pane_series_count` / `pane_price_scale`，以及 `series.delete()`（一次摘掉指标线 + 左上角图例标签，最后一个序列被摘掉时空 pane 自动消失）与 `series.pane_index`；顶栏 switcher 切换副图指标、按钮对比"保留空 pane"、按钮"删除最后一个副图"（`remove_last_pane()`：先逐个 `series.delete()`，保留的空 pane 再 `remove_pane()`）|
| `21_text_multi_line.py` | `shapes.text(price, text, offset=, color=, font_size=, align=, baseline=, line_height=)` —— **多行文本**（文本里的换行符按行拆开绘制，与 bokeh 的 `LabelSet` 一致）、`baseline` 决定整块文字向下/向上/居中铺开、逐点文本/颜色/行距放进数据列、**像素偏移 `offset_x`/`offset_y`**、字号、`background_color`+`padding` 文本底色、与 `shapes.marker` 组合（一个点 = 标记 + 文本）|
| `22_line_gaps.py` | **NaN 断点**：`[1,2,3,nan,nan,6,7,8]` 画成**两段** —— LWC v5 的 whitespace 只延长时间轴、不会断线，所以 pylightcharts 先把主序列藏着（`lineVisible:false`），再按连续段各画一条同款、不进图例的 Line；副图用 `nan→0` 作对照，展示"连过去"长什么样 |
| `23_fill_between_gaps.py` | **色带断点**：`series.fill_between(other, color=, opacity=)` 在通道线有 `nan` 时**不填色** —— 通道线多空段交替（一侧 `nan`）与"双缺口"两种情形都断成一段一段；`nan` 段两端各自收口，不会连成大三角 |
| `24_layouts_and_legend_settings.py` | **迁移时加的扩展**：2D tile 布局 `chart.win.layout.arrange_tiles([(w,h), ...], dividers=True)`（行间/行内都可拖的分隔条，切回 `arrange()`/`single()` 自动 `clearLayoutTiles` 复位）、图例齿轮 `series.enable_legend_settings(callback)`（点齿轮回调 `callback(series, x, y)`）、常显图例行 `series.pin_legend_row(True)`、指标线样式 `series.set_line_width/set_line_color/set_line_style` + `series.set_price_visible('price_line'/'price_label', bool)` + `series.is_visible()`、以及 `chart.remove()` 连 DOM wrapper 一起摘掉 |
| `25_live_value_table.py` | **指标数值表格**：`chart.events.crosshair_move` + `create_table(..., draggable=True)` 实现“鼠标移到哪根就显示那根的指标值，移出 K 线回到最后一根”（表格常显、不像图例标签会消失）；`chart.update` + `series.update` + `series.subscribe_data_changed` 让实时更新时表格同步刷新 |
| `26_volume_profile.py` | **滚动成交量分布图（Volume Profile）**：用 `add_custom_series(spec={...})` + `register_js_callback` 画横条 —— `rendererDraw` 的**位置固定在可视 X 轴最右端**（`anchor = scope.mediaSize.width`，绘图区右边缘，与主图**成交量柱**的最右边缘对齐），只有**数值**跟随鼠标：按鼠标的 CSS x（`bar.x` 也是 CSS 像素）挑**最近的那根 K 线**当数据源，鼠标不在图上就回落到最右那根；满量程柱长 = **可视跨度 × 0.30**，用 `priceConverter` 把价格档映射成 y，所以移动鼠标 / 拖动 / 缩放全自动跟随；`priceValueBuilder` / `isWhitespace` 配合自动缩放；主图用**价格档中心**、副图（`pane_index='new'`）用**档位序号**（分层直方图）；量最大的一档用 POC 色高亮。鼠标跟随靠 `chart.run_script` + `addCrosshairListener` 挂的**纯 JS** 十字线监听（不回调 Python），并在里面 `series.applyOptions({})` 强制序列重绘 —— 实测 lightweight-charts 的十字线移动**不会**重绘序列层 |
| `27_volume_profile_live.py` | 上一例的**实时版**：后台线程每 2 秒 `chart.update(...)` 推一根 K 线 + `vp_series.update({...})` 推这一根的分布（`rendererDraw` 读的就是每行数据，逐点 `update` 即可）；`vmax` 做成**逐行列**，量做大时柱长比例跟着变；**优先级：实时更新 > 鼠标跟随** —— 每次推数据后调 `_volume_profile.reset_vp_hover()` 清掉鼠标坐标，本帧先画最新一根，鼠标再动才重新跟随 |

> `_volume_profile.py`（下划线开头）是 `26`/`27` 共用的实现，本身不是示例。
> 在 minibt 里画 VP 时样式由指标上的 **`vpstyle = VPStyle(...)`**
> （`minibt/utils.py`，只有 `category='vp'` 生效，pylightcharts 与 bokeh 同
> 步）控制，不需要像示例这样手写 JS。

## 说明

- 图例（OHLC 区块 + 每条序列的标签行）**默认是关闭的**（与
  `lightweight-charts-python` 一致），所以时间轴类示例都会调用
  `chart.legend(True)`；`12_numeric_and_scale.py` 是数值轴图表，
  没有 Legend 对象，不能调用。
- `pylightcharts` 的根样式接口在 `Window` 上，故示例写作 `chart.win.style(...)`。
- 数值轴图表（`YieldCurveChart` / `OptionsChart`）没有 K 线，用 `add_curve`/`add_series`。
- 函数式 options（formatter/provider）与声明式 primitive 的绘制逻辑是 **JS 片段**，由
  `register_js_callback` 注册；这是渲染时序决定的。

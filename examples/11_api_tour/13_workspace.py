"""工作台：表格 / 顶栏控件 / 工具箱 / 子图同步 / 截图。

覆盖的 API：
- 表格：`chart.create_table(...)`、`Table.new_row`、`Table.format`、
  `Table.resize`、`Table.visible`、`Table.set_position`、`Table.get`、
  `Row.__setitem__`、header / footer 的 `Section`。
- 顶栏：`chart.topbar.textbox/switcher/menu/button`，以及
  `TextWidget.set` / `SwitcherWidget.set` / `MenuWidget.set` /
  `MenuWidget.update_items` / `ButtonWidget.set`。
- 工具箱：`chart.toolbox.save_drawings_under / load_drawings /
  export_drawings / import_drawings`（JSON 写到本目录）。
- 键盘：内置方向键作用于“鼠标所在/第一张”图表（`window.handlerInFocus`），
  子图不会抢走焦点；`Chart(keyboard=..., keyboard_step=...)` 可配。
- 窗口：`chart.create_subchart(...)` + `chart.sync(other)`、
  `chart.screenshot()`（PNG 写到本目录）、`chart.legend(...)`、
  `chart.crosshair(...)`（十字线样式 / 模式 / 标签底色）、
  `chart.win.style(...)`（根 CSS 变量）、`set_attribution_logo(...)`。

注意：`screenshot()` 等需要窗口已经加载，所以 `main()` 先 `show(block=False)`，
截图完成后再 `show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/13_workspace.py
"""
import os

import numpy as np
import pandas as pd

from pylightcharts import Chart, set_attribution_logo
from pylightcharts.table import Table

# 导出文件写在本示例目录，避免依赖外部路径
HERE = os.path.dirname(os.path.abspath(__file__))
DRAWINGS_PATH = os.path.join(HERE, 'drawings_13.json')
SCREENSHOT_PATH = os.path.join(HERE, 'screenshot_13.png')


def make_data(rows: int = 1000) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(1313)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.8)
    open_ = close + rng.standard_normal(rows) * 0.4
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.2, rows)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.2, rows)
    volume = rng.integers(1_000, 50_000, rows)
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='D'),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


# 顶栏控件回调统一接收 chart（Widget 内部以 topbar._chart 调用）
def on_symbol(chart) -> None:
    print('[topbar] symbol ->', chart.topbar['symbol'].value)


def on_timeframe(chart) -> None:
    print('[topbar] timeframe ->', chart.topbar['timeframe'].value)


def on_indicator(chart) -> None:
    print('[topbar] indicator ->', chart.topbar['indicator'].value)


def on_button(chart) -> None:
    print('[topbar] button ->', chart.topbar['reload'].value)


# 表格行点击回调：不管 return_clicked_cells 是 True 还是 False 都能直接用。
#   * return_clicked_cells=True  -> 框架额外传“被点单元格的列名”作为第 2 个参数
#     （不写第 2 个参数也行，table.py 会按签名自动少传，不会报 TypeError）；
#   * return_clicked_cells=False -> 只传整行 Row。
def on_cell(row, column=None) -> None:
    print('[table] row clicked ->', dict(row), '| column =', column)


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    # set：主 K 线 + 成交量
    chart.set(df)

    # ------------------------------------------------------------------
    # 根样式（Window.style）与图例
    # ------------------------------------------------------------------
    # style：设置根 CSS 变量（背景 / 悬停 / 点击 / 激活 / 边框 / 文字）
    chart.win.style(
        background_color='#0b0e14',
        hover_background_color='#2a2e39',
        click_background_color='#363a45',
        active_background_color='rgba(41, 98, 255, 0.70)',
        muted_background_color='rgba(41, 98, 255, 0.30)',
        border_color='#2a2e39',
        color='#d1d4dc',
        active_color='#ffffff',
    )
    # legend：显示 OHLC / 涨跌幅 / 指标行图例
    chart.legend(visible=True, ohlc=True, percent=True, lines=True,
                 color='#d1d4dc', font_size=12, font_family='Monaco', text='WORKSPACE')

    # crosshair：鼠标十字线的样式，等价于官方文档里的
    #   chart.applyOptions({ crosshair: { mode: CrosshairMode.Normal,
    #       vertLine: { width: 8, color: '#C3BCDB44', style: LineStyle.Solid,
    #                   labelBackgroundColor: '#9B7DFF' },
    #       horzLine: { color: '#9B7DFF', labelBackgroundColor: '#9B7DFF' } } })
    # mode='normal' 让十字线自由移动不吸附；horz_width / horz_style 不传就是
    # 引擎默认（1px / large_dashed），和官方示例一致。
    chart.crosshair(
        mode='normal',
        vert_width=8,
        vert_color='#C3BCDB44',
        vert_style='solid',
        vert_label_background_color='#9B7DFF',
        horz_color='#9B7DFF',
        horz_label_background_color='#9B7DFF',
    )

    # ------------------------------------------------------------------
    # 表格：create_table + Row + Section + format/resize/visible/get
    # ------------------------------------------------------------------
    # create_table：浮动表格，含表头 / 列宽 / 对齐 / 位置 / 配色 / 点击回调
    # position 与 Table.set_position 取值一致（默认 'top-right'）：'top-left' /
    # 'top-right' / 'bottom-left' / 'bottom-right'；'left'/'right'/'top'/'bottom'
    # 是兼容旧代码的别名。
    table = chart.create_table(
        width=340, height=180,
        headings=('symbol', 'price', 'change'),
        widths=(120, 100, 100),
        alignments=('left', 'right', 'right'),
        position='top-right', draggable=True,
        background_color='#121417', border_color='rgb(70, 70, 70)', border_width=1,
        heading_text_colors=('#d1d4dc',) * 3,
        heading_background_colors=('#1b1f2a',) * 3,
        return_clicked_cells=True,
        func=on_cell,
    )
    # format：注册列格式，VALUE 占位符在写单元格时被实际值替换
    table.format('change', Table.VALUE + '%')

    # new_row：按 headings 顺序新增一行，返回 Row
    row = table.new_row('BTCUSDT', 64231.5, 1.23)
    # new_row(..., id=...)：显式指定行 id，方便后续 get
    table.new_row('ETHUSDT', 3120.4, -0.85, id=2)
    # Row.__setitem__：按键更新单元格（自动套用列格式）
    row['price'] = 65120.0
    # Row.__setitem__ 支持元组键批量赋值
    row[('symbol', 'change')] = ('BTCUSDT', 2.05)
    # get：按行 id 取回 Row（与 new_row 返回的是同一个对象）
    same = table.get(row.id)
    same['price'] = 65150.0

    # Section：header 区（1 个文本框）
    table.header(1)
    # Section.__setitem__：写入 header 文本
    table.header[0] = 'MARKET WATCH'
    # Section：footer 区（1 个文本框）
    table.footer(1)
    # Section.__setitem__：写入 footer 文本
    table.footer[0] = 'streaming...'

    # resize：调整表格尺寸（宽 / 高）
    table.resize(360, 190)
    # set_position：运行中改锚点（与 create_table(position=...) 同一套取值）
    table.set_position()
    # visible：先隐藏再显示表格
    table.visible(False)
    table.visible(True)

    # ------------------------------------------------------------------
    # 顶栏控件：textbox / switcher / menu / button + 各 set 方法
    # ------------------------------------------------------------------
    # textbox：可编辑文本框（回车触发回调）
    chart.topbar.textbox('symbol', 'BTCUSDT', align='left', func=on_symbol)
    # TextWidget.set：程序化修改文本框内容
    chart.topbar['symbol'].set('ETHUSDT')

    # switcher：分段选择器
    chart.topbar.switcher('timeframe', ('1m', '5m', '1h', '1d'),
                          default='5m', align='left', func=on_timeframe)
    # SwitcherWidget.set：切到某个选项（会触发回调）
    chart.topbar['timeframe'].set('1h')

    # menu：下拉菜单
    chart.topbar.menu('indicator', ('SMA', 'EMA', 'RSI', 'MACD'),
                      default='SMA', separator=True, align='left', func=on_indicator)
    # TopBar.get：按名字取回控件实例
    chart.topbar.get('indicator')
    # MenuWidget.update_items：重建菜单项
    chart.topbar['indicator'].update_items('SMA', 'EMA', 'RSI', 'MACD', 'BOLL')
    # MenuWidget.set：选中某个菜单项（会触发回调）
    chart.topbar['indicator'].set('MACD')

    # button：普通按钮（toggle=False）
    chart.topbar.button('reload', 'Reload', separator=True, align='right',
                        toggle=False, func=on_button)
    # ButtonWidget.set：修改按钮文字
    chart.topbar['reload'].set('Reloaded')

    # ------------------------------------------------------------------
    # 工具箱：手绘的保存 / 加载 / 导出 / 导入
    # ------------------------------------------------------------------
    # save_drawings_under：把用户在该图上画的手绘保存到 symbol 控件名下
    chart.toolbox.save_drawings_under(chart.topbar['symbol'])
    # load_drawings：按 tag 重新加载手绘（无对应 tag 时安全空操作）
    chart.toolbox.load_drawings(chart.topbar['symbol'].value)
    # export_drawings：把手绘集合导出为本目录下的 JSON 文件
    chart.toolbox.export_drawings(DRAWINGS_PATH)
    # import_drawings：再从该 JSON 文件导入手绘集合
    chart.toolbox.import_drawings(DRAWINGS_PATH)

    # ------------------------------------------------------------------
    # 子图 + 同步
    # ------------------------------------------------------------------
    # create_subchart：在右侧创建宽 40% / 高 40% 的子图（sync=None，稍后手动同步）
    sub = chart.create_subchart(position='right', width=0.4, height=0.4,
                                sync=None, toolbox=True)
    # sub.set：给子图灌入同一份 K 线数据
    sub.set(df)
    # sub.legend：子图自己的图例（关闭 OHLC 行）
    sub.legend(visible=True, ohlc=False, percent=True, lines=False, text='SUB')
    # sync：把子图与本图做平移 / 缩放双向同步
    chart.sync(sub)
    #
    # from pylightcharts import color_by
    chart.color_by(df["close"] > 96., 'orange', wick_color=False)
    df["sma"] = df['close'].rolling(10).mean()
    sma_line = chart.create_line("sma")
    sma_line.set(df[['time', 'sma']])
    sma_line.color_by(df['sma'] > df['sma'].shift(),
                      '#26A69A', else_color='#EF5350')
    chart.color_by(df['close'] >= df['sma'], "#EE0A0A", else_color="#93EC35")

    #
    # from pylightcharts.indicators import swing_points
    # chart.mark_swings(length=10, size=1)
    chart.add_zigzag(name="zigzag")

    chart.apply_options(rightPriceScale=dict(invertScale=True))


def capture(chart) -> None:
    """截图 / readback —— 需要已经加载完成的真实窗口（build() 里不能调用）。"""
    # chart_options：读回当前（合并后的）图表选项
    print('[chart_options]', list(chart.chart_options().keys()))
    # screenshot：把图表截成 PNG 字节并写入本目录
    png = chart.screenshot()
    with open(SCREENSHOT_PATH, 'wb') as f:
        f.write(png)
    print('[screenshot]', len(png), 'bytes ->', SCREENSHOT_PATH)


def main() -> None:
    # set_attribution_logo：让此后创建的图表（含子图）显示归属 logo
    set_attribution_logo(True)
    # Chart(toolbox=True)：创建带工具箱的主窗口
    chart = Chart(width=1200, height=820,
                  title='pylightcharts - 工作台', toolbox=True)
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再截图
    chart.show(block=False)
    capture(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()

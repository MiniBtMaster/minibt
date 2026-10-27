"""图表事件、数据变更回调、热键、表格与顶栏控件。

覆盖的 API：
- 事件：`chart.events.click` / `dblclick` / `crosshair_move` / `range_change` /
  `visible_time_range_change` / `size_change` / `new_bar` / `search`，以及
  `JSEmitter.unsubscribe()`。
- 序列数据变更：`series.subscribe_data_changed(fn)` /
  `series.unsubscribe_data_changed()`；`series.delete()`（序列与图例行一起移除）。
- 全局快捷键：`chart.hotkey(modifier, keys, func)`。
- 表格：`chart.create_table(...)` + `Table.new_row / clear / get / format /
  resize / visible`。
- 顶栏控件：`chart.topbar.textbox / switcher / menu / button`。

运行：
    python examples/11_api_tour/04_events.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart


def make_data(rows: int = 300) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(20240501)
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


def build(chart: Chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()

    # ------------------------------------------------------------------
    # 事件回调（JS 侧触发后回到 Python）
    # ------------------------------------------------------------------
    # 单击事件：回调签名 (chart, time, price)
    def on_click(chart, time, price):
        print(f'[click] time={time} price={price}')

    chart.events.click += on_click

    # 双击事件：回调签名 (chart, time, price)
    def on_dblclick(chart, time, price):
        print(f'[dblclick] time={time} price={price}')

    chart.events.dblclick += on_dblclick

    # 十字光标移动：回调签名 (chart, time, price)
    def on_crosshair_move(chart, time, price):
        print(f'[crosshair_move] time={time} price={price}')

    chart.events.crosshair_move += on_crosshair_move

    # 可见逻辑范围变化：回调签名 (chart, bars_before, bars_after)
    def on_range_change(chart, bars_before, bars_after):
        print(
            f'[range_change] bars_before={bars_before} bars_after={bars_after}')

    chart.events.range_change += on_range_change

    # 可见时间范围变化：回调签名 (chart, from_timestamp, to_timestamp)
    def on_visible_time_range_change(chart, from_time, to_time):
        print(f'[visible_time_range_change] from={from_time} to={to_time}')

    chart.events.visible_time_range_change += on_visible_time_range_change

    # 时间轴尺寸变化：回调签名 (chart, width, height)
    def on_size_change(chart, width, height):
        print(f'[size_change] width={width} height={height}')

    chart.events.size_change += on_size_change

    # 新 bar 事件：回调签名 (series)
    def on_new_bar(series):
        print('[new_bar] 产生了新的 K 线')

    chart.events.new_bar += on_new_bar

    # 搜索事件：回调签名 (chart, searched_string)
    def on_search(chart, searched_string):
        print(f'[search] 搜索内容={searched_string!r}')

    chart.events.search += on_search

    # ------------------------------------------------------------------
    # 卸载订阅：JSEmitter.unsubscribe() 会同时移除 JS 监听与 Python 回调
    # ------------------------------------------------------------------
    # 先注册一个临时回调，再卸载，演示 subscribe / unsubscribe 配对
    def on_size_change_tmp(chart, width, height):
        print(f'[size_change/tmp] {width}x{height}')

    chart.events.size_change += on_size_change_tmp
    chart.events.size_change.unsubscribe()
    # 重新注册正式回调，保证演示窗口里尺寸变化事件依然有效
    chart.events.size_change += on_size_change

    # ------------------------------------------------------------------
    # 数据与序列
    # ------------------------------------------------------------------
    # 主图：K 线 + 成交量
    chart.set(df)
    chart.legend(True)

    # 触发 new_bar：更新一根时间更晚的 K 线
    last = df.iloc[-1]
    next_bar = pd.Series({
        'time': last['time'] + pd.Timedelta(days=1),
        'open': last['close'],
        'high': float(last['close']) + 1.0,
        'low': float(last['close']) - 1.0,
        'close': float(last['close']) + 0.5,
        'volume': int(last['volume']),
    })
    chart.update(next_bar)

    # 叠加一条收盘价折线，用于演示数据变更回调
    line = chart.create_line('close', color='#FF9800', width=2)
    line.set(df)

    # 序列数据变更回调：回调签名 (series, scope)，scope 为 'full' / 'update'
    def on_data_changed(series, scope):
        print(f'[data_changed] scope={scope}')

    line.subscribe_data_changed(on_data_changed)

    # update 一次该折线即可触发上面的回调
    line.update(pd.Series({'time': last['time'] + pd.Timedelta(days=1),
                           'close': float(last['close']) + 0.5}))

    # 演示 unsubscribe_data_changed：再建一条临时线，注册后立刻注销
    # 注意 unsubscribe_data_changed() 只摘掉回调，序列和图例行都还在；
    # 要让临时序列连色块/名称/眼睛一起消失，得 delete()
    temp = chart.create_line('open', color='#26A69A')

    def on_temp_changed(series, scope):
        print(f'[data_changed/tmp] scope={scope}')

    temp.subscribe_data_changed(on_temp_changed)
    temp.unsubscribe_data_changed()
    temp.delete()

    # ------------------------------------------------------------------
    # 全局快捷键：ctrl+s，回调接收按下的键名
    # ------------------------------------------------------------------
    def on_hotkey(key):
        print(f'[hotkey] ctrl+{key} 被按下')

    chart.hotkey('ctrl', 's', on_hotkey)
    # 内置方向键（无需注册，Chart(keyboard=False) 可关掉，
    # Chart(keyboard_step=0.2) / chart.keyboard(step=...) 调步长）：
    #   ←/→ = 可视窗口左右移动一格（默认 10% 宽度，100..200 → ~90..190）
    #   ↑/↓ = 缩放一格（以窗口中心为锚点，左右两边同时向中间/两边推进）；
    #   Shift = 近整屏 / 2.5 倍步长
    #   Ctrl+←/→ 或 PageUp/PageDown = 整屏翻页；Home = 第一根；End = 最新
    #   Ctrl+0 = 全量适配（等同 chart.fit()）；按住键会自动重复
    # 优先级：自己的 hotkey 先匹配（所以可以覆盖方向键），输入框聚焦时
    # 内置方向键不生效，多图时只作用于鼠标所在那张图。

    # ------------------------------------------------------------------
    # 表格：create_table + new_row / clear / get / format / resize / visible
    # ------------------------------------------------------------------
    table = chart.create_table(
        0.22, 0.30,
        ('Field', 'Value'),
        widths=(0.55, 0.45),
        alignments=('left', 'right'),
        position='right',
        draggable=True,
    )
    # Table.format：给整列设置输出模板（Table.VALUE 占位符会被单元格值替换）
    table.format('Value', '$' + table.VALUE)
    # Table.new_row：新增一行（可指定整数 id）
    table.new_row('last close', f"{df['close'].iloc[-1]:.2f}", id=1)
    # Table.get：按 id 取回 Row，再修改单元格
    table.get(1)['Field'] = 'last close (updated)'
    # 再加一行，稍后用 clear 演示清空
    table.new_row('last volume', int(df['volume'].iloc[-1]))
    # Table.clear：清空所有行，然后补写一行
    table.clear()
    table.new_row('last close', f"{df['close'].iloc[-1]:.2f}")
    # Table.resize：调整表格尺寸
    table.resize(0.24, 0.22)
    # Table.visible：先隐藏再显示，演示显隐开关
    table.visible(False)
    table.visible(True)

    # ------------------------------------------------------------------
    # 顶栏控件：textbox / switcher / menu / button
    # ------------------------------------------------------------------
    def on_period_change(chart):
        print(f"[topbar] switcher period -> {chart.topbar['period'].value}")

    def on_menu_change(chart):
        print(f"[topbar] menu indicator -> {chart.topbar['indicator'].value}")

    def on_button(chart):
        print(f"[topbar] button toggle -> {chart.topbar['mark'].value}")

    # 文本框
    chart.topbar.textbox('symbol', 'TOUR')
    # 切换器（带回调）
    chart.topbar.switcher('period', ('1D', '1W', '1M'),
                          default='1D', func=on_period_change)
    # 下拉菜单（带回调）
    chart.topbar.menu('indicator', ('SMA', 'EMA', 'RSI'),
                      default='SMA', func=on_menu_change)
    # 按钮（toggle=True 表示开关式，带回调）
    chart.topbar.button('mark', 'Mark', toggle=True, func=on_button)


def main() -> None:
    chart = Chart(width=1100, height=750, title='pylightcharts - 事件 / 表格 / 顶栏')
    build(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()

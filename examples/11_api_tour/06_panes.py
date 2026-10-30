"""多面板（panes）：创建 / 查询 / 排序 / 尺寸 / primitive。

覆盖的 API：
- `add_pane` / `pane_count` / `remove_pane` / `swap_panes` / `pane_move_to`
- `create_area(pane_index=...)` / `add_series(..., pane_index=...)` /
  `add_custom_series(..., pane_index='new')`
- `pane_add_series` / `pane_add_custom_series`
- `set_pane_stretch` / `pane_stretch_factor` / `set_pane_height` / `pane_height`
- `set_pane_preserve_empty` / `pane_preserve_empty`
- `pane_size` / `pane_price_scale` / `pane_series_count`
- `pane_get_htmlelement` / `pane_series_handle`
- `attach_pane_primitive` / `detach_pane_primitive`
  （配合 `register_js_callback` + `create_pane_primitive`）

注意：`pane_*` 的查询方法需要真实窗口，因此在 `main()` 里先 `show(block=False)`，
完成状态读取后再 `show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/06_panes.py
"""
import numpy as np
import pandas as pd

from pylightcharts import Chart, shapes


def make_data(rows: int = 300) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(606)
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

    # 主面板（pane 0）：K 线
    chart.set(df)
    chart.legend(True)

    # add_pane：新增一个空面板，返回其索引
    pane_area = chart.add_pane()
    # pane_count：读取当前面板数量（此时为 2）
    print('[build] pane_count ->', chart.pane_count())

    # create_area(pane_index=...)：在指定面板创建 Area 序列
    area = chart.create_area(
        name='close',
        line_color='#26A69A',
        top_color='rgba(38, 166, 154, 0.30)',
        bottom_color='rgba(38, 166, 154, 0.03)',
        pane_index=pane_area,
    )
    area.set(df)

    # 再建一个面板放折线
    pane_line = chart.add_pane()
    # add_series(..., pane_index=...)：在指定面板创建内置序列
    line = chart.add_series('Line', name='close', pane_index=pane_line,
                            color='#FF9800', line_width=2)
    line.set(df)

    # add_custom_series(pane_index='new')：自动新建一个面板放自定义序列
    # color 只影响图例色块（自定义序列的颜色由 shapes 决定），但必须显式给，
    # 否则图例只能用默认蓝
    custom = chart.add_custom_series('range', pane_index='new',
                                     color='#2962FF')
    custom.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high'],
                                                       color='rgba(41, 98, 255, 0.45)'))

    # pane_add_series：直接通过面板句柄在内置面板里创建序列（索引 4）
    pane_hist = chart.pane_add_series(4, 'Histogram', name='volume',
                                      color='rgba(100, 150, 250, 0.5)')
    pane_hist.set(df)

    # pane_add_custom_series：直接通过面板句柄创建自定义序列（索引 5）
    pane_custom = chart.pane_add_custom_series(5, name='range2',
                                               color='#FF9800')
    pane_custom.set(df, shapes=lambda row: shapes.range_bar(row['low'], row['high'],
                                                            color='rgba(255, 152, 0, 0.45)'))

    # set_pane_stretch：设置面板的相对高度权重
    chart.set_pane_stretch(pane_area, 1.6)
    # set_pane_height：以像素为单位设置面板高度
    chart.set_pane_height(240, index=pane_line)
    # set_pane_preserve_empty：即使面板里没有序列也保留它
    chart.set_pane_preserve_empty(True, index=4)
    # pane_price_scale：取得某个面板的价格轴并调整模式
    chart.pane_price_scale(pane_area, 'right').set_mode('normal')

    # ------------------------------------------------------------------
    # 面板 primitive：绘制逻辑必须写成 JS 片段（渲染帧内执行）
    # ------------------------------------------------------------------
    # register_js_callback：注册一个 JS 绘制回调
    chart.register_js_callback(
        'pane_stripe', ['target', 'priceConverter', 'view', 'prim'],
        "target.useBitmapCoordinateSpace(scope => {"
        "  const ctx = scope.context;"
        "  ctx.fillStyle = 'rgba(0, 188, 212, 0.30)';"
        "  ctx.fillRect(0, 0, scope.bitmapSize.width, 6);"
        "});")

    # create_pane_primitive：用 spec 构造一个面板 primitive
    stripe = chart.create_pane_primitive({
        'paneViews': [{'draw': 'pane_stripe', 'zOrder': 'top'}],
    })
    # attach_pane_primitive：把 primitive 挂到 pane_area 面板上
    chart.attach_pane_primitive(stripe.id, pane_area)

    # detach_pane_primitive：再建一个临时 primitive，挂上后立即摘下
    temp_spec = chart.create_pane_primitive({
        'paneViews': [{'draw': 'pane_stripe', 'zOrder': 'bottom'}],
    })
    chart.attach_pane_primitive(temp_spec.id, pane_line)
    chart.detach_pane_primitive(temp_spec.id, pane_line)

    # ------------------------------------------------------------------
    # 面板排序 / 删除（放在最后，避免打乱上面的索引）
    # ------------------------------------------------------------------
    # swap_panes：交换两个面板的位置，再换回来保持布局
    chart.swap_panes(pane_area, pane_line)
    chart.swap_panes(pane_area, pane_line)
    # pane_move_to：把最后一个面板移动到自身位置（改目标即可真正换位）
    last = chart.pane_count() - 1
    chart.pane_move_to(last, last)
    # remove_pane：新建一个临时空面板再删除（位于末尾，不影响其他索引）
    tmp_pane = chart.add_pane(preserve_empty=True)
    chart.remove_pane(tmp_pane)


def report_panes(chart) -> None:
    """读取面板状态 —— 这些是 readback，需要已经加载完成的真实窗口。"""
    # pane_count：面板总数
    print('pane_count          :', chart.pane_count())
    # pane_stretch_factor：读取面板高度权重
    print('pane_stretch_factor :', chart.pane_stretch_factor(1))
    # pane_height：读取面板像素高度
    print('pane_height         :', chart.pane_height(2))
    # pane_preserve_empty：读取“空面板保留”开关
    print('pane_preserve_empty :', chart.pane_preserve_empty(4))
    # pane_size：读取面板尺寸（width / height）
    print('pane_size           :', chart.pane_size(1))
    # pane_series_count：读取面板中的序列数量
    print('pane_series_count   :', chart.pane_series_count(1))
    # pane_get_htmlelement：取得面板 DOM 节点的句柄
    print('pane_get_htmlelement:', chart.pane_get_htmlelement(1))
    # pane_series_handle：取得面板 getSeries() 返回数组的句柄
    print('pane_series_handle  :', chart.pane_series_handle(1))


def main() -> None:
    chart = Chart(width=1100, height=800, title='pylightcharts - 多面板')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再读取面板状态
    chart.show(block=False)
    report_panes(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()

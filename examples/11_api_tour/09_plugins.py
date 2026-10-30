"""v5 插件生命周期：series markers / up-down markers / 文本与图片水印。

覆盖的 API：
- `series.markers_plugin()`：`set_markers` / `markers` / `apply_options` /
  `detach` / `get_series`。
- 经典标记：`series.marker` / `series.marker_list` / `series.remove_marker` /
  `series.clear_markers`。
- `series.up_down_markers_plugin(...)`：`set_data` / `update` / `markers` /
  `set_markers` / `clear_markers` / `apply_options` / `detach` / `get_series`。
- `chart.text_watermark_plugin(...)`：`apply_options` / `detach` / `get_pane`。
- `chart.image_watermark_plugin(...)`：`apply_options` / `detach` / `get_pane`。
- `chart.legend(True)`：打开图例（默认关闭），显示 OHLC 区块与序列标签行。

注意：`markers()` 是 readback，需要真实窗口；因此 `main()` 先
`show(block=False)`，读取插件状态后再 `show(block=True)` 阻塞显示。

运行：
    python examples/11_api_tour/09_plugins.py
"""
import numpy as np
from numpy import char, sign
import pandas as pd

from pylightcharts import Chart

# 8x8 棋盘 PNG（不透明，白 + 蓝 #2962FF），内联 data URI，不依赖外部图片文件。
# 图片水印画的是图片的**像素**，所以下面两种情况都“什么都看不见”，而且引擎
# 不会报错，很容易误判成插件没生效：
#   * 图片是全透明的（例如常见的 1x1 全透明 PNG）；
#   * data URI / base64 写错（断行断错位置也算）导致图片加载失败。
# 换成自己的 logo 即可（也可以是 URL 或本地文件路径，后者会被读成 data URI）。
LOGO_PNG = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAH0lEQVR42mPQTPr/////'
    '//9x0Qz4JDWT/v9nGBYmAABn3dChRFM/NwAAAABJRU5ErkJggg=='
)


def make_data(rows: int = 320) -> pd.DataFrame:
    """自包含的合成 OHLCV，避免依赖外部 csv。"""
    rng = np.random.default_rng(909)
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

    # 主图 K 线
    chart.set(df)
    # legend(True)：打开图例（默认关闭），给插件宿主序列一个标签行
    chart.legend(True)
    # 统一的时间轴（epoch 秒），与 chart.set 内部使用的格式保持一致
    epoch = df['time'].astype('int64') // 10 ** 9

    # 建一条折线作为 marker API 的宿主
    signals = chart.create_line(name='close', color='#FFD54F', width=1)
    signals.set(df[['time', 'close']])

    # ------------------------------------------------------------------
    # 经典 marker API（series.marker / marker_list / remove_marker / clear_markers）
    # ------------------------------------------------------------------
    # 在最后一根 K 线上放一个向上箭头标记（不传时间则用最后一根）
    # size：标记大小的倍数（默认 1）。引擎的基础尺寸是 12~30px（跟着 bar
    # 间距走），所以 size=1 在 320 根全入镜时只有 ~7px，基本看不清；
    # size=3 大约 20px，密集视图里也很明显（面积约 9 倍）。
    first = signals.marker(
        position='below', shape='arrow_up', color='#26A69A', text='buy',
        size=3)
    # 批量创建标记，返回 id 列表
    signals.marker_list([
        {'time': df['time'].iloc[40], 'position': 'above', 'shape': 'arrow_down',
         'color': '#EF5350', 'text': 'sell', 'size': 3},
        {'time': df['time'].iloc[80], 'position': 'below', 'shape': 'circle',
         'color': '#29B6F6', 'text': 'note', 'size': 3},
    ])
    # 按 id 删除刚创建的第一个标记
    signals.remove_marker(first)
    # 清空该系列当前的所有标记
    # signals.clear_markers()
    open = chart.create_line(name='open')
    open.set(df[['time', 'open']])
    last = open.marker(df['time'].iloc[100], position='above', shape='square',
                       color="#E91212", text='方形', size=10)

    # ------------------------------------------------------------------
    # SeriesMarkersPlugin 生命周期（v5 primitive）
    # ------------------------------------------------------------------
    # markers_plugin()：拿到某个序列的 markers 插件句柄
    markers = signals.markers_plugin()
    # set_markers()：用插件接口一次性替换全部标记（v5 词汇）
    markers.set_markers([
        {'time': int(epoch.iloc[120]), 'size': 3,
         'position': 'aboveBar', 'shape': 'arrowDown', 'color': '#EF5350', 'text': 'p1'},
        {'time': int(epoch.iloc[160]), 'size': 3,
         'position': 'belowBar', 'shape': 'arrowUp', 'color': '#26A69A', 'text': 'p2'},
    ])
    # 注意：v5 的 markers 插件与经典 marker() 接口操作的是**同一个** primitive，
    # set_markers() 会把前面 marker()/marker_list() 加过的标记整体替换掉
    # （所以最终停留在图上的只有下面这两个 p1 / p2）。
    # apply_options()：透传插件选项（snake_case 自动转 camelCase）
    markers.apply_options(z_index=1)
    # get_series()：取得插件所依附系列的手柄
    markers.get_series()

    # ------------------------------------------------------------------
    # UpDownMarkersPlugin 生命周期（只支持 Line / Area）
    # ------------------------------------------------------------------
    # 另建一条折线作为 up/down markers 的宿主
    updown_series = chart.create_line(name='close', color='#42A5F5', width=1)
    # up_down_markers_plugin(...)：创建插件并设置正/负颜色、更新可见时长
    # update_visibility_duration：update() 自动产生的标记存活多久（毫秒）
    updown = updown_series.up_down_markers_plugin(
        positive_color='#26A69A', negative_color='#EF5350',
        update_visibility_duration=10_000)
    # set_data()：由插件接管系列数据
    updown.set_data([
        {'time': int(t), 'value': float(v)}
        for t, v in zip(epoch, df['close'])
    ])
    # update()：增量更新最后一个点
    updown.update({
        'time': int(epoch.iloc[-1]),
        'value': float(df['close'].iloc[-1]) + 1.5,
    })
    # set_markers()：手动替换插件标记 —— 这里是**插件的**标记格式
    # {'time', 'value', 'sign'}：value 是标记画在哪个价位，sign 决定箭头方向
    # （1 上 / 0 平 / -1 下），不是 marker() 的 position/shape/color/text。
    # 传错格式（缺 value）引擎不会报错，只是什么都不画，所以 pylightcharts
    # 会在 set_markers() 里直接抛 ValueError 提醒。
    # 注意：up/down 标记的大小引擎写死了（圆点半径 4px、箭头 4.7px），
    # 没有 size 选项，只能靠正/负颜色区分；想要更大的标记就用经典 marker()
    # （支持 size=）。
    updown.set_markers([
        {'time': int(epoch.iloc[200]), 'value': float(df['close'].iloc[200]),
         'sign': 1},
    ])
    # clear_markers()：清空插件标记
    # updown.clear_markers()
    # apply_options()：透传插件选项。注意引擎的实现：marker 的三种颜色是
    # 建视图时读走的，attach 之后再改 positive_color / negative_color 不会
    # 重绘已有 marker（想换色就在 up_down_markers_plugin(...) 里传）；
    # update_visibility_duration 这类“行为”选项随时改都生效。
    updown.apply_options(positive_color='#00E676')
    # get_series()：取得插件所依附系列的手柄
    updown.get_series()

    # ------------------------------------------------------------------
    # 文本水印插件
    # ------------------------------------------------------------------
    # text_watermark_plugin(...)：创建文本水印并返回插件句柄
    text = chart.text_watermark_plugin('pylightcharts', font_size=40,
                                       color='rgba(140, 160, 200, 0.35)')
    # apply_options()：调整水印对齐 / 可见性（图片水印固定在 pane 中心，所以
    # 文本水印放到下边，两者不会叠在一起）
    text.apply_options(horz_align='center', vert_align='bottom', visible=True)
    # get_pane()：取得水印所在 pane 的手柄
    text.get_pane()

    # ------------------------------------------------------------------
    # 图片水印插件
    # ------------------------------------------------------------------
    # image_watermark_plugin(...)：用内联 data URI 创建图片水印。
    # 位置固定在 pane 中心（引擎只提供 max_width / max_height / padding /
    # alpha 四个选项，没有对齐参数）；alpha=0.4 会与背景混色，所以色值会比
    # LOGO_PNG 里更淡。
    image = chart.image_watermark_plugin(LOGO_PNG, max_width=64,
                                         max_height=64, pane_index=0)
    # apply_options()：调整不透明度与内边距
    image.apply_options(alpha=0.40, padding=12)
    # get_pane()：取得水印所在 pane 的手柄
    image.get_pane()

    # 插件句柄暂存到 chart 上，供 report 阶段读取状态后再卸载
    chart._tour_plugins = {'markers': markers, 'updown': updown,
                           'text': text, 'image': image}

    # ------------------------------------------------------------------
    # 让所有标记都进视野
    # ------------------------------------------------------------------
    # 经典 marker() 和上面的 markers_plugin() 共用同一个 primitive，所以
    # 两套 API 谁最后调用谁生效（这里最终留下的是插件那两个 p1 / p2）；想
    # 让它们同时出现，就把其中一套挂到另一条序列上。
    #
    # fit()：默认视图只显示最后 ~170 根，前面那些 bar 上的标记会落在可视
    # 范围外 —— 引擎只在标记的时间落进可视范围时才画它，所以“标记没显示”
    # 往往只是被 zoom 掉了。fit() 让全部数据入镜（也可以用 scroll_to_*
    # 或 set_visible_range 自己控制）。
    chart.fit()


def report_plugins(chart: Chart) -> None:
    """读取插件状态并卸载 —— 这些是 readback，需要已加载的真实窗口。"""
    plugins = chart._tour_plugins
    # markers()：读取 SeriesMarkersPlugin 当前持有的标记
    print('[markers] ->', plugins['markers'].markers())
    # markers()：读取 UpDownMarkersPlugin 当前持有的标记
    print('[updown]  ->', plugins['updown'].markers())
    # detach()：卸载 markers primitive
    # plugins['markers'].detach()
    # # detach()：卸载 up/down markers 插件
    # plugins['updown'].detach()
    # # detach()：卸载文本水印
    # plugins['text'].detach()
    # # detach()：卸载
    # plugins['image'].detach()
    # 插件句柄：build() 里创建的那些（打印对象只能看到类名与句柄 id）。
    # 注意别在这里再调 markers_plugin() / up_down_markers_plugin() /
    # text_watermark_plugin() / image_watermark_plugin() —— 那些是**工厂**，
    # 再调一次会创建/替换插件（比如用空文本把刚才的水印覆盖掉），
    # 而 up_down_markers_plugin() 挂在图表（K 线）上会直接报错。
    for name, plugin in plugins.items():
        print(f'[plugin] {name:8} {type(plugin).__name__:22} {plugin.id}')


def main() -> None:
    chart = Chart(width=1100, height=800, title='pylightcharts - v5 插件')
    build(chart)
    # 先非阻塞显示，待窗口加载完成后再读取插件状态
    chart.show(block=False)
    report_plugins(chart)
    # 继续阻塞，直到用户关闭窗口
    chart.show(block=True)


if __name__ == '__main__':
    main()

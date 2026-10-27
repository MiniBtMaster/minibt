"""滚动成交量分布图（Rolling Volume Profile）：用声明式自定义系列画横条。

覆盖的 API：
- `chart.add_custom_series(spec={...})`：完全自定义的 paneView。
- `chart.register_js_callback`：注册 `rendererDraw` / `priceValueBuilder` /
  `isWhitespace`。
- `chart.run_script` + `addCrosshairListener`：挂一个**纯 JS** 的十字线监听
  （不回调 Python），让分布图跟随鼠标。
- `view.visibleBars()`：逐帧拿到当前可视的 K 线（`bar.x` = 屏幕 CSS 像素 x、
  `bar.originalData` = 该根的数据行）。
- `target.useBitmapCoordinateSpace(scope => ...)`：在设备像素层绘制
  （`scope.context` / `horizontalPixelRatio` / `verticalPixelRatio`）。
- `priceConverter(price)`：该 pane 的价格 -> 屏幕 y（CSS 像素）。

几何约定（与 minibt 的 bokeh 版 Volume Profile 一致）::

    anchor = 鼠标最近的那根 K 线（鼠标不在图上 -> 最右可见那根）
    band   = 可视跨度 * 0.30          # 满量程柱长（随缩放自适应）
    left   = anchor - 该档量 / vmax * band      # 向左生长
    档区   = 该根往前 window 根的 [min(low), max(high)]（逐根滚动）

量最大的一档（POC）用橙色高亮；主图用**价格档中心**做 y，副图
（`pane_index='new'`）改用**档位序号**做 y（画成“分层直方图”）。

实现细节都放在同目录的 `_volume_profile.py`（`26`/`27` 共用）；
实时版本见 `27_volume_profile_live.py`。

运行：
    python examples/11_api_tour/26_volume_profile.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pylightcharts import Chart                                    # noqa: E402
from _volume_profile import (add_vp, build_frame, make_data,       # noqa: E402
                             volume_profile)


def build(chart) -> None:
    """把本文件覆盖的 API 全部作用在传入的 chart 上（不调用 show）。"""
    df = make_data()
    lo, hi, matrix = volume_profile(df)

    chart.set(df)                       # 主图 K 线
    frame = build_frame(chart, df, lo, hi, matrix)

    # 系列 1（主图）：VP 叠加在 K 线上，y = 价格档中心
    add_vp(chart, frame, 'volume profile', pane_index=None, price_mode=True)
    # 系列 2（新面板）：VP 单独占一个副图，y = 档位序号
    add_vp(chart, frame, 'profile pane', pane_index='new', price_mode=False)


def main() -> None:
    chart = Chart(width=1100, height=800, title='pylightcharts - 滚动成交量分布')
    build(chart)
    chart.show(block=True)


if __name__ == '__main__':
    main()

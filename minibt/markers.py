"""交易信号的箭头图形（**自定义序列**版 ✓）

以前 desk 用 lightweight-charts 的**原生 marker**（`createSeriesMarkers`）：

* 不计入自动缩放 → 放大后箭头被裁掉；
* 回放时序列数据被截断，但 marker 是挂在序列上的 primitive，**截不掉**
  → 未来的信号全堆在最后一根 K 线上；
* 逐点颜色 / 文字受限。

所以改成「自定义序列 + 图形列表」（`pylightcharts` 的
`custom-series` 渲染器，回测图 `apply_signals` 用的就是它）。

这里把**原来那两种箭头**（向上 / 向下实心三角）归纳成 `Markers`，
两个图表（本地图表 / 看盘窗口）和回测图共用同一份定义 ✓

图形名字和 `custom-series.ts::drawMarker` 的 `kind` 一致：
`triangle` / `inverted_triangle` / `diamond` / `square` / `circle` / `cross` …
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

def marker_name(shape: Optional[str]) -> str:
    """任何写法 → `custom-series` 认识的 marker 名字 ✓

    映射表只有一份：`minibt.constant._MARKER_CANVAS_GLYPH` /
    `marker_glyph()`（`SignalStyle` 用的 `Markers.arrow_up` 也在里面）✓
    """
    try:
        from .constant import marker_glyph
        return marker_glyph(shape, 'triangle')
    except Exception:                                            # noqa: BLE001
        return 'triangle'


class Markers:
    """箭头 / 标记图形的工厂（返回 `custom-series` 的 shape 字典 ✓）"""

    #: 默认大小（像素）—— 和原生 marker 的 `size: 1` 观感接近
    SIZE = 12

    @staticmethod
    def arrow(price: float, *, up: bool = True, color: Optional[str] = None,
              size: int = 0, offset: float = 0.0, text: str = '',
              shape: Optional[str] = None, text_size: Optional[int] = None,
              text_color: Optional[str] = None) -> Dict[str, Any]:
        """一个箭头（`up=True` 向上三角，否则向下三角）"""
        item: Dict[str, Any] = {
            'type': 'marker',
            # 默认就是**箭头**（三角形头 + 竖杆），和 LWC 原生 `arrowUp` 同观感 ✓
            'marker': marker_name(shape or ('arrow_up' if up
                                            else 'arrow_down')),
            'price': float(price),
            'offset': float(offset or 0.0),
            'size': int(size or Markers.SIZE),
        }
        if color:
            item['color'] = color
        if text:
            item['text'] = str(text)
            if text_size:
                item['textSize'] = int(text_size)      # `set_label("B", 14)` ✓
            if text_color:
                item['textColor'] = str(text_color)
        return item

    @staticmethod
    def triangle(price: float, **kwargs) -> Dict[str, Any]:
        return Markers.arrow(price, up=True, **kwargs)

    @staticmethod
    def inverted_triangle(price: float, **kwargs) -> Dict[str, Any]:
        return Markers.arrow(price, up=False, **kwargs)

    @staticmethod
    def at(value: float, *, shape: Optional[str] = None,
           color: Optional[str] = None, size: int = 0) -> Dict[str, Any]:
        """任意形状（`shape` 用 `custom-series` 的名字 ✓）"""
        return Markers.arrow(value, up=True, color=color, size=size,
                             shape=shape or 'circle')

    @staticmethod
    def series(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """`[{time, price, up, color, text}, …]` → 自定义序列的数据行 ✓

        每行 `{time, value, shapes:[…]}`：`value` 是自动缩放用的「价格」，
        `shapes` 才是真正画出来的箭头 ✓
        """
        rows: List[Dict[str, Any]] = []
        for item in values or []:
            price = item.get('price')
            stamp = item.get('time')
            if price is None or stamp is None:
                continue
            row = {
                'time': int(stamp),
                'value': float(price),
                'shapes': [Markers.arrow(
                    float(price),
                    up=bool(item.get('up', True)),
                    color=item.get('color'),
                    size=int(item.get('size') or 0),
                    text=str(item.get('text') or ''),
                    shape=item.get('shape'),
                    text_size=int(item.get('textSize') or 0),
                    text_color=item.get('textColor'),
                )],
            }
            rows.append(row)
        return rows

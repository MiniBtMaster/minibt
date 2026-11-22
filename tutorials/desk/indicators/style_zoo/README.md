# Style Zoo：minibt desk 指标样式示例

这一组文件从 `~/.minibt/personal/indicators/style_zoo_*.py` 整理而来，
专门演示 **`BtIndicator` / `PlotInfo` 的样式能力**。在 desk 的本地图表里：

1. 打开一个本地 CSV；
2. 编辑器打开本目录下的任意一个 `.py`；
3. 点「加到图表」→ 指标会按当前 CSV 重算并套用样式。

也可以在 **看盘窗口** 加到实时合约；本地图表与看盘窗口使用同一套
样式渲染。

## 分类

| 文件 | 分类 | 重点样式 | 图上应该看到 |
| --- | --- | --- | --- |
| `style_zoo_main.py` | 主图 | `linestyle` / `bandstyle` / `signalstyle` / `watermark` | 6 种线型 + 色带 + 价格线 / 标签 + 买卖箭头 + 水印 |
| `style_zoo_osc.py` | 副图 | `LineDash.vbar` / `spanstyle` / `tablestyle` / `isplot` | 红绿柱 + 水平参考线 + 右上角统计表 + 隐藏原始列 |
| `style_zoo_candle.py` | 蜡烛型 | `candlestyle` | 平滑 OHLC 小蜡烛（涨绿跌红） |
| `style_zoo_signals.py` | 信号文字 | `signalstyle` / `signal_text()` / `Markers` | 箭头 + 逐点文字 + 自定义字号 / 颜色 |
| `style_zoo_table.py` | 动态表格 | `tablestyle` + `table_rows()` | 表格跟随鼠标，显示当前 bar 的值 |
| `style_zoo_vp.py` | 成交量分布 | `category='vp'` + `vpstyle` | 主图右侧横向成交量分布、POC 高亮 |
| `style_zoo_mixed.py` | 主副图混排 | 逐线 `overlap` / 圆形离场标记 | 趋势线在主图、振荡线在副图 + 圆形平仓标记 |
| `style_zoo_func.py` | 函数式 | 自动配色 / `__desk_indicator__` | 多列 DataFrame 自动上色（函数式写不了 PlotInfo） |

## 写样式指标的最小规则

```python
class MyIndicator(BtIndicator):
    lines = ('a', 'b', 'long_signal')       # 数量、顺序 = next() 返回值
    params = dict(length=20)
    overlap = True                          # 或 dict(a=True, b=False)
    linestyle = dict(a=LineStyle(...))
    signalstyle = dict(long_signal=SignalStyle(...))
    bandstyle = [BandStyle(lower='b', upper='a')]
    tablestyle = TableStyle(...)
    watermark = WaterMark(text='MY IND')

    def next(self):
        return a, b, long_signal
```

* 信号列不要写 `isplot=False`；只在 `signalstyle` 里声明就会被画成箭头。
* `isplot=False` 只用于“纯数据列”。
* 函数式指标（`def MyInd(frame): ...`）只能自动配色，不能写 `PlotInfo`；
  需要完整样式请用 `BtIndicator` 子类。
* `pair_klines = (腿A, 腿B)` 是 **回测 / 优化** 的约定，不影响指标样式。

## 注意

* `style_zoo_vp.py` 固定 40 条 `vp0..vp39` 线；改档数要同时改 `lines`
  和 `next()` 的二维矩阵列数。
* 样式示例里的信号是**低频**的（带冷却），一屏可能只有一两个箭头。
* 如果某个样式没生效，先看该样式是否属于本文件的分类（例如
  `vpstyle` 只对 `category='vp'` 生效）。

更多规则见 `minibt_docs/docs/minibt_desk/manual/13.17_local_chart_add.md`
和 `13.21_local_chart_indicator_styles.md`。

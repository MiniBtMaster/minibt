"""11 · 九种模式合一（CCI 均值回归策略）

一个文件看懂 **三个图表引擎 × 三个使用场景 = 九种模式**。

引擎（``Gui.`` 枚举）：

| 引擎 | 渲染位置 | 依赖 |
| --- | --- | --- |
| ``Gui.Bokeh`` | 浏览器（纯 bokeh server） | 只要 bokeh |
| ``Gui.Pylightcharts`` | **原生窗口**（Qt + WebView2） | PyQt6 + PyQt6-WebEngine |
| ``Gui.PylightchartsWeb`` | 浏览器标签（本地 HTTP + SSE） | 只要标准库 |

场景（都支持三个引擎）：

| 场景 | 入口 | 默认引擎 |
| --- | --- | --- |
| ① 回测 | ``Bt().run(gui=...)`` | ``Gui.Pylightcharts`` |
| ② 回放 | ``Bt(replay=True).run(gui=...)`` | ``Gui.Pylightcharts`` |
| ③ 实时 | ``Bt(auto=False, live=True)`` + ``addTqapi`` + ``addstrategy`` + ``bt.run(gui=...)`` | ``Gui.Pylightcharts`` |

所以 9 行入口就是「3 × 3」，文件末尾按引擎分 3 组列出，**只取消注释一行**即可。

    运行：``python tutorials/plots/11_all_nine_modes_cci.py``

    默认跑 **纯 pylightcharts + 回放**（下面 __main__ 里那一行没被注释的）；
    其它 8 行都注着，想换模式就注释/取消注释对应那行。

本示例顺带演示 1.2.9 的图表能力（都写在策略里，不需要碰图表 API）：

* ``Config.watermark``（默认 ``True``）—— 水印 = **合约自身名称**；``False`` 全部不画
* ``LineStyle`` 的柱体系列 —— ``line_dash=LineDash.vbar`` + ``vbar_base`` 柱底基线，
  以及 ``vbar_up_color`` / ``vbar_down_color`` / ``vbar_color_base`` 上下行配色与分界
* ``run(..., y_margin=...)`` —— 价格轴上下留白（**默认 0.03**；``(0.2, 0.1)`` 回到
  lightweight-charts 原样，``0.0`` 铺满），只作用于 pylightcharts
* ``data_length`` + ``history_length`` —— 实盘「无限历史」：开局只放 200 根，
  向左滚动由底层 1 万根快照补历史
* 回测/回放都带「回测结果 / 指标记录」两页：权益、回撤、每笔盈亏、交易记录

策略要点（CCI 均值回归，来自天勤示例）：
``cci`` 上穿 -100 / 下穿 +100 的状态机 → ``cross_up(0)`` / ``cross_down(0)`` 出信号，
BBand 式色带（``bandstyle``）+ ±100/0 水平线（``spanstyle``）看位置，
``color_by`` 给 K 线和均线逐点配色，``signal_style`` 给信号加 ``B``/``S`` 文字。
"""

import os
import sys

# 保证用本仓库的 minibt（避免被 site-packages 里的旧版本遮蔽）
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *          # noqa: F401,F403  (Strategy/Config/LocalDatas/...)


class CCI(BtIndicator):
    """CCI 指标：均值回归的经典用法。

    https://www.shinnytech.com/articles/trading-strategy/mean-reversion/cci-strategy
    """

    # 信号线本身不上图（只留图例文字）：`long_signal` / `short_signal` 这两条
    # 0/1 序列画出来会是一条锯齿线，没意义；信号用 marker 表达就够了。
    isplot = dict(long_signal=False, short_signal=False)
    params = dict(CCI_PERIOD=10, CCI_UPPER=100, CCI_LOWER=-100)
    # 指标放副图（不叠加到 K 线上）：CCI 量级 ±100，和价格放一起会互相压扁
    overlap = False

    def next(self):
        CCI_PERIOD = self.params.CCI_PERIOD          # CCI 计算周期
        CCI_UPPER = self.params.CCI_UPPER            # CCI 上轨
        CCI_LOWER = self.params.CCI_LOWER            # CCI 下轨
        cci = self.close.cci(CCI_PERIOD)
        size = cci.size
        cci_state = self.ones
        for i in range(CCI_PERIOD + 1, size):
            # 状态机：> 上轨记 1、< 下轨记 -1、中间保留原始 CCI。
            #
            # 注意 else 分支要用**当前**的 cci[i]，不能用 cci[i-1]：
            # 用 cci[i-1] 相当于把状态整体滞后一根，cross_up(0)/cross_down(0)
            # 会在 0 轴穿越的**下一根**才出信号（信号滞后一根）。
            cci_state[i] = cci[i] > CCI_UPPER and 1. or (
                cci[i] < CCI_LOWER and -1. or cci[i])
        # 状态穿越 0 轴 = 原始 CCI 穿越 0 轴（夹取只改幅度、不改符号）
        long_signal = cci_state.cross_up(0.)
        short_signal = cci_state.cross_down(0.)
        zero = self.zeros()
        # 返回值就是画出来的线（顺序对应 `lines`）：cci / zero 两条，
        # 信号两条因为 isplot=False 只进图例
        return cci, zero, long_signal, short_signal


class CCIStrategy(Strategy):
    """CCI 均值回归策略（回测 / 回放 / 实时三场景共用）。"""

    # `Config` 是**策略级**的图表/回测配置（三个引擎共用）：
    #   equity_overlay=True  回放/实时在 K 线主图叠加权益曲线（左刻度）
    #   capital_line=True    画初始资金虚线（+ 与权益之间的色带）
    #   bokeh_fullscreen     bokeh 页面铺满视口（None=自动：浏览器 True / Jupyter False）
    #   theme                深/浅色（'dark' / 'light'）
    #   watermark=True       水印=合约自身名称（默认就是 True，这里显式写出来看的清楚）
    # 价格轴留白不是 Config 字段，而是**每次 run(...) 传的参数**（见文件末尾）：
    #   run(gui=..., y_margin=0.03)     默认就是 3%（面板高度上下各 3%）
    #   run(gui=..., y_margin=(0.2,0.1)) 回到 lightweight-charts 原样
    #   run(gui=..., y_margin=0.0)       铺满
    config = Config(equity_overlay=True, capital_line=True, watermark=True,
                    bokeh_fullscreen=True, theme='light')
    # 实盘/实时的合约；回测/回放用下面的本地数据
    params = dict(symbol='SHFE.ni2612')

    def __init__(self):
        self.min_start_length = 300          # 至少 300 根才开始交易（暖机）
        if self.is_live_trading:
            # 实盘「无限历史」：底层一次取 10000 根（向左滚动时可翻），
            # 图表开局只放出最后 200 根。
            # 另外 `data_length` 也是**每根行情变化要重算指标的根数**（preload）：
            # 1000 根时重算约 48ms/策略，200 根只要 ~18ms，越小越跟手。
            self.data = self.get_kline(
                self.params.symbol, data_length=200, history_length=10000)
        else:
            # 回测/回放：本地 CSV（`LocalDatas` 里还有 test / l2609_60 /
            # pp2609_60 ...；自己放进 ~/.minibt/datas 的数据也会出现在这）
            self.data = self.get_kline(LocalDatas.pp2609_60, height=500)
            # 第二个合约：只画 K 线（没有交易），用来对照
            self.data1 = self.get_kline(LocalDatas.l2609_60)

        # K 线逐根配色：阳线 lime、阴线 tomato
        # （等价于 Candlestick 的 bull_color/bear_color，但支持任意条件）
        self.data.color_by(self.data.close >= self.data.open,
                           Colors.lime, Colors.tomato)

        self.cci = CCI(self.data)

        # 均线：点划线 + 黄色 + 不画价格线/标签；`color_by` 再让上行段变橙
        self.ma = self.data.close.sma(30)
        self.ma.line_style = LineStyle(
            line_dash=LineDash.dashdot, line_width=3,
            line_color=Colors.yellow, price_label=False, price_line=False)
        self.ma.color_by(self.ma.diff() > 0, Colors.orange)

        # 水印：`Config.watermark=True` 时**不写这行也是合约名**；
        # 想自定义文本就显式设（例如 self.data.watermark = '我的策略'）：
        # self.data.watermark = f'{self.data.symbol}'
        # 注意：只在 `python cci.py`（回测/回放，走本地数据）时才有意义

        # CCI 副图：0 / ±100 三条水平线 + cci~zero 之间的红色色带
        self.cci.span_style += [
            SpanStyle(0), SpanStyle(-100), SpanStyle(100)]
        self.cci.bandstyle += BandStyle(
            'cci', 'zero', fill_color=Colors.red, fill_alpha=0.3)   # alpha>=0.15 才明显

        # MACD：三线指标，画在另一个副图（每个指标一个 pane）
        self.macd = self.data.close.macd()
        # 想让 MACD 柱体（macdh）按上下行分色，可以这样写：
        # self.macd.line_style = dict(
        #     macdh=LineStyle(line_dash=LineDash.vbar, vbar_base=0,
        #                     vbar_up_color=Colors.lime,      # 分界之上
        #                     vbar_down_color=Colors.tomato,  # 分界之下
        #                     vbar_color_base=0))             # 配色分界（默认跟柱底）
        # 不写 `vbar_up/down_color` 时自动跟主图 K 线的涨/跌色

        # 交易信号：图标 + 文字标签（`set_label('B')` 会在信号旁写 B）
        self.cci.signal_style = dict(
            long_signal=SignalStyle(
                'low', Colors.red, Markers.triangle).set_label('B'),
            short_signal=SignalStyle(
                'high', Colors.yellow,
                Markers.inverted_triangle).set_label('S'),
        )

        # RSI 画成**柱体**（LineDash.vbar），并绕中轴 50 振荡：
        #   line_dash=vbar  柱体（正负/上下自动分色）
        #   vbar_base=50.   柱底基线（默认 0；RSI 用 50 才是“绕中轴”）
        #   vbar_color_base 配色分界（不写就跟随 vbar_base）
        #   vbar_up_color / vbar_down_color 不写就跟主图 K 线涨/跌色
        self.rsi = self.data.close.rsi()
        self.rsi.line_style = LineStyle(line_dash=LineDash.vbar,
                                        vbar_base=50.)

    def next(self):
        # 空仓时按信号开仓；止损交给 `SegmentationTracking`（分段跟踪止损）
        if not self.data.position:
            if self.cci.long_signal.new:
                self.data.buy(stop=BtStop.SegmentationTracking)
            elif self.cci.short_signal.new:
                self.data.sell(stop=BtStop.SegmentationTracking)


# ============================================================================
# 九种模式入口：三个引擎 × 三个场景
#
# 用法：取消注释**一行**运行；想换引擎/换场景就换那一行。
#   * 回测：一次跑完，图表上能看「回测结果 / 指标记录」两页
#   * 回放：播放 / 暂停 / 单步 / 调速，指标与回测曲线逐根推进
#   * 实时：接天勤（TqApi）按 tick 推进，默认引擎是原生窗口
#
# 小贴士：
#   * `gui=` 也可以直接写字符串：`'bokeh'` / `'pylightcharts'` /
#     `'pylightcharts_web'`（等价于对应枚举）
#   * `run(..., y_margin=0.05)` 可以**逐次**覆盖价格轴留白；
#     `wait_update` 驱动的刷新节奏也可调：`period_milliseconds=100`
#   * 浏览器模式可指定端口：`run(gui=Gui.PylightchartsWeb, port=8123)`
#   * Jupyter 里用 `Gui.Jupyter`（本地 SSE + iframe，不阻塞 kernel）
# ============================================================================
if __name__ == '__main__':
    # ---------------------------------------------------------------- ① Bokeh
    # 纯 bokeh server：回测报告 / 回放 / 实时共用同一套构建器
    # Bt().run(gui=Gui.Bokeh)                          # ① 回测（bokeh；默认是 pylightcharts）
    # Bt(replay=True).run(gui=Gui.Bokeh)               # ② 回放（内存逐 bar 揭开）
    # from tqsdk import TqApi, TqAuth, TqKq            # ③ 实时
    # api = TqApi(TqKq(), auth=TqAuth('用户名', '密码'))
    # bt = Bt(auto=False, live=True)
    # bt.addTqapi(api=api)
    # bt.addstrategy(CCIStrategy.copy(name = "CCIStrategy", params=dict(symbol='SHFE.ni2612')))
    # # 多合约：每加一个策略就多一个合约 tab（各占一个 pane）
    # # bt.addstrategy(CCIStrategy.copy(params=dict(symbol='SHFE.ag2612')))
    # bt.run(gui=Gui.Bokeh)

    # ------------------------------------------------- ② 纯 pylightcharts（原生窗口）
    # 不依赖浏览器；本示例**默认只跑这一行**（回放）
    # Bt().run(gui=Gui.Pylightcharts)                  # ① 回测展示
    Bt(replay=True).run(gui=Gui.Pylightcharts)         # ② 回放 ← 默认
    # Bt().run(gui=Gui.Pylightcharts, y_margin=0.05)   # ① 回测 + 自定义价格轴留白
    # from tqsdk import TqApi, TqAuth, TqKq            # ③ 实时
    # api = TqApi(TqKq(), auth=TqAuth('用户名', '密码'))
    # bt = Bt(auto=False, live=True)
    # bt.addTqapi(api=api)
    # bt.addstrategy(CCIStrategy.copy(name = "CCIStrategy1", params=dict(symbol='SHFE.ni2612')))
    # # bt.addstrategy(CCIStrategy.copy(name = "CCIStrategy2", params=dict(symbol='SHFE.ag2612')))
    # # bt.addstrategy(CCIStrategy.copy(name = "CCIStrategy3", params=dict(symbol='SHFE.au2612')))
    # bt.run(gui=Gui.Pylightcharts, y_margin=0.03)

    # --------------------------------------------- ③ pylightcharts_web（浏览器标签）
    # 本地 HTTP + SSE，同一端口可以开多个浏览器标签；服务器/远程也能看
    # Bt().run(gui=Gui.PylightchartsWeb)               # ① 回测展示
    # Bt(replay=True).run(gui=Gui.PylightchartsWeb)    # ② 回放
    # from tqsdk import TqApi, TqAuth, TqKq            # ③ 实时
    # api = TqApi(TqKq(), auth=TqAuth('用户名', '密码'))
    # bt = Bt(auto=False, live=True)
    # bt.addTqapi(api=api)
    # bt.addstrategy(CCIStrategy.copy(name = "CCIStrategy", params=dict(symbol='SHFE.ni2612')))
    # bt.run(gui=Gui.PylightchartsWeb, port=8123)

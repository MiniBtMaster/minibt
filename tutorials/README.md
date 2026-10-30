# tutorials —— 可运行示例总索引

> **约定（例子先行）**：每个主题 = 一个 `.py`（一个功能一篇），先在仓库根目录能
> `python xxx.py` 跑通，再写文档；文档在 `minibt_docs/docs/` 里**同号同名**引用它。
> 完整规则见 `minibt_docs/DOCS_PLAN.md`。

## 目录一览

| 目录 | 对应文档 | 内容 |
| --- | --- | --- |
| `basic/` | `minibt_basic/` | 早期通用示例（btplot / live_chart / stop / table / optstrategy / signal_* / 策略回放 …） |
| `plots/` | `minibt_basic/1.29` | 三引擎 × 三场景（九种图表模式）+ 本地 mock 实时 |
| `strategies/` | `minibt_strategies/` | 18 个策略示例（原 `strategy/`） |
| `styles/` | `minibt_styles/`（第 7 章） | **图表样式（PlotInfo）逐字段示例** ★新增 |
| `tips/` | `minibt_tips/`（第 5 章） | 使用技巧 5.9–5.25（图表技巧 / 数据性能 / 仓位止损 / 实盘 / 排错） |
| [`indicators/`](indicators/README.md) | `minibt_indicators/`（第 8 章） | 指标库与自定义指标 8.1–8.14（12 个门面 / 自定义 / 字段 / 解包 / 回测 / 性能 / 共享副图），见 [`indicators/README.md`](indicators/README.md) |
| [`elegantrl/`](elegantrl/README.md) | `minibt_reinforcement_learning/`（第 4 章） | 参数优化 / Cython 信号优化 / ElegantRL 动态仓位 / 参数 bandit；结论见第 4.8 章 |
| `vscode/` | `minibt_ide/`（第 12 章） | 编辑器/工具链 12.1–12.5（扩展 / btplot / 九模式 / notebook / 打包）★新增 |
| `realtime/` | `minibt_realtime/`（第 11 章） | 实时/实盘 11.1–11.9（不联网、不下单）★新增 |
| `orders/` | `minibt_orders/`（第 10 章） | 订单/止损/仓位/费用/日志/时段/账户 10.1–10.12（共用 `_shared.py`） |
| `data/` | `minibt_data/`（第 9 章） | 数据层 9.1–9.12（对象总览 / LocalDatas / KLine / IndFrame / IndSeries / Line / 代理 / 数据源 / resample / 长度 / DataFrame / 多合约）；**`13_futu.ipynb`（富途取数 · Jupyter）、`14_futu_quota.py`（富途额度实测）** ★新增 |


## styles/（第 7 章 图表样式）

| # | 例子 | 文档 | 演示 |
| --- | --- | --- | --- |
| 01 | `01_plotinfo_overview.py` | 7.1 PlotInfo 心智模型 | 主图 / 副图 / 信号一次讲清 |
| 02 | `02_lines.py` | 7.2 lines / line_filed / signallines | 列名与顺序、信号自动识别、`lines` 自动解析 |
| 03 | `03_category.py` | 7.3 category | `category='candles'` → 4 条线合成一根蜡烛 |
| 04 | `04_isplot.py` | 7.4 isplot | `bool` / 按线序 `list` / 按线名 `dict` |
| 05 | `05_legend.py` | 7.5 legend | 线照画、图例行隐藏 |
| 06 | `06_overlap.py` | 7.6 overlap | 副图蜡烛 → 叠到主图（覆盖型蜡烛图） |
| 07 | `07_linestyle.py` | 7.7 linestyle | 4 种线型 / 线宽 / 颜色 + 右轴价格线 |
| 08 | `08_vbar.py` | 7.8 vbar | `LineDash.vbar` + `vbar_base` / 上下行色 |
| 09 | `09_candlestyle.py` | 7.9 candlestyle | 主图 K 线 + 副图蜡烛两套配色 |
| 10 | `10_signalstyle.py` | 7.10 signalstyle | 4 种图标 / 大小 / 标签 / `show=False` |
| 11 | `11_signal_text.py` | 7.11 signal_texts | `signal_text()` 逐根写价格 |
| 12 | `12_spanstyle.py` | 7.12 spanstyle | 3 条水平分界线 |
| 13 | `13_bandstyle.py` | 7.13 bandstyle | 均线通道色带 |
| 14 | `14_watermark.py` | 7.14 watermark | 自定义水印文本 |
| 15 | `15_source.py` | 7.15 source | 两个指标 → 两个副图 |
| 16 | `16_vpstyle.py` | 7.16 vpstyle | 成交量分布 + POC |
| 17 | `17_tablestyle.py` | 7.17 tablestyle | 可拖动统计表格 |
| 18 | `18_color_rules.py` | 7.18 color_rules | 放量柱上色 + 零轴上下变色 |
| 19 | `19_tradestyle.py` | 7.19 tradestyle | 成交标记 + 入场→离场连线（真回测） |
| 20 | `20_config.py` | 7.20 Config | grid / y_margin / tradestyle=show=False |
| 21 | `21_run_params.py` | 7.21 入口参数 | `y_margin=(0.2,0.1)` 留白对比 |
| 22 | `22_theme.py` | 7.22 主题 | `theme='dark'` 深色图 |
| 23 | `23_engine_diff.py` | 7.23 引擎差异 | BOLL 色带 + 右轴价格线（综合） |

运行（仓库根目录）：

```bash
python tutorials/styles/01_plotinfo_overview.py
# 想用浏览器而不是原生窗口：把脚本里的 btplot(gui=gui) 传 'pylightcharts_web'
```

例子默认只依赖**内置数据**（`LocalDatas.test / pp2609_60 / l2609_60`），
不需要联网、不需要账号、不下单。

## 文档截图

`minibt_docs` 里的图由 `scripts/capture_docs_images.py` 用**同一套 pylightcharts
渲染器**（网页版静态页 + headless Edge/Chrome）批量生成，可重复：

```bash
python scripts/capture_docs_images.py tutorials/styles \
    --out-dir minibt_docs/docs/minibt_styles/images
```

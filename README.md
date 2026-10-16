# MiniBT Charts（VS Code 扩展）

[![VS Marketplace](https://img.shields.io/visual-studio-marketplace/v/MiniBtMaster.minibt-charts?label=marketplace&color=green)](https://marketplace.visualstudio.com/items?itemName=MiniBtMaster.minibt-charts)

在 **VS Code 编辑器页签**里运行并查看 [MiniBT](https://github.com/MiniBtMaster/minibt)
的图表 —— 就像打开一个代码文件那样，和代码**并排、可拖拽分屏**：

- **回测 / K 线回放 / 实时行情**三种策略场景（`Bt().run()` / `Bt(replay=True).run()` / `Bt(live=True).run()`）；
- **`btplot` 指标图**（`ind.btplot()` / `kline.macd().btplot()`）；
- 通过编辑器标题栏的**快速按钮**（**MiniBT 专属的 K 线图标**）运行策略和指标。

```
Ctrl+Alt+M   运行策略，图表开在编辑器页签（实时刷新）
Ctrl+Alt+L   策略日志页签（带进度条）
```

## 快速开始

1. 你的 Python 环境里装好 minibt：

   ```bash
   pip install minibt
   ```

2. 装了多个 Python / 用了虚拟环境时，在工作区设置 `.vscode/settings.json` 里指定：

   ```json
   { "minibt.pythonPath": ".venv/Scripts/python.exe" }
   ```

   （**不指定也行** —— 扩展会自动挑一个 `minibt` 依赖齐全的解释器 ✓）

3. 打开策略 / 指标 `.py`，按 **`Ctrl+Alt+M`**（或点标题栏的 **K 线按钮**）——
   图表就开在**编辑器页签**里；关掉页签即结束策略进程，日志在 `MiniBT` 输出面板 ✓。

## 它是怎么做到的

| MiniBT 图表模式 | 能否嵌进 VS Code | 说明 |
| --- | --- | --- |
| `Gui.Pylightcharts`（原生窗口） | ❌ | PyQt6 + WebView2 的**独立操作系统窗口**，webview 装不下 |
| `Gui.PylightchartsWeb`（网页版） | ✅ **默认就用它** | 同一套 lightweight-charts + pylightcharts bundle，画出来的图**完全一致**，只是容器从原生窗口换成浏览器页 |
| `Gui.Bokeh` | ✅ | bokeh server 是网页：回放/实时按 URL 嵌 iframe，回测自动导出成自包含 HTML |

扩展在运行策略前接管 `Bt.run` / `btplot`，**跟随策略里写的 gui**：

| 策略里写的 | 扩展里看到的 |
| --- | --- |
| `gui=Gui.Bokeh` | bokeh（回放/实时用 bokeh server 嵌 iframe；回测是自包含 HTML 快照） |
| `gui=Gui.PylightchartsWeb` | pylightcharts 网页版（本地 SSE + iframe，活图） |
| `gui=Gui.Pylightcharts`（原生窗口） | 自动换成**同一渲染器**的网页版（原生窗口没法嵌） |
| 没写 gui | 同上（minibt 默认是原生窗口 → 网页版） |

想强制一个引擎就设 `minibt.engine`（`pylightcharts` / `bokeh`）。

> 策略里写的是 `Gui.Pylightcharts` 也没关系 —— 你看到的仍然是 pylightcharts
> 渲染的图表。需要原生窗口（多显示器摆放、窗口拖拽）时，照旧直接运行策略。

扩展只看两类标记，非常直白：

```
MINIBT_URL=http://127.0.0.1:PORT/    → iframe 嵌本地服务（活图，持续刷新）
MINIBT_HTML=/path/chart.html         → 自包含 HTML 直接当页签内容（bokeh 回测/静态图）
```

## 命令

| 命令（命令面板 `Ctrl+Shift+P` 输入 `MiniBT`） | 快捷键 | 作用 |
| --- | --- | --- |
| `MiniBT: 在编辑器页运行策略图表` | `Ctrl+Alt+M` | 当前编辑器是 `.py` 就用它；否则弹文件选择框 |
| `MiniBT: 显示策略日志（带进度）` | `Ctrl+Alt+L` | 日志页签 + 进度条（认 `进度 x/y`、`xx%`、`[i/n]`，报错标红） |
| `MiniBT: 刷新图表` | — | 重新加载图表（live 页签加时间戳防缓存；快照页签重读文件） |
| `MiniBT: 停止策略进程` | — | 结束整棵策略进程树（关页签时也会自动结束） |
| `MiniBT: 在浏览器中打开图表` | — | 用系统浏览器打开同一张图（live 用地址，快照用文件） |
| `MiniBT: 显示策略输出（原始日志）` | — | 打开 `MiniBT` 输出面板 |

编辑器标题栏会有一个 **MiniBT 快速按钮**（K 线图标），就在原生「运行 ▾」
按钮右边的同一行里（「运行」是**独立图标**，不占 VS Code 原生运行按钮 ✓）；
图表页签自己则会出现「日志 / 刷新 / 停止」图标按钮。

## 设置

| 设置项 | 默认 | 说明 |
| --- | --- | --- |
| `minibt.pythonPath` | `python` | **最重要**：指向装了 `minibt` 的解释器（例如虚拟环境的 `python.exe`）；留默认 `python` 且它不能用时会**自动挑**一个 |
| `minibt.engine` | `auto` | `auto` 跟随策略（`Gui.Bokeh` → bokeh；`Gui.Pylightcharts` / `PylightchartsWeb` → 网页版）；也可强制 `pylightcharts` / `bokeh` |
| `minibt.port` | `0` | 本地服务端口；0 = 自动挑空闲端口（推荐）；想固定地址再设 |
| `minibt.cwd` | 空 | 策略的工作目录（相对路径取数据用）；留空 = 工作区根目录 |
| `minibt.extraPythonArgs` | `[]` | 附加 Python 参数，如 `["-X", "faulthandler"]` |
| `minibt.openBrowser` | `false` | 是否额外用系统浏览器打开 |
| `minibt.openLog` | `true` | 运行时自动打开日志页签 |
| `minibt.keepAliveOnClose` | `false` | 关闭图表页签时是否保留策略进程 |

> 建议在**工作区设置**里指定虚拟环境的解释器：
> `.vscode/settings.json` → `{"minibt.pythonPath": ".venv/Scripts/python.exe"}`。
> 想让它自动找，就**不要**显式配 —— 扩展会依次试
> `python.defaultInterpreterPath`、`py -0p` 列出的各版本、`python`/`python3`，
> 选第一个能 `import rich, pylightcharts` 的（minibt 的依赖齐）。

## 常见问题

**图表页签一直白屏 / 提示"图表服务没起来"**
1. 打开 `MiniBT` 输出面板看报错；
2. 确认 `minibt.pythonPath` 的解释器里装了 minibt：
   `python -c "import minibt; print(minibt.__version__)"`；
3. 报 `ModuleNotFoundError: No module named 'xxx'` 说明解释器选错了 —— 输出面板
   会告诉你当前用的是哪个 `python.exe`、缺哪个包，并给出可直接复制的
   `"...\python.exe" -m pip install xxx`；也可以直接把 `minibt.pythonPath`
   指向装了 minibt 的那个解释器；
4. 确认策略里取数据用的是**绝对路径**或正确的工作目录（`minibt.cwd`）；
5. 换一个端口试试（`minibt.port`）。

**页签里看不到实时刷新**
网页版是 SSE 推送、bokeh 是 server 推送，两者都是实时的；bokeh 的**回测结果**
本来就是一帧定格（静态 HTML），这是正常的。

**bokeh 回测为什么是"快照"而不是活图？**
bokeh 的回测结果是一个静态 HTML 页面（没有 server），扩展会把它作为静态页签嵌
进来；回放/实时才是 bokeh server（活图）。

## 开发 / 打包 / 发布

见 [`PUBLISHING.md`](PUBLISHING.md)（本地 VSIX 安装、F5 调试、发布到 Marketplace
全流程、常见报错表）。

仓库里 `tests/test_vscode_extension.py` 会校验清单/代码/运行器三方一致
（命令、设置项、打包白名单；并确认不再占用 `editor/title/run` ✓）。

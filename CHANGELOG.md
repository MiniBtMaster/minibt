# 更新日志

## 0.3.7

### 其它

- **只修正商店页的介绍（功能与 0.3.6 完全一致）**：插件市场的**版本号不可覆盖** ✗
  （0.3.6 已发布，网页/命令行重传都会报 `version '0.3.6' already exists`），
  而商店页的 README（Overview）取的是**最新已发布版本**里那份 ✓ ——
  所以把“介绍还停在 0.3.5”的问题随新版本一起发出来 ✓。
  详见 `PUBLISHING.md` 「六、常见问题」。

- 版本 0.3.6 → **0.3.7**（内容同 0.3.6，见下）。

## 0.3.6

### 修复

- **`python` 不是装了 minibt 的那个解释器 → 图表起不来**
  （`ModuleNotFoundError: No module named 'rich'`）：扩展原来直接拿
  `minibt.pythonPath`（默认 `python`）去跑 —— 但 PATH 上的 `python` 常常不是
  工作区配的那个版本，minibt 的依赖（rich 等）就缺了 ✗。现在：
  - `minibt.pythonPath` **未显式配置**时自动挑一个能用的：
    VS Code / Python 扩展的 `python.defaultInterpreterPath` → Windows
    `py -0p` 列出的全部版本 → `python` / `python3`，选第一个依赖齐
    （`rich` / `pylightcharts`）的 ✓。探测只在配置的解释器不能用时才跑，
    且用便宜的 `import rich, pylightcharts`（`import minibt` 要 ~10s，会把
    启动拖死 ✗）；显式配了 `minibt.pythonPath` 就完全尊重、不探测 ✓。
  - runner 的报错**指名缺哪个模块**、当前解释器是谁，并给出可直接复制的
    `"...\python.exe" -m pip install rich` ✓。

### 内部

- 版本 0.3.5 → **0.3.6**。

## 0.3.5

### 修复

- **运行入口改成编辑器标题栏的「快速按钮」（和 Pi Agent Studio 一样）**：
  之前用的是通用条形图图标 `$(graph)`，而且挂在 `navigation@1`、总是排在其他
  扩展图标之后，编辑器图标一多就容易被挤进 `…` 溢出菜单，用户根本找不到 ✗。
  现在换成 **MiniBT 专属的 K 线图标**（`media/run-dark.svg` /
  `media/run-light.svg`，跟随深/浅色主题自动切换），并**去掉
  `editorLangId == python` 限制** —— 任何文件都能看到这个「运行」快速按钮，
  点它就运行当前 `.py`（当前不是 `.py` 时会弹文件选择框）✓。
- **修掉图表起不来提示里的死命令**：错误提示还在让用户去试
  「MiniBT: 导出图表到编辑器页（静态快照）」，而该命令 0.3.4 已删除 ✗；
  改成提示检查 `minibt.pythonPath` 的解释器里有没有装 minibt。

### 内部

- 版本 0.3.4 → **0.3.5**；`minibt.engine` 在代码里的兜底值与清单默认值
  统一成 `auto`。

## 0.3.4

### 删除

- **「导出图表到编辑器页（静态快照）」与「导出图表为 HTML 文件…」**：静态快照
  在多合约回测下不能切换合约，不适合当成编辑器页签 ✗。
- **「MiniBT: 程序内回测（MiniQT 结果面板）」**：MiniQT 内已有策略回测按钮，
  功能重复 ✗。相应地删掉了扩展里的 MiniQT 宿主 RPC（`hostRpc` / `callHost`）、
  `minibt.hostAvailable` 上下文，以及运行器的 `--export-html` 导出模式。

### 修复

- **不再占用 VS Code 原生的「运行 ▾」（`editor/title/run`）**：之前把
  `runInEditor` 挂进 `editor/title/run`，会把编辑器右上角的运行按钮顶掉/显示
  异常 ✗。现在改为编辑器标题栏的**独立图标**（`editor/title`，仍只在
  `editorLangId == python` 时显示），原生运行按钮不受影响 ✓。

### 保留

- **「在编辑器页运行策略图表」**（`Ctrl+Alt+M`）：子进程跑策略，把
  pylightcharts 网页版 / bokeh 的活图嵌进编辑器页签；配套「日志 / 刷新 / 停止 /
  在浏览器打开 / 输出」等命令不变 ✓。

### 内部

- 版本 0.3.3 → **0.3.4**；运行器去掉 `--export-html` / `_collect_export`。

## 0.3.3

### 新增

- **「MiniBT: 程序内回测（MiniQT 结果面板）」**：挂在编辑器**「运行 ▾」菜单**里
  （`editor/title/run`）。它不在 VS Code 里跑进程，而是通过 **MiniQT 宿主**的
  bridge 调 `minibtBacktest`，请 MiniQT 在**它自己的进程内** `import` 策略并
  `Bt.run(isplot=False)` —— 因为只有在本进程里跑，才能拿到 `Strategy` 实例
  （broker 成交流水、`profits`），把**指标卡 / 权益曲线 / 交易明细 / 参数优化**
  开在 MiniQT 的标题栏标签页里。子进程那条路（「运行策略」）继续只负责图表页签。

### 修复

- **声明 `activationEvents: ["onStartupFinished"]`**：新菜单项的 `when` 依赖
  `activate()` 里设的 `minibt.hostAvailable` 上下文；不声明启动激活时 `activate()`
  要等第一次执行命令才跑，上下文永远设不上 → 菜单项永远不显示（鸡生蛋）。
- 桌面版 VS Code 里没有 MiniQT 宿主（读不到 `QTVSCODE_RPC_URL` /
  `QTVSCODE_RPC_TOKEN`），该项**自动隐藏**；若用命令面板强行调用会给出明确提示。

## 0.3.2

### 新增

- **主题跟随 VS Code**：扩展把当前 VS Code 深浅色（`activeColorTheme.kind`）作为
  `--theme` 传给运行器；用户没显式指定 `theme=` / `black_style=` 时图表跟着 VS Code
  走，显式指定则原样生效（挂在 `minibt.utils.resolve_theme` 上，Bt.run / btplot /
  bokeh / 实时所有路径全覆盖）。

### 修复

- bokeh 看门狗把**上一次运行**留下的 `minibt_bokeh_*.html` 当成本次结果（导致页签从
  活图切成旧快照、SSE 报 `ConnectionAbortedError`）—— 现在只认本次运行新写出的文件。
- 配合 minibt：图表默认主题由深色改为**浅色**（`theme` 没设置时默认 `light`）。

## 0.3.1

- 排障更省事：输出面板第一行会打印**扩展版本**（`MiniBT Charts v0.3.1`），
  运行器每次决定引擎时打印一行 `[minibt] gui=Gui.Bokeh → bokeh（engine=auto）`，
  一眼看出"谁被映射成了谁"。

## 0.3.0

### 新增

- **`minibt.engine` 默认改成 `auto`：跟随策略里写的 gui**，不再强制统一：

  | 策略里写的 | 扩展里看到的 |
  | --- | --- |
  | `gui=Gui.Bokeh` | bokeh（回放/实时 bokeh server 嵌 iframe；回测自包含 HTML 快照） |
  | `gui=Gui.PylightchartsWeb` | pylightcharts 网页版（本地 SSE + iframe 活图） |
  | `gui=Gui.Pylightcharts`（原生） | 自动换成同一渲染器的网页版 |
  | 没写 gui | 同上（minibt 默认原生 → 网页版） |

  想强制就在设置里选 `pylightcharts` / `bokeh`（运行器 `--engine`）。
- **`btplot` 同样跟随**：在 `minibt.btplot._resolve_btplot_gui` 这个统一出入口挂
  映射，覆盖 `btplot(...)` 的所有调用方式（模块函数 / 访问器方法 / 指标方法）。
- **bokeh 地址不再猜**：包装 `bokeh.server.server.Server`，等 `start()` 真的监听
  后才报 `MINIBT_URL=`；bokeh 回测（没有 server）改报它写出的自包含 HTML，扩展
  自动开快照页签。

### 修复

- bokeh server 的 WebSocket Origin：webview 里的 Origin 不是 localhost
  （`vscode-webview://…` / `null`），bokeh 默认白名单会拒 —— 现在设
  `BOKEH_ALLOW_WS_ORIGIN=*` 并给 `Server(...)` 补 `allow_websocket_origin=['*']`。

## 0.2.1

### 修复

- **`btplot` 的图表打不开（`ERR_CONNECTION_REFUSED`）**：`_btplot_pylightcharts`
  里写死了 `live=False`（静态图只写文件、**不起服务**），而 `btplot` 又不走
  `Bt.run`，所以旧版补丁拦不到它 —— 扩展拿到的 URL 后面什么都没有。现在运行器
  在 `RealtimeChart` 这一层接管（覆盖 `Bt.run` 回测/实时、`btplot`、回测展示），
  统一成网页版**活图**。
- **不再由运行器猜端口**：`btplot` 不会把选中端口传下去（图表会自己另挑一个），
  现在改成问图表本人要**真实地址**（`BrowserChart.show` 返回的 URL）再报给扩展；
  静态图（`live=False`）则改报 `MINIBT_HTML=`，扩展自动开**快照页签**而不是一个
  连不上的 iframe。
- **图表页签不再直接显示错误页**：先显示「正在启动图表服务…」占位，探测到端口
  才把 iframe 换进来；等不到就显示可读的提示 + 回退建议；策略跑完却没有图时给
  一条「没看到图表（isplot=False？）」提示。

## 0.2.0

### 新增

- **bokeh 引擎**：`minibt.engine = bokeh`。回放/实时用 bokeh server（嵌 iframe，
  已确认 bokeh server 不发 `X-Frame-Options` / CSP），回测自动导出成 bokeh 的
  自包含 HTML（`INLINE` 资源）当静态页签；运行器会关掉 `server.show()` 弹窗，
  并用看门狗线程发现 bokeh 写出的临时页面。
- **导出静态快照到编辑器页签**：`MiniBT: 导出图表到编辑器页（静态快照）`。
  pylightcharts 走 `BrowserChart.show(path=...)`（导出时自动把 `live` 关掉，
  得到纯静态页面），bokeh 复制它的自包含页面。不占端口、不常驻进程、离线可看。
- **导出为 HTML 文件…**：存到指定路径，可发邮件 / 丢服务器 / 双击打开。
- **策略日志页签（带进度条）**：`Ctrl+Alt+L`。识别 `进度 x/y`（bokeh）、
  `xx%`（tqdm 等）、`[i/n]`，报错标红、自动滚到底；日志同时进 `MiniBT` 输出面板。
- 端口探测改为**纯 TCP 连接**（不 GET），避免给 bokeh 造出"幽灵会话"。

### 变更

- `minibt.engine` 设置项（`pylightcharts` 默认 / `bokeh`）、`minibt.openLog`。
- 编辑器标题栏图标：日志 / 刷新 / 停止。
- 关闭页签用整棵进程树结束（Windows `taskkill /t /f`）。

## 0.1.0

- 首个版本：在 VS Code 编辑器页签里运行 MiniBT 策略图表。
- 命令：`在编辑器页运行策略图表`（`Ctrl+Alt+M`）、`刷新图表`、`停止策略进程`、
  `在浏览器中打开图表`、`显示策略输出`。
- 运行前把 `Bt.run(gui=...)` 强制为 `pylightcharts_web`，并屏蔽系统浏览器弹窗，
  图形用 `<iframe>` 嵌进 webview（同一套 pylightcharts 渲染器）。
- 设置项：`pythonPath`、`port`、`cwd`、`extraPythonArgs`、`openBrowser`、
  `keepAliveOnClose`。

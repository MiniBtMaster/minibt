# 更新日志

## 0.3.11 - 2026-10-27

### 变更

- **「打开 MiniBT 看盘终端」的图标换成 minibt desk 的 LOGO**（4 根蜡烛 +
  上升趋势线，和 desk 顶栏 LOGO 同一套图形；深色 / 浅色两版各自配色 ✓），
  编辑器标题栏 / 命令面板 / 状态栏三处一起生效。

### 新增

- **在 VS Code 里用 minibt 看盘终端（desk）**：命令
  「MiniBT: 打开 MiniBT 看盘终端」（编辑器标题栏 🕯 图标 / 状态栏
  「MiniBT 看盘」/ `Ctrl+Alt+D`）。内部还是**子进程 + 本地服务 + iframe**：
  `python -m minibt desk --browser --json` 起 `127.0.0.1` 服务，等
  `/healthz` 就绪再把页面换进来 ✓（和「在编辑器页运行策略图表」同一套壳）。
- **设置项**（`.vscode/settings.json`，都有默认值，不配也能用）：

  | 键 | 默认 | 说明 |
  |---|---|---|
  | `minibt.desk.account` | `""` | 天勤账号；留空 = 不连期货 |
  | `minibt.desk.password` | `""` | **明文兜底**，推荐用命令存加密存储 |
  | `minibt.desk.futuHost` | `127.0.0.1` | FutuOpenD 地址 |
  | `minibt.desk.futuPort` | `11111` | FutuOpenD 端口 |
  | `minibt.desk.stocks` | `auto` | `auto` / `on` / `off` |
  | `minibt.desk.offline` | `false` | 离线演示（不连网关） |
  | `minibt.desk.theme` | `auto` | 跟随 VS Code / `dark` / `light` |
  | `minibt.desk.autoStart` | `false` | 打开工作区就自动起（常驻进程） |
  | `minibt.desk.port` | `0` | 0 = 自动挑空闲端口 |

- **密码不进 settings.json**：命令
  「MiniBT: 设置天勤密码（加密存储）」→ VS Code `SecretStorage`；
  优先级 `SecretStorage` → 环境变量 `MINIBT_TQ_PASSWORD` → `settings.json`。
  传给子进程一律走**环境变量**（命令行 / `ps` 里看不到明文 ✓）。
- **启动前体检 + 提醒**：
  - 有账号 + 密码 → 期货（+ 股票）
  - 没账号但 FutuOpenD 通（TCP 探测 `127.0.0.1:11111`，1.2s）→ 只连股票
  - **都没有 → 弹提醒**：【输入天勤账号】【只连 Futu 股票】【进入离线演示】
    【打开设置】，选过就记住（`globalState`），下次不再打扰 ✓
- **状态栏**「MiniBT 看盘」：`$(pulse) MiniBT 看盘 · 期货+股票` /
  `$(graph) MiniBT 看盘`，点一下起 / 停 ✓
- **命令**：`minibt.openDesk` / `minibt.stopDesk` / `minibt.showDeskOutput`
  / `minibt.desk.setPassword` / `minibt.desk.clearPassword`。

### 修复

- **看盘终端白屏（重要）**：`minibt desk --browser` 的静态资源以前**只**认
  `/static/...`，而 `desk.html` 里用的是相对路径 `./desk.js` → 请求
  `/desk.js` 全部 404 → **浏览器和 VS Code 页签都是空白** ✗。
  现在服务端对根路径也认（`/desk.js` 与 `/static/desk.js` 都 200）✓。
- **浏览器壳收不到任何补丁（重要）**：`SseTransport` 以前只
  `POST /callback`、没有 `EventSource` → 后端的 boot / 类型 / 交易所 /
  合约 / 报价补丁全部广播给 0 个客户端，页面只有空壳、一直
  「正在加载合约…」✗。现在订阅 `/events` 并执行补丁；命令先排队、
  等 SSE `onopen` 再发，避免 `ready` 早于 `/events` 注册而丢首屏 ✓。
- **VS Code 里打开时不再同时弹系统浏览器**：新增 `minibt desk --no-browser`
  （环境变量 `MINIBT_DESK_NO_BROWSER`），扩展启动时带上它 ✓。
- **本地开发优先用仓库里的 `minibt`**：`workdir()` 现在从扩展目录 / 工作区
  **逐级向上**找 `minibt/__init__.py`，在 `vscode-minibt/` 里调试时也不会
  误用 site-packages 里的旧版 ✓。

### 变更

- **看盘终端的图标**：页签图标 + 编辑器标题栏按钮统一用
  `media/desk-{light,dark}.svg`（K 线蜡烛），和状态栏一致 ✓。

### 依赖（minibt 侧，同版本起支持）

- `minibt desk` 读环境变量：`MINIBT_TQ_USER` / `MINIBT_TQ_PASSWORD`
  / `MINIBT_FUTU_HOST` / `MINIBT_FUTU_PORT` / `MINIBT_DESK_*`
  （命令行给了的参数**永远优先** ✓）。
- `minibt desk --browser --json` 启动后打一行就绪 JSON
  `{"ready": true, "url": "http://127.0.0.1:PORT/", ...}`；
  新增 `GET /healthz` 返回连接状态（`{"ready", "offline", "futures", "stocks"}`）✓。


## 0.3.10

### 新增

- **本地 minibt 优先，系统安装的兜底**：runner 现在从脚本目录 / 工作区
  **逐级向上**找含 `minibt/__init__.py` 的目录（例如脚本在 `tutorials/`
  时能找到仓库根的 `minibt`），找到就放到 `sys.path[0]`，优先于
  `site-packages` ✓。本地找不到时才回退到解释器里安装的 minibt；两者都
  没有时打印明确的放置/安装提示。

## 0.3.9

### 修复

- **旧版 minibt 导致建图直接失败**：日志出现
  `module 'minibt.utils' has no attribute 'resolve_theme'`。这通常是 VS Code
  扩展子进程导入了**解释器里安装的旧 minibt**（如 1.2.6），而不是脚本旁边
  仓库里的新版（1.3.x）。现在：
  - runner 把**脚本所在目录**放在 VS Code 工作区根目录**之前**的 `sys.path`
    优先级，优先用脚本项目自带的 minibt ✓；
  - `_patch_theme` 遇到没有 `resolve_theme` 的旧版 minibt 时**跳过「跟随
    VS Code 主题」**，不再中断建图；图表照常显示 ✓；
  - 失败提示会打印**实际导入的 minibt 路径 / 版本**，并给出升级命令
    `python -m pip install -U minibt`。

## 0.3.8（预留 / 未发布）

> ⏳ **尚未发布**。下面是已改好、等下次一起发的内容。发布前记得：
> 把 `package.json` 的 `version` 改成 `0.3.8`、补上发布日期，再
> `vsce package` → `vsce publish`（Marketplace）/ `ovsx publish`（Open VSX），
> 并把 `.vsix` 挂到 GitHub Releases。

### 新增

- **图表页 `Ctrl+C` 停止策略进程**：在图表页里按 `Ctrl+C` 等同点「停止策略
  进程」按钮。图表是嵌在 VS Code webview 里的**跨域 iframe**，父页面收不到
  它里面的按键、VS Code 的 webview 键绑定也进不去 ✗，所以热键由 runner
  **注入到图表页内部**（走 pylightcharts 的 `callbackFunction` 通道回调
  Python，再打印 `MINIBT_STOP` 让扩展停进程）✓；webview 外壳上也挂了
  一份监听器、并注册了 `activeWebviewPanelId == 'minibtChart'` 的键绑定
  （`Ctrl+C` / `Cmd+C`），焦点在外壳上时也生效 ✓。

### 修复

- **停止策略时把图表页和日志页一并关掉**：以前 `stopSession()` 只是把两个
  页签内容换成一段“已停止”的提示，页签还在 ✗。现在按 `Ctrl+C`（或点停止
  按钮）会**先杀掉策略进程**（同步等它停），**再** `dispose()` 掉
  「MiniBT 图表」和「MiniBT 策略日志」两个页签 ✓。
- **`Ctrl+Alt+M` 运行不了策略**：Code Runner 也把 `Ctrl+Alt+M` 绑成
  `code-runner.stop`，而且它**没有 `when` 条件**；VS Code 的键绑定解析器里，
  一个无条件的后注册绑定会把前面的有条件绑定**移除**，于是我们的绑定被吃掉 ✗。
  新增 **`Ctrl+Alt+B`** 作为主快捷键（无冲突），保留 `Ctrl+Alt+M` 作为备用
 （卸掉 / 重排 Code Runner 后它就可用）✓。
- **运行策略后图表把编辑器拆成左右两半（页面宽度减半）**：
  日志页签先以 `ViewColumn.Beside` 打开，`active` 列随之变成右边那一列；
  图表再用 `ViewColumn.Active` 打开，自然也跟着跑到右边 ✗。
  现在命令发起时会**先记下代码所在的列**，图表和日志都回到这一列 ——
  代码 / 日志 / 图表是同一页签组里的标签，按标签切换，不再拆分页面 ✓。
- **策略日志出现两遍**：运行时扩展用 `channel.show(true)` 主动把底部的
  「输出」面板打开，于是同一份日志既在「MiniBT 策略日志」页签、又在底部
  输出面板里各显示一份 ✗。现在**不再自动打开输出面板**，日志只显示在
  编辑器页签；输出面板仍保留内容，需要时用命令
  「显示策略输出（原始日志）」手动查看 ✓。
- 新增 `minibt.openBeside`（默认 `false`）。想恢复“右侧单独一列”的
  左右分屏时，把它设为 `true` 即可。

### 文档

- **README 补上安装渠道**：顶部加 **Open VSX** badge；「安装渠道」列出
  VS Marketplace / Open VSX / 离线 `.vsix`（GitHub Releases），并把
  **VSX Pulse**（`vsx-pulse.org`）标注为**第三方索引**（可查版本，安装仍建议走
  两个市场）。
- `minibt/README.md` 的 VS Code 扩展小节同步补上 Marketplace / Open VSX 直链。
- README「设置」表补上 `minibt.openBeside`。

### 内部

- `.vscodeignore` 不再把 `PUBLISHING.md` 打进 `.vsix`（维护者手册不随扩展分发）。
- `.gitignore` 忽略 `_vsix_backup/`（旧版本 `.vsix` 的本地备份目录）。

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

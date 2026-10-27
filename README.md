# MiniBT Charts（VS Code 扩展）

[![VS Marketplace](https://img.shields.io/visual-studio-marketplace/v/MiniBtMaster.minibt-charts?label=marketplace&color=green)](https://marketplace.visualstudio.com/items?itemName=MiniBtMaster.minibt-charts)
[![Open VSX](https://img.shields.io/open-vsx/v/MiniBtMaster/minibt-charts?label=Open%20VSX&color=purple)](https://open-vsx.org/extension/MiniBtMaster/minibt-charts)
[![GitHub](https://img.shields.io/badge/GitHub-minibt--charts-181717?logo=github)](https://github.com/MiniBtMaster/minibt-charts)

当前版本 **0.3.11** · [CHANGELOG](CHANGELOG.md) · [RELEASE_NOTES](https://github.com/MiniBtMaster/minibt-charts/blob/main/RELEASE_NOTES.md)

安装渠道：

- **VS Code**：扩展面板搜 `MiniBT Charts`，或
  [VS Marketplace](https://marketplace.visualstudio.com/items?itemName=MiniBtMaster.minibt-charts)；
- **VSCodium / Gitpod / Theia 等**：[Open VSX](https://open-vsx.org/extension/MiniBtMaster/minibt-charts)；
- **离线 / 指定版本**：下载本仓库 [Releases](../../releases) 里的 `.vsix`，
  `code --install-extension minibt-charts-x.y.z.vsix --force`。
  （[VSX Pulse](https://vsx-pulse.org/Extension/MiniBtMaster.minibt-charts)
  是一个第三方索引，可用来查版本，安装仍建议走上面两个市场。）

在 **VS Code 编辑器页签**里运行并查看 [MiniBT](https://github.com/MiniBtMaster/minibt)
的图表 —— 图表、日志和代码**在同一个页签组内按标签切换**（默认不拆分页面，
不会把编辑区宽度减半）；想要左右分屏可把 `minibt.openBeside` 设为 `true`：

- **回测 / K 线回放 / 实时行情**三种策略场景（`Bt().run()` / `Bt(replay=True).run()` / `Bt(live=True).run()`）；
- **`btplot` 指标图**（`ind.btplot()` / `kline.macd().btplot()`）；
- 通过编辑器标题栏的**快速按钮**（**MiniBT 专属的 K 线图标**）运行策略和指标。

```
Ctrl+Alt+B   运行策略，图表开在编辑器页签（实时刷新）
Ctrl+Alt+M   同上（备用；若装了 Code Runner 等占用了这个键就被它抢走了）
Ctrl+Alt+L   策略日志页签（带进度条）
Ctrl+C       在图表页里停止策略进程，并关闭图表 / 日志页签（等同「停止策略进程」按钮）
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

3. 打开策略 / 指标 `.py`，按 **`Ctrl+Alt+B`**（或点标题栏的 **K 线按钮**）——
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

## 看盘终端（minibt desk）

`minibt desk` 本来就能**脱离 Qt** 跑：

```bash
python -m minibt desk --browser            # 起 127.0.0.1 服务 + 打开浏览器
python -m minibt desk --browser --json      # 额外打一行就绪 JSON（扩展读它）
```

扩展就是起这个子进程、等 `GET /healthz` 返回 `{"ready": true, ...}`，再把
`http://127.0.0.1:PORT/` 交给 iframe 外壳 —— 和「策略图表」用同一套壳，
所以页面里的一切（报价 / K 线 / 指标 / 交易 / 回放）都和桌面版一致 ✓。

> 0.3.11 起修复了浏览器壳的补丁链路（`SseTransport` 订阅 `/events`）：
> 报价页的类型/交易所 chips 和行情会正常出现与刷新。

## 命令

| 命令（命令面板 `Ctrl+Shift+P` 输入 `MiniBT`） | 快捷键 | 作用 |
| --- | --- | --- |
| `MiniBT: 在编辑器页运行策略图表` | `Ctrl+Alt+B`（备用 `Ctrl+Alt+M`） | 当前编辑器是 `.py` 就用它；否则弹文件选择框 |
| `MiniBT: 显示策略日志（带进度）` | `Ctrl+Alt+L` | 日志页签 + 进度条（认 `进度 x/y`、`xx%`、`[i/n]`，报错标红） |
| `MiniBT: 刷新图表` | — | 重新加载图表（live 页签加时间戳防缓存；快照页签重读文件） |
| `MiniBT: 停止策略进程` | `Ctrl+C`（图表页里） | 结束整棵策略进程树（关页签时也会自动结束） |
| `MiniBT: 在浏览器中打开图表` | — | 用系统浏览器打开同一张图（live 用地址，快照用文件） |
| `MiniBT: 显示策略输出（原始日志）` | — | 打开 `MiniBT` 输出面板 |
| **`MiniBT: 打开 MiniBT 看盘终端`** | `Ctrl+Alt+D` | 起 `minibt desk`（报价 + 看盘 + 交易），页面嵌在编辑器页签里 |
| **`MiniBT: 停止看盘终端`** | `Ctrl+Alt+Shift+D` | 结束看盘终端进程（关页签也会自动结束） |
| `MiniBT: 显示看盘终端日志` | — | 打开 `MiniBT 看盘` 输出面板 |
| `MiniBT: 设置天勤密码（加密存储）` | — | 密码存 VS Code `SecretStorage`，**不写 settings.json** |
| `MiniBT: 清除已保存的天勤密码` | — | 删掉加密存储里的密码 |

编辑器标题栏会有一个 **MiniBT 快速按钮**（K 线图标），就在原生「运行 ▾」
按钮右边的同一行里（「运行」是**独立图标**，不占 VS Code 原生运行按钮 ✓）；
图表页签自己则会出现「日志 / 刷新 / 停止」图标按钮。

在**图表页里按 `Ctrl+C`** 就会停止当前策略进程，并把「MiniBT 图表」
和「MiniBT 策略日志」两个页签一起关掉（和点「停止策略进程」按钮一样）。
图表是嵌在 VS Code webview 里的跨域 iframe，父页面收不到它里面的按键，
所以这个热键是**注入到图表页内部**的（见 `runner/vscode_runner.py`），
无论焦点在图表上还是页签外壳上都能生效。

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
| `minibt.openBeside` | `false` | 图表/日志在代码右侧单独开一列（左右分屏）；关闭（默认）则与代码在同一页签组内按标签切换，不拆分页面 |
| `minibt.keepAliveOnClose` | `false` | 关闭图表页签时是否保留策略进程 |

### 看盘终端（`minibt desk`）

| 设置项 | 默认 | 说明 |
| --- | --- | --- |
| `minibt.desk.account` | 空 | 天勤账号（快期）；**留空 = 不连期货** |
| `minibt.desk.password` | 空 | 明文兜底；推荐用命令「设置天勤密码」（加密存储）。优先级：`SecretStorage` → 环境变量 `MINIBT_TQ_PASSWORD` → 这里 |
| `minibt.desk.futuHost` | `127.0.0.1` | FutuOpenD 地址（Futu 客户端改过地址才需要改） |
| `minibt.desk.futuPort` | `11111` | FutuOpenD 端口 |
| `minibt.desk.stocks` | `auto` | `auto` 检测到 FutuOpenD 就连 / `on` 总是连 / `off` 只看期货 |
| `minibt.desk.offline` | `false` | 离线演示（不连任何网关，只看界面 / 演示数据） |
| `minibt.desk.theme` | `auto` | 跟随 VS Code 配色，或固定 `dark` / `light` |
| `minibt.desk.autoStart` | `false` | 打开工作区就自动起（**会常驻一个 Python 进程**） |
| `minibt.desk.port` | `0` | 本地服务端口；0 = 自动挑空闲端口 |

工作区示例（`.vscode/settings.json`）：

```jsonc
{
  "minibt.pythonPath": ".venv/Scripts/python.exe",
  "minibt.desk.account": "你的天勤账号",
  "minibt.desk.futuPort": 11111,
  "minibt.desk.theme": "auto"
}
```

> 密码**别写在这里**（工作区设置会跟着仓库走）。用命令
> 「MiniBT: 设置天勤密码」存进加密存储，或设环境变量
> `MINIBT_TQ_PASSWORD`。扩展传给子进程一律走环境变量，命令行 / `ps` 里
```bash
$env:MINIBT_TQ_USER = '账号'
$env:MINIBT_TQ_PASSWORD = '密码'
```

**启动前会体检**：有账号 + 密码 → 期货（+ 股票）；没账号但 FutuOpenD 通
（TCP 探 `127.0.0.1:11111`）→ 只连股票；**都没有会弹提醒**，让选
【输入天勤账号】【只连 Futu 股票】【进入离线演示】【打开设置】，
选过就记住，下次不再打扰 ✓。状态栏右侧的「MiniBT 看盘」会显示
`● 期货+股票` / `○ 未启动`，点一下就能起停。

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

## 从源码开发

独立仓库（`minibt-charts`）的根目录就是扩展目录：

```bash
git clone https://github.com/MiniBtMaster/minibt-charts.git
cd minibt-charts

npm run package                    # 生成 minibt-charts-0.3.11.vsix
code --install-extension minibt-charts-0.3.11.vsix --force
```

日常调试：在 VS Code 里打开扩展目录按 **F5**，或直接用目录联接：

```powershell
powershell -ExecutionPolicy Bypass -File link-dev.ps1
```

如果当前在 **minibt 主仓库**里，扩展源码位于 `vscode-minibt/`，把上面的
`cd minibt-charts` 换成 `cd vscode-minibt` 即可。

### 仓库结构

```text
extension.js                 扩展入口：命令 / webview / 子进程
desk.js                      minibt desk 启动参数、连接体检、状态栏逻辑
runner/vscode_runner.py      Python 侧：启动策略 / 图表服务 / 停止进程
media/                       图标（扩展 / 运行 / desk，深浅两套）
package.json                 清单：命令、快捷键、设置、VSIX 元数据
CHANGELOG.md                 版本历史
RELEASE_NOTES.md             当前版本可粘贴到 GitHub Release 的正文
PUBLISHING.md                VSIX / Marketplace / Open VSX 发布教程
GITHUB.md                    GitHub 首次上传 / tag / Release 流程
.github/workflows/           CI + 自动打包并挂 Release 的工作流
```

## 开发 / 打包 / 发布

见 [`PUBLISHING.md`](https://github.com/MiniBtMaster/minibt-charts/blob/main/PUBLISHING.md)
（本地 VSIX 安装、F5 调试、发布到 Marketplace 全流程、常见报错表）和
[`GITHUB.md`](https://github.com/MiniBtMaster/minibt-charts/blob/main/GITHUB.md)
（GitHub 首次上传、tag、自动 Release）。

本仓库 CI 会执行：

```bash
node --check extension.js
node --check desk.js
python -m py_compile runner/vscode_runner.py
npx --yes @vscode/vsce ls
```

完整 minibt monorepo 里还有 `tests/test_vscode_extension.py`，会校验清单/代码/
运行器三方一致（命令、设置项、打包白名单；并确认不再占用
`editor/title/run` ✓）。

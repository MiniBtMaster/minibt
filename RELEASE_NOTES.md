# minibt-charts 0.3.11 发布说明

**版本**：0.3.11
**发布日期**：2026-10-27
**适用**：VS Code 1.85+ / Cursor / VSCodium / Gitpod / Theia

## 亮点

- **VS Code 内打开 minibt desk**：新增命令
  「MiniBT: 打开 MiniBT 看盘终端」，快捷键 `Ctrl+Alt+D`；
  编辑器标题栏图标 / 状态栏「MiniBT 看盘」也可启动。
- **看盘终端（报价 + 看盘 + 交易）直接嵌在编辑器页签里**：扩展开启
  `python -m minibt desk --browser --no-browser --json` 子进程，等待
  `/healthz` 就绪后把本地页面嵌入 iframe；关闭页签或停止命令会结束进程。
- **天勤密码走 VS Code 加密存储**：命令「设置天勤密码（加密存储）」写入
  `SecretStorage`，不写 `settings.json`；优先级
  `SecretStorage` → `MINIBT_TQ_PASSWORD` → `settings.json`。
- **启动前体检**：天勤账号 + 密码 → 期货 + 股票；只有 FutuOpenD →
  只连股票；都没有 → 提示输入账号 / 只连股票 / 进入离线演示。
- **窗口 / 页签图标**：统一使用 minibt desk 的 K 线 LOGO（深浅两套）。

## 修复

- 修复浏览器壳 desk 页面白屏：`desk.html` 使用相对路径 `./desk.js`，
  服务端现在同时支持 `/desk.js` 与 `/static/desk.js`。
- 修复浏览器壳收不到补丁：`SseTransport` 订阅 `/events`，命令在
  SSE `onopen` 后发送，避免首屏补丁丢失。
- VS Code 内打开 desk 时不再同时弹系统浏览器（使用 `--no-browser`）。
- 本地开发优先使用工作区 / 仓库里的 `minibt` 源码，避免误用
  site-packages 旧版。

## 安装

```bash
code --install-extension minibt-charts-0.3.11.vsix
```

或从 VS Code 扩展面板安装 **MiniBT Charts**；VSCodium / Cursor 等使用
Open VSX。安装后建议执行 `Developer: Reload Window`。

## 验证

```bash
node --check extension.js
node --check desk.js
python -m py_compile runner/vscode_runner.py
npx --yes @vscode/vsce package
```

## 说明

本扩展需要目标 Python 环境安装 `minibt`（以及 `pylightcharts`）。
看盘终端还支持离线模式：在设置中打开 `minibt.desk.offline`，不连接任何
行情网关也可以查看界面 / 本地图表。

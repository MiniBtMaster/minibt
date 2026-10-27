# 打包 · 安装 · 发布教程

> **目录说明**
>
> 本文按 **minibt 主仓库**里的 `vscode-minibt/` 目录写的，所以命令里会出现
> `cd vscode-minibt`。如果当前目录就是独立的 `minibt-charts` GitHub 仓库根目录，
> 直接在当前目录执行即可，**不要**再 `cd vscode-minibt`。
> GitHub 首次上传、tag 和自动 Release 见 [`GITHUB.md`](GITHUB.md)。

> **先看这里：三条路怎么选**
>
> | 想达到的效果 | 走哪条路 | 门槛 |
> | --- | --- | --- |
> | 自己 / 团队内部用 | **本地 VSIX**（第一、三节） | 无 |
> | 让用户能下载安装（不上商店） | **GitHub Releases 挂 .vsix**（第五节） | 无 |
> | VSCodium / Cursor / Theia 等能从商店装 | **Open VSX**（第五节之二） | 只要 GitHub 账号 |
> | VS Code 官方扩展面板里能搜到 | **微软 Marketplace**（第四节） | 需要 Azure DevOps PAT |
>
> ⚠️ 微软 Marketplace 发布**必须**用 Azure DevOps 的 Personal Access Token，
> 而**新建 Azure DevOps 组织现在常被要求先绑定 Azure 订阅**（要 Owner/Contributor
> 角色的订阅）。这是微软的门槛，不是你操作错了。卡住就先用 VSIX / Open VSX，
> 详见第五节的排错清单。

三种用法，按需要选：

| 场景 | 怎么做 |
| --- | --- |
| 自己电脑上长期用 | **打包 .vsix → 安装**（第一、三节） |
| 改代码调试 | **F5 开发主机**（第二节） |
| 给所有人从应用商店装 | **发布到 Marketplace**（第四节） |

---

## 一、安装（最快：本地 VSIX）

### 1. 打包

```bash
cd vscode-minibt
npx --yes @vscode/vsce package          # 生成 minibt-charts-0.3.11.vsix
```

（`package.json` 里已经加了 `npm run package` 脚本，等价。）

如果报 `A 'repository' field is missing`，是因为 `package.json` 里的
`repository.url` 不是合法地址；本仓库已填好，改到自己仓库时注意别留占位符。

### 2. 安装

图形界面：VS Code → 扩展面板（`Ctrl+Shift+X`）→ 右上角 `...` → **Install from VSIX...**
→ 选 `minibt-charts-0.3.11.vsix` → 出现提示后 **Reload**。

命令行：

```bash
code --install-extension minibt-charts-0.3.11.vsix
```

### 3. 用起来

1. 打开装了策略的工作区（`File → Open Folder`）；
2. 在**工作区设置**里指定解释器（很重要）：

   ```jsonc
   // .vscode/settings.json
   {
     "minibt.pythonPath": ".venv/Scripts/python.exe",   // Windows 虚拟环境
     "minibt.cwd": "${workspaceFolder}"
   }
   ```

   验证：`python -c "import minibt, pylightcharts; print(minibt.__version__)"` 能打印版本；
3. 打开一个策略 `.py`，按 **`Ctrl+Alt+M`**（或点编辑器标题栏 MiniBT 的
   **K 线快速按钮** —— 就在原生「运行 ▾」按钮右边的同一行里，
   或命令面板搜 `MiniBT`）；
4. 图表出现在**编辑器页签**里（和代码文件并排、可拖拽分屏）；
5. 页签关闭或按 `MiniBT: 停止策略进程` 结束策略子进程；日志在 `MiniBT` 输出面板。

### 4. 升级本地扩展

改完代码重新打包（**版本号要往上加**，例如 `0.3.10` → `0.3.11`），再用 `--force`
覆盖安装：

```bash
cd vscode-minibt
# 1) 先把 package.json 的 "version" 往上加（+ 写 CHANGELOG），再打包
npx --yes @vscode/vsce package
# 2) 覆盖安装新版本
code --install-extension minibt-charts-0.3.11.vsix --force
# 3) 确认版本变了（应只出现新版本）
code --list-extensions --show-versions | grep minibt
```

然后 **`Ctrl+Shift+P` → `Developer: Reload Window`**（不重载，跑着的还是旧代码）。
升级后建议：把旧的图表/日志页签关掉再重开；如果扩展目录里同时躺着两个版本
（`~/.vscode/extensions/minibtmaster.minibt-charts-*`），把旧的目录删掉——
VS Code 会优先用版本号最大的那份，但删干净不混淆。

> 小贴士：不想每次升级都重新打包，用第二节的 `link-dev.ps1`（目录联接），
> 改代码后只要 Reload Window 就行。

### 5. 卸载

命令行（ID = `<publisher>.<name>`，见 `package.json`，这里是小写
`minibtmaster.minibt-charts`）：

```bash
code --uninstall-extension minibtmaster.minibt-charts
```

图形界面：扩展面板（`Ctrl+Shift+X`）→ 找到 **MiniBT Charts** → 点齿轮 → **Uninstall**。

卸载后同样要 **`Ctrl+Shift+P` → `Developer: Reload Window`** 才会从当前会话摘掉。

彻底清理（可选）：`--uninstall-extension` 一般会连目录一起删；万一留下孤儿目录，
手动删掉即可：

```bash
# Windows (PowerShell)
Remove-Item "$env:USERPROFILE\.vscode\extensions\minibtmaster.minibt-charts-*" -Recurse -Force
# macOS / Linux
rm -rf ~/.vscode/extensions/minibtmaster.minibt-charts-*
```

卸载只删**已安装的那份**；源码（`vscode-minibt/`）和打包产物 `.vsix` 都还在，
随时可以用上面的命令重装。想改从商店安装：
`code --install-extension MiniBtMaster.minibt-charts`。

---

## 二、开发调试（F5）

```bash
cd vscode-minibt
code .            # 在 VS Code 里打开这个扩展目录
```

- 按 **F5** → 弹出「扩展开发主机」窗口（标题带 `[Extension Development Host]`）；
- 在**那个新窗口**里打开你的策略工作区，按 `Ctrl+Alt+M` 测试；
- 改 `extension.js` 后在开发主机里 `Ctrl+R` 重载，或在调试工具条点重启；
- 看扩展自己的日志：`Help → Toggle Developer Tools → Console`。

### 2.1 免打包的开发循环（推荐日常改代码用）

每次改 `extension.js` 都 `vsce package` + 装 VSIX 太慢。用目录联接（junction）把
仓库目录直接当成"已装扩展"，改完只要 Reload Window：

```powershell
cd vscode-minibt
powershell -ExecutionPolicy Bypass -File link-dev.ps1          # 建联接
# 改代码 → Ctrl+Shift+P → Developer: Reload Window
powershell -ExecutionPolicy Bypass -File link-dev.ps1 -Remove  # 取消联接
```

联接名字按 `package.json` 自动算成 `<publisher>.<name>-<version>`，删联接不会动
源码目录。注意：联接存在期间，扩展用**仓库里的这份**代码（而不是 .vsix 装的那份）。

### 2.2 直接跑 Python 侧

调试 Python 侧（runner）时，可以直接命令行跑，最省事：

```bash
python -u runner/vscode_runner.py /path/to/strategy.py --port 0 --open
# 控制台会打印 MINIBT_URL=http://127.0.0.1:xxxxx/，浏览器能打开
```

---

## 三、打包细节

```bash
npx --yes @vscode/vsce package            # 当前版本
npx --yes @vscode/vsce package 0.3.11      # 顺便把 package.json 版本改成 0.3.11
```

打包前检查：

- `package.json` 的 `version` 已经加过（Marketplace **不允许**重复版本号）；
- `publisher` 字段与你在 Marketplace 注册的 **publisher id 完全一致**；
- `README.md`、`CHANGELOG.md`、`LICENSE` 都在（README 会当作商店介绍页）；
- `.vscodeignore` 没有漏掉 `runner/`（那是 Python 侧入口，必须进包）：
  `npx --yes @vscode/vsce ls` 可以列出最终包含的文件。
- 图标可选：放 `media/icon.png`（128×128）并在 `package.json` 加 `"icon": "media/icon.png"`。

---

## 四、发布到 VS Code Marketplace

### 1. 注册 publisher（一次性）

1. 打开 <https://marketplace.visualstudio.com/manage>，用 Microsoft / GitHub 账号登录；
2. **Create publisher** → ID 填 `MiniBtMaster`（必须和 `package.json` 的 `publisher` 一致）；
3. 记下 publisher id。

### 2. 创建 Personal Access Token（PAT）

1. 打开 <https://dev.azure.com> → 右上角用户头像 → **Personal access tokens** →
   **New Token**；
2. Organization 选 **All accessible organizations**（关键，选错会 401）；
3. Scopes 里勾 **Marketplace → Manage**；
4. 生成后**复制** token（只显示一次）。

### 3. 登录并发布

```bash
cd vscode-minibt
npx --yes @vscode/vsce login MiniBtMaster     # 粘贴 PAT
npx --yes @vscode/vsce publish                # 用 package.json 里的版本
# 或者：
npx --yes @vscode/vsce publish minor          # 自动 0.3.11 -> 0.4.0 并发布
npx --yes @vscode/vsce publish --packagePath minibt-charts-0.3.11.vsix
```

发布后 1～5 分钟内就能在商店搜到 `MiniBT Charts`，别人即可：

- 在 VS Code 扩展面板搜 **MiniBT Charts** → Install；
- 或 `code --install-extension MiniBtMaster.minibt-charts`。

撤销/下架：`npx @vscode/vsce unpublish MiniBtMaster.minibt-charts`。

### 4. 常见报错

| 报错 | 原因 |
| --- | --- |
| `401 Unauthorized` | PAT 的 Organization 没选 *All accessible organizations*，或 Scope 少了 Marketplace→Manage |
| `Publisher 'xxx' not found` | `package.json` 的 `publisher` 与注册的 id 不一致（大小写敏感） |
| `Extension version must be greater than the last one` | 版本号没加 |
| `Missing repository field` / `LICENSE` | 补齐 `repository`、`LICENSE` |

---

## 五、不上微软商店的两种发法

### 5.1 只发 VSIX（零门槛）

把 `.vsix` 传到 **GitHub Releases**，用户下载后：

```bash
code --install-extension minibt-charts-0.3.11.vsix
```

（VS Code 界面里也可以：扩展面板 → `...` → Install from VSIX。）

手动发布（已安装 GitHub CLI）：

```bash
npm run package
gh release create v0.3.11 minibt-charts-0.3.11.vsix   --title "minibt-charts 0.3.11"   --notes-file RELEASE_NOTES.md
```

或者直接推 tag，让 `.github/workflows/release.yml` 自动打包并挂 Release：

```bash
git tag -a v0.3.11 -m "minibt-charts 0.3.11"
git push origin v0.3.11
```

### 5.2 发 Open VSX（像商店一样能搜到，只要 GitHub 账号）

[Open VSX](https://open-vsx.org) 是 Eclipse 基金会维护的开放扩展市场，
**VSCodium / Cursor / Theia / Gitpod / code-server 默认就从它装扩展**，
而且发布完全不需要 Azure DevOps、不需要 Azure 订阅。

```bash
# 1. 用 GitHub 账号登录 https://open-vsx.org
# 2. 认领命名空间：https://open-vsx.org/user-settings/namespaces
#    命名空间要和 package.json 的 publisher 一致（MiniBtMaster）；
#    用你自己的、或你有权限的 GitHub 组织 MiniBtMaster 账号登录即可认领。
# 3. 拿 token：https://open-vsx.org/user-settings/tokens
# 4. 发布（ovsx 会读环境变量 OVSX_PAT）
cd vscode-minibt
export OVSX_PAT=<上面的 token>        # Windows PowerShell: $env:OVSX_PAT="..."
npm run publish:ovsx                 # = npx ovsx publish
```

发完在 <https://open-vsx.org/extension/MiniBtMaster/minibt-charts> 就能看到，
VSCodium 等客户端里搜 **MiniBT Charts** 即可安装（微软的 VS Code 仍只认自家商店，
那边用 5.1 的 VSIX）。

### 5.3 微软商店卡在 Azure 订阅怎么办

按顺序试：

1. **别从向导进**：直接开 <https://aex.dev.azure.com/me>，或直接在地址栏输
   `https://dev.azure.com/<你想用的组织名>`，看能不能直接建；
2. **换浏览器 / 隐私模式**重登同一个账号再走一遍向导 —— 有不少账号在这一步
   会被直接放过去（向导里的订阅选择不是所有人都会出现）；
3. **建一个免费 Azure 订阅**：<https://azure.microsoft.com/free>（要信用卡验证，
   免费额度内 $0，用完可以删订阅）→ 回来就能建 Azure DevOps 组织；
4. **用 GitHub 身份登录 Azure DevOps** 再建组织（Azure DevOps 支持 GitHub 登录，
   有时就不会要求 Azure 订阅）；
5. 找一个**已有 Azure 订阅**的账号，把你这账号加成该订阅的 **Contributor**，
   再回来建组织；
6. 实在不行就先用 **5.1 / 5.2** —— 扩展本身和发布渠道无关，以后随时能补发微软商店。

---

## 六、常见问题：同一版本号能重复上传吗？

**不能 ✗（上传到市场）。** VS Code Marketplace 把版本号当**不可变**的：

* `npx @vscode/vsce publish`（或 `--packagePath xxx.vsix`）如果这个版本已经存在，
  会直接报错，类似
  `The extension 'MiniBtMaster.minibt-charts' version '0.3.11' already exists` ✗；
* 所以**改了任何东西（包括 README / 描述 / 图标）都必须把版本号 +1**，
  再打包 + 发布 ✓ —— 商店页上的 README（Overview）取的是**最新已发布版本**里的那份 ✓，
  发个新版本它自然就刷新了 ✓。
* 网页后台能改的只有少数展示字段（描述 / 分类 / 标记等）；**README 是随 vsix 上去的**，
  改了就得发新版本 ✓。同样规则适用于 Open VSX ✓。

**对照：本地安装同版本是**可以的** ✓**（这是本地开发，与市场无关）：

```bash
code --install-extension minibt-charts-0.3.11.vsix --force   # 同版本覆盖安装 ✓
```

> 所以日常流程是：本地用 `--force` 反复装同一个版本调试 ✓；
> **一但要让市场重新拉取（或改了 README），就把 `package.json` 的 version 往上加**
> （把 `0.3.11` 往上加一个版本号）再 `npx @vscode/vsce publish` ✓。

---

## 七、版本发布检查清单

- [ ] `package.json` `version` 已加；
- [ ] `CHANGELOG.md` 写了这一版；
- [ ] `RELEASE_NOTES.md` 是本次 GitHub Release 正文；
- [ ] `README.md` 的使用说明与截图（可选）是最新的；
- [ ] `python -c "import py_compile; py_compile.compile('runner/vscode_runner.py', doraise=True)"` 通过；
- [ ] `node --check extension.js` 通过；
- [ ] `python -m pytest tests/test_vscode_extension.py -q` 通过（清单/代码/运行器一致性 + 真的跑一次导出）；
- [ ] 在 Extension Development Host 里用手上的策略实测三种场景（回测 / 回放 / 实时）；
- [ ] 打包：`npx @vscode/vsce package`；装 VSIX 复测；
- [ ] 发布：`npm run publish`（微软商店）/ `npm run publish:ovsx`（Open VSX）/ 上传 VSIX 到 GitHub Release，三选一即可。

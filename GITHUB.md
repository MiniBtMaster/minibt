# 上传到 GitHub（minibt-charts）

目标仓库：<https://github.com/MiniBtMaster/minibt-charts>

## 0. 先确认目录干净

```bash
cd /path/to/minibt-charts
git status
```

如果你现在在旧的 `marster/` 目录里，请先确认它的 `.git` 历史：

```bash
git remote -v
git log --oneline -5
```

`marster/` 当前若是 **minibt 主包**的历史，不要直接把 `origin` 改到
`minibt-charts` 后强推。建议新建一个干净目录，把本扩展的源码复制进去；
或者在旧仓库里新建 orphan 分支（高级操作，见文末）。

## 1. 初始化独立仓库

```bash
# 假设已经复制到 minibt-charts/，且目录里只有本扩展源码
cd minibt-charts
git init
git branch -M main
git add .
git status                 # 确认没有 *.vsix / _vsix_backup / __pycache__
git commit -m "Release minibt-charts 0.3.11"
git remote add origin https://github.com/MiniBtMaster/minibt-charts.git
git push -u origin main
```

首次推送前，GitHub 上需要已经创建空仓库 `MiniBtMaster/minibt-charts`。
不要勾选自动生成 README / LICENSE / .gitignore，否则首次推送需要先合并。

## 2. 打 tag，触发 GitHub Release

```bash
git tag -a v0.3.11 -m "minibt-charts 0.3.11"
git push origin v0.3.11
```

仓库里的 `.github/workflows/release.yml` 会在 tag 推送后：

1. 校验 `extension.js` / `desk.js` / Python runner；
2. 执行 `npx @vscode/vsce package`；
3. 创建 GitHub Release，并上传 `minibt-charts-0.3.11.vsix`。

也可以手动上传：

```bash
npm run package
gh release create v0.3.11 minibt-charts-0.3.11.vsix \
  --title "minibt-charts 0.3.11" \
  --notes-file RELEASE_NOTES.md
```

## 3. 仓库资料检查

提交到 GitHub 的应包含：

```text
package.json
extension.js
desk.js
runner/vscode_runner.py
media/
README.md
CHANGELOG.md
RELEASE_NOTES.md
LICENSE
PUBLISHING.md
GITHUB.md
.gitignore
.gitattributes
.vscodeignore
.github/workflows/ci.yml
.github/workflows/release.yml
```

**不要提交**：

```text
node_modules/
*.vsix
_vsix_backup/
__pycache__/
.venv/
.vscode/
*.log
```

## 4. 仓库页面建议

- Description：`VS Code extension for MiniBT strategy charts and minibt desk`
- Topics：`minibt`, `trading`, `quant`, `vscode-extension`, `pylightcharts`, `bokeh`
- License：MIT
- Releases：每个版本挂 `.vsix`，正文使用 `RELEASE_NOTES.md`
- 默认分支：`main`

## 5. 如果必须复用旧仓库历史

确认要保留旧历史时，可以新建 orphan 分支，把扩展源码作为新的根提交：

```bash
git checkout --orphan minibt-charts
git rm -rf .
# 把扩展文件复制进来
git add .
git commit -m "Initial minibt-charts 0.3.11"
git branch -M minibt-charts
```

之后可以把它作为默认分支，或合并到 `main`。这不会删除旧分支，但请先备份
原仓库；不熟悉时建议直接用新的干净目录。

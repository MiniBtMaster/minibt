# 发布 `pylightcharts`（维护者手册）

一次完整发布 = 下面 8 步，全程约 15 分钟。`main`/`master` 上的
CI（`.github/workflows/ci.yml`）会替你校验其中的第 3、4、5、6 步。

> 只在**干净的工作区**发布：`git status` 除了本次要提交的内容外应当为空。

## 1. 版本号（三处必须一致）

| 文件 | 位置 |
| --- | --- |
| `pyproject.toml` | `version = "x.y.z"` |
| `pylightcharts/__init__.py` | 模块 docstring 里的 `- Version: x.y.z` |
| `pylightcharts/__init__.py` | `__version__` **和** `__version_info__` |

`tests/test_packaging.py::test_version_is_consistent` 会强制这三处一致：

```bash
python -m pytest tests/test_packaging.py -q
```

## 2. 写 changelog

`docs/changelog.md` 顶部加一节（Keep a Changelog 风格：`Added` /
`Changed` / `Fixed` / `Notes`，再补发布当天的日期）：

```markdown
## [0.1.7] - 2026-10-30
```

## 3. 重新构建 JS bundle（改了 `jslib/` 才需要）

```bash
# 也行：npm --prefix jslib run build  （PowerShell 5.1 不认 `&&` ✓）
cd jslib
node node_modules/rollup/dist/bin/rollup -c   # npx rollup -c 在本机可能卡住
node scripts/postbuild.mjs                    # 拷到 pylightcharts/js/
cd ..
```

产物必须**字节级**一致，否则 CI 的 `js` job 会红：

```bash
git diff --exit-code -- pylightcharts/js      # 提交后应当没有输出
```

## 4. 重新生成 API 文档

```bash
python scripts/gen_api_docs.py                # 更新 docs/api.md
```

CI 会重跑一遍并比对：`docs/api.md` 过期就报错。

## 5. 全量测试

```bash
python -m pytest tests -q                     # 应为 0 failed
```

需要 `minibt` / `miniqt` / `tutorials` 源码的测试会自动 skip，
所以 CI（只装本包）也能全绿。

## 6. 构建并检查产物

```bash
rm -rf dist build pylightcharts.egg-info
python -m build                               # wheel + sdist
```

* **wheel**：只装 `pylightcharts/` + `pylightcharts/js/{bundle,lightweight-charts}.js`
  + `index.html` + `styles.css` + `licenses/{LICENSE,NOTICE}`；不含 tests。
* **sdist**：完整源码树（`MANIFEST.in`：`examples/`、`scripts/`、`docs/`、
  `tests/`、`jslib/`、`requirements.txt`……），解压后可以直接
  `pytest tests -q` 跑通 —— 这样打包发行版/离线环境的人不用回仓库。
* 两个产物都不应包含 `minibt/`、`tutorials/`、`minibt_docs/`、`_diag_*.py`、
  `node_modules/` 或任何凭据 —— 用脚本检查（CI 也会跑）：

```bash
python scripts/check_sdist.py
```

```bash
# 干净环境装 wheel 再 import（CI 的 package job 也会做）
python -m venv /tmp/verify && /tmp/verify/bin/pip install dist/*.whl
/tmp/verify/bin/python -c "import pylightcharts; print(pylightcharts.__version__)"
```

## 7. 提交并打 tag

```bash
git add -A
git commit -m "Release 0.1.7"
git tag -a v0.1.7 -m "pylightcharts 0.1.7"
git push origin master --tags
```

## 8. 上传 PyPI

```bash
python -m pip install --upgrade twine
python -m twine check dist/*
python -m twine upload dist/*                 # 需要 PyPI API token
```

## 发布前最后确认（容易忘）

- 根目录的 `cci.py`、`example_realtime.py` 里有**真实天勤账号**，它们
  是**未跟踪**文件：不要 `git add -A` 时误加（`.gitignore` 也没忽略它们，
  提交前先 `git status` 看一眼）。
- `git add -A` 会不会带进 `_diag_*.py` / `_*.png`（已被 `.gitignore` 忽略，
  但新名字未必）？
- `pylightcharts/js/*` 是否已提交（`include-package-data` 靠它）。
- `README.md` 的「非 LWC 原生 API」清单、`README.zh-CN.md`、
  `docs/`、`docs/changelog.md` 四者描述是否一致。
- `python scripts/gen_api_docs.py` 生成的 `docs/api.md` 是否已提交
  （新增了公开方法却忘了重跑，CI 的 `docs` job 会红）。

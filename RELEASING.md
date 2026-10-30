# minibt 发布手册（1.3.4）

本手册只针对 **minibt Python 包**。所有打包前资料都放在 `minibt/` 目录下，
不需要回到仓库根目录查找发布文档。

## 0. 前置条件

- Python **3.12+**
- 已安装 `build`、`twine`、`Cython>=3.0`、`numpy>=2.2.6`
- Windows 构建 wheel 需要 MSVC Build Tools；否则只能构建纯 Python 回退包
- 有 C 编译器时，`setup.py` 会在构建阶段编译以下扩展：
  `backtest_engine` / `backtrader_from_signals` /
  `backtrader_pair_from_signals` / `signal_profit` / `zigzag.core`

工作区应当只包含本次发布要提交的内容：

```bash
git status --short
```

> `minibt/build/`、`minibt/dist/`、`minibt/*.egg-info/` 都是构建产物，不提交。

## 1. 版本号（三处一致）

| 文件 | 位置 |
| --- | --- |
| `minibt/pyproject.toml` | `version = "1.3.4"` |
| `minibt/__init__.py` | `版本信息: v1.3.4`、`__version__`、`__version_info__` |
| `minibt/README.md` | 版本徽章 `version-1.3.4-green` + `v1.3.4 更新亮点` |

自动检查：

```bash
cd minibt
python -m pytest ../tests/test_minibt_packaging.py::test_version_consistent_across_package_files -q
```

## 2. 打包前资料

确认以下文件已更新：

- `minibt/CHANGELOG.md` —— 本次版本条目
- `minibt/RELEASE_NOTES.md` —— 可直接发布的说明
- `minibt/README.md` —— 安装、快速开始、更新亮点
- `minibt/requirements.txt` —— 与 `pyproject.toml` 的依赖集合一致
- `minibt/MANIFEST.in` —— 发布资料 / 数据 / Cython 源码进入 sdist

检查依赖和包声明：

```bash
cd minibt
python -m pytest ../tests/test_minibt_packaging.py -q
```

## 3. 完善并运行 tutorials 示例

本次重点检查 `tutorials/indicators/`：

```bash
cd ..
python -m pytest tests/test_minibt_packaging.py::test_tutorials_compile -q

# 逐个示例（全部只使用内置数据，不需要联网 / 账号）
for f in tutorials/indicators/*.py; do
    python "$f" || exit 1
done
```

Windows PowerShell：

```powershell
Get-ChildItem tutorials/indicators/*.py | ForEach-Object {
    python $_.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

如果终端是 GBK，先设置 UTF-8：

```bash
set PYTHONIOENCODING=utf-8          # cmd
$env:PYTHONIOENCODING = "utf-8"      # PowerShell
export PYTHONIOENCODING=utf-8        # bash
```

说明：`14_shared_pane.py` 会打开图表窗口；其余示例以打印结果为主。

## 4. 构建

```bash
cd minibt
rm -rf build dist minibt.egg-info        # bash
# Windows: rmdir /s /q build dist minibt.egg-info
python -m build        # 同时生成 wheel + sdist（推荐）
```

只打其中一种：

```bash
python -m build --wheel
python -m build --sdist
```

> sdist 必须包含 `cython_functions/*.pyx` 与 `zigzag/*.pyx`，否则从 sdist
> 再构建 wheel 会报 `doesn't match any files`。`MANIFEST.in` 的路径是相对
> `minibt/` 项目根写的（不要加 `minibt/` 前缀）。

没有编译环境时可以临时跳过 Cython（不建议用于正式发布）：

```bash
MINIBT_NO_CYTHON=1 python -m build --wheel
```

构建时 `setup.py` 会自动复位 `LocalDatas` 索引，只保留包内基础数据，
避免把本机 `~/.minibt/datas` 的私人数据名写进 wheel。

## 5. 检查产物

```bash
cd minibt
python -m twine check dist/*

python - <<'PY'
import pathlib, zipfile
wheel = next(pathlib.Path('dist').glob('minibt-1.3.4-*.whl'))
with zipfile.ZipFile(wheel) as z:
    names = set(z.namelist())
required = {
    'minibt/__init__.py',
    'minibt/bt.py',
    'minibt/data/utils.py',
    'minibt/data/test',
    'minibt/cython_functions/backtest_engine',
    'minibt/cython_functions/backtrader_from_signals',
    'minibt/cython_functions/backtrader_pair_from_signals',
    'minibt/cython_functions/signal_profit',
    'minibt/zigzag/core',
}
missing = [name for name in required
           if not any(n == name or n.startswith(name + '.')
                      or n.startswith(name + '/')
                      for n in names)]
assert not missing, missing
forbidden = [n for n in names if n.startswith(('tests/', 'tutorials/',
                                               'minibt_docs/', 'build/'))]
assert not forbidden, forbidden
print('wheel OK:', wheel, len(names), 'paths')
PY
```

轮子应包含：

- 全部 Python 包（含 `minibt.desk` / `minibt.indicators` / `minibt.strategy` …）
- `minibt.cython_functions.*` 与 `minibt.zigzag.core` 的 `.pyd` / `.so`
- `minibt/data/*.csv`、`*.ini`、`*.png`、`data/test/*.csv`
- `minibt/strategy/*.js`

轮子不应包含：`tests/`、`tutorials/`、`minibt_docs/`、`build/`、本机日志、
`__pycache__`、私人数据 CSV。

## 6. 干净环境验证

```bash
python -m venv /tmp/minibt-verify --system-site-packages
/tmp/minibt-verify/bin/python -m pip install --no-deps \
    dist/minibt-1.3.4-*.whl
/tmp/minibt-verify/bin/python - <<'PY'
import minibt
from minibt import Bt, LocalDatas, Strategy
print(minibt.__version__, len(LocalDatas.test.kline))
PY
```

Windows 使用 `.venv-verify\Scripts\python.exe`。

重点确认：

- `minibt.__version__ == "1.3.4"`
- `LocalDatas.test.kline` 能加载
- `python -m minibt.cli --help` 或 `minibt --help` 不报错

## 7. 提交与打 tag

在 minibt 独立仓库根目录：

```bash
git add -A
git commit -m "Release minibt 1.3.4"
git tag -a v1.3.4 -m "minibt 1.3.4"
git push origin master --tags
```

如果当前工作区是 `pylightcharts` 的 monorepo，只在对应子仓库 / 子目录打
`minibt-v1.3.4`，不要误提交根目录其他包的构建产物。

## 8. 上传 PyPI

```bash
cd minibt
python -m pip install --upgrade twine
python -m twine check dist/*
python -m twine upload dist/*
```

需要 PyPI API token；上传前再确认 `dist/` 里只有本次的 1.3.4 产物。

## 发布前最后检查

- [ ] `pyproject.toml` / `__init__.py` / `README.md` 都是 1.3.4
- [ ] `CHANGELOG.md` / `RELEASE_NOTES.md` 已写本次版本
- [ ] `requirements.txt` 与 `pyproject.toml` 一致
- [ ] `tutorials/indicators/*.py` 全部运行通过
- [ ] `python -m pytest ../tests/test_minibt_packaging.py -q` 通过
- [ ] wheel 内没有 `tests/` / `tutorials/` / `minibt_docs/` / 私人数据
- [ ] 干净环境安装 wheel 后能 `import minibt`
- [ ] 没有把 `build/`、`dist/`、`*.egg-info/`、`__pycache__` 提交

"""``tutorials/plots`` 里的 `Gui.Desk` 示例（12~15）护栏用例。

非 notebook 的完整示例在 ``tutorials/desk/gui/``；这里只放「一个模式一个
最小例子」，并额外提供 **.ipynb**（Jupyter 里 desk 自动 iframe 内嵌）。

这些断言保证：

* 每个模式都有 ``.py`` + ``.ipynb``（Jupyter 与脚本都能跑）；
* notebook 的第一个 code cell 会把**仓库根目录**放进 ``sys.path`` ——
  否则 kernel 的 cwd 是 ``tutorials/plots``，会 import 到 site-packages 里的
  旧 minibt 副本（v1.3.4 排查时踩过 ✗）；
* 全部用 ``Gui.Desk``，且实时示例的合约能被 ``strategy_plan`` 解析出来。
"""
import ast
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLOTS = ROOT / 'tutorials' / 'plots'

EXAMPLES = {
    '12_desk_btplot': 'btplot',
    '13_desk_backtest': 'backtest',
    '14_desk_replay': 'replay',
    '15_desk_live': 'live',
}


def _py(name: str) -> pathlib.Path:
    return PLOTS / f'{name}.py'


def _nb(name: str) -> pathlib.Path:
    return PLOTS / f'{name}.ipynb'


@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_py_exists_and_parses(name):
    path = _py(name)
    assert path.is_file(), f'缺少 {path.name}'
    ast.parse(path.read_text(encoding='utf-8'))
    assert 'Gui.Desk' in path.read_text(encoding='utf-8')


@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_notebook_exists_and_is_valid(name):
    path = _nb(name)
    assert path.is_file(), f'缺少 {path.name}'
    notebook = json.loads(path.read_text(encoding='utf-8'))
    assert notebook['nbformat'] >= 4
    cells = notebook['cells']
    assert cells and cells[0]['cell_type'] == 'markdown'
    code = [cell for cell in cells if cell['cell_type'] == 'code']
    assert code, 'notebook 至少要有一个 code cell'
    text = ''.join(''.join(cell['source']) for cell in code)
    assert 'Gui.Desk' in text
    # 仓库根目录 bootstrap（见模块 docstring）✓
    assert "os.path.join(_here, 'minibt')" in text
    assert 'sys.path.insert(0, _here)' in text


@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_notebook_keeps_all_classes(name):
    """notebook 里必须保留 .py 的**所有类 / 顶层常量**。

    回归：重构笔记本的 bootstrap 时曾把 `class LiveMa` / `LiveMaStrategy`
    一起覆盖掉 → 运行格子 `NameError: name 'LiveMaStrategy' is not defined` ✗
    """
    tree = ast.parse(_py(name).read_text(encoding='utf-8'))
    expected = [node.name for node in tree.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
    # 脚本入口 `main()` 不在 notebook 里（notebook 直接写运行格子 ✓）
    expected = [item for item in expected
                if not item.startswith('_') and item != 'main']
    notebook_text = _notebook_code(name)
    missing = [item for item in expected
               if f'class {item}' not in notebook_text
               and f'def {item}' not in notebook_text]
    assert not missing, f'{name}.ipynb 丢了定义：{missing}'


@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_notebook_defines_things_before_using_them(name):
    """策略类必须在**执行格子之前**定义（类格子不能跑到后面）✓"""
    notebook = json.loads(_nb(name).read_text(encoding='utf-8'))
    code = [''.join(cell['source']) for cell in notebook['cells']
            if cell['cell_type'] == 'code']
    run_index = max(i for i, text in enumerate(code)
                    if 'bt.run(' in text or '.btplot(' in text)
    before = '\n'.join(code[:run_index])
    for item in re.findall(r'^(?:class|def)\s+(\w+)',
                           '\n'.join(code), re.MULTILINE):
        assert re.search(r'^(?:class|def)\s+%s\b' % item, before, re.M), (
            f'{name}.ipynb：{item} 在运行格子之后才定义 ✗')


@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_notebook_does_not_hardcode_credentials(name):
    """示例里不能写死天勤账号 / 密码（只允许空默认值 + 环境变量）✓"""
    text = _notebook_code(name)
    for key in ('TQ_USER', 'TQ_PASS'):
        for match in re.finditer(
                r"os\.environ\.get\(\s*'%s'\s*,\s*'([^']*)'" % key, text):
            assert match.group(1) == '', f'{name}.ipynb 写死了 {key}'


@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_readme_lists_example(name):
    readme = (PLOTS / 'README.md').read_text(encoding='utf-8')
    assert f'{name}.py' in readme, f'README 没提到 {name}.py'


def test_live_example_exposes_shfe_symbol():
    from minibt.desk.strategy_plan import analyze
    plan = analyze(str(_py('15_desk_live')))
    assert plan['contracts'] == ['SHFE.ag2612']


def test_live_example_has_params_symbol():
    """`strategy_symbols` 先看类里的 params —— 实时页靠它决定打开哪个合约 ✓"""
    from minibt.desk import gui as dgui

    module = _load(_py('15_desk_live'), 'plots_desk_live')
    assert dgui.strategy_symbols(module.LiveMaStrategy) == ['SHFE.ag2612']


def test_replay_example_uses_replay_mode():
    text = _py('14_desk_replay').read_text(encoding='utf-8')
    assert 'replay=True' in text
    assert "desk_mode='replay'" in text


def test_backtest_example_uses_backtest_mode():
    text = _py('13_desk_backtest').read_text(encoding='utf-8')
    assert "desk_mode='backtest'" in text


def test_btplot_example_uses_btplot_desk():
    text = _py('12_desk_btplot').read_text(encoding='utf-8')
    assert '.btplot(gui=Gui.Desk)' in text


def test_docs_mention_jupyter_iframe():
    """文档要写清“notebook 里是 iframe 内嵌、不阻塞 kernel” ✓"""
    doc = (ROOT / 'minibt_docs' / 'docs' / 'minibt_basic'
           / '1.33minibt_desk_gui.md').read_text(encoding='utf-8')
    assert 'Jupyter' in doc
    assert 'iframe' in doc
    assert '15_desk_live' in doc or 'tutorials/plots' in doc


def test_docs_cover_all_jupyter_modes():
    """1.33 的 Jupyter 节要覆盖 btplot / 回测 / 回放 / 实时 ✓"""
    doc = (ROOT / 'minibt_docs' / 'docs' / 'minibt_basic'
           / '1.33minibt_desk_gui.md').read_text(encoding='utf-8')
    section = doc[doc.index('## 七、'):]
    for needle in ('.btplot(gui=Gui.Desk)',
                   "desk_mode='backtest'",
                   'Bt(auto=False, replay=True)',
                   'Bt(auto=False, live=True)',
                   'MINIBT_DESK_JUPYTER_HEIGHT',
                   'keep_alive'):
        assert needle in section, f'Jupyter 节缺少：{needle}'


# ------------------------------------------------------------------ helper
def _notebook_code(name: str) -> str:
    notebook = json.loads(_nb(name).read_text(encoding='utf-8'))
    return '\n'.join(''.join(cell['source']) for cell in notebook['cells']
                     if cell['cell_type'] == 'code')


def _load(path: pathlib.Path, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

"""`tutorials/desk/gui/*.py`（`Gui.Desk` 示例）的护栏用例。

这些例子是给用户直接 `python xxx.py` 跑的，所以至少要保证：

* 语法 / 导入没错（每个文件都能编译）；
* 每个例子都真的用 `Gui.Desk`（而不是悄悄用了别的引擎）；
* 静态分析（`strategy_plan.analyze`）能从策略里解析出合约 —— 否则
  desk 的「加到图表」会以"没找到合约"结束，示例看起来像坏了 ✗；
* 实时示例的 `params` 里写的上期所主力合约都能被解析出来。
"""
import ast
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUI_DIR = ROOT / 'tutorials' / 'desk' / 'gui'

EXPECTED = (
    '01_btplot_style.py',
    '02_btindicator_style.py',
    '03_strategy_local_chart.py',
    '04_backtest_local_chart.py',
    '05_optimize_local_chart.py',
    '06_live_single_shfe.py',
    '07_live_pair_shfe.py',
    '08_live_multi_shfe.py',
)


def _read(name: str) -> str:
    return (GUI_DIR / name).read_text(encoding='utf-8')


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_example_files_exist_and_parse():
    assert GUI_DIR.is_dir()
    names = {path.name for path in GUI_DIR.glob('*.py')}
    for name in EXPECTED:
        assert name in names, f'缺少示例 {name}'
        ast.parse(_read(name))            # 语法 ✓


def test_every_example_uses_gui_desk():
    for name in EXPECTED:
        source = _read(name)
        assert 'Gui.Desk' in source, f'{name} 没有用 Gui.Desk'


def test_readme_lists_every_example():
    readme = (GUI_DIR / 'README.md').read_text(encoding='utf-8')
    for name in EXPECTED:
        assert name in readme, f'README 没提到 {name}'


def test_examples_readme_is_linked_from_tutorials_desk():
    text = (ROOT / 'tutorials' / 'desk' / 'README.md').read_text(
        encoding='utf-8')
    assert 'gui/README.md' in text


# ------------------------------------------------------------ 合约解析
def test_plan_reads_params_and_constants(tmp_path):
    """`params = dict(symbol=SYMBOL)` + `get_kline(self.params.symbol)` ✓"""
    from minibt.desk.strategy_plan import analyze
    path = tmp_path / 'p.py'
    path.write_text('''
SYMBOL = 'SHFE.ag2612'


class S:
    params = dict(symbol=SYMBOL, size=1)

    def __init__(self):
        self.data = self.get_kline(self.params.symbol)
        self.other = self.get_kline('SHFE.au2612')
''', encoding='utf-8')
    plan = analyze(str(path))
    assert plan['contracts'] == ['SHFE.ag2612', 'SHFE.au2612']


def test_plan_reads_leg_params(tmp_path):
    """配对策略的 `leg_a` / `leg_b` 也要认 ✓"""
    from minibt.desk.strategy_plan import analyze
    path = tmp_path / 'p.py'
    path.write_text('''
LEG_A = 'SHFE.ag2612'
LEG_B = 'SHFE.au2612'


class P:
    params = dict(leg_a=LEG_A, leg_b=LEG_B)

    def __init__(self):
        self.a = self.get_kline(self.params.leg_a)
        self.b = self.get_kline(self.params.leg_b)
''', encoding='utf-8')
    assert analyze(str(path))['contracts'] == ['SHFE.ag2612', 'SHFE.au2612']


@pytest.mark.parametrize('name,expected', [
    ('06_live_single_shfe.py', ['SHFE.ag2612']),
    ('07_live_pair_shfe.py', ['SHFE.ag2612', 'SHFE.au2612']),
])
def test_live_examples_expose_their_shfe_symbols(name, expected):
    from minibt.desk.strategy_plan import analyze
    assert analyze(str(GUI_DIR / name))['contracts'] == expected


def test_multi_strategy_example_symbols_per_strategy():
    """一个文件三个策略：按类里的 params 分别取合约（不是"文件第一个"✓）"""
    from minibt.desk import gui as dgui
    module = _load(GUI_DIR / '08_live_multi_shfe.py', 'desk_gui_ex_multi')
    symbols = [dgui.strategy_symbols(cls) for cls in
               (module.LiveMaAg, module.LiveMaAu, module.LiveBreakCu)]
    assert symbols == [['SHFE.ag2612'], ['SHFE.au2612'], ['SHFE.cu2612']]


def test_strategy_path_points_at_the_example_file():
    from minibt.desk import gui as dgui
    module = _load(GUI_DIR / '06_live_single_shfe.py', 'desk_gui_ex_single')
    path = dgui.strategy_path(module.LiveSingleMa)
    assert pathlib.Path(path).resolve() == (
        GUI_DIR / '06_live_single_shfe.py').resolve()

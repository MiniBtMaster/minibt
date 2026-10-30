"""``Gui.Desk`` 在 **Jupyter** 里的内嵌支持（v1.3.4）。

要点：

* 真正的 notebook（``ZMQInteractiveShell``）里，``Gui.Desk`` 自动改用
  **浏览器壳 + iframe**（Qt 的 ``application.exec()`` 会把 kernel 卡死 ✗）；
* ``web.serve()`` 跑在 daemon 线程、``keep_alive=True``（iframe 重绘 /
  单元格滚动造成的短暂断线不能把服务停掉）；
* notebook 里 **不再**把 desk 日志刷进单元格（节拍线程持续写 stdout
  会让 IPython 收尾时卡住 ✗）；
* notebook 里定义的策略类：拷贝**整个单元格**（含同格的指标类），
  否则 desk 导入生成的 .py 时 ``NameError: <指标类> is not defined`` ✗。
"""
import pathlib
import sys
import time
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip('IPython')

from minibt.desk import gui  # noqa: E402


class _FakeDesk:
    """只实现 show_in_notebook 用到的字段（不建真窗口 / 不连行情）✓"""

    def __init__(self):
        self.browser = False
        self.open_browser = True
        self.url = ''
        self.port = 0
        self.closed = False
        self._notebook_quiet = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _clean_jupyter_desks():
    yield
    for desk in list(gui._JUPYTER_DESKS):
        try:
            desk.close()
        except Exception:                                        # noqa: BLE001
            pass
    gui._JUPYTER_DESKS.clear()


def test_in_notebook_false_when_not_in_kernel():
    """普通进程（pytest）里不能误判成 notebook —— 否则会起 HTTP 服务。"""
    assert gui.in_notebook() is False


def test_show_in_notebook_starts_browser_shell(monkeypatch):
    """``show_in_notebook``：后台 serve(keep_alive) → 等 url → display(IFrame) ✓"""
    from minibt.desk import web

    served = {}

    def fake_serve(desk, **kwargs):
        served['desk'] = desk
        served['kwargs'] = dict(kwargs)
        desk.port = 45231
        desk.url = 'http://127.0.0.1:45231/'
        while True:                      # 真实 serve 也是 serve_forever ✓
            time.sleep(0.05)

    monkeypatch.setattr(web, 'serve', fake_serve)

    shown = []

    class FakeIFrame:
        def __init__(self, url, **kwargs):
            self.url = url
            self.kwargs = kwargs

    import IPython.display as ipy_display
    monkeypatch.setattr(ipy_display, 'IFrame', FakeIFrame)
    monkeypatch.setattr(ipy_display, 'display', lambda obj: shown.append(obj))

    desk = _FakeDesk()
    url = gui.show_in_notebook(desk, height=700, timeout=10)

    assert url == 'http://127.0.0.1:45231/'
    assert served['kwargs'] == {'open_browser': False, 'keep_alive': True}
    assert desk.browser is True
    assert desk.open_browser is False
    assert desk._notebook_quiet is True      # 日志不刷单元格 ✓
    assert shown and shown[0].url == url
    assert shown[0].kwargs.get('width') == '100%'
    assert shown[0].kwargs.get('height') == 700
    assert desk in gui._JUPYTER_DESKS


def test_show_in_notebook_raises_when_server_fails(monkeypatch):
    """``serve`` 抛错（desk.html 没构建 / 端口失败）→ 明确报错，不要静默 ✓"""
    from minibt.desk import web

    def broken(desk, **kwargs):
        raise FileNotFoundError('desk.html 不存在')

    monkeypatch.setattr(web, 'serve', broken)
    with pytest.raises(RuntimeError, match='desk 浏览器壳启动失败'):
        gui.show_in_notebook(_FakeDesk(), timeout=2)


def test_run_desk_never_blocks_in_notebook(monkeypatch):
    """notebook 里 ``run_desk`` 走 iframe，**不**调用阻塞的 ``desk.run()`` ✓"""
    monkeypatch.setattr(gui, 'in_notebook', lambda: True)
    called = []
    monkeypatch.setattr(gui, 'show_in_notebook',
                        lambda desk, **kwargs: called.append(desk))

    class BlockingDesk:
        def run(self):
            raise AssertionError('notebook 里不能走 Qt / 阻塞 run()')

    desk = BlockingDesk()
    gui.run_desk(desk)
    assert called == [desk]


def test_desk_run_falls_back_to_iframe_in_notebook(monkeypatch):
    """``Desk.run()`` 被直接调用时也要降级（防止某个入口忘了 run_desk ✓）"""
    from minibt.desk import app as appmod

    monkeypatch.setattr(gui, 'in_notebook', lambda: True)
    called = []
    monkeypatch.setattr(gui, 'show_in_notebook',
                        lambda desk, **kwargs: called.append(desk))

    desk = appmod.Desk(offline=True)
    desk.run()
    assert called == [desk]
    assert desk.browser is True            # 不会再开 Qt 窗口 ✓
    assert desk.open_browser is False


# ------------------------------------------------------------ 单元格源码
def _fake_notebook_shell(cells):
    shell = types.SimpleNamespace(user_ns={'In': [''] + list(cells)})
    return shell


def test_cell_source_returns_the_whole_cell(monkeypatch):
    """策略依赖同格的指标类 → 必须拷整个单元格（不是只有策略类）✓"""
    import IPython

    cell = textwrap_dedent('''
        class DeskMa(BtIndicator):
            pass

        class MyStrat(Strategy):
            pass
    ''')
    monkeypatch.setattr(IPython, 'get_ipython',
                        lambda: _fake_notebook_shell([cell]))
    target = type('MyStrat', (), {})
    assert gui._cell_source(target) == cell


def test_cell_source_returns_empty_when_not_found(monkeypatch):
    import IPython
    monkeypatch.setattr(IPython, 'get_ipython',
                        lambda: _fake_notebook_shell(['x = 1']))
    assert gui._cell_source(type('Missing', (), {})) == ''


def test_strategy_path_writes_whole_cell_for_notebook_class(
        monkeypatch, tmp_path):
    """notebook 类没有源文件 → 写到 GENERATED_DIR，且**两个类都在** ✓"""
    import IPython

    cell = textwrap_dedent('''
        class NbrIndicator(BtIndicator):
            lines = ('ma',)

        class NbrStrategy(Strategy):
            params = dict(symbol='SHFE.ag2612', size=1)
    ''')
    monkeypatch.setattr(IPython, 'get_ipython',
                        lambda: _fake_notebook_shell([cell]))
    monkeypatch.setattr(gui, 'GENERATED_DIR', str(tmp_path))

    target = type('NbrStrategy', (), {'__module__': 'minibt_nb_fake'})
    sys.modules['minibt_nb_fake'] = types.ModuleType('minibt_nb_fake')

    path = gui.strategy_path(target)
    text = pathlib.Path(path).read_text(encoding='utf-8')
    assert pathlib.Path(path).parent == tmp_path
    assert 'from minibt import *' in text
    assert 'import numpy as np' in text
    assert 'class NbrIndicator' in text      # 依赖的指标类 ✓
    assert 'class NbrStrategy' in text


def textwrap_dedent(text: str) -> str:
    import textwrap
    return textwrap.dedent(text).strip() + '\n'


# ------------------------------------------------------- 单元格里的常量
def test_cell_missing_names_ignores_minibt_and_local_defs():
    """``SYMBOL`` 算“缺”，``np`` / ``Strategy`` / 本格定义的类不算 ✓"""
    cell = ('class S(Strategy):\n'
            '    params = dict(symbol=SYMBOL)\n'
            '    x = np.array([1])\n')
    names = gui._cell_missing_names(cell)
    assert 'SYMBOL' in names
    assert 'np' not in names          # 生成文件头部已 import ✓
    assert 'Strategy' not in names    # `from minibt import *` 里有 ✓
    assert 'S' not in names


def test_cell_constants_carries_only_literals(monkeypatch):
    """只带字面量常量（``SYMBOL`` / ``SIZE``），不带模块 / 对象 ✓"""
    import IPython
    cell = ('class S(Strategy):\n'
            '    params = dict(symbol=SYMBOL, size=SIZE)\n'
            '    other = SOMETHING\n')
    namespace = {'In': [''], 'SYMBOL': 'SHFE.ag2612', 'SIZE': 2,
                 'SOMETHING': object()}
    monkeypatch.setattr(
        IPython, 'get_ipython',
        lambda: types.SimpleNamespace(user_ns=namespace))
    lines = gui._cell_constants(cell)
    assert "SYMBOL = 'SHFE.ag2612'" in lines
    assert 'SIZE = 2' in lines
    assert not any(line.startswith('SOMETHING') for line in lines)


def test_strategy_path_carries_constants_from_other_cells(monkeypatch,
                                                          tmp_path):
    """回归：``SYMBOL`` 写在上一格 → 生成文件里必须补上，且能正常 import ✓"""
    import IPython
    cell = textwrap_dedent('''
        class NbrConstStrategy(Strategy):
            params = dict(symbol=SYMBOL, size=1)
    ''')
    namespace = {'In': ['', cell], 'SYMBOL': 'SHFE.ag2612'}
    monkeypatch.setattr(
        IPython, 'get_ipython',
        lambda: types.SimpleNamespace(user_ns=namespace))
    monkeypatch.setattr(gui, 'GENERATED_DIR', str(tmp_path))

    target = type('NbrConstStrategy', (), {'__module__': 'minibt_nb_fake2'})
    sys.modules['minibt_nb_fake2'] = types.ModuleType('minibt_nb_fake2')

    path = gui.strategy_path(target)
    text = pathlib.Path(path).read_text(encoding='utf-8')
    assert "SYMBOL = 'SHFE.ag2612'" in text

    namespace_out = {'__name__': 'generated_check'}
    exec(compile(text, path, 'exec'), namespace_out)
    cls = namespace_out['NbrConstStrategy']
    assert cls.params['symbol'] == 'SHFE.ag2612'


def test_show_in_notebook_honours_height_env(monkeypatch):
    """iframe 高度可用 `MINIBT_DESK_JUPYTER_HEIGHT` 覆盖 ✓"""
    from minibt.desk import web

    def fake_serve(desk, **kwargs):
        desk.port = 45232
        desk.url = 'http://127.0.0.1:45232/'
        while True:
            time.sleep(0.05)

    monkeypatch.setattr(web, 'serve', fake_serve)
    monkeypatch.setenv('MINIBT_DESK_JUPYTER_HEIGHT', '1000')

    shown = []

    class FakeIFrame:
        def __init__(self, url, **kwargs):
            self.kwargs = kwargs

    import IPython.display as ipy_display
    monkeypatch.setattr(ipy_display, 'IFrame', FakeIFrame)
    monkeypatch.setattr(ipy_display, 'display', lambda obj: shown.append(obj))

    gui.show_in_notebook(_FakeDesk(), height=600, timeout=10)
    assert shown[0].kwargs.get('height') == 1000

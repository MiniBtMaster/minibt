"""QuoteBoard 面板（pylightcharts 的新「行情报价」插件）+ 示例。

覆盖：
* Python 包装层的 JS 调用（`setTypes` / `setRows` / `setLoading` …）
* 事件回调分发（`click` / `dblclick` / `context` / `filter` / `refresh`）
* 主题下发
* TS 源码 / 构建产物
* `examples/13_panels/12_quote_board.py --check`
"""
import contextlib
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pylightcharts.panels import Column, QuoteBoard      # noqa: E402


class FakeWin:
    """够用的假 Window（只收集脚本 / handlers ✓）"""

    def __init__(self):
        self.scripts = []
        self.handlers = {}
        self._panels = []

    def run_script(self, script):
        self.scripts.append(script)

    def invoke(self, *args, **kwargs):
        return None

    def invoke_get(self, *args, **kwargs):
        return None

    @contextlib.contextmanager
    def bulk_run(self):
        yield

    class _Gen:
        count = 0

        def generate(self):
            FakeWin._Gen.count += 1
            index = FakeWin._Gen.count

            class Handle:
                def __str__(self):
                    return f'window.qb{index}'

                def __getattr__(self, item):
                    return f'window.qb{index}.{item}'

            return Handle()

    _id_gen = _Gen()


def _board(**kwargs):
    window = FakeWin()
    board = QuoteBoard(window, columns=[Column('symbol', '代码'),
                                        Column('last', '最新', type='number')],
                       types=[('FUT', '期货'), ('STOCK', '股票')],
                       exchanges=[('SHFE', '上期所')],
                       type='FUT', exchange='SHFE', **kwargs)
    return board, window


def test_create_passes_options():
    board, window = _board(show_ticker=True)
    first = window.scripts[0]
    assert 'new Lib.QuoteBoard(' in first
    # js_raw 会把中文转成 unicode 转义，所以只断言结构 ✓
    assert '"types":[{"key":"FUT"' in first
    assert '"exchange":"SHFE"' in first and '"showTicker":true' in first
    assert list(window.handlers) == [str(board.id)]      # callback 已绑定 ✓


def test_data_methods_emit_js():
    board, window = _board()
    window.scripts.clear()
    board.set_rows([{'symbol': 'SHFE.rb2610', 'last': 3600.0}])
    board.append_rows([{'symbol': 'SHFE.rb2611'}])
    board.update_rows([{'symbol': 'SHFE.rb2610', 'last': 3610.0}])
    board.set_loading(True, '正在加载 SHFE 合约…')
    board.set_loading(False)
    board.set_count('2 行')
    board.set_ticker([{'symbol': 'SHFE.rb2610', 'last': 3600.0}])
    board.set_column_visibility('strike', True)
    board.set_types([('FUT', '期货')], 'FUT')
    board.set_exchanges([('SHFE', '上期所')], 'SHFE')

    joined = '\n'.join(window.scripts)
    assert '.setRows([{"symbol":"SHFE.rb2610","last":3600.0}])' in joined
    assert '.appendRows(' in joined and '.updateRows(' in joined
    assert '.setLoading(true, ' in joined and '.setLoading(false, "")' in joined
    assert '.setCount("2 ' in joined              # 「2 行」
    assert '.setTicker(' in joined
    assert '.setColumnVisibility("strike", true)' in joined
    assert '.setTypes([{"key":"FUT"' in joined
    assert '.setExchanges([{"key":"SHFE"' in joined


def test_callbacks_dispatch():
    board, _window = _board()
    calls = []
    board.on_filter(lambda kind, exchange, text: calls.append(
        ('filter', kind, exchange, text)))
    board.on_click(lambda symbol, x, y: calls.append(('click', symbol, x, y)))
    board.on_double_click(lambda symbol: calls.append(('dbl', symbol)))
    board.on_context(lambda symbol: calls.append(('ctx', symbol)))
    board.on_refresh(lambda: calls.append(('refresh',)))

    board._dispatch('filter;;;FUT;;;SHFE;;;rb')
    board._dispatch('SHFE.rb2610;;;click;;;120;;;240')
    board._dispatch('SHFE.rb2610;;;dblclick')
    board._dispatch('SHFE.rb2610;;;context')
    board._dispatch('refresh')

    assert calls == [
        ('filter', 'FUT', 'SHFE', 'rb'),
        ('click', 'SHFE.rb2610', 120, 240),
        ('dbl', 'SHFE.rb2610'),
        ('ctx', 'SHFE.rb2610'),
        ('refresh',),
    ]


def test_callbacks_optional():
    board, _window = _board()
    # 没注册回调 → 不能炸 ✓
    board._dispatch('filter;;;FUT;;;SHFE;;;')
    board._dispatch('SHFE.rb2610;;;click;;;1;;;2')
    board._dispatch('SHFE.rb2610;;;dblclick')
    board._dispatch('SHFE.rb2610;;;context')
    board._dispatch('refresh')


def test_apply_theme():
    board, window = _board()
    window.scripts.clear()
    board.apply_theme({'background': '#0c0d0f', 'text': '#d8d9db',
                       'border': '#3C434C'})
    assert '.setOptions(' in window.scripts[-1]
    assert '"background":"#0c0d0f"' in window.scripts[-1]


def test_chips_normalisation():
    from pylightcharts.panels.quote_board import _chips

    assert _chips([('FUT', '期货')]) == [{'key': 'FUT', 'label': '期货'}]
    assert _chips(['FUT']) == [{'key': 'FUT', 'label': 'FUT'}]
    assert _chips([{'key': 'HK', 'label': '港股'}]) == [
        {'key': 'HK', 'label': '港股'}]
    assert _chips(None) == []


# ------------------------------------------------------------ TS / 产物
def test_ts_panel_and_bundle():
    source = (REPO / 'jslib' / 'src' / 'panels' / 'quote-board.ts').read_text(
        encoding='utf-8')
    for key in ('export class QuoteBoard', 'setTypes', 'setExchanges',
                'setRows', 'updateRows', 'setLoading', 'setTicker',
                'setColumnVisibility', 'visibleKeys', 'pylc-qb-chip'):
        assert key in source, key
    assert "export * from './quote-board';" in (
        REPO / 'jslib' / 'src' / 'panels' / 'index.ts').read_text(
        encoding='utf-8')
    bundle = (REPO / 'pylightcharts' / 'js' / 'bundle.js').read_text(
        encoding='utf-8', errors='ignore')
    for key in ('pylc-qb', 'pylc-qb-chip', 'QuoteBoard'):
        assert key in bundle, key


def test_example_check_mode(tmp_path):
    script = REPO / 'examples' / '13_panels' / '12_quote_board.py'
    assert script.is_file()
    result = subprocess.run([sys.executable, str(script), '--check'],
                            capture_output=True, text=True, encoding='utf-8',
                            env={**dict(__import__('os').environ),
                                 'PYTHONIOENCODING': 'utf-8'})
    assert result.returncode == 0, result.stderr[-800:]
    assert 'QuoteBoard 数据检查通过' in result.stdout
    assert 'FUT' in result.stdout and 'STOCK' in result.stdout


def test_examples_readme_lists_quote_board():
    readme = (REPO / 'examples' / '13_panels' / 'README.md').read_text(
        encoding='utf-8')
    assert '12_quote_board.py' in readme
    assert 'QuoteBoard' in readme

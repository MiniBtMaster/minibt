"""图表多布局：策略线按合约分组 / 工具栏跟随当前格 / 底部面板比例缩放。"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def _frame(rows=400, base=100.0):
    close = base + np.arange(rows, dtype=float) * 0.1 \
        + np.sin(np.arange(rows) / 9) * 2
    return pd.DataFrame({
        'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                     for i in range(rows)],
        'open': close - 0.5, 'high': close + 1.0, 'low': close - 1.0,
        'close': close, 'volume': np.ones(rows) * 10,
        'symbol': 'X', 'duration': 60, 'price_tick': 1.0,
        'volume_multiple': 10,
    })


def test_strategy_lines_stay_on_their_own_contract(tmp_path):
    """test_8 的 ma1/ma2 算在 ag2612 上，不能跑到 au2612 ✓"""
    source = tmp_path / 'pair.py'
    source.write_text(
        '''from minibt import *


class Pair(Strategy):
    def __init__(self):
        self.min_start_length = 20
        self.data = self.get_kline("SHFE.ag2612", height=500)
        self.data1 = self.get_kline("SHFE.au2612", height=500)
        self.data2 = IndFrame(
            dict(pp_close=self.data.close.values,
                 l_close=self.data1.close.values), overlap=False)
        self.data2.plot_symbol = "SHFE.au2612"
        self.ma1 = self.data.close.sma(5, overlap=True)
        self.ma2 = self.data.close.sma(60, overlap=True)
        self.i = 0

    def next(self):
        self.i += 1
''', encoding='utf-8')
    from minibt.desk import personal, strategy_overlay
    module = personal._import_file(str(source))
    cls = strategy_overlay.classes_of(module)['strategy'][0]
    ag = _frame(base=8000)
    au = _frame(base=600)
    result = strategy_overlay.run_overlay(
        ag, cls, 'SHFE.ag2612', 60,
        frames=[('SHFE.ag2612', ag), ('SHFE.au2612', au)])
    assert result['ok'], result.get('error')
    groups = result['groups']
    ag_labels = [item['label'] for item in groups.get('SHFE.ag2612', [])]
    au_labels = [item['label'] for item in groups.get('SHFE.au2612', [])]
    assert ag_labels.count('pta_sma') == 2
    assert 'pta_sma' not in au_labels
    assert {'pp_close', 'l_close'} <= set(au_labels)


def test_chart_page_toolbar_follows_clicked_cell():
    page = _read(JSLIB / 'chart-page.ts')
    assert 'private activeCell = 0;' in page
    assert '_setSymbolButton(symbol)' in page
    assert 'this._setSymbolButton(this.cellSymbols[0]' in page
    block = page.split('cell.addEventListener(\'pointerdown\'', 1)[1][:900]
    # ★ 指针按下 → `_activateCell(index)`（里面才写 `this.activeCell = index`）
    assert 'this._activateCell(index)' in block
    # 活动格会同步工具栏商品按钮 / 交易标的 / 画线导航条 ✓
    activate = page.split('private _activateCell(index: number): void {',
                          1)[1][:900]
    assert '_setSymbolButton' in activate and 'setTradeSymbol' in activate
    # 搜索框打开时也用当前格
    assert 'this.cellSymbols[this.activeCell] || this.options.symbol' in page


def test_both_charts_scale_dock_height_with_window():
    chart = _read(JSLIB / 'chart-page.ts')
    local = _read(JSLIB / 'local-chart-page.ts')
    for page in (chart, local):
        assert 'private dockRatio' in page
        assert 'private _applyDockRatio(' in page
        assert 'this._applyDockRatio()' in page
        assert 'this.dockRatio = this.dockHeight / total' in page
    assert 'this.dockRatio = 1 / 3' in chart
    assert 'this.dockRatio = 1 / 4' in local
    assert 'this.dockRestoreRatio = this.dockRatio' in chart
    assert 'this.dockRestoreRatio = this.dockRatio' in local

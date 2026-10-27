"""P64：编辑器空白右键 / 按钮图标与「加到图表」/ 无限历史 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


# ------------------------------------------------------- ① 资源管理器空白右键
def test_explorer_blank_area_context_menu():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    # 空白处右键 → 新建文件 / 新建文件夹（点到行上仍然走那一行的菜单 ✓）
    assert "this.tree.addEventListener('contextmenu'" in panel
    assert "closest('.desk-editor-node')" in panel
    assert "label: '新建文件…'" in panel
    assert "label: '新建文件夹…'" in panel
    assert 'private _newEntryAt(' in panel


# ------------------------------------------------------- ② 工具栏按钮
def test_editor_toolbar_icons_and_add_button():
    panel = (DESK_TS / 'editor-panel.ts').read_text(encoding='utf-8')
    # 「加到图表」不再只对指标可用（策略文件也能加 ✓）
    assert 'this.addButton.disabled = !tab;' in panel
    assert "tab.kind !== 'indicator'" not in panel
    # 刷新 → 图标；复制全部代码 → 复制图标（不是相机 ✓）
    assert 'refreshButton.innerHTML = ICON_REFRESH;' in panel
    assert 'shotButton.innerHTML = ICON_COPY;' in panel
    assert 'ICON_CAMERA' not in panel.split('import {', 1)[1].split('}', 1)[0]
    icons = (DESK_TS / 'icons.ts').read_text(encoding='utf-8')
    assert 'export const ICON_REFRESH' in icons
    assert 'export const ICON_COPY' in icons


# ------------------------------------------------------- ③ 无限历史
def test_infinite_history_backend(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.set_setting('chart_data_length', 200)
    up.set_setting('chart_history', 800)

    last = 1_700_500_000

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = min(int(length), 3000)      # 尾部对齐（真行情 ✓）
            start = last - (rows - 1) * 60
            close = 100 + np.sin(np.arange(rows) / 9) * 3
            return pd.DataFrame({
                'datetime': [(start + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close + 0.4, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(rows),
                'symbol': symbol, 'duration': cycle,
                'price_tick': 1.0, 'volume_multiple': 10,
            })

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = Feed()
    desk.feeds = [desk.futures]
    desk.offline = False

    assert desk.chart_lengths() == (800, 200)
    assert desk.data_length() == 200

    desk._on_open_chart({'symbol': 'SHFE.demo01'})

    def patches(kind):
        out = []
        prefix = 'window.__desk.applyPatch('
        for row in desk.sent:
            if prefix in row and f'"type":"{kind}"' in row:
                import json
                out.append(json.loads(row[len(prefix):-2]))
        return out

    first_bars = patches('kline')[-1]['bars']
    assert len(first_bars) == 200                 # 首屏 = 数据长度 ✓
    assert desk.tabs['SHFE.demo01']['loaded_len'] == 200

    # 往左翻 → 补 500 根
    desk.sent.clear()
    desk._on_history_load({'symbol': 'SHFE.demo01',
                           'before': first_bars[0]['time'], 'page': 500})
    added = patches('history_bars')[-1]
    assert added['bars'] and not added['exhausted']
    assert added['loaded'] == 700

    # 再翻 → 到上限 800（exhausted ✓）
    desk.sent.clear()
    desk._on_history_load({'symbol': 'SHFE.demo01',
                           'before': added['bars'][0]['time'], 'page': 500})
    last_batch = patches('history_bars')[-1]
    assert last_batch['loaded'] == 800
    assert last_batch['exhausted'] is True


def test_infinite_history_off_when_equal(tmp_path, monkeypatch):
    """`chart_history == chart_data_length` → 没有无限历史（直接 exhausted）✓"""
    from minibt.desk import user_prefs as up

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    up.set_setting('chart_data_length', 1000)
    up.set_setting('chart_history', 1000)

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.tabs['SHFE.demo01'] = {'feed': None, 'cycle': 60, 'indicators': [],
                               'loaded_len': 1000}
    desk._on_history_load({'symbol': 'SHFE.demo01', 'before': 1, 'page': 500})
    payload = None
    for row in desk.sent:
        if '"type":"history_bars"' in row:
            import json
            payload = json.loads(row[len('window.__desk.applyPatch('):-2])
    assert payload and payload['bars'] == []
    assert payload['exhausted'] is True


def test_infinite_history_frontend_wiring():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'subscribeVisibleLogicalRangeChange' in page
    assert 'private _maybeHistory(): void' in page
    assert 'prependHistory(bars: ChartBar[], exhausted = false)' in page
    assert "onCommand?.('history_load'" in page
    assert 'historyGrace' in page            # 刚打开不补（用户还没翻 ✓）
    app = (DESK_TS / 'app.ts').read_text(encoding='utf-8')
    assert "case 'history_bars':" in app
    application = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(
        encoding='utf-8')
    assert "'history_load': self._on_history_load" in application
    assert 'def data_length(self) -> int:' in application

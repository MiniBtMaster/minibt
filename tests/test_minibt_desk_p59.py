"""P59：回放视窗 / 编辑器标签样式 / 去掉「常用」/ 个人指标参数 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 回放视窗
def test_replay_keeps_visible_count_and_right_gap():
    # P60：chart-page 改成「播放中不动视窗」（LWC 自己跟随 ✓）；
    # 本地图表保持原来的显式算法（用户说它的表现是对的 ✓）
    name = 'chart-page.ts'
    if True:
        page = (JSLIB / name).read_text(encoding='utf-8')
        block = page.split('private _syncReplayViewport', 1)[1].split(
            '\n    private ', 1)[0]
        # 不再简单 +1（LWC 自己会锚右边 → 再 +1 会越来越空 ✗）
        # P60：只有「首次 / seek」才摆窗口（整段 + 右侧留白）；
        # 播放中不动 → 最新一根不贴边、用户拖动/缩放也不会被拉回 ✓
        assert 'REPLAY_WINDOW' in block and 'REPLAY_PADDING' in block
        assert 'setRange.call(scale' in block
        assert 'from: range.from + 1' not in block
        assert 'scrollToRealTime' not in block


# ------------------------------------------------------- ② 编辑器标签样式
def test_editor_tab_active_uses_accent_border():
    panel = (JSLIB / 'editor-panel.ts').read_text(encoding='utf-8')
    base = panel.split('.desk-editor-tab {', 1)[1].split('}', 1)[0]
    assert 'border: 1px solid transparent' in base      # 未选中：无描边 ✓
    active = panel.split('.desk-editor-tab.on {', 1)[1].split('}', 1)[0]
    assert 'border-color: var(--desk-accent)' in active  # 选中：主题色描边 ✓
    assert 'color: var(--desk-accent)' in active


# ------------------------------------------------------- ③ 去掉「常用」组
def test_picker_has_no_common_section(tmp_path, monkeypatch):
    from minibt.desk import user_prefs as up
    from minibt.desk import indicator_catalog as cat

    monkeypatch.setattr(up, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(cat, 'CACHE_FILE', str(tmp_path / 'ind.json'))

    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk._strategy_sync = True

    groups = desk._picker_groups()
    sections = [section['key'] for group in groups
                for section in group.get('sections', [])]
    assert 'common' not in sections
    assert 'all' in sections

    items = desk.picker_items()
    counts: dict = {}
    for item in items:
        counts[item.get('section')] = counts.get(item.get('section'), 0) + 1
    assert counts.get('common', 0) == 0          # 常用 6 个不再出现 ✓
    # 「全部指标」在前端是「不过滤」的伪分组 → 这里查总量 ✓
    assert len(items) > 300                      # 全部指标仍来自 minibt 库 ✓
    # 前端默认停在「全部指标」（「常用」没了 ✓）
    page = (JSLIB / 'chart-page.ts').read_text(encoding='utf-8')
    assert "favorites.length ? 'favorites' : 'all'" in page


# ------------------------------------------------------- ④ 个人指标参数
def test_personal_indicator_params_reach_settings(tmp_path, monkeypatch):
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))
    made = pi.create_file('indicator', 'my_test')

    from minibt.desk.app import Desk

    np = pytest.importorskip('numpy')
    pd = pytest.importorskip('pandas')

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = 160
            close = 100 + np.sin(np.arange(rows) / 9) * 3
            return pd.DataFrame({
                'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close + 0.4, 'high': close + 2, 'low': close - 2,
                'close': close,
                'volume': np.abs(np.sin(np.arange(rows) / 5)) * 100,
                'symbol': 'SHFE.demo01', 'duration': 60,
            })

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.futures = Feed()
    desk.feeds = [desk.futures]
    desk.offline = False
    desk.tabs['SHFE.demo01'] = {'feed': desk.futures, 'cycle': 60,
                               'indicators': []}
    desk._on_editor_add_indicator({'path': made['path']})

    payload = desk.indicator_payload('SHFE.demo01')
    items = payload.get('items') or []
    assert items
    for item in items:
        assert item.get('params'), f'{item["key"]} 没有参数（⚙ 里会是空的 ✗）'
        assert item.get('source', '').startswith('pi:')
    # 类指标只带类上定义的参数（length），函数还带 color ✓
    top = {item['key'].split(':')[-1]: item['params'] for item in items}
    assert top.get('my_test', {}).get('length') == 20
    assert 'length' in str(top.get('my_test_indicator'))

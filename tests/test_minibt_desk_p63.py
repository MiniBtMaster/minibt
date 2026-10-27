"""P63：回放图标 / 加图策略优先 / 页签顺序 / 代码补全 ✓"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


# ------------------------------------------------------- ① 回放播放图标
def test_replay_play_button_uses_svg_icons():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    bar = page.split('private _ensureReplayBar(): void {', 1)[1].split(
        'private _speedText(', 1)[0]
    # 播放 / 暂停 / 前进一根都是 SVG（`⏸` / `↦` 在 QtWebEngine 里没字形 ✗）
    assert 'play.innerHTML = ICON_PLAY;' in bar
    assert 'step.innerHTML = ICON_STEP;' in bar
    assert "play.textContent = '▶'" not in bar
    assert "step.textContent = '↦'" not in bar
    # 和「退出回放（rewind）」同款按钮类 ✓
    assert 'desk-tool desk-tool-replay desk-replay-play' in bar
    # 状态同步也必须用 innerHTML（用 textContent 会把 SVG 换成文字 ✗）
    sync = page.split('private _syncReplayBar(', 1)[1].split('\n    }', 1)[0]
    assert 'this.replayPlayButton.innerHTML = state.playing' in sync
    assert 'this.replayPlayButton.textContent' not in sync
    icons = (DESK_TS / 'icons.ts').read_text(encoding='utf-8')
    assert 'export const ICON_PLAY' in icons
    assert 'export const ICON_PAUSE' in icons
    assert 'export const ICON_STEP' in icons


# ------------------------------------------------------- ② 加图：策略优先
def test_add_to_chart_prefers_strategy(tmp_path, monkeypatch):
    pd = pytest.importorskip('pandas')
    np = pytest.importorskip('numpy')
    from minibt.desk import personal as pi

    monkeypatch.setattr(pi, 'PERSONAL_ROOT', str(tmp_path / 'personal'))
    monkeypatch.setattr(pi, 'CONFIG_FILE', str(tmp_path / 'cfg.json'))

    class Feed:
        kind = 'futures'
        api = None

        def available(self):
            return True

        def klines(self, symbol, cycle, length=500):
            rows = 200
            close = 101 + np.sin(np.arange(rows) / 7) * 3
            return pd.DataFrame({
                'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                             for i in range(rows)],
                'open': close + 0.4, 'high': close + 2, 'low': close - 2,
                'close': close, 'volume': np.ones(rows) * 10,
                'symbol': 'SHFE.demo01', 'duration': 60,
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
    desk.tabs['SHFE.demo01'] = {'feed': desk.futures, 'cycle': 60,
                               'indicators': []}

    # 策略文件 → 只画策略的线（策略优先 ✓）
    strategy = pi.create_file('strategy', 'st_demo')
    desk._on_editor_add_indicator({'path': strategy['path']})
    payload = desk.indicator_payload('SHFE.demo01')
    keys = [item['key'] for item in payload.get('items') or []]
    assert keys and all(key.startswith('editor:') for key in keys)
    assert payload.get('strategy')
    assert desk.tabs['SHFE.demo01']['indicators'] == []   # 不能同时 ✓

    # P66：策略和指标**共存**（指标不限、策略最多 1 个 ✓）
    indicator = pi.create_file('indicator', 'ind_demo')
    desk._on_editor_add_indicator({'path': indicator['path']})
    payload = desk.indicator_payload('SHFE.demo01')
    keys = [item['key'] for item in payload.get('items') or []]
    assert any(key.startswith('editor:') for key in keys)      # 策略还在 ✓
    assert any(key.startswith('pi:') for key in keys)      # 指标也在 ✓
    assert payload.get('strategy')


def test_strategy_overlay_maps_specs_to_items():
    pytest.importorskip('pandas')
    from minibt.desk import strategy_overlay as so

    assert hasattr(so, 'run_overlay') and hasattr(so, 'classes_of')
    source = (ROOT / 'minibt' / 'desk' / 'strategy_overlay.py').read_text(
        encoding='utf-8')
    assert "kind': 'marker'" in source
    assert "'overlay': bool(getattr(spec, 'overlap', False))" in source
    # P65：引擎搬进 minibt 了（不再依赖 miniqt ✓）
    assert 'from miniqt' not in source


# ------------------------------------------------------- ③ 页签顺序
def test_dock_tab_order():
    dock = (DESK_TS / 'account-dock.ts').read_text(encoding='utf-8')
    block = dock.split("for (const [key, label] of [['account', '交易账户'],", 1)[1]
    block = block.split('as const) {', 1)[0]
    order = ['account'] + [line.strip().split("'")[1]
                           for line in block.splitlines()
                           if line.strip().startswith("['")]
    assert order == ['account', 'code', 'log']
    assert "'编辑器'" in block


# ------------------------------------------------------- ④ 代码补全
def test_editor_completion_words():
    bundle = (DESK_TS / 'editor-bundle.ts').read_text(encoding='utf-8')
    assert 'PY_KEYWORDS' in bundle and 'lambda' in bundle
    # 单词表是空格分隔的字符串（不是带引号的数组 ✓）
    assert 'NUMPY_API' in bundle and 'arange' in bundle
    assert 'PANDAS_API' in bundle and 'DataFrame' in bundle
    assert 'MINIBT_API' in bundle and 'BtIndicator' in bundle
    assert 'KLINE_FIELDS' in bundle
    # 按 `xxx.` 选不同的表 ✓
    assert "owner === 'np' || owner === 'numpy'" in bundle
    assert "owner === 'pd' || owner === 'pandas'" in bundle
    assert "owner === 'minibt' || owner === 'bt'" in bundle
    # 装到 CodeMirror（语言 data + autocompletion 扩展 ✓）
    assert 'pythonLanguage.data.of({ autocomplete: pythonCompletions })' in bundle
    assert 'autocompletion({' in bundle
    assert 'completionKeymap' in bundle
    # 打好的 bundle 里确实带了补全（懒加载包 ✓）
    built = (ROOT / 'pylightcharts' / 'js' / 'desk-editor.js').read_text(
        encoding='utf-8', errors='ignore')
    assert 'arange' in built and 'DataFrame' in built
    assert 'activateOnTyping' in built

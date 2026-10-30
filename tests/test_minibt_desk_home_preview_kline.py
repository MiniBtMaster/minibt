"""首页下方预览图：**K 线开关**必须按开关显示（默认 K 线）✓

用户 2026-10-30 反馈：左击首页中间报价列表的合约 → 下方图表「默认 K 线」，
但**大多时候显示的是迷你折线**。原因：
1. 首拍 `home_preview` 拿到的 bars 是空的（天勤 `get_kline_serial` 刚订阅时是
   占位表），而 `_requestBars()` 有「同一个 合约|周期 只请求一次」的节流 →
   永远不重试 ✗；
2. K 线模式下数据没到时直接 `sparkSvg(row.spark)` 顶替 → 看起来就是
   「K 线开着却显示迷你图」✗。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (JSLIB / name).read_text(encoding='utf-8')


def test_home_preview_pushes_pending_when_empty(tmp_path, monkeypatch):
    import pandas as pd
    import numpy as np
    from minibt.desk import app as appmod, local_data, user_prefs
    monkeypatch.setattr(user_prefs, 'PREFS_FILE', str(tmp_path / 'p.json'))
    monkeypatch.setattr(local_data, 'STATE_FILE', str(tmp_path / 'state.json'))
    monkeypatch.setattr(local_data, 'FOLDERS_FILE',
                        str(tmp_path / 'folders.json'))

    desk = appmod.Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    desk._booted = True
    desk.log_to_stdout = False
    desk.log_to_ui = False

    class Feed:
        kind = 'futures'
        api = None

        def __init__(self, frame):
            self.frame = frame

        def available(self):
            return True

        def quotes(self, keys):
            return []

        def spec(self, symbol):
            return None

        def klines(self, symbol, cycle, length=500):
            return self.frame

    def frame(rows=120):
        close = 100 + np.sin(np.arange(rows) / 9) * 3
        return pd.DataFrame({
            'datetime': [(1_700_000_000 + i * 60) * 10 ** 9
                         for i in range(rows)],
            'open': close, 'high': close + 1, 'low': close - 1, 'close': close,
            'volume': np.ones(rows), 'symbol': 'X', 'duration': 60,
        })

    def payloads():
        import json
        out = []
        for script in desk.sent:
            text = str(script)
            if text.startswith('window.__desk.applyPatch('):
                out.append(json.loads(text[len('window.__desk.applyPatch('):-2]))
        return [item for item in out if item.get('type') == 'home_preview']

    # ① 占位表（datetime = 0）→ bars 空 + pending=True
    placeholder = frame()
    placeholder['datetime'] = [0] * len(placeholder)
    desk.futures = Feed(placeholder)
    desk.feeds = [desk.futures]
    desk.sent.clear()
    desk._on_home_preview({'symbol': 'DCE.pp2609', 'cycle': 300})
    first = payloads()[-1]
    assert first['bars'] == [] and first['pending'] is True

    # ② 数据到了 → 有 bars + pending=False
    desk.futures.frame = frame()
    desk.sent.clear()
    desk._on_home_preview({'symbol': 'DCE.pp2609', 'cycle': 300})
    second = payloads()[-1]
    assert second['bars'] and second['pending'] is False
    assert len(second['bars']) <= 200


def test_frontend_kline_mode_never_falls_back_to_spark():
    page = _read('home-page.ts')
    block = page.split('private _previewChart(', 1)[1].split(
        'private renderQuickStats', 1)[0]
    kline_block = block.split('if (this.klineOn) {', 1)[1].split(
        '// ★ 非 K 线', 1)[0]
    # K 线模式：没有 bars 时**不再** sparkSvg 顶替，而是占位 + 重试 ✓
    assert 'sparkSvg' not in kline_block
    assert 'K 线加载中' in kline_block
    assert '_schedulePreviewRetry()' in kline_block
    assert 'candleSvg(bars, 600, 130)' in kline_block


def test_frontend_home_preview_retries_empty_bars():
    page = _read('home-page.ts')
    assert 'private previewRetryLeft = 0;' in page
    assert 'private _schedulePreviewRetry(): void {' in page
    # 空数据到达 → 安排重试；有数据 → 清零 ✓
    tail = page.split('setPreviewBars(payload', 1)[1][:900]
    assert '_schedulePreviewRetry()' in tail
    assert 'this.previewRetryLeft = 0;' in tail
    # 打开 K 线开关 / 点合约 / 切周期都要强制重发一次 ✓
    assert 'this._requestBars(undefined, true);' in page
    assert 'this._requestBars(row, true);' in page
    assert 'force = false' in page
    # 占位样式
    css = (JSLIB / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-home-preview-wait {' in css

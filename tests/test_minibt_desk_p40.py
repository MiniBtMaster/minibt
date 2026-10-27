"""P40：工具栏重排 / 移除播放条导出历史 / 回放（miniqt 同款）✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def _page():
    return (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')


# ------------------------------------------------------- ① 工具栏重排
def test_layout_and_tools_sit_left_of_trade():
    page = _page()
    tail = page.split('const deleteIndicator = this._toolButton(', 1)[1]
    tail = tail.split('toolbar.append(', 1)[1].split(');', 1)[0]
    assert tail.index('layoutButton') < tail.index('tradeButton')
    # P50：画线移到「持仓线」左边（用户要求）✓
    assert tail.index('lineButton') < tail.index('ticketButton')
    assert tail.index('ticketButton') < tail.index('layoutButton')
    assert tail.index('layoutButton') < tail.index('tradeButton')


# ------------------------------------------------------- ② 移除报价页专属按钮
def test_ticker_and_export_removed_from_chart():
    page = _page()
    assert "const tickerButton = this._toolButton(" not in page
    assert "'播放条'" not in page
    assert "this._toolButton(\n            '导出历史'" not in page
    # 报价页仍然有这两个入口 ✓
    quote = (DESK_TS / 'quote-page.ts').read_text(encoding='utf-8')
    assert '播放条' in quote or 'ticker' in quote.lower()
    assert 'openExportHistory' in quote


# ------------------------------------------------------- ③ 回放（miniqt 同款）
def test_replay_button_is_toggle():
    page = _page()
    assert 'toggleReplay()' in page
    assert 'REWIND_SVG' in page                       # miniqt 的 rewind 图标 ✓
    assert 'this._syncReplayButton();' in page
    assert "classList.toggle('on', this.replaying)" in page


def test_replay_bar_matches_miniqt():
    page = _page()
    body = page.split('private _ensureReplayBar(', 1)[1]
    body = body.split('private _speedText(', 1)[0]
    for key in ('选择K线', '选择合约', '选择时间段', '回放速度', '更换周期',
                '跳转到实时图表', '前进一根', 'REPLAY_SEEKS', 'REPLAY_SPEEDS',
                'REPLAY_CYCLES'):
        assert key in body, key
    # 顺序：选择K线 → 播放 → 前进 → 速度 → 周期 → 退出 ✓
    assert body.index('select') < body.index('replayPlayButton')
    assert 'bar.append(select, play, step, speed, cycle, this.replayLabel, exit)' \
        in body


def test_replay_engine_supports_seek():
    engine = (DESK_TS / 'replay.ts').read_text(encoding='utf-8')
    assert 'export const REPLAY_SEEKS' in engine
    assert 'seek(fraction: number)' in engine
    assert 'load(bars: ReplayBar[], speed = 5, seek = 0.1)' in engine
    # 速度档位和 miniqt 一致 ✓
    for label in ("['0.5x'", "['1x'", "['2x'", "['4x'"):
        assert label in engine, label


def test_replay_seek_passed_to_backend():
    page = _page()
    assert "this.options.onCommand?.('replay', {" in page
    assert 'seek: this.replaySeek,' in page
    app = _read('minibt/desk/app.py')
    assert "seek = float(payload.get('seek') or 0.1)" in app
    assert "'seek': seek," in app


def test_exit_replay_restores_live():
    """退出回放后不能又被引擎的空回调翻回「回放中」✗"""
    page = _page()
    assert 'this.replaying = !!this.replay?.active;' in page
    assert 'this.replay?.stop();' in page

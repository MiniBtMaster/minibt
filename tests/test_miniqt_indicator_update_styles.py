"""miniqt 图表指标**实时更新**的样式修复（源码约束）。

历史问题：
* 副图 vbar（macd）实时刷新只发 ``{time, value}``（不带 ``color``）→ 每根都
  退回指标线单色 ✗；
* 信号图标只在 ``not tail`` 时重画 → 形成中的那根翻信号后图标不出现（晚一根
  甚至丢单根脉冲）✗；
* 色带隐藏边 / 蜡烛在 tail 时完全不刷新 ✗。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
WINDOW = REPO / 'miniqt' / 'app' / 'windows' / 'pylightcharts_window.py'


def _source() -> str:
    return WINDOW.read_text(encoding='utf-8')


def test_vbar_colors_reapplied_on_update():
    """vbar 柱体在实时刷新时也要带上涨/跌色列 ✓。"""
    source = _source()
    # 初始化时记住基准 / 涨跌色
    assert '_miniqt_vbar' in source
    # 更新/整表重发都按这份重算 color 列
    assert 'def update_point(' in source
    assert 'def set_frame(' in source
    assert "point['color']" in source
    assert "frame['color']" in source
    # 更新走的是带 color 的 helper（不再裸 series.update）
    assert 'update_point(series, line_name, last' in source
    assert 'set_frame(series, line_name, values, times)' in source


def test_signals_refresh_on_tail():
    """tail 增量刷新也要刷新信号，并合并历史（不冲掉老图标）✓。"""
    source = _source()
    assert 'force=full, tail=tail' in source
    assert "def _draw_indicator_signals(self, target, plot, times, source, entry,\n                                force: bool = False, tail: bool = False)" in source
    assert 'def _refresh_indicator_overlays(self, indicator, plot, times,\n                                    source=None, force: bool = False,\n                                    tail: bool = False)' in source
    # 合并已有信号行（按 raw time 去重）
    assert "entry.setdefault('signal_rows', {})" in source
    assert "old_df['time'].isin(data['time'])" in source
    # tail 没信号时不清空历史
    assert 'if series is not None and not tail:' in source


def test_bands_and_candles_have_tail_path():
    """色带隐藏边 / 蜡烛型指标也有 tail（只更新最后一根）路径 ✓。"""
    source = _source()
    assert 'def _refresh_indicator_bands(self, plot, times, entry, tail: bool = False)' in source
    assert 'def _refresh_indicator_candles(self, plot, times, entry,\n                                   tail: bool = False)' in source
    assert 'self._refresh_indicator_bands(plot, times, entry, tail=tail)' in source
    assert 'self._refresh_indicator_candles(plot, times, entry, tail=tail)' in source
    # tail 时只 update 最后一根
    assert "series.update(pd.Series(\n                            {'time': times[-1], name: float(last)}))" in source


def test_signal_overlay_skips_unchanged_on_tail():
    """tail 每拍跑信号叠加层 —— 信号没变时**不重画**（否则全量 setData+shapes 拖死图）✓"""
    source = _source()
    assert "entry.setdefault('signal_sig', {})" in source
    assert 'if tail and signatures.get(name) == signature:' in source


def test_recompute_keeps_vbar_color_column():
    """★ 回归：``replay_indicator_params`` → ``_recompute_indicator`` 只发
    ``{time, value}`` 会把 vbar 的**逐根涨/跌色**整段丢掉 ✗（RSI 柱体改个
    ``length`` 就变单色）。重算必须和创建/实时刷新一样带上 ``color`` 列 ✓。
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / 'miniqt' / 'app' /
           'windows' / 'pylightcharts_window.py').read_text(encoding='utf-8')
    start = src.index('def _recompute_indicator')
    end = src.index('def _frame_generation', start)
    body = src[start:end]
    assert '_miniqt_vbar' in body, '重算时没带 vbar 涨/跌色 ✗'
    assert "frame['color']" in body
    assert 'vbar[\'base\']' in body

"""策略回测 / 参数优化（P118+）的回归测试。"""
from __future__ import annotations

import time
from pathlib import Path

from minibt.desk.strategy_lab import StrategyLab

ROOT = Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


class _Desk:
    def __init__(self):
        self.patches = []

    def push(self, patch):
        self.patches.append(patch)


def _wait(lab, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if lab.status not in ('idle', 'running'):
            # status=ready 时 _push_selected 还在后面继续推 chart/trades；
            # 多等一拍，避免测试在补丁到达前就取 next() ✓
            if lab.status == 'ready':
                time.sleep(0.2)
            return
        time.sleep(0.2)
    raise AssertionError(f'backtest did not finish: {lab.status} {lab.error}')


def test_backtest_emits_chart_result_and_trades():
    desk = _Desk()
    lab = StrategyLab(desk, 'test-cmo')
    lab.start({'file': str(ROOT / 'tutorials/strategies/cmo.py'),
               'mode': 'backtest'})
    _wait(lab)

    assert lab.status == 'ready', lab.error
    result = next(p for p in desk.patches if p['type'] == 'strategy_result')
    assert result['metrics']['trades'] == 481
    assert result['metrics']['profit'] == -1345.0
    assert result['equity']['values']
    assert result['contracts'][0]['symbol'] == 'DCE.v2601'
    chart = next(p for p in desk.patches if p['type'] == 'strategy_chart')
    assert 8000 <= len(chart['bars']) <= 10000
    assert chart['indicators']
    assert chart['markers']
    assert chart['links']
    assert result['trade_style']['show'] is True
    trades = next(p for p in desk.patches if p['type'] == 'strategy_trades')
    assert trades['rows']
    assert {'direction', 'price', 'qty', 'pnl'} <= set(trades['rows'][0])


def test_frontend_strategy_lab_and_editor_entries():
    app = _read(JSLIB / 'app.ts')
    page = _read(JSLIB / 'strategy-lab-page.ts')
    editor = _read(JSLIB / 'editor-panel.ts')
    local = _read(JSLIB / 'local-chart-page.ts')

    assert "kind: 'home' | 'quote' | 'chart' | 'local' | 'strategy'" in app
    assert 'openStrategyLab' in app
    assert "this.send('strategy_start'" in app
    assert 'strategy_chart' in app and 'strategy_result' in app
    assert "['result', '回测结果']" in page
    assert "['record', '指标/记录']" in page
    assert 'contractTabs' in page
    assert 'desk-strategy-iframe' in page
    assert '_chartUrl' in page and 'strategy_chart' in page
    assert 'strategy_chart_file' in page and 'setChartFile' in page
    assert 'fileMode' in page
    # srcdoc 优先级高于 src：拿到真实文件 URL 后必须清掉，否则一直停在加载页
    assert "removeAttribute('srcdoc')" in page
    chart_page = _read(JSLIB / 'chart-page.ts')
    assert 'resetForSymbol' in chart_page and '_clearAlertLines' in chart_page
    assert 'resetForSymbol()' in app
    miniqt = _read(ROOT / 'minibt' / 'desk' /
                   'miniqt_backtest_chart.py')
    assert 'HeadlessChart' in miniqt
    assert 'BacktestPage' in miniqt and 'draw_trade_lines' in miniqt
    assert '参数优化结果' in page
    assert 'strategy_trial_run' in page
    assert '策略回测' in editor and '参数优化' in editor
    assert 'onStrategy' in local


def test_writeback_params_goes_to_editor_buffer():
    editor = _read(JSLIB / 'editor-panel.ts')
    assert 'applyParams(path: string' in editor
    assert 'tab.editor.setValue(text)' in editor
    assert '未保存' in editor


def test_multi_contract_uses_one_account_and_two_klines(tmp_path):
    source = tmp_path / 'multi.py'
    source.write_text(
        'from minibt import *\n\n'
        'class Multi(Strategy):\n'
        '    def __init__(self):\n'
        '        self.a = self.get_kline(LocalDatas.pp2609_60, height=500)\n'
        '        self.b = self.get_kline(LocalDatas.l2609_60, height=500)\n'
        '        self.i = 0\n'
        '    def next(self):\n'
        '        self.i += 1\n'
        '        if self.i == 20:\n'
        '            self.a.buy()\n'
        '        elif self.i == 40:\n'
        '            self.a.sell()\n',
        encoding='utf-8')
    desk = _Desk()
    lab = StrategyLab(desk, 'test-multi')
    lab.start({'file': str(source), 'mode': 'backtest'})
    _wait(lab)
    assert lab.status == 'ready', lab.error
    result = next(p for p in desk.patches if p['type'] == 'strategy_result')
    symbols = {item['symbol'] for item in result['contracts']}
    assert len(symbols) == 2, symbols
    assert len(result['contracts']) == 2


def test_multi_strategy_each_has_own_result(tmp_path):
    source = tmp_path / 'multi_strategy.py'
    body = 'from minibt import *\n\n'
    for name, data in (('A', 'pp2609_60'), ('B', 'l2609_60')):
        body += (
            f'class {name}(Strategy):\n'
            '    def __init__(self):\n'
            f'        self.d = self.get_kline(LocalDatas.{data}, height=500)\n'
            '        self.i = 0\n'
            '    def next(self):\n'
            '        self.i += 1\n'
            '        if self.i == 20:\n'
            '            self.d.buy()\n'
            '        elif self.i == 40:\n'
            '            self.d.sell()\n\n')
    source.write_text(body, encoding='utf-8')
    desk = _Desk()
    lab = StrategyLab(desk, 'test-multi-strategy')
    lab.start({'file': str(source), 'mode': 'backtest'})
    _wait(lab)
    assert lab.status == 'ready', lab.error
    state = [p for p in desk.patches if p['type'] == 'strategy_state'][-1]
    assert {item['name'] for item in state['strategies']} == {'A', 'B'}
    assert len(lab.strategies) == 2


# --------------------------------------------------------------- P119
def test_strategy_lab_chart_tools_frontend():
    """回测页签行右侧的图表设置：回放 / 图表类型 / 画线工具 / 删除画线工具 ✓"""
    page = _read(JSLIB / 'strategy-lab-page.ts')
    assert 'desk-strategy-charttools' in page
    for label in ('回放', '画线工具', '删除画线工具'):
        assert label in page
    assert "const CHART_KINDS" in page and "'bar'" in page
    assert 'const REPLAY_SPEEDS = [1, 2, 5, 10]' in page
    # 命令都是 postMessage 发给 iframe 里的驱动 ✓
    for cmd in ('replayStart', 'replayStep', 'replayExit', 'type', 'toolbox',
                'clearDrawings'):
        assert f"'{cmd}'" in page or f'`{cmd}`' in page, cmd
    # 回放时钟由**父页面**统一驱动 → 两个图表永远同一根、一起播一起停 ✓
    assert 'private replayTimer' in page
    assert 'private _startReplayClock(): void {' in page
    assert 'private _stopReplayClock(): void {' in page
    assert "this._postFrames('replayStep', {});" in page
    assert 'Math.round(400 / Math.max(1,' in page
    # 切页签 / iframe 重载后继续（不再变暂停 ✗）
    assert 'private _resyncFrame(' in page
    assert "this._resyncFrame(key === 'result' ? this.resultFrame" in page
    # 画线工具：先更新本地状态再发，才能二次点击隐藏 / 按钮立即高亮 ✓
    assert 'this.toolState.toolbox = !this.toolState.toolbox' in page
    assert "if (typeof data.toolbox === 'boolean')" in page
    # 图表设置同步鼠标标签颜色（iframe 里的 MiniQT 图也要跟设置 ✓）
    assert "this._postFrames('crosshair'" in page
    assert 'window.addEventListener(\'message\', this.onFrameMessage)' in page
    assert 'window.removeEventListener(\'message\', this.onFrameMessage)' in page
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    for name in ('.desk-strategy-charttools', '.desk-sl-btn', '.desk-sl-speed',
                 '.desk-sl-progress'):
        assert name in css, name


def test_strategy_chart_driver_injected():
    """图表 HTML 里注入驱动：回放 / 图表类型 / 画线工具 + toolbox 可用 ✓"""
    from minibt.desk import miniqt_backtest_chart as chart_mod
    html = '<html><head></head><body><div id="container"></div></body></html>'
    out = chart_mod._inject_driver(chart_mod._inject_separator_css(html))
    assert 'desk-sl-style' in out and 'desk-sl-driver' in out
    assert '__deskSL' in out
    for cmd in ('replayStart', 'replayPlay', 'replayStep', 'replayExit',
                'setType', 'clearDrawings', 'desk-sl-toolbox',
                'applyCrosshair'):
        assert cmd in out, cmd
    # 重复注入不会叠两份 ✓
    assert out.count('desk-sl-driver') == chart_mod._inject_driver(out).count(
        'desk-sl-driver')
    # 两个 builder 都开了 toolbox 并注入驱动
    src = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert src.count('toolbox=True') >= 2
    assert src.count('_inject_driver(') >= 3      # 定义 1 + 两处调用 ✓


def test_strategy_chart_driver_behaviour(tmp_path):
    """用 Node + 假 LWC 跑驱动：回放截断 / 类型切换 / 画线工具 / 删除画线 ✓"""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        import pytest
        pytest.skip('没有 node，跳过驱动行为测试')
    from minibt.desk import miniqt_backtest_chart as chart_mod
    driver = tmp_path / 'driver.js'
    driver.write_text(chart_mod.DESK_DRIVER_JS, encoding='utf-8')
    helper = ROOT / 'tests' / 'helpers' / 'strategy_driver_test.js'
    result = subprocess.run(
        [node, str(helper), str(driver)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'all checks passed' in result.stdout


# --------------------------------------------------------------- P120
def test_contract_chart_uses_custom_series_signals():
    """合约图的交易信号改用 `apply_signals`（custom series）✓

    以前用 `chart.marker_list`（LWC 原生 marker primitive）：
    标记不计入自动缩放、回放时**截不掉** → 未来信号全堆在最后一根 K 线上 ✗
    """
    src = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert 'apply_signals' in src
    assert 'extract_minibt_signal_texts' in src
    # 只剩注释里提到过；代码里不再调用原生 marker ✓
    assert src.count('chart.marker_list(') == 1
    assert 'def _tail_values(values, count: int):' in src
    # 信号值要和当前图最后一屏对齐（全量 → 尾部 n 个）
    assert '_tail_values(values, total)' in src


def test_backtest_chart_does_not_import_qt_chart():
    """策略回测只画 HTML，不应在导入阶段拉 pylightcharts.Chart（Qt）✓"""
    src = _read(ROOT / 'minibt' / 'strategy' / 'strategy_window.py')
    assert '\nfrom pylightcharts import Chart\n' not in src   # 不在模块顶层
    assert '            from pylightcharts import Chart' in src  # 创建原生窗口时
    block = src.split('from pylightcharts import Chart', 1)[1]
    assert 'self.chart = Chart(' in block


def test_theme_accent_and_crosshair_persist_to_body():
    """主题色 / 鼠标标签色重启后生效：body 变量也要写（浅色主题变量在 body）✓"""
    app = _read(JSLIB / 'app.ts')
    accent = app.split('private _applyAccent', 1)[1].split(
        'openChart(', 1)[0]
    assert 'document.documentElement, document.body' in accent
    assert "setProperty('--desk-active'" in accent
    assert 'this._applyAccent(this.accent)' in app
    # 策略页把标签色传给 iframe，并在 setChartConfig 里实时同步 ✓
    lab = _read(JSLIB / 'strategy-lab-page.ts')
    assert 'crosshairColor' in lab
    assert "'chart_color_crosshair'" in lab
    assert "_postFrames('crosshair'" in lab


def test_pane_separator_2px_theme_colors():
    """主图 / 副图之间的分隔线：高度 2px，深色浅色都有可见底色 ✓"""
    from minibt.desk import miniqt_backtest_chart as chart_mod
    dark = chart_mod._inject_separator_css('<html><head></head><body></body></html>',
                                            True)
    light = chart_mod._inject_separator_css('<html><head></head><body></body></html>',
                                             False)
    assert 'height: 2px !important' in dark
    assert 'height: 2px !important' in light
    assert 'rgba(148, 163, 184, .45)' in dark
    assert 'rgba(100, 116, 139, .32)' in light
    assert 'height: 0 !important' not in dark


def test_replay_keeps_visible_width():
    """回放：只**平移**，缩放级别和「最新 K 线到右边界的距离」都保持 ✓"""
    from minibt.desk import miniqt_backtest_chart as chart_mod
    js = chart_mod.DESK_DRIVER_JS
    assert 'function measureWindow' in js
    assert 'function currentRange' in js
    assert 'function shiftForBars' in js
    # 只加 delta 平移（不再把右边界钉死在最新一根 ✗）
    assert 'from: range.from + delta, to: range.to + delta' in js
    # 用户拖到历史里（最新一根不在视窗）就不动 ✓
    assert 'if (range.to < newest - 0.5) return;' in js
    # 每拍只切一刀（二分 + 未变化跳过），回测结果图十几条序列也不卡 ✓
    assert 'function cutIndex' in js
    assert 'if (cut === entry.cut) continue;' in js


# --------------------------------------------------------------- P122
def test_pareto_chart_axes_and_grid():
    """帕累托图：自适应宽度 + 坐标轴标签 / 刻度 + 网格虚线 ✓"""
    page = _read(JSLIB / 'strategy-lab-page.ts')
    assert 'private _paretoSvg(' in page
    # 数据驱动的范围（不再 `Math.min(..., 0)` 把 0 硬塞进来 ✗）
    assert 'const [xMin, xMax] = span(xs);' in page
    assert 'Math.min(...values)' in page and '* 0.12' in page
    # 自适应宽度
    assert 'const width = Math.max(420, Math.min(1600, hostWidth - 60));' in page
    # 刻度 / 轴标签 / 网格虚线
    assert 'desk-opt-tick' in page and 'desk-opt-label' in page
    assert 'stroke-dasharray="4 4"' in page
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-opt-tick {' in css
    assert '.desk-opt-label {' in css
    assert '.desk-strategy-opt-svg { width: 100%; height: auto; display: block; }' in css


def test_legend_light_theme_dot_collapse_and_font():
    """图例：浅色主题用深色、色块→圆点、∧/∨ 折叠按钮、字号跟设置 ✓"""
    from minibt.desk import miniqt_backtest_chart as chart_mod
    css = chart_mod.DESK_DRIVER_CSS
    assert 'var(--desk-sl-font, 13px)' in css
    assert 'body.desk-sl-light #container .legend' in css
    assert '#131722 !important' in css
    assert 'border-radius: 50% !important' in css
    assert 'legend-collapse' in css
    js = chart_mod.DESK_DRIVER_JS
    assert 'function enableCollapse' in js and 'enableCollapse()' in js
    assert "case 'font': applyFont(payload.size); break;" in js
    src = (ROOT / 'minibt' / 'desk' / 'miniqt_backtest_chart.py').read_text(
        encoding='utf-8')
    assert 'chart.enable_legend_collapse()' in src
    assert 'desk-sl-light' in src          # 浅色主题给 body 加类 ✓


def test_legend_font_from_settings():
    """设置 → 图表配置 → 图表字体大小 → 两个回测图表都跟着变 ✓"""
    page = _read(JSLIB / 'strategy-lab-page.ts')
    app = (ROOT / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(encoding='utf-8')
    assert 'fontSize?: number;' in page
    assert 'setChartConfig(values: Record<string, unknown>): void {' in page
    assert "this._postFrames('font', { size });" in page
    assert "fontSize: Number(this.settingsValues.chart_font_size) || 13," in app
    assert 'for (const page of this.strategyPages.values()) {' in app


def test_zoom_out_limit_padding():
    """缩放上限：两端各补 100 根空白 + 放开 minBarSpacing ✓"""
    from minibt.desk import miniqt_backtest_chart as chart_mod
    js = chart_mod.DESK_DRIVER_JS
    assert 'var PAD_BARS = 100;' in js
    assert 'function buildPad(' in js
    assert 'function withPad(' in js
    assert 'minBarSpacing: 0.02' in js
    assert 'rightOffset: 100' in js
    assert 'var lastIdx = state.padLen + (target - 1) + 1;' in js


# --------------------------------------------------------------- P123
def test_equity_chart_font_matches_title():
    """权益/回撤图里的文字（2 个 Y 轴刻度 + 左右图例）字号字体跟标题一致 ✓"""
    page = _read(JSLIB / 'strategy-lab-page.ts')
    assert 'class="desk-eq-tick"' in page
    assert 'class="desk-eq-label"' in page
    assert 'font-size="10"' not in page       # 不再写死 10px ✗
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    title = css.split('.desk-strategy-equity-title {', 1)[1].split('}', 1)[0]
    assert 'font-size: 11px' in title
    block = css.split('.desk-strategy-equity text {', 1)[1].split('}', 1)[0]
    assert 'font-size: 11px' in block and 'font-family: inherit' in block


def test_new_tab_button_borderless():
    """顶栏「＋ ▾」不要边框（深 / 浅主题都不画）✓"""
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    block = css.split('.desk-tab-new {', 1)[1].split('}', 1)[0]
    assert 'border-color: transparent' in block
    assert 'rgba(41, 98, 255, .30)' not in block
    light = css.split('body.theme-light .desk-tab-new {', 1)[1].split('}', 1)[0]
    assert 'border-color: transparent' in light


def test_pane_separator_2px_in_desk_charts():
    """看盘窗口 / 本地图表的分隔线：2px + 深浅主题都合适的底色 ✓"""
    theme = (ROOT / 'jslib' / 'src' / 'desk' / 'theme.ts').read_text(
        encoding='utf-8')
    block = theme.split('panes: {', 1)[1].split('},', 1)[0]
    assert 'separatorColor' in block
    assert "'rgba(100,116,139,0.32)'" in block     # 浅色
    assert "'rgba(148,163,184,0.45)'" in block     # 深色
    assert "'rgba(0,0,0,0)'" not in block          # 不再是全透明 ✗
    styles = (ROOT / 'jslib' / 'src' / 'general' / 'styles.css').read_text(
        encoding='utf-8')
    assert '.tv-lightweight-charts tr > td[colspan="3"]' in styles
    assert 'height: 2px !important' in styles


def test_editor_personal_root_menu():
    """编辑器「系统目录 ▾」第一项 = 系统指标和策略（personal）✓"""
    editor = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    block = editor.split("this._button('系统目录 ▾'", 1)[1].split(']);', 1)[0]
    first = block.split('{ label:', 1)[1].split(',', 1)[0]
    assert '系统指标和策略（personal）' in first
    assert "kind: 'all'" in block
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    block2 = backend.split('def _on_explorer_system_dir', 1)[1].split(
        'def _on_explorer_set_root', 1)[0]
    assert "'indicator', 'strategy', 'all'" in block2
    assert '_pi.PERSONAL_ROOT' in block2


# --------------------------------------------------------------- P124
def test_strategy_check_gate():
    """回测 / 优化前体检：语法 → Strategy → op_config；不通过只弹顶部提示 ✓"""
    from minibt.desk import personal
    import tempfile
    import os

    assert personal.check_strategy_file('tutorials/strategies/cmo.py')['ok']
    missing = personal.check_strategy_file('nope.py')
    assert not missing['ok'] and '不存在' in missing['reason']

    folder = tempfile.mkdtemp()
    bad = os.path.join(folder, 'bad.py')
    open(bad, 'w', encoding='utf-8').write('class A(Strategy)\n    pass\n')
    result = personal.check_strategy_file(bad)
    assert not result['ok'] and '语法错误' in result['reason']

    indicator = os.path.join(folder, 'ind.py')
    open(indicator, 'w', encoding='utf-8').write(
        'from minibt import BtIndicator\n\nclass I(BtIndicator):\n'
        '    lines = ("a",)\n')
    result = personal.check_strategy_file(indicator)
    assert not result['ok'] and 'Strategy' in result['reason']

    opt = os.path.join(folder, 'opt.py')
    open(opt, 'w', encoding='utf-8').write(
        'from minibt import Strategy\n\nclass X(Strategy):\n'
        '    op_config = dict(a=(1, 10, 1))\n')
    result = personal.check_strategy_file(opt)
    assert result['ok'] and result['has_op_config']
    assert result['strategies'] == ['X']

    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert "'strategy_check': self._on_strategy_check" in backend
    block = backend.split('def _on_strategy_check', 1)[1].split(
        'def _on_editor_help', 1)[0]
    assert "mode == 'optimize' and not result.get('has_op_config')" in block
    editor = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert 'this.options.onCommand(\'strategy_check\',' in editor
    assert 'private _toastTop(' in editor
    assert "this.options.onToast?.(level, text, [], undefined, 'top');" in editor


def test_editor_help_button_and_copy_path():
    """编辑器「帮助」在**最右边**（MiniQT 那份内容）+ 右键「复制地址」✓"""
    editor = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    assert "this._button('帮助', () => {" in editor
    assert "'editor_help'" in editor
    assert 'shotButton, this.tabs,\n                       helpButton);' in editor
    assert "label: '复制地址', run: () => this._copyPath(item.path)," in editor
    # 「复制地址」改走后端系统剪贴板（P139）✓
    assert "this.options.onCommand('clipboard_set', { text });" in editor
    backend = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    # 「帮助」内容在 P128 换成了「指标 / 策略 / 回测 / 参数优化」说明 ✓
    block = backend.split('EDITOR_HELP = , 1)[1].split(', 1)[0]
    assert '【指标】' in block and '【策略】' in block
    assert '【策略回测 / 参数优化】' in block
    css = (ROOT / 'jslib' / 'src' / 'desk' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-toast.top {' in css
    assert '.desk-editor-toolbar .desk-editor-help { margin-left: auto; }' in css


def test_indicator_table_draggable():
    """`TableStyle.draggable=True` → 指标表格真的能拖动 ✓"""
    js = (ROOT / 'jslib' / 'src' / 'desk' / 'indicator.ts').read_text(
        encoding='utf-8')
    assert 'private readonly tableOffsets = new Map<string, { x: number; y: number }>();' in js
    assert 'private _makeTableDraggable(' in js
    assert "node.style.cursor = 'move';" in js
    assert 'this._makeTableDraggable(node, item.key);' in js
    assert 'const moved = this.tableOffsets.get(item.key);' in js


def test_switch_symbol_drops_old_contract_state():
    app = _read(ROOT / 'minibt' / 'desk' / 'app.py')
    switch = app.split('def _on_switch_symbol', 1)[1].split(
        'def _on_alerts', 1)[0]
    assert "info.pop('strategy_items', None)" in switch
    assert "info.pop('strategy_runner', None)" in switch
    assert "info['indicators'] = []" in switch
    assert "info.pop('layout', None)" in switch
    assert "'_add_strategy_to_chart(new, old_path'" not in switch
    assert 'self.replay_symbols.discard(old)' in switch
    # 指标补丁始终带 strategy（空串才能清掉旧图例）
    assert "payload['strategy'] = strategy_name" in app
    app_ts = _read(JSLIB / 'app.ts')
    assert 'currentSymbol()' in app_ts
    assert '_chartPageFor' in app_ts
    assert "symbol: () => this.options.symbol" in _read(
        JSLIB / 'chart-page.ts')
    assert "requested = str((payload or {}).get('symbol') or '')" in app


def test_realtime_live_is_default_when_tq_connected():
    app = _read(ROOT / 'minibt' / 'desk' / 'app.py')
    runner = _read(ROOT / 'minibt' / 'desk' / 'strategy_runner.py')
    overlay = _read(ROOT / 'minibt' / 'desk' / 'strategy_overlay.py')
    context = app.split('def _strategy_live_context', 1)[1].split(
        'def _add_strategy_to_chart', 1)[0]
    # 实时图表 + 天勤已连接就 live，不再要求策略写 live=True
    assert 'self.trading' in context and 'self.futures' in context
    assert "getattr(cls, 'live'" not in context
    assert 'Base._is_live_trading' in overlay
    assert 'kline._is_live_trading = True' in runner
    assert 'live: bool = False' in runner
    assert 'live=live, api=api' in overlay


def test_editor_live_buttons_and_four_space_indent():
    editor = _read(JSLIB / 'editor-panel.ts')
    bundle = _read(JSLIB / 'editor-bundle.ts')
    # 本地图表隐藏两个按钮；实时图表两个都显示
    assert "this.options.allowLive !== false" in editor
    assert "this.stopLiveButton.style.display = allowLive ? '' : 'none'" in editor
    assert "this.liveButton.style.display = allowLive ? '' : 'none'" in editor
    # Python 习惯：Enter / Tab 缩进 4 空格
    assert "indentUnit.of('    ')" in bundle
    assert 'EditorState.tabSize.of(4)' in bundle
    # 搜索 / 替换面板在编辑器顶部（工具栏下面），不在底部 ✓
    assert 'search({ top: true })' in bundle
    # Ctrl+S 保存后保持滚动 / 光标位置（后端回推同一文本不 setValue）✓
    assert 'scrollDOM.scrollTop' in bundle
    panel = _read(JSLIB / 'editor-panel.ts')
    assert 'if (tab.text !== text)' in panel
    assert 'tab.saved = text' in panel


def test_editor_alt_click_and_alt_shift_click_multicursor():
    bundle = _read(JSLIB / 'editor-bundle.ts')
    # CodeMirror 默认不允许一个 state 里存多个 selection range
    assert 'EditorState.allowMultipleSelections.of(true)' in bundle
    # Alt+单击加光标（矩形选择扩展仍保留，Alt+拖拽可框选）
    assert 'EditorView.clickAddsSelectionRange.of' in bundle
    assert 'event.altKey && event.button === 0' in bundle
    # Alt+Shift+左击：按点击列从主光标行到点击行逐行加光标
    assert 'event.altKey && event.shiftKey' in bundle
    assert 'selection.addRange(' in bundle
    assert 'EditorSelection.cursor(at)' in bundle
    assert 'scrollIntoView: true' in bundle


def test_next_on_new_bar_false_runs_on_each_tick():
    runner = _read(ROOT / 'minibt' / 'desk' / 'strategy_runner.py')
    app = _read(ROOT / 'minibt' / 'desk' / 'app.py')
    assert 'def next_on_new_bar(self) -> bool:' in runner
    # 指标 / 策略 __init__ 共用统一频率（不再用 _strat_stamp 卡住）
    update = app.split('def _update_strategy_items', 1)[1].split(
        'def _refresh_indicators', 1)[0]
    assert '_chart_update_interval_ms()' in update
    assert "_strat_stamp" not in update
    # 逻辑与初始化分开：runner 里有 on_close / 频率模式分支 ✓
    assert "cfg.get('on_close'" in runner
    assert "cfg.get('next_on_new_bar', True)" in runner


def test_account_switch_routes_chart_and_strategy_live():
    app = _read(ROOT / 'minibt' / 'desk' / 'app.py')
    live = _read(ROOT / 'minibt' / 'desk' / 'strategy_live.py')
    runner = _read(ROOT / 'minibt' / 'desk' / 'live_runner.py')
    # 实盘登录同时挂模拟 + 实盘，账户页可切换
    assert 'TqMultiAccount(accounts)' in app
    assert 'self._preferred_account_index' in app
    assert '_restart_chart_strategies_for_account' in app
    # 图表策略使用 AccountView 当前账户
    assert 'account = self.account_view().current()' in app
    assert 'live=live, api=api, account=account' in app
    # 策略实盘子进程带账户下标 / 实盘凭据
    assert 'MINIBT_TQ_ACCOUNT_INDEX' in live
    assert "add_argument('--account-index'" in runner
    assert 'bt.addstrategy(file, account=selected)' in runner


def test_single_objective_opt_csv_normalized(tmp_path):
    """单目标 Optuna CSV 的 `value` → 前端统一用 `values_0` ✓"""
    desk = _Desk()
    lab = StrategyLab(desk, 'opt-single')
    lab._opt_key = 'opt_Demo_sharpe'
    path = tmp_path / 'opt_Demo_sharpe.csv'
    path.write_text(
        'number,value,params_window\n'
        '0,0.75,60\n'
        '1,0.85,90\n', encoding='utf-8')
    class _Bt:
        _Bt__op_path = str(tmp_path)
    lab._collect_optimization(_Bt())
    assert len(lab.optimization_rows) == 2
    assert lab.optimization_rows[0]['values_0'] == '0.75'
    assert 'value' not in lab.optimization_rows[0]


def test_opt_chart_supports_single_and_parameter_rank():
    page = _read(JSLIB / 'strategy-lab-page.ts')
    # 单目标 `value` 兼容
    assert "key === 'value'" in page
    # 参数排名按 params_* 显示（不是 values_*）✓
    block = page.split('const targetKey = valueKeys[0]', 1)[1]
    block = block.split('const max =', 1)[0]
    assert 'params.map' in block
    assert 'importance(key)' in block
    assert 'values.sort' in block
    # 单目标帕累托图退化为「trial number → value」历史图 ✓
    pareto = page.split('private _paretoSvg(', 1)[1]
    assert 'const single = valueKeys.length < 2;' in pareto
    assert "const xKey = single ? 'number' : valueKeys[0];" in pareto

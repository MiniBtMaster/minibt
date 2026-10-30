"""看盘窗口编辑器工具栏：`加到图表` 后面的「策略管理」按钮 ✓

用户 2026-10-28 要求：编辑器工具栏在「加到图表」后面加一个「策略管理」，
点击弹出的界面与工具栏「指标 → 策略管理…」**完全一样**（后端命令
`strategy_manage`，弹窗 `StrategyManager` 复用布局管理那套 UI ✓）。
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(name: str) -> str:
    return (JSLIB / name).read_text(encoding='utf-8')


def test_editor_toolbar_has_strategy_manage_button():
    panel = _read('editor-panel.ts')
    # ① 按钮就在「加到图表」后面创建 ✓
    assert "this.addButton = this._button('加到图表'" in panel
    assert "this.manageButton = this._button('策略管理', () => {" in panel
    assert panel.index("this._button('加到图表'") < \
        panel.index("this._button('策略管理'")
    # ② 走的是和「指标 → 策略管理…」同一个后端命令 ✓
    assert "this.options.onCommand('strategy_manage', {});" in panel
    # ③ 真的挂到工具栏上（只创建不 append = 看不见 ✗）
    assert 'this.manageButton,' in panel
    # ④ 按钮不随“有没有打开文件”灰掉（它管的是已加载的策略 ✓）
    assert 'this.manageButton.disabled' not in panel


def test_chart_menu_uses_the_same_strategy_manage_command():
    chart = _read('chart-page.ts')
    assert "{ label: '策略管理…'," in chart
    assert "onCommand?.('strategy_manage', {})" in chart
    # 弹窗（界面复用布局管理）+ 两个开关 / 删除都走后端 ✓
    app = _read('app.ts')
    assert 'case \'strategy_manage\':' in app
    assert 'showStrategyManage(' in app
    assert "this.send('strategy_manage_update'" in app

"""扩展功能接入：命令表 / 前端页面 / 命令面板 / REST 入口。"""
from __future__ import annotations

import json
import pathlib

from minibt.desk.app import Desk

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSLIB = ROOT / 'jslib' / 'src' / 'desk'


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def test_desk_commands_cover_suite():
    desk = Desk(offline=True)
    commands = desk.commands()
    for name in ('workbench', 'workbench_submit', 'workbench_cancel',
                 'workbench_modify', 'workbench_close_partial',
                 'workbench_limits', 'workbench_reconcile',
                 'workbench_export', 'research', 'research_start',
                 'research_cancel', 'research_report', 'datahub',
                 'datahub_quality', 'datahub_resample', 'datahub_roll',
                 'datahub_ticks', 'datahub_query', 'datahub_export',
                 'ops', 'ops_token_issue', 'ops_token_revoke',
                 'ops_task_add', 'ops_task_run', 'ops_notify_config',
                 'ops_notify_test', 'ops_version_snapshot',
                 'ops_version_rollback', 'ops_versions'):
        assert name in commands, name


def test_palette_shortcut_is_ctrl_p_not_ctrl_k():
    """命令面板 = `Ctrl/⌘ + P`；`Ctrl+K` 留给编辑器的 `Ctrl+K Ctrl+C` 注释 ✓

    两段式快捷键的第一段会被全局 keydown 截胡（编辑器里按注释弹命令面板 ✗）。
    """
    app = _read(JSLIB / 'app.ts')
    editor = _read(JSLIB / 'editor-bundle.ts')
    assert "event.key === 'p' || event.key === 'P'" in app
    assert "event.key === 'k' || event.key === 'K'" not in app
    # 编辑器注释快捷键保持 VS Code 同款 ✓
    assert "key: 'Mod-k Mod-c'" in editor
    assert "key: 'Ctrl-K Ctrl-C'" in editor
    # `Ctrl+P` 会触发浏览器打印对话框 → 必须 preventDefault ✓
    assert 'this.openPalette();' in app
    block = app.split("event.key === 'p' || event.key === 'P'", 1)[1]
    assert block.index('event.preventDefault();') < block.index('this.openPalette();')


def test_suite_pages_are_wired_into_app():
    app = _read(JSLIB / 'app.ts')
    pages = _read(JSLIB / 'suite-pages.ts')
    palette = _read(JSLIB / 'command-palette.ts')
    css = _read(JSLIB / 'desk.css')
    for name in ('WorkbenchPage', 'ResearchPage', 'DataPage', 'OpsPage'):
        assert f'export class {name}' in pages
        assert f'new {name}' in app
    for command in ('openWorkbench', 'openResearch', 'openDataHub', 'openOps',
                    'openPalette'):
        assert command in app
    assert 'Ctrl/⌘ + P' in palette or 'Ctrl/⌘ + P' in app
    for css_class in ('.desk-suite-page', '.desk-palette',
                      '.desk-suite-table'):
        assert css_class in css


def test_suite_page_patch_dispatch():
    app = _read(JSLIB / 'app.ts')
    for patch_type in ("case 'workbench'", "case 'research_result'",
                       "case 'datahub_quality'", "case 'ops_token'"):
        assert patch_type in app


def test_suite_pages_send_commands_not_dom_side_effects():
    pages = _read(JSLIB / 'suite-pages.ts')
    for command in ('workbench_submit', 'workbench_limits',
                    'workbench_reconcile', 'research_start',
                    'datahub_resample', 'datahub_query',
                    'ops_token_issue', 'ops_notify_test'):
        assert f"'{command}'" in pages, command
    for marker in ('metric0', 'metric1', 'metric2', 'rs-data-names',
                   'heatMetric', 'LocalDatas'):
        assert marker in pages, marker


def test_workbench_handlers_push_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv('MINIBT_DESK_AUDIT_DB', str(tmp_path / 'audit.db'))
    monkeypatch.setenv('MINIBT_DESK_WORKBENCH_CONFIG',
                       str(tmp_path / 'config.json'))
    desk = Desk(offline=True, allow_trading=False)
    desk._on_workbench({})
    desk._on_workbench_submit({'symbol': 'SHFE.ag2612', 'side': 'buy',
                               'volume': 1})
    types = []
    for script in desk._pending:
        try:
            types.append(json.loads(
                script[script.index('(') + 1:script.rindex(')')])['type'])
        except Exception:                                    # noqa: BLE001
            continue
    assert 'workbench' in types
    assert 'toast' in types


def test_research_datahub_ops_handlers_push(tmp_path, monkeypatch):
    monkeypatch.setenv('MINIBT_DESK_RESEARCH_DB', str(tmp_path / 'r.db'))
    monkeypatch.setenv('MINIBT_DESK_OPS_DIR', str(tmp_path / 'ops'))
    monkeypatch.setenv('MINIBT_DESK_DATAS', str(tmp_path / 'datas'))
    (tmp_path / 'datas').mkdir()
    desk = Desk(offline=True)
    desk._on_research({})
    desk._on_ops({})
    desk._on_datahub({})
    types = []
    for script in desk._pending:
        try:
            types.append(json.loads(
                script[script.index('(') + 1:script.rindex(')')])['type'])
        except Exception:                                    # noqa: BLE001
            continue
    assert {'research', 'ops', 'datahub'} <= set(types)


def test_web_rpc_is_token_guarded():
    source = _read(ROOT / 'minibt' / 'desk' / 'web.py')
    assert "path == '/api/rpc'" in source
    assert "path == '/ws'" in source
    assert '_api_token_ok' in source
    assert 'command not allowed' in source
    assert "path in ('/api/status', '/api/snapshot')" in source


def test_websocket_accept_matches_rfc6455():
    from minibt.desk.web import ws_accept
    assert ws_accept('dGhlIHNhbXBsZSBub25jZQ==') ==         's3pPLMBiTxaQ9kYGzzhZRbK+xOo='


def test_headless_module_exists():
    path = ROOT / 'minibt' / 'desk' / 'headless.py'
    assert path.is_file()
    source = _read(path)
    assert 'keep_alive=True' in source
    assert 'X-Desk-Token' in _read(ROOT / 'minibt' / 'desk' / 'web.py') \
        or 'X-Desk-Token' in source

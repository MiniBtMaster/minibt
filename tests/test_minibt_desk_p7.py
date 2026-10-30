"""P7 测试：静态导出（minibt-charts 嵌入）+ 打磨（主题/快捷键/上限/截图/CSV）。"""

import json
import pathlib
import sys

import pytest

from minibt.desk.app import Desk
from minibt.desk import protocol

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def test_export_static_writes_embeddable_bundle(tmp_path):
    desk = Desk(offline=True, theme='light', title='我的终端')
    target = desk.export_static(str(tmp_path / 'static'))
    folder = pathlib.Path(target)
    for name in ('desk.html', 'desk.js', 'desk.css', 'styles.css',
                 'lightweight-charts.js', 'config.json'):
        assert (folder / name).is_file(), name
    config = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    assert config == {'transport': 'rest', 'theme': 'light',
                      'title': '我的终端'}
    html = (folder / 'desk.html').read_text(encoding='utf-8')
    assert './desk.js' in html and './lightweight-charts.js' in html


def test_export_static_without_config(tmp_path):
    desk = Desk(offline=True)
    target = desk.export_static(str(tmp_path / 'static'), config=False)
    assert not (pathlib.Path(target) / 'config.json').exists()
    assert (pathlib.Path(target) / 'desk.js').is_file()


def test_set_theme_command_persists_and_broadcasts(tmp_path):
    sent = []
    desk = Desk(offline=True)
    desk.sender = sent.append
    desk._booted = True
    desk.handle(protocol.encode_command({'cmd': 'set_theme',
                                         'payload': {'theme': 'light'}}))
    assert desk.theme == 'light'
    patch = json.loads(sent[-1][len('window.__desk.applyPatch('):-2])
    assert patch == {'type': 'theme', 'theme': 'light'}

    desk.handle(protocol.encode_command({'cmd': 'set_theme',
                                         'payload': {'theme': 'nope'}}))
    assert desk.theme == 'light'                      # 非法值忽略 ✓


def test_p7_assets_and_sources():
    js_dir = REPO / 'pylightcharts' / 'js'
    script = (js_dir / 'desk.js').read_text(encoding='utf-8', errors='ignore')
    css = (js_dir / 'desk.css').read_text(encoding='utf-8')
    # 主题 / 快捷键 / 上限 / 截图 / CSV 都进了产物 ✓
    lowered = script.lower()
    for key in ('takescreenshot', 'desk-dock-action', 'text/csv'):
        assert key in lowered, key          # 截图 / CSV 导出都在产物里 ✓
    assert 'theme' in lowered and 'localstorage' in lowered  # 主题记忆 ✓
    assert 'theme-light' in css

    app = (REPO / 'jslib' / 'src' / 'desk' / 'app.ts').read_text(
        encoding='utf-8')
    for key in ('MAX_CHART_TABS', '_installShortcuts', 'toggleTheme',
                'THEME_KEY', "'set_theme'"):
        assert key in app, key
    chart = (REPO / 'jslib' / 'src' / 'desk' / 'chart-page.ts').read_text(
        encoding='utf-8')
    assert 'screenshot()' in chart and 'takeScreenshot' in chart
    dock = (REPO / 'jslib' / 'src' / 'desk' / 'account-dock.ts').read_text(
        encoding='utf-8')
    assert 'exportCsv' in dock and 'text/csv' in dock

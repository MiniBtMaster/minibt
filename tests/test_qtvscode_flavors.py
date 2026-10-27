"""qtvscode 多后端（flavor）测试：VS Code 品牌 vs 原味 VSCodium。

全部用临时目录 + 自造的 ``product.json``，不碰真实产物、不联网。

    pytest tests/test_qtvscode_flavors.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'qtvscode'))

flavors = pytest.importorskip('qtvscode.flavors')
paths = pytest.importorskip('qtvscode.paths')

# server.py / download.py 依赖 Qt，但这两个模块的纯函数不需要真正 Qt 窗口
server = pytest.importorskip('qtvscode.server')
download = pytest.importorskip('qtvscode.download')


VSCODE_PRODUCT = {
    'nameShort': 'qtvscode',
    'applicationName': 'qtvscode',
    'serverApplicationName': 'qtvscode-server',
}
VSCODIUM_PRODUCT = {
    'nameShort': 'VSCodium',
    'applicationName': 'codium',
    'serverApplicationName': 'codium-server',
}


def make_server(base: pathlib.Path, name: str, product: dict) -> pathlib.Path:
    """造一个最小 server 目录（out/server-main.js + product.json）。"""
    directory = base / name
    (directory / 'out').mkdir(parents=True)
    (directory / 'out' / 'server-main.js').write_text('// fake\n', encoding='utf-8')
    (directory / 'product.json').write_text(
        json.dumps(product), encoding='utf-8')
    return directory


# ------------------------------------------------------------------ 纯函数
def test_resolve_flavor_aliases():
    assert flavors.resolve_flavor(None).key == 'vscode'
    assert flavors.resolve_flavor('vscode').key == 'vscode'
    assert flavors.resolve_flavor('code').key == 'vscode'
    assert flavors.resolve_flavor('qtvscode').key == 'vscode'
    assert flavors.resolve_flavor('VSCodium').key == 'vscodium'
    assert flavors.resolve_flavor('codium').key == 'vscodium'


def test_resolve_flavor_rejects_unknown():
    with pytest.raises(ValueError):
        flavors.resolve_flavor('emacs')


def test_detect_flavor_reads_product_json(tmp_path):
    vscode = make_server(tmp_path, 'a', VSCODE_PRODUCT)
    codium = make_server(tmp_path, 'b', VSCODIUM_PRODUCT)
    assert flavors.detect_flavor(vscode) == 'vscode'
    assert flavors.detect_flavor(codium) == 'vscodium'
    # 认不出的品牌 / 没有 product.json → None
    unknown = make_server(tmp_path, 'c', {'nameShort': 'Foo'})
    assert flavors.detect_flavor(unknown) is None
    assert flavors.detect_flavor(tmp_path / 'nope') is None


# ------------------------------------------------------------------ 产物定位
def test_find_server_dir_filters_by_flavor(tmp_path):
    vscode = make_server(tmp_path, 'vscode-reh-web-x64', VSCODE_PRODUCT)
    codium = make_server(tmp_path, 'codium-reh-web-x64', VSCODIUM_PRODUCT)
    # 显式传入时按品牌校验：选对返回，品牌不符返回 None（绝不静默回退）
    assert paths.find_server_dir(codium, flavor='vscodium') == codium.resolve()
    assert paths.find_server_dir(vscode, flavor='vscode') == vscode.resolve()
    assert paths.find_server_dir(codium, flavor='vscode') is None
    assert paths.find_server_dir(vscode, flavor='vscodium') is None


def test_find_server_dir_runtime_dir_by_flavor(tmp_path, monkeypatch):
    """两种产物同名时，靠 product.json 品牌从运行时目录挑对。"""
    monkeypatch.setattr(paths, 'qtvscode_home', lambda: tmp_path / 'qhome')
    runtime = tmp_path / 'qhome' / 'runtime'
    make_server(runtime / 'vscode', 'vscode-reh-web-x64', VSCODE_PRODUCT)
    make_server(runtime / 'vscodium', 'vscodium-reh-web-x64', VSCODIUM_PRODUCT)
    found = paths.find_server_dir(flavor='vscodium')
    assert found is not None
    assert flavors.detect_flavor(found) == 'vscodium'


def test_require_server_dir_error_mentions_flavor(tmp_path):
    with pytest.raises(FileNotFoundError) as excinfo:
        paths.require_server_dir(tmp_path / 'missing', flavor='vscodium')
    message = str(excinfo.value)
    assert 'VSCodium' in message
    assert 'codium-server' in message


def test_default_dirs_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'qtvscode_home', lambda: tmp_path / 'qhome')
    vscode_data = paths.default_user_data_dir('vscode')
    codium_data = paths.default_user_data_dir('vscodium')
    assert vscode_data.name == 'data'
    assert codium_data.name == 'data-codium'
    assert vscode_data != codium_data
    assert paths.default_extensions_dir('vscode').name == 'extensions'
    assert paths.default_extensions_dir('vscodium').name == 'extensions-codium'


# ------------------------------------------------------------------ 默认设置 / 主题
def test_default_settings_drops_qtvscode_theme_for_vscodium():
    vscode = server.default_settings_for('vscode')
    codium = server.default_settings_for('vscodium')
    assert vscode.get('workbench.colorTheme') == 'qtvscode Dark'
    assert 'workbench.colorTheme' not in codium
    # 其它默认设置两边都有
    assert codium.get('telemetry.telemetryLevel') == 'off'


def test_resolve_color_theme_per_flavor():
    assert server.resolve_color_theme('dark', flavor='vscode') == 'Dark 2026'
    assert (server.resolve_color_theme('light', flavor='vscode')
            == 'Light 2026')
    assert (server.resolve_color_theme('dark', flavor='vscodium')
            == 'Default Dark Modern')
    # 具体主题名原样返回
    assert server.resolve_color_theme('Monokai', flavor='vscodium') == 'Monokai'
    assert server.resolve_color_theme(None) is None


def test_seed_default_settings_flavor(tmp_path):
    vscode_dir = tmp_path / 'vdata'
    server.seed_default_settings(vscode_dir, flavor='vscode')
    vscode = json.loads((vscode_dir / 'User' / 'settings.json')
                        .read_text(encoding='utf-8'))
    assert vscode['workbench.colorTheme'] == 'qtvscode Dark'

    codium_dir = tmp_path / 'cdata'
    server.seed_default_settings(codium_dir, flavor='vscodium')
    codium = json.loads((codium_dir / 'User' / 'settings.json')
                        .read_text(encoding='utf-8'))
    assert 'workbench.colorTheme' not in codium


# ------------------------------------------------------------------ 下载地址解析
def test_resolve_server_url_prefers_explicit_and_env(monkeypatch):
    monkeypatch.setenv('QTVSCODE_VSCODIUM_SERVER_URL', 'https://example/x.tar.gz')
    assert (download.resolve_server_url('vscodium')
            == 'https://example/x.tar.gz')
    assert (download.resolve_server_url('vscodium', 'https://explicit/y.tar.gz')
            == 'https://explicit/y.tar.gz')


def test_resolve_server_url_vscode_requires_env(monkeypatch):
    monkeypatch.delenv('QTVSCODE_SERVER_URL', raising=False)
    with pytest.raises(ValueError):
        download.resolve_server_url('vscode')


def test_stable_port_differs_by_flavor():
    """同一工作区的 VS Code / VSCodium 必须用**不同端口**（否则浏览器缓存会串味）。"""
    widget = pytest.importorskip('qtvscode.widget')
    workspace = pathlib.Path('C:/work/ws')
    vscode_port = widget._stable_server_port(workspace, 'vscode')
    codium_port = widget._stable_server_port(workspace, 'vscodium')
    assert vscode_port != codium_port
    # 同 flavor + 同工作区 → 稳定（能恢复会话 ✓）
    assert vscode_port == widget._stable_server_port(workspace, 'vscode')


def test_widget_can_hide_the_secondary_sidebar():
    """VSCodium 默认会显示空的「辅助栏」→ 提供命令把它关掉（与 VS Code 一致 ✓）。"""
    widget = pytest.importorskip('qtvscode.widget')
    assert hasattr(widget.QtVscodeWidget, 'close_auxiliary_bar')
    source = (REPO / 'qtvscode' / 'qtvscode' / 'widget.py').read_text(
        encoding='utf-8')
    assert 'workbench.action.closeAuxiliaryBar' in source


def test_widget_relayouts_the_workbench_after_resize():
    """窗口缩放后补发 resize，避免 VS Code 把编辑区算短、状态栏上方留白 ✗。"""
    widget = pytest.importorskip('qtvscode.widget')
    assert hasattr(widget.QtVscodeWidget, 'resizeEvent')
    assert hasattr(widget.QtVscodeWidget, 'showEvent')
    source = (REPO / 'qtvscode' / 'qtvscode' / 'widget.py').read_text(
        encoding='utf-8')
    assert "dispatchEvent(new Event('resize'))" in source
    assert '_relayout_timer' in source


def test_widget_and_server_accept_flavor():
    import inspect
    widget = pytest.importorskip('qtvscode.widget')
    assert 'flavor' in inspect.signature(
        widget.QtVscodeWidget.__init__).parameters
    assert widget.QtVscodiumWidget is not None
    assert 'flavor' in inspect.signature(
        server.QtVscodeServer.__init__).parameters


def test_has_download_source(monkeypatch):
    monkeypatch.delenv('QTVSCODE_SERVER_URL', raising=False)
    monkeypatch.delenv('QTVSCODE_VSCODIUM_SERVER_URL', raising=False)
    # qtvscode 品牌默认没有下载地址；VSCodium 有官方地址
    assert download.has_download_source('vscode') is False
    assert download.has_download_source('vscodium') is True
    # 配了环境变量就可用
    monkeypatch.setenv('QTVSCODE_SERVER_URL', 'https://x/y.tar.gz')
    assert download.has_download_source('vscode') is True


def test_download_cli_passes_flavor(monkeypatch):
    called = {}
    monkeypatch.setattr(download, 'ensure_server',
                        lambda **kw: (called.update(kw), 'DEST')[1])
    assert download.main(['--flavor', 'vscodium', '--dest', 'x']) == 0
    assert called['flavor'] == 'vscodium'
    assert called['dest'] == 'x'


def test_autodownload_runs_in_a_worker_thread(tmp_path, monkeypatch):
    """下载必须在 QThread 里跑（以前在 UI 线程 urlopen，网络一卡整个界面像死了一样 ✗）。"""
    import threading
    import time

    autodownload = pytest.importorskip('qtvscode.autodownload')
    monkeypatch.setattr(autodownload, 'find_server_dir',
                        lambda flavor=None: None)
    seen = {}

    def fake_ensure(**kwargs):
        seen['thread'] = threading.current_thread()
        time.sleep(0.15)
        return str(tmp_path / 'server')

    monkeypatch.setattr(autodownload, 'ensure_server', fake_ensure)
    path = autodownload.ensure_server_with_dialog(flavor='vscodium')
    assert str(path) == str(tmp_path / 'server')
    assert seen['thread'] is not threading.current_thread()


def test_autodownload_returns_existing_without_dialog(tmp_path, monkeypatch):
    autodownload = pytest.importorskip('qtvscode.autodownload')
    existing = tmp_path / 'srv'
    monkeypatch.setattr(autodownload, 'find_server_dir',
                        lambda flavor=None: existing)
    # 已存在时直接返回，不构造任何对话框 / 不联网
    assert autodownload.ensure_server_with_dialog(flavor='vscodium') == existing


def test_package_scripts_bundle_both_servers():
    """胖包默认同时带 qtvscode 与 VSCodium 两份产物。"""
    scripts = REPO / 'qtvscode' / 'scripts'
    package = (scripts / 'package.ps1').read_text(encoding='utf-8')
    assert 'server-codium' in package
    assert 'qtvscode.download' in package
    build = (scripts / 'build_server.ps1').read_text(encoding='utf-8')
    assert 'server-codium' in build
    assert '$ServerDir' in build


def test_miniqt_exposes_editor_flavor_setting():
    """miniqt 侧要有「编辑器后端」设置，并把它传给 qtvscode。"""
    app = REPO / 'miniqt' / 'app'
    config = (app / 'common' / 'config.py').read_text(encoding='utf-8')
    assert 'editorFlavor' in config
    # miniqt 默认用 VSCodium 后端
    assert '"Flavor", "vscodium"' in config
    setting = (app / 'view' / 'setting_interface.py').read_text(encoding='utf-8')
    assert 'cfg.editorFlavor' in setting
    for name in ('common/qtvscode_shared.py', 'view/qtvscode_interface.py',
                 'windows/qtvscode_page.py'):
        source = (app / name).read_text(encoding='utf-8')
        assert 'flavor=flavor' in source, name


def test_vscodium_latest_url_picks_matching_asset(monkeypatch):
    release = {
        'tag_name': '1.104.0',
        'assets': [
            {'name': 'vscodium-reh-web-linux-x64-1.104.0.tar.gz',
             'browser_download_url': 'https://ex/linux.tar.gz'},
            {'name': f'vscodium-reh-web-{download._platform_name()}-'
                     f'{download._arch_name()}-1.104.0.tar.gz',
             'browser_download_url': 'https://ex/match.tar.gz'},
        ],
    }
    monkeypatch.setattr(download, '_http_json', lambda url, timeout=60: release)
    assert download.vscodium_latest_url() == 'https://ex/match.tar.gz'

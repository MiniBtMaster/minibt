"""qtvscode 预装扩展（``<server>/extensions-user/``）测试。

预装的意义：``QtVscodeServer.start()`` 会把产物里 ``extensions-user/`` 的扩展
**补齐到用户持久目录**，所以放进去就等于"用户已安装" —— miniqt 分发时不用联网、
不用手动装扩展。

这里全部用临时目录 + 自造的假 VSIX / 假已装扩展，不碰真实环境。

    pytest tests/test_qtvscode_bundle.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import zipfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'qtvscode'))

bundle = pytest.importorskip('qtvscode.bundle')


MANIFEST = {
    'name': 'minibt-charts',
    'publisher': 'MiniBtMaster',
    'version': '9.9.9',
    'main': './extension.js',
    'activationEvents': ['onStartupFinished'],
}


def make_vsix(path: pathlib.Path, manifest: dict | None = None,
              extra: dict[str, str] | None = None) -> pathlib.Path:
    """造一个最小可用的 VSIX（zip：extension.vsixmanifest + extension/…）。"""
    payload = dict(extra or {'extension.js': '// fake\n'})
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('extension.vsixmanifest',
                         '<?xml version="1.0"?><PackageManifest/>')
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('extension/package.json',
                         json.dumps(manifest or MANIFEST))
        for name, text in payload.items():
            archive.writestr(f'extension/{name}', text)
    return path


def make_installed(base: pathlib.Path, name: str, version: str,
                   activation: bool = False) -> pathlib.Path:
    folder = base / f'{name.lower()}-{version}-universal'
    folder.mkdir(parents=True)
    manifest = {'name': name.split('.')[-1], 'publisher': name.split('.')[0],
                'version': version, 'main': './extension.js'}
    if activation:
        manifest['activationEvents'] = ['onStartupFinished']
    (folder / 'package.json').write_text(json.dumps(manifest),
                                         encoding='utf-8')
    return folder


# ------------------------------------------------------------------ 解包/拷贝
def test_install_bridge_extensions_copies_from_vscode_flavor(tmp_path):
    """官方 VSCodium 产物没有 qtvscode-bridge/theme → 要能从 vscode 产物补一份。"""
    copied = bundle.install_bridge_extensions(tmp_path)
    if not copied:
        pytest.skip('没有可用的 qtvscode 产物（无 bridge 扩展源）')
    joined = ' '.join(copied)
    assert 'qtvscode-bridge' in joined
    for name in copied:
        assert (tmp_path / name / 'package.json').is_file()
    # 幂等：再调一次不重复拷
    assert bundle.install_bridge_extensions(tmp_path) == []


def test_add_vsix_uses_the_conventional_folder_name(tmp_path):
    vsix = make_vsix(tmp_path / 'x.vsix')
    target = tmp_path / 'extensions-user'
    target.mkdir()
    destination = bundle.add_vsix(vsix, target)
    assert destination.name == 'minibtmaster.minibt-charts-9.9.9'
    assert (destination / 'package.json').is_file()
    assert (destination / 'extension.js').is_file()
    # VSIX 外壳文件不该被解出来
    assert not (destination / 'extension.vsixmanifest').exists()


def test_add_vsix_rejects_a_broken_archive(tmp_path):
    bad = tmp_path / 'bad.vsix'
    with zipfile.ZipFile(bad, 'w') as archive:
        archive.writestr('something.txt', 'x')
    with pytest.raises(ValueError):
        bundle.add_vsix(bad, tmp_path)


def test_add_installed_copies_the_folder(tmp_path):
    installed = tmp_path / 'installed'
    source = make_installed(installed, 'johnny-zhao.pi-agent-studio', '1.3.10')
    target = tmp_path / 'extensions-user'
    target.mkdir()
    destination = bundle.add_installed(
        'johnny-zhao.pi-agent-studio', target, source=installed)
    # 保留原目录名（含 -universal 这类平台后缀），VS Code 靠它识别
    assert destination.name == source.name
    assert (destination / 'package.json').is_file()


def test_add_installed_picks_the_highest_version(tmp_path):
    installed = tmp_path / 'installed'
    make_installed(installed, 'foo.bar', '1.0.0')
    make_installed(installed, 'foo.bar', '2.10.3')
    found = bundle._find_installed('foo.bar', installed)
    assert found is not None and '2.10.3' in found.name


def test_add_installed_raises_when_missing(tmp_path):
    installed = tmp_path / 'installed'
    installed.mkdir()
    with pytest.raises(FileNotFoundError):
        bundle.add_installed('nope.nope', tmp_path, source=installed)


# ------------------------------------------------------------------ 迁移
def test_migrate_copies_missing_only(tmp_path):
    legacy = tmp_path / 'server' / 'extensions-user'
    target = tmp_path / 'user' / 'extensions'
    legacy.mkdir(parents=True)
    (legacy / 'foo.bar-1.0.0').mkdir()
    (legacy / 'foo.bar-1.0.0' / 'package.json').write_text('{}',
                                                           encoding='utf-8')
    (legacy / 'extensions.json').write_text('[]', encoding='utf-8')

    first = bundle.migrate_bundled_extensions(legacy, target)
    assert first == ['foo.bar-1.0.0']
    # 账本文件不该被搬过去
    assert not (target / 'extensions.json').exists()
    # 第二次不再重复拷
    assert bundle.migrate_bundled_extensions(legacy, target) == []


def test_migrate_does_not_resurrect_uninstalled(tmp_path):
    """用户卸载过的（写在 .obsolete 里）别再装回来，否则装回来→再删来回循环。"""
    legacy = tmp_path / 'server' / 'extensions-user'
    target = tmp_path / 'user' / 'extensions'
    legacy.mkdir(parents=True)
    target.mkdir(parents=True)
    (legacy / 'foo.bar-1.0.0').mkdir()
    (legacy / 'foo.bar-1.0.0' / 'package.json').write_text('{}',
                                                           encoding='utf-8')
    (target / '.obsolete').write_text(
        json.dumps({'foo.bar-1.0.0': True}), encoding='utf-8')
    assert bundle.read_obsolete(target) == {'foo.bar-1.0.0'}
    assert bundle.migrate_bundled_extensions(legacy, target) == []
    assert not (target / 'foo.bar-1.0.0').exists()


def test_read_obsolete_tolerates_junk(tmp_path):
    target = tmp_path / 'extensions'
    target.mkdir()
    (target / '.obsolete').write_text('not json', encoding='utf-8')
    assert bundle.read_obsolete(target) == set()
    (target / '.obsolete').write_text('[1, 2]', encoding='utf-8')
    assert bundle.read_obsolete(target) == set()
    assert bundle.read_obsolete(tmp_path / 'missing') == set()


# ------------------------------------------------------------------ 总入口
def test_bundle_extensions_runs_activation_and_cleans_ledgers(tmp_path):
    server = tmp_path / 'server'
    server.mkdir()
    vsix = make_vsix(tmp_path / 'chart.vsix', manifest=dict(
        MANIFEST, activationEvents=[]))       # 故意不声明启动激活

    added = bundle.bundle_extensions([str(vsix)], server_dir=server)
    assert added == ['minibtmaster.minibt-charts-9.9.9']

    folder = server / 'extensions-user' / added[0]
    text = (folder / 'package.json').read_text(encoding='utf-8')
    manifest = json.loads(text)
    # 补上了启动激活，否则 activate() 不跑、依赖上下文的菜单永远不显示
    assert '*' in manifest['activationEvents']
    # 账本文件不会留在预装目录
    assert not (server / 'extensions-user' / 'extensions.json').exists()
    assert bundle.list_bundled(server) == added


def test_bundle_extensions_clean_wipes_first(tmp_path):
    server = tmp_path / 'server'
    server.mkdir()
    stale = server / 'extensions-user' / 'old.ext-0.0.1'
    stale.mkdir(parents=True)
    (stale / 'package.json').write_text('{}', encoding='utf-8')
    vsix = make_vsix(tmp_path / 'chart.vsix')
    added = bundle.bundle_extensions([str(vsix)], server_dir=server,
                                     clean=True)
    assert added == ['minibtmaster.minibt-charts-9.9.9']
    assert not stale.exists()


def test_bundle_extensions_can_copy_an_installed_extension(tmp_path):
    server = tmp_path / 'server'
    server.mkdir()
    installed = tmp_path / 'installed'
    make_installed(installed, 'johnny-zhao.pi-agent-studio', '1.3.10')
    added = bundle.bundle_extensions(['johnny-zhao.pi-agent-studio'],
                                     server_dir=server,
                                     installed_source=installed)
    assert added == ['johnny-zhao.pi-agent-studio-1.3.10-universal']


def test_bundle_extensions_needs_a_server_dir():
    with pytest.raises(FileNotFoundError):
        bundle.bundle_extensions(['foo.vsix'], server_dir=None, target=None)


def test_main_list_and_usage(tmp_path, capsys):
    server = tmp_path / 'server'
    server.mkdir()
    assert bundle.main(['--server', str(server), '--list']) == 0
    assert '还没有预装扩展' in capsys.readouterr().out
    assert bundle.main(['--server', str(server)]) == 2
    assert bundle.main(['--help']) == 0

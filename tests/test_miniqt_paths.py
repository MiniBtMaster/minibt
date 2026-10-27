"""Default folders must live under ``miniqt/app``, not under the working directory.

The folder config items used relative defaults (``app/download``, ``app/ollama``,
``app/llama``). qfluentwidgets' ``FolderValidator.correct()`` turns a value that
does not exist into an absolute one **relative to the current working directory**
and creates it, so launching miniqt from anywhere else left an empty ``app/``
folder next to wherever it was started - and the setting drifted to that new
location for good (one machine ended up with ``D:/up/app/download``).

Defaults are now absolute (``<miniqt>/app/...``) and stored values that are
relative, or that point at some other directory's ``app/``, are migrated on load.
A path the user picked themselves (``D:/models``) is left alone.

    pytest tests/test_miniqt_paths.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

miniqt = pytest.importorskip('miniqt')
if not pathlib.Path(miniqt.__file__).resolve().parent.is_relative_to(REPO):
    # 例如从 sdist 里跑、而环境里装的是 site-packages 版 miniqt：
    # 这些断言只对“本仓库旁边的源码副本”有意义
    pytest.skip('miniqt 不是本仓库里的源码副本（跳过布局单测）',
                allow_module_level=True)

config = pytest.importorskip('miniqt.app.common.config')

APP_DIR = REPO / 'miniqt' / 'app'


def as_posix(path) -> str:
    return str(path).replace('\\', '/')


def test_app_folder_is_absolute_and_inside_miniqt():
    for name in ('download', 'ollama', 'llama'):
        folder = config.app_folder(name)
        assert os.path.isabs(folder), folder
        assert as_posix(folder).startswith(as_posix(APP_DIR) + '/'), folder
        assert folder.endswith('/' + name)


def test_the_folder_defaults_are_absolute():
    """A relative default is what made the directory follow the working directory."""
    assert os.path.isabs(config.cfg.downloadFolder.value)
    assert as_posix(config.cfg.downloadFolder.value).startswith(as_posix(APP_DIR))
    assert config.app_folder('download') == config.cfg.downloadFolder.value


def test_legacy_relative_paths_are_resolved():
    assert config.resolve_folder('app/download') == config.app_folder('download')
    assert config.resolve_folder('app/llama') == config.app_folder('llama')
    assert config.resolve_folder('ollama') == config.app_folder('ollama')


def test_paths_corrected_against_a_working_directory_are_recovered():
    """FolderValidator used to rewrite the default into <cwd>/app/<name>."""
    assert config.resolve_folder('D:/up/app/download') == config.app_folder('download')
    assert (config.resolve_folder('D:/newminibt/gallery/app/llama')
            == config.app_folder('llama'))
    assert (config.resolve_folder('C:/somewhere/app/ollama')
            == config.app_folder('ollama'))


def test_a_path_the_user_chose_is_left_alone():
    for value in ('D:/models', 'D:/ollama_models/.ollama/models', 'E:/data/contracts'):
        assert config.resolve_folder(value) == value


def test_an_already_correct_path_is_unchanged():
    for name in ('download', 'ollama', 'llama'):
        folder = config.app_folder(name)
        assert config.resolve_folder(folder) == folder


def test_importing_the_config_creates_nothing_in_the_working_directory(tmp_path):
    """The regression itself: start from an empty directory and import miniqt."""
    script = (
        'import sys; sys.path.insert(0, r"%s")\n' % REPO
        + 'import miniqt\n'
        + 'from miniqt.app.common.config import cfg\n'
        + 'from miniqt.app.common.data_config import data_cfg\n'
        # a marker: qfluentwidgets prints a banner on stdout too
        + 'print("VALUE", miniqt.__file__)\n'
        + 'print("VALUE", cfg.downloadFolder.value)\n'
        + 'print("VALUE", data_cfg.ollamaPath.value)\n'
        + 'print("VALUE", data_cfg.llamaCppConversationsPath.value)\n'
    )
    result = subprocess.run([sys.executable, '-c', script], cwd=str(tmp_path),
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr[-2000:]

    printed = [line.split('VALUE ', 1)[1].strip()
               for line in result.stdout.splitlines() if 'VALUE ' in line]
    assert len(printed) == 4, result.stdout
    # the repo copy must win, not a stale installed one
    assert as_posix(REPO) in as_posix(printed[0]), printed[0]
    for value in printed[1:4]:
        assert os.path.isabs(value), value
        assert as_posix(value).startswith(as_posix(APP_DIR) + '/'), value

    leftovers = [p.name for p in tmp_path.iterdir()]
    assert leftovers == [], f'the working directory was polluted: {leftovers}'

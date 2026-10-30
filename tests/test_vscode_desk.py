"""P42：minibt-charts 扩展里托管 minibt desk（VS Code 看盘终端）✓"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXT = ROOT / 'vscode-minibt'

NODE = shutil.which('node')


def _pkg() -> dict:
    return json.loads((EXT / 'package.json').read_text(encoding='utf-8'))


def _ext_source() -> str:
    return (EXT / 'extension.js').read_text(encoding='utf-8')


def _desk_source() -> str:
    return (EXT / 'desk.js').read_text(encoding='utf-8')


def _node(script: str, timeout: int = 120):
    """跑一段 node 脚本 → (returncode, stdout)"""
    if NODE is None:
        pytest.skip('没有 node')
    done = subprocess.run([NODE, '-e', script], capture_output=True,
                          text=True, encoding='utf-8', errors='replace',
                          timeout=timeout, cwd=str(EXT))
    return done.returncode, (done.stdout or '') + (done.stderr or '')


# ------------------------------------------------------- ① 后端：env / healthz
def test_cli_reads_env_but_commandline_wins(tmp_path):
    from minibt.cli import apply_env_defaults, build_parser

    argv = ['desk']
    args = build_parser().parse_args(argv)
    apply_env_defaults(args, {
        'MINIBT_TQ_USER': 'env_user',
        'MINIBT_TQ_PASSWORD': 'env_pwd',
        'MINIBT_FUTU_HOST': '10.0.0.9',
        'MINIBT_FUTU_PORT': '22222',
        'MINIBT_DESK_TITLE': 'env_title',
        'MINIBT_DESK_THEME': 'light',
        'MINIBT_DESK_OFFLINE': '1',
    }, argv)
    assert args.user == 'env_user'
    assert args.password == 'env_pwd'            # 密码走 env，不进命令行 ✓
    assert args.futu_host == '10.0.0.9'
    assert args.futu_port == 22222
    assert args.title == 'env_title'
    assert args.theme == 'light'
    assert args.offline is True

    # 命令行给了的**不被覆盖** ✓
    argv2 = ['desk', '--user', 'cli_user', '--futu-port', '33333']
    args2 = build_parser().parse_args(argv2)
    apply_env_defaults(args2, {'MINIBT_TQ_USER': 'env_user',
                               'MINIBT_FUTU_PORT': '22222'}, argv2)
    assert args2.user == 'cli_user'
    assert args2.futu_port == 33333


def test_desk_status_and_healthz(tmp_path):
    from minibt.desk.app import Desk

    desk = Desk(offline=True)
    desk.sent = []
    desk.sender = desk.sent.append
    status = desk.status()
    assert status['ready'] is True
    assert status['offline'] is True
    assert 'futures' in status and 'stocks' in status
    source = (ROOT / 'minibt' / 'desk' / 'web.py').read_text(encoding='utf-8')
    assert "if path == '/healthz':" in source
    assert "json.dumps(payload, ensure_ascii=False)" in source


def test_desk_serve_prints_ready_json():
    source = (ROOT / 'minibt' / 'desk' / 'web.py').read_text(encoding='utf-8')
    assert 'as_json' in source
    assert "{'ready': True, 'url': url, 'port': port," in source
    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'def run(self, *, as_json: bool = False)' in app
    assert 'def status(self)' in app


# ------------------------------------------------------- ② 纯逻辑（node 直跑）
def test_desk_module_builds_args_and_env():
    code = """
const d = require('./desk');
const s = d.normalizeSettings({account: 'u1', password: 'p1',
    futuHost: '10.0.0.2', futuPort: '22222', theme: 'light'});
process.stdout.write(JSON.stringify({
  args: d.buildDeskArgs(s),
  argsOffline: d.buildDeskArgs({offline: true}),
  env: d.buildDeskEnv({PATH: 'x'}, s),
  status: d.statusText({running: true, futures: true}),
}));
"""
    code_ok, out = _node(code)
    assert code_ok == 0, out
    data = json.loads(out.strip().splitlines()[-1])
    args = data['args']
    assert args[:4] == ['-m', 'minibt', 'desk', '--browser']
    assert '--json' in args
    assert '--user' in args and 'u1' in args
    assert 'p1' not in args                       # 密码**不进命令行** ✓
    assert '--futu-port' in args and '22222' in args
    assert '--theme' in args and 'light' in args
    assert '--offline' in data['argsOffline']
    env = data['env']
    assert env['MINIBT_TQ_PASSWORD'] == 'p1'      # 走环境变量 ✓
    assert env['MINIBT_TQ_USER'] == 'u1'
    assert env['MINIBT_FUTU_PORT'] == '22222'
    assert '期货' in data['status']


def test_desk_module_decide_start_branches():
    code = """
const d = require('./desk');
process.stdout.write(JSON.stringify({
  full: d.decideStart({account: 'u', password: 'p'}),
  noPassword: d.decideStart({account: 'u'}),
  stocks: d.decideStart({futuReachable: true}),
  nothing: d.decideStart({}),
  offline: d.decideStart({offline: true}),
  ready: d.parseReadyLine('{"ready":true,"url":"http://x/"}'),
  garbage: d.parseReadyLine('hello'),
}));
"""
    code_ok, out = _node(code)
    assert code_ok == 0, out
    data = json.loads(out.strip().splitlines()[-1])
    assert data['full']['action'] == 'start' and data['full']['futures']
    assert data['noPassword']['action'] == 'warn'
    assert data['stocks']['action'] == 'start' and data['stocks']['stocks']
    assert data['nothing']['action'] == 'warn'
    assert data['offline']['mode'] == 'offline'
    assert data['ready']['url'] == 'http://x/'
    assert data['garbage'] is None


# ------------------------------------------------------- ③ 扩展贡献点
def test_package_json_contributes_desk():
    pkg = _pkg()
    assert pkg['version'].startswith('0.3.1')
    commands = {item['command'] for item in pkg['contributes']['commands']}
    for name in ('minibt.openDesk', 'minibt.stopDesk',
                 'minibt.desk.setPassword', 'minibt.desk.clearPassword',
                 'minibt.showDeskOutput'):
        assert name in commands, name
    props = pkg['contributes']['configuration']['properties']
    for key in ('minibt.desk.account', 'minibt.desk.password',
                'minibt.desk.futuHost', 'minibt.desk.futuPort',
                'minibt.desk.stocks', 'minibt.desk.offline',
                'minibt.desk.theme', 'minibt.desk.autoStart',
                'minibt.desk.port'):
        assert key in props, key
    # 默认值（Futu 客户端默认地址 ✓）
    assert props['minibt.desk.futuHost']['default'] == '127.0.0.1'
    assert props['minibt.desk.futuPort']['default'] == 11111
    assert props['minibt.desk.autoStart']['default'] is False
    # 标题栏按钮 + 快捷键
    title = {row['command'] for row in pkg['contributes']['menus']['editor/title']}
    assert 'minibt.openDesk' in title
    keys = {row['command']: row['key'] for row in pkg['contributes']['keybindings']}
    assert keys['minibt.openDesk'] == 'ctrl+alt+d'


def test_extension_has_desk_entrypoints():
    source = _ext_source()
    for key in ("require('./desk')", 'async function startDesk(',
                'async function readDeskSettings(', 'async function askDeskStart(',
                'function stopDeskSession(', 'function updateDeskStatus(',
                "registerCommand('minibt.openDesk'", "registerCommand('minibt.desk.setPassword'",
                "secrets.get('minibt.desk.password')",
                "config.get('desk.autoStart', false)",   # 配置键（不带前缀 ✓）
                'createStatusBarItem(',
                "postMessage({ type: 'url', url: url })"):
        assert key in source, key
    # 密码优先 SecretStorage，其次 env，最后 settings ✓
    assert source.index('secrets.get') < source.index('process.env.MINIBT_TQ_PASSWORD')


# ------------------------------------------------------- ④ 端到端（真起子进程）
def _python_path():
    return sys.executable.replace('\\', '\\\\')


@pytest.mark.parametrize('config,expect', [
    ({'desk.offline': True}, {'ok': True, 'offline': True}),
    ({'desk.futuPort': 1}, {'ok': False, 'warn': True}),
])
def test_extension_selftest(config, expect):
    """用假 vscode 跑一遍扩展：离线能起、没配置会弹提醒 ✓"""
    config = dict(config, pythonPath=sys.executable)
    script = str(ROOT / 'tests' / 'helpers' / 'desk_selftest.js')
    if NODE is None:
        pytest.skip('没有 node')
    done = subprocess.run(
        [NODE, script, json.dumps(config, ensure_ascii=False)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=180, cwd=str(ROOT))
    out = (done.stdout or '').strip().splitlines()
    assert out, (done.stdout, done.stderr)
    data = json.loads(out[-1])
    if expect.get('ok'):
        assert data['ok'] is True, data
        assert data['url'].startswith('http://127.0.0.1:')
        assert data['healthz']['ready'] is True
        if expect.get('offline'):
            assert data['healthz']['offline'] is True
    else:
        assert data['warn'] is True, data
        assert 'Futu OpenD' in (data['message'] or '')
        assert data['url'] is None

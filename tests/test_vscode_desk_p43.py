"""P43：浏览器壳静态资源 404（白屏）/ --no-browser / 看盘终端图标 ✓"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXT = ROOT / 'vscode-minibt'


# ------------------------------------------------------- ① 白屏根因：静态资源
def test_static_files_served_at_root():
    """`desk.html` 里是 `./desk.js`（相对路径）→ 请求 `/desk.js` 必须能拿到 ✓

    以前服务端只认 `/static/...` → JS/CSS 全 404 → **浏览器和 VS Code 都白屏** ✗
    """
    source = (ROOT / 'minibt' / 'desk' / 'web.py').read_text(encoding='utf-8')
    assert "name = os.path.basename(path)" in source
    assert "target = os.path.join(STATIC_DIR, name)" in source
    # 不再只匹配 `/static/` 前缀
    assert "if path.startswith('/static/'):" not in source


def test_browser_shell_serves_all_assets(tmp_path):
    """真起一个浏览器壳，逐个取 HTML 里引用的资源 ✓"""
    import os

    log = tmp_path / 'shell.log'
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT))
    handle = open(log, 'w', encoding='utf-8')
    proc = subprocess.Popen(
        [sys.executable, '-m', 'minibt', 'desk', '--browser', '--no-browser',
         '--offline', '--port', '0', '--json'],
        stdout=handle, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
    try:
        base = ''
        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(0.5)
            text = log.read_text(encoding='utf-8', errors='replace')
            for line in text.splitlines():
                if line.strip().startswith('{'):
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    base = data.get('url') or ''
                    break
            if base:
                break
        assert base, '浏览器壳没起来：\n' + log.read_text(
            encoding='utf-8', errors='replace')[-1500:]
        html = urllib.request.urlopen(base, timeout=5).read().decode('utf-8')
        assert 'desk.js' in html
        # HTML 里引用的每个相对资源都必须 200 ✓
        for name in ('desk.js', 'desk.css', 'styles.css',
                     'lightweight-charts.js'):
            with urllib.request.urlopen(base + name, timeout=10) as resp:
                assert resp.status == 200, name
                assert resp.read(), name
        # `/static/` 前缀仍然可用（老用法）✓
        with urllib.request.urlopen(base + 'static/desk.js', timeout=10) as resp:
            assert resp.status == 200
        with urllib.request.urlopen(base + 'healthz', timeout=5) as resp:
            assert json.loads(resp.read().decode())['ready'] is True
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:                                        # noqa: BLE001
            proc.kill()
        handle.close()


# ------------------------------------------------------- ② 不要再弹系统浏览器
def test_no_browser_flag_and_env():
    from minibt.cli import apply_env_defaults, build_parser

    args = build_parser().parse_args(['desk', '--browser', '--no-browser'])
    assert args.no_browser is True
    env_args = build_parser().parse_args(['desk', '--browser'])
    apply_env_defaults(env_args, {'MINIBT_DESK_NO_BROWSER': '1'},
                       ['desk', '--browser'])
    assert env_args.no_browser is True

    app = (ROOT / 'minibt' / 'desk' / 'app.py').read_text(encoding='utf-8')
    assert 'self.open_browser = True' in app
    assert "open_browser=bool(getattr(self, 'open_browser', True))" in app
    cli = (ROOT / 'minibt' / 'cli.py').read_text(encoding='utf-8')
    assert "desk.open_browser = not bool(getattr(args, 'no_browser', False))" \
        in cli


def test_extension_passes_no_browser():
    code = ('const d = require("./desk");'
            'process.stdout.write(JSON.stringify({'
            'args: d.buildDeskArgs({account: "u"}),'
            'env: d.buildDeskEnv({}, {account: "u"})}));')
    done = subprocess.run([__import__('shutil').which('node') or 'node', '-e',
                           code], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', cwd=str(EXT))
    assert done.returncode == 0, done.stderr
    data = json.loads(done.stdout.strip().splitlines()[-1])
    assert '--no-browser' in data['args']          # 扩展托管时不再弹浏览器 ✓
    assert data['env']['MINIBT_DESK_NO_BROWSER'] == '1'


# ------------------------------------------------------- ③ 图标
def test_desk_icon_shared_by_panel_and_button():
    for name in ('desk-light.svg', 'desk-dark.svg'):
        assert (EXT / 'media' / name).is_file(), name
    pkg = json.loads((EXT / 'package.json').read_text(encoding='utf-8'))
    command = next(item for item in pkg['contributes']['commands']
                   if item['command'] == 'minibt.openDesk')
    assert command['icon']['light'] == 'media/desk-light.svg'
    assert command['icon']['dark'] == 'media/desk-dark.svg'
    source = (EXT / 'extension.js').read_text(encoding='utf-8')
    assert 'function deskIcon(context)' in source
    assert 'panel.iconPath = deskIcon(context);' in source

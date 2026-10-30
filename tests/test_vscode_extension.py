"""VS Code 扩展（``vscode-minibt/``）的一致性测试。

这里**不需要**装 VS Code：只检查「清单 / 扩展代码 / Python 运行器」三方一致
（命令、设置项、打包白名单），并在有 Node 的时候顺手校验 JS 语法和进度解析。

0.3.4 起只保留「在编辑器页运行策略图表」：静态快照导出 + MiniQT 结果面板
已删除；并且**不再占用「运行 ▾」（``editor/title/run``）**，免得把 VS Code
原生的运行按钮顶掉/报错。

0.3.5 把它做成编辑器标题栏的**快速按钮**：专属 K 线图标（深浅色 SVG）、
不再限制 ``editorLangId == python``，和 Pi Agent Studio 一样常驻在原生
「运行 ▾」按钮右边的同一行。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / 'vscode-minibt'
MANIFEST = EXT / 'package.json'
EXTENSION_JS = EXT / 'extension.js'
RUNNER = EXT / 'runner' / 'vscode_runner.py'


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


# ------------------------------------------------------------------ 清单/代码
def test_only_run_in_editor_is_kept():
    """0.3.4 只保留「在编辑器页运行策略图表」；另两个功能已删除 ✓。"""
    manifest = _manifest()
    commands = {item['command']: item for item in
                manifest['contributes']['commands']}
    assert 'minibt.runInEditor' in commands
    assert '在编辑器页运行策略图表' in commands['minibt.runInEditor']['title']
    # 删掉的 3 个命令：静态快照导出 ×2 + MiniQT 结果面板
    for gone in ('minibt.exportHtmlInEditor', 'minibt.saveHtmlAs',
                 'minibt.backtestInMiniQT'):
        assert gone not in commands, f'{gone} 应该已删除'
    # 代码里也不能再注册它们
    source = EXTENSION_JS.read_text(encoding='utf-8')
    for gone in ('exportHtmlInEditor', 'saveHtmlAs', 'backtestInMiniQT',
                 'hostRpc', 'callHost', 'exportTo'):
        assert gone not in source, f'{gone} 应该已从 extension.js 删除'


def test_editor_run_button_is_a_quick_button():
    """不能占 ``editor/title/run``（会把 VS Code 原生运行按钮顶掉/报错 ✗）。

    0.3.5 改成编辑器标题栏的**快速按钮**：专属 K 线图标、常驻显示
    （不限制语言），和 Pi Agent Studio 一样排在原生「运行 ▾」右边的同一行。
    """
    menus = _manifest()['contributes']['menus']
    assert 'editor/title/run' not in menus
    title_commands = [item['command'] for item in menus['editor/title']]
    assert 'minibt.runInEditor' in title_commands
    entry = next(item for item in menus['editor/title']
                 if item['command'] == 'minibt.runInEditor')
    # 常驻快速按钮：不能再被语言 ``when`` 挡住（挡住就找不到了）
    assert not entry.get('when')
    # 图标是 MiniBT 专属的 K 线 SVG（深浅色两版），不是通用 codicon
    command = next(item for item in _manifest()['contributes']['commands']
                   if item['command'] == 'minibt.runInEditor')
    icon = command['icon']
    assert set(icon) == {'light', 'dark'}
    for key in ('light', 'dark'):
        assert (EXT / icon[key]).exists(), f'缺少图标 {icon[key]}'


def test_extension_folder_is_complete():
    for path in (MANIFEST, EXTENSION_JS, RUNNER, EXT / 'README.md',
                 EXT / 'PUBLISHING.md', EXT / 'LICENSE',
                 EXT / 'media' / 'icon.png',
                 EXT / 'media' / 'run-light.svg',
                 EXT / 'media' / 'run-dark.svg'):
        assert path.exists(), f'缺少 {path.relative_to(EXT)}'


def test_every_declared_command_is_registered():
    declared = {item['command'] for item in _manifest()['contributes']['commands']}
    registered = set(re.findall(r"registerCommand\('([\w.]+)'",
                                EXTENSION_JS.read_text(encoding='utf-8')))
    assert declared == registered


def test_every_setting_is_declared_and_used():
    keys = set(_manifest()['contributes']['configuration']['properties'])
    js = EXTENSION_JS.read_text(encoding='utf-8')
    # 只看 ``minibt`` 命名空间：``config`` 就是 ``getConfiguration('minibt')``，
    # 另有一处直接 ``getConfiguration('minibt').get(...)``。不能一把抓所有
    # ``get('...')`` —— 代码里还会读 ``getConfiguration('python')
    # .get('defaultInterpreterPath')``（那是 Python 扩展的设置、不是本扩展的）✗
    # 设置名里可能带点（`desk.account` / `desk.futuPort` …）✓
    used = {'minibt.' + name
            for name in re.findall(r"config\.get\('([\w.]+)'", js)}
    used |= {'minibt.' + name for name in re.findall(
        r"getConfiguration\('minibt'\)\s*\.get\('([\w.]+)'", js)}
    assert used <= keys, f'代码里读了没声明的设置：{sorted(used - keys)}'
    assert keys <= used, f'声明了代码没用到的设置：{sorted(keys - used)}'


def test_chart_panel_enables_scripts():
    """图表页签必须 `enableScripts: true`。

    VS Code webview 的 sandbox 标志会被**子 iframe 继承**：关掉脚本后，iframe
    里的图表 JS（顶栏、K 线、bokeh 页面全是 JS 画的）全被拦掉，页面只剩黑色
    背景 —— 就是那个"能打开但一片漆黑"的 bug。这里守住它。
    """
    js = EXTENSION_JS.read_text(encoding='utf-8')
    assert 'enableScripts: true' in js
    assert 'enableScripts: false' not in js


def test_start_does_not_auto_open_output_panel():
    """运行时不能自动打开底部「输出」面板。

    以前 `start()` 里调 `channel.show(true)`，日志既在「MiniBT 策略日志」页签、
    又在底部输出面板各显示一份（用户反馈重复 ✗）。现在只在编辑器页签显示；
    输出面板仍可用命令「显示策略输出（原始日志）」手动打开。
    """
    js = EXTENSION_JS.read_text(encoding='utf-8')
    assert 'channel.show(' not in js
    # 手动打开输出面板的命令保留
    assert 'getOutput().show(true)' in js


def test_packaging_keeps_the_python_runner():
    """`.vscodeignore` 不能把 runner/ 排除掉（进了包扩展才能跑）。"""
    ignored = (EXT / '.vscodeignore').read_text(encoding='utf-8')
    lines = {line.strip() for line in ignored.splitlines()
             if line.strip() and not line.startswith('#')}
    assert 'runner' not in lines and 'runner/**' not in lines
    assert '**/runner/**' not in lines


def test_runner_compiles():
    import py_compile

    py_compile.compile(str(RUNNER), doraise=True)


def test_runner_declares_the_documented_cli():
    text = RUNNER.read_text(encoding='utf-8')
    for flag in ('--engine', '--port', '--cwd', '--open', '--theme'):
        assert f"'{flag}'" in text, f'运行器少了 {flag}'
    # 静态导出模式已删除（0.3.4 ✓）
    assert '--export-html' not in text
    assert "'auto'" in text and '_resolve_btplot_gui' in text
    for marker in ('MINIBT_URL=', 'MINIBT_HTML='):
        assert marker in text


# ----------------------------------------------------------------------- Node
def _node_available() -> bool:
    return shutil.which('node') is not None


@pytest.mark.skipif(not _node_available(), reason='没有 node')
def test_extension_syntax():
    result = subprocess.run(['node', '--check', str(EXTENSION_JS)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _extract_function(source: str, name: str) -> str:
    """按大括号配对，从 `extension.js` 里抠出一个函数（用于单独测逻辑）。"""
    start = source.index(f'function {name}(')
    index = source.index('{', start)
    depth = 0
    for position in range(index, len(source)):
        if source[position] == '{':
            depth += 1
        elif source[position] == '}':
            depth -= 1
            if depth == 0:
                return source[start:position + 1]
    raise AssertionError(f'找不到 {name} 的结尾')


@pytest.mark.skipif(not _node_available(), reason='没有 node')
def test_activate_registers_every_command(tmp_path):
    """用假的 `vscode` 模块跑一遍 activate，确认命令都注册上、不抛异常。"""
    manifest = _manifest()
    declared = sorted(item['command'] for item in manifest['contributes']['commands'])
    mock_dir = tmp_path / 'node_modules' / 'vscode'
    mock_dir.mkdir(parents=True)
    (mock_dir / 'index.js').write_text(MOCK_VSCODE, encoding='utf-8')
    (mock_dir / 'package.json').write_text(
        json.dumps({'name': 'vscode', 'version': '0.0.0', 'main': 'index.js'}),
        encoding='utf-8')
    shutil.copyfile(EXTENSION_JS, tmp_path / 'extension.js')
    # 看盘终端的纯逻辑模块（`extension.js` 里 `require('./desk')` ✓）
    shutil.copyfile(EXT / 'desk.js', tmp_path / 'desk.js')
    shutil.copyfile(MANIFEST, tmp_path / 'package.json')   # 扩展会读它取版本号
    (tmp_path / 'run.js').write_text(
        chr(10).join([
            "const ext = require('./extension.js');",
            'const context = { subscriptions: [], extensionPath: __dirname,',
            '  secrets: { get: async () => undefined, store: async () => {},',
            '             delete: async () => {} },',
            '  globalState: { get: (key, fallback) => fallback,',
            '                 update: async () => {} } };',
            'ext.activate(context);',
            'const registered = global.__registered__ || [];',
            'console.log(JSON.stringify(registered));',
            # 每个命令都登记到 subscriptions；状态栏等别的东西也会登记，
            # 所以只要求「不少于注册的命令数」✓
            'if (context.subscriptions.length < registered.length) {',
            "  console.error('订阅数偏少'); process.exit(1);",
            '}',
            'ext.deactivate();',
        ]), encoding='utf-8')
    # Windows 下 `text=True` 用 GBK 解码 → node 输出里的中文会炸掉 reader 线程
    # （stdout/stderr 变成 None，报一句莫名其妙的 TypeError ✗）
    result = subprocess.run(['node', str(tmp_path / 'run.js')],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace',
                            cwd=str(tmp_path))
    assert result.returncode == 0, (result.stdout or '') + (result.stderr or '')
    registered = json.loads(result.stdout.strip().splitlines()[-1])
    assert sorted(registered) == declared


MOCK_VSCODE = '''
const registered = [];
global.__registered__ = registered;
const disposable = () => ({ dispose() {} });
const webview = () => ({
  html: '',
  postMessage: async () => true,
  onDidReceiveMessage: () => disposable(),
  asWebviewUri: (uri) => uri,
  cspSource: 'vscode-webview://test',
});
module.exports = {
  commands: {
    registerCommand: (id) => { registered.push(id); return disposable(); },
    executeCommand: async () => undefined,
  },
  window: {
    activeTextEditor: undefined,
    createOutputChannel: () => Object.assign(disposable(), {
      append() {}, appendLine() {}, clear() {}, show() {},
    }),
    createWebviewPanel: () => Object.assign(disposable(), {
      webview: webview(), title: '', iconPath: null,
      reveal() {}, onDidDispose: () => disposable(),
    }),
    showOpenDialog: async () => undefined,
    showSaveDialog: async () => undefined,
    showInformationMessage() {}, showWarningMessage() {}, showErrorMessage() {},
    showInputBox: async () => undefined,
    activeColorTheme: { kind: 2 },
    // 状态栏「MiniBT 看盘」（看盘终端用 ✓）
    createStatusBarItem: () => Object.assign(disposable(), {
      name: '', text: '', tooltip: '', command: '', show() {}, hide() {},
    }),
  },
  workspace: {
    workspaceFolders: [{ uri: { fsPath: process.cwd() } }],
    getConfiguration: () => ({ get: (key, fallback) => fallback }),
  },
  ViewColumn: { Active: 1, Beside: -2, One: 1 },
  StatusBarAlignment: { Left: 1, Right: 2 },
  ConfigurationTarget: { Global: 1, Workspace: 2, WorkspaceFolder: 3 },
  ThemeIcon: class { constructor(id) { this.id = id; } },
  Uri: { file: (p) => ({ fsPath: p }), parse: (u) => ({ fsPath: u }) },
  env: { openExternal: async () => true },
};
'''


@pytest.mark.skipif(not _node_available(), reason='没有 node')
def test_progress_parser_reads_minibt_output(tmp_path):
    """进度解析要认得 bokeh 的「进度 x/y」、tqdm 的百分比、[i/n]。"""
    source = EXTENSION_JS.read_text(encoding='utf-8')
    cases = [
        ('  进度 3/10  ', 30.0, None),
        (' 37%|███ | 37/100 [00:01<00:02]', 37.0, None),
        ('[2/4] 回测中', 50.0, None),
        ('DCE.v2601 tick', None, None),
    ]
    lines = [_extract_function(source, 'parseProgress'), 'const cases = [']
    for text, percent, _ in cases:
        wanted = 'null' if percent is None else repr(percent)
        lines.append('  [%s, %s],' % (json.dumps(text), wanted))
    lines += [
        '];',
        "for (const [text, want] of cases) {",
        '  const got = parseProgress(text);',
        '  const value = got ? Math.round(got.percent * 100) / 100 : null;',
        "  if (value !== want) { console.error('失败:', text, value, want);"
        ' process.exit(1); }',
        '}',
        "console.log('ok');",
    ]
    script = tmp_path / 'progress.js'
    script.write_text(chr(10).join(lines), encoding='utf-8')
    result = subprocess.run(['node', str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_engine_setting_defaults_to_auto():
    """默认 `auto`：跟随策略里写的 gui。"""
    props = _manifest()['contributes']['configuration']['properties']
    engine = props['minibt.engine']
    assert engine['default'] == 'auto'
    assert set(engine['enum']) == {'auto', 'pylightcharts', 'bokeh'}


def test_open_beside_defaults_to_false():
    """图表/日志默认与代码同一页签组（不拆分页面），`openBeside=false`。"""
    props = _manifest()['contributes']['configuration']['properties']
    assert props['minibt.openBeside']['default'] is False


def test_stop_hotkey_is_declared():
    """图表页里 `Ctrl+C` 停止策略进程（键绑定 + MINIBT_STOP 信令）。"""
    keybindings = _manifest()['contributes']['keybindings']
    stop = [item for item in keybindings
            if item['command'] == 'minibt.stopChart']
    assert stop, 'minibt.stopChart 需要一键绑定'
    entry = stop[0]
    assert entry['key'] == 'ctrl+c'
    assert entry.get('mac') == 'cmd+c'
    # 只在图表 webview 页签激活时生效，不能抢代码编辑器的 Ctrl+C
    assert 'activeWebviewPanelId' in entry['when']
    assert 'minibtChart' in entry['when']
    js = EXTENSION_JS.read_text(encoding='utf-8')
    assert 'MINIBT_STOP' in js                 # 认 runner 的信令
    assert "type: 'stop'" in js                # 外壳转发


def test_run_keybinding_avoids_code_runner_conflict():
    """运行策略的主快捷键不能用 `Ctrl+Alt+M`（Code Runner 占着它）。

    Code Runner 的 `code-runner.stop` 无条件绑定了 `Ctrl+Alt+M`；VS Code 的
    键绑定解析器会让这个后注册的无条件绑定移除我们的有条件绑定，于是热键失灵 ✗。
    所以主键改用无冲突的 `Ctrl+Alt+B`，`Ctrl+Alt+M` 只作备用保留。
    """
    keybindings = _manifest()['contributes']['keybindings']
    run_keys = {item['key'] for item in keybindings
                if item['command'] == 'minibt.runInEditor'}
    assert 'ctrl+alt+b' in run_keys
    assert 'ctrl+alt+m' in run_keys


def test_stop_session_closes_both_tabs():
    """Ctrl+C / 停止按钮要**关掉**图表页和日志页，而不是只写“已停止”。"""
    js = EXTENSION_JS.read_text(encoding='utf-8')
    body = _extract_function(js, 'stopSession')
    assert 'dispose()' in body
    assert 'session.panel' in body and 'session.logPanel' in body
    # 不再只把内容换成那段“已停止”的 HTML
    assert '策略进程已结束' not in body
    # ★ 顺序：先停服务（stopChildProcess），再关页面（dispose）
    assert 'stopChildProcess(child)' in body
    assert body.index('stopChildProcess(child)') < body.index('target.dispose()')


def test_runner_injects_stop_hotkey(capsys):
    """runner 把 Ctrl+C 注到图表页内部，按下后打印 MINIBT_STOP。"""
    module = _runner_module()

    class FakeWin:
        def __init__(self):
            self.handlers = {}

    class FakeChart:
        def __init__(self):
            self.win = FakeWin()
            self.scripts = []

        def run_script(self, script, run_last=False):
            self.scripts.append(script)

    chart = FakeChart()
    module._install_stop_hotkey(chart)
    handler = chart.win.handlers.get(module._STOP_CALLBACK)
    assert handler is not None
    handler()                                  # 要能吃下 *args 调用
    assert 'MINIBT_STOP' in capsys.readouterr().out
    script = '\n'.join(chart.scripts)
    assert 'keydown' in script
    assert 'callbackFunction' in script
    assert module._STOP_CALLBACK in script


@pytest.mark.skipif(not _node_available(), reason='没有 node')
def test_runner_stop_hotkey_script_is_valid_js(tmp_path):
    """注入的 Ctrl+C 脚本必须合法。

    历史 bug：拼字符串时多了一个 `}`，导致图表页**整段** `<script>` 解析失败
    —— 表现就是“图是黑的、右下角还显示 live · N”（用户反馈 ✗）。
    """
    module = _runner_module()

    class FakeWin:
        handlers = {}

    class FakeChart:
        win = FakeWin()
        scripts = []

        def run_script(self, script, run_last=False):
            self.scripts.append(script)

    chart = FakeChart()
    module._install_stop_hotkey(chart)
    path = tmp_path / 'hotkey.js'
    path.write_text(chart.scripts[0], encoding='utf-8')
    result = subprocess.run(['node', '--check', str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not _node_available(), reason='没有 node')
def test_panel_column_stays_in_the_code_group(tmp_path):
    """★ 默认不能拆分：回到命令发起时的代码列，而不是会漂移的 `Active`。

    历史 bug：日志页签先用 `Beside` 打开，`active` 列随之变成右边；图表再用
    `ViewColumn.Active` 打开也跟着跑到右边，整个编辑区被拆成左右两半 ✗。
    """
    source = EXTENSION_JS.read_text(encoding='utf-8')
    fn = _extract_function(source, 'panelColumn')
    script = tmp_path / 'column.js'
    script.write_text(
        "const vscode = { ViewColumn: { Active: -1, Beside: -2, One: 1 },\n"
        "  workspace: { getConfiguration: () => ({ get: (k, d) => "
        "globalThis.__beside }) } };\n"
        "let session = { column: 7 };\n"
        + fn + '\n'
        "globalThis.__beside = false;\n"
        "if (panelColumn() !== 7) { console.error('editor 模式应回代码列');"
        ' process.exit(1); }\n'
        "globalThis.__beside = true;\n"
        "if (panelColumn() !== -2) { console.error('beside 模式应分屏');"
        ' process.exit(1); }\n'
        'session = null;\n'
        'globalThis.__beside = false;\n'
        "if (panelColumn() !== 1) { console.error('无 session 回 One');"
        ' process.exit(1); }\n'
        "console.log('ok');\n",
        encoding='utf-8')
    result = subprocess.run(['node', str(script)], capture_output=True,
                            text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def _runner_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location('vscode_runner_probe', RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_prefers_local_minibt_from_a_parent_dir(tmp_path, monkeypatch):
    """脚本在 tutorials/ 时，应向上找到仓库根的 minibt（当前目录优先 ✓）。"""
    runner = _runner_module()
    repo = tmp_path / 'repo'
    pkg = repo / 'minibt'
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text('__version__ = "9.9.9"\n', encoding='utf-8')
    script = repo / 'tutorials' / 'test.py'
    script.parent.mkdir()
    script.write_text('', encoding='utf-8')
    monkeypatch.setattr(runner.sys, 'path', list(runner.sys.path))
    chosen = runner._prefer_local_minibt(str(script), str(script.parent))
    assert chosen == str(repo)
    assert runner.sys.path[0] == str(repo)


def test_runner_falls_back_to_the_installed_minibt(tmp_path, monkeypatch):
    """当前目录没有 minibt → 返回 None，交给 site-packages ✓。"""
    runner = _runner_module()
    script = tmp_path / 'test.py'
    script.write_text('', encoding='utf-8')
    monkeypatch.setattr(runner.sys, 'path', list(runner.sys.path))
    assert runner._prefer_local_minibt(str(script), str(tmp_path)) is None


def test_runner_main_prefers_local_minibt():
    text = RUNNER.read_text(encoding='utf-8')
    assert '_prefer_local_minibt(script, workdir)' in text
    assert "'minibt', '__init__.py'" in text


def test_runner_tolerates_old_minibt_without_resolve_theme(monkeypatch, capsys):
    """旧版 minibt（无 resolve_theme）不能让建图整体失败 —— 跳过主题接管即可 ✓。"""
    import types

    runner = _runner_module()
    fake_minibt = types.ModuleType('minibt')
    fake_utils = types.ModuleType('minibt.utils')
    fake_minibt.utils = fake_utils
    monkeypatch.setitem(sys.modules, 'minibt', fake_minibt)
    monkeypatch.setitem(sys.modules, 'minibt.utils', fake_utils)
    runner._patch_theme('dark')          # 不应抛
    assert 'resolve_theme' in capsys.readouterr().err


def test_runner_prefers_the_script_directory_over_the_workspace():
    """脚本目录要优先于 VS Code 工作区根目录（否则会用到工作区里的旧 minibt ✗）。"""
    text = RUNNER.read_text(encoding='utf-8')
    assert 'for entry in (workdir, os.path.dirname(script)):' in text
    assert 'pip install -U minibt' in text


def test_gui_mapping_follows_the_strategy():
    """auto：`Gui.Bokeh` → bokeh；原生 / 网页版 / 没写 → pylightcharts 网页版。"""
    map_gui = _runner_module()._map_gui
    assert map_gui('bokeh', 'auto') == 'bokeh'
    assert map_gui('pylightcharts', 'auto') == 'pylightcharts_web'
    assert map_gui('pylightcharts_web', 'auto') == 'pylightcharts_web'
    assert map_gui(None, 'auto') == 'pylightcharts_web'
    # 显式指定引擎时覆盖策略里的写法
    assert map_gui('bokeh', 'pylightcharts') == 'pylightcharts_web'
    assert map_gui('pylightcharts', 'bokeh') == 'bokeh'

    class FakeGui:                      # 模拟 Gui.Bokeh（枚举）
        value = 'bokeh'

    assert map_gui(FakeGui, 'auto') == 'bokeh'


def test_btplot_gui_is_remapped_too(tmp_path):
    """btplot 的 gui 走同一条映射（子进程里跑，不污染本进程的 minibt）。"""
    pytest.importorskip('minibt')
    root = str(Path(__file__).resolve().parents[1])
    lines = [
        'import importlib.util, sys, threading',
        'spec = importlib.util.spec_from_file_location("vr", %r)' % str(RUNNER),
        'vr = importlib.util.module_from_spec(spec)',
        'spec.loader.exec_module(vr)',
        'sys.path.insert(0, %r)' % root,
        'vr._patch_minibt("auto", 0, "", {"done": threading.Event()})',
        'module = sys.modules["minibt.btplot"]',
        'print(module._resolve_btplot_gui("bokeh"),',
        '      module._resolve_btplot_gui("pylightcharts"),',
        '      module._resolve_btplot_gui(None))',
    ]
    script = tmp_path / 'probe.py'
    script.write_text(chr(10).join(lines), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=root)
    result = subprocess.run([sys.executable, str(script)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.split()[-3:] == ['bokeh', 'pylightcharts_web',
                                          'pylightcharts_web']


def test_library_theme_defaults_to_light():
    """非扩展：theme 没设置 → 浅色；显式指定则按用户的来（点 3）。"""
    pytest.importorskip('minibt')
    from minibt.utils import resolve_theme, theme_is_dark

    assert resolve_theme(None) == 'light'
    assert theme_is_dark(None) is False
    assert resolve_theme('dark') == 'dark'


def test_extension_theme_follows_vscode_when_unset():
    """扩展：theme=None 用 VS Code 主题；显式指定则原样（点 4）。"""
    pytest.importorskip('minibt')
    import minibt.utils as mu

    module = _runner_module()
    original = mu.resolve_theme
    try:
        module._patch_theme('dark')
        assert mu.resolve_theme(None) == 'dark'
        assert mu.resolve_theme('light') == 'light'
        assert mu.resolve_theme('dark') == 'dark'
        assert mu.resolve_theme(None, black_style=False) == 'light'
        assert mu.resolve_theme(None, black_style=True) == 'dark'
    finally:
        mu.resolve_theme = original           # 别污染其它测试


def test_bokeh_watcher_ignores_stale_temp_files(tmp_path):
    """上一次运行留下的 `minibt_bokeh_*.html` 不能被当成本次结果。"""
    import os
    import time

    module = _runner_module()
    old = tmp_path / 'minibt_bokeh_9999.html'
    old.write_text('x' * 9000, encoding='utf-8')
    new = tmp_path / 'minibt_bokeh_1234.html'
    new.write_text('y' * 9000, encoding='utf-8')
    then = time.time() - 5000
    os.utime(old, (then, then))
    os.utime(new, (time.time(), time.time()))
    module._RUN_SINCE = time.time() - 60
    assert module._find_bokeh_html(str(tmp_path)) == str(new)


"""VS Code 扩展的 Python 侧入口：把 minibt 策略的图表切到可嵌入的形态。

扩展（``extension.js``）用子进程跑本文件：

    # 运行（本地 SSE 服务 + iframe，实时刷新）
    python -u runner/vscode_runner.py <策略.py> --engine pylightcharts --port 0

    # bokeh 引擎（回放 / 实时用 bokeh server）
    python -u runner/vscode_runner.py <策略.py> --engine bokeh --port 0

它做这几件事：

1. 挑一个空闲端口（``--port 0`` 时），把工作目录 / 脚本目录放进 ``sys.path``；
2. 屏蔽浏览器弹窗，并把 ``Bt.run`` 的 ``gui`` 强制成可嵌入的引擎
   （``pylightcharts`` 网页版，或 ``bokeh``），端口一并传进去；
3. 等图表真的开始服务了，把它**自己用的**地址打印成
   ``MINIBT_URL=http://127.0.0.1:<port>/``（不猜端口：btplot 会另挑端口），
   然后保持进程存活（否则本地服务随进程退出，页签里的图表就白了），由扩展在
   页签关闭时结束本进程；静态图（如 btplot 的快速出图）没有服务，改报
   ``MINIBT_HTML=<文件>``；bokeh 的静态回测同样由看门狗线程报 ``MINIBT_HTML=``。

> 0.3.4 起**删除了静态快照导出**（多合约回测不能切合约）+ MiniQT 结果面板
> （与 MiniQT 自带回测按钮重复），只保留「在编辑器页运行策略图表」✓。

为什么不能把"纯 pylightcharts（原生窗口）"嵌进 VS Code：那是一个 PyQt6 + WebView2
的独立操作系统窗口，VS Code 的 webview 装不下；网页版用的是同一套
lightweight-charts + pylightcharts bundle，画出来的图完全一致。
"""
from __future__ import annotations

import argparse
import glob
import os
import runpy
import socket
import sys
import tempfile
import threading
import time
import webbrowser

#: 本次运行的开始时间（过滤掉上一次运行留下的旧 bokeh 临时文件）
_RUN_SINCE = 0.0


def free_port() -> int:
    """让系统分配一个空闲端口（绑到 0 看系统给了什么，然后立刻释放）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def parse_args(argv):
    parser = argparse.ArgumentParser(description='在 VS Code 里跑 minibt 策略图表')
    parser.add_argument('script', help='策略脚本（.py）')
    parser.add_argument('--engine', default='auto',
                        choices=['auto', 'pylightcharts', 'bokeh'],
                        help='auto（默认，跟随策略里的 gui）/ 强制 pylightcharts 网页版 / 强制 bokeh')
    parser.add_argument('--theme', default='',
                        help="扩展传入的 VS Code 主题（light/dark）；用户没显式指定时当默认主题")
    parser.add_argument('--port', type=int, default=0,
                        help='本地服务端口；0 = 自动挑一个空闲端口')
    parser.add_argument('--cwd', default='', help='工作目录（默认脚本所在目录）')
    parser.add_argument('--open', action='store_true',
                        help='额外用系统浏览器打开（默认只交给 VS Code 嵌入）')
    return parser.parse_args(argv)


#: 图表页里 Ctrl+C 的回调名（扩展侧不解析，只认 runner 打印的 MINIBT_STOP）
_STOP_CALLBACK = 'minibt_stop'


def _install_stop_hotkey(chart) -> None:
    """把 ``Ctrl+C`` → 停策略进程的热键**注入到图表页本身**。

    ★ 图表是嵌在 VS Code webview 里的一个**跨域 iframe**：父页面（扩展的外壳）
    收不到 iframe 里的按键，VS Code 的 webview 键绑定也进不去 ✗。所以只能在
    图表页内部挂监听器；按下 Ctrl+C 时走 pylightcharts 现成的
    ``callbackFunction`` 通道（POST /callback）回调 Python，再打印
    ``MINIBT_STOP``，扩展看到就把策略进程停掉 ✓。
    """
    try:
        chart.win.handlers[_STOP_CALLBACK] = (
            lambda *_a, **_k: print('MINIBT_STOP', flush=True))
    except Exception:                             # 没桥也不影响图
        pass
    script = (
        ";(function(){"
        "if (window.__minibtStopHotkey) return;"
        "window.__minibtStopHotkey = true;"
        "window.addEventListener('keydown', function(e){"
        "if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')) {"
        "e.preventDefault(); e.stopPropagation();"
        "try { if (window.callbackFunction) "
        f"window.callbackFunction('{_STOP_CALLBACK}_~_'); }}"
        "catch (err) {}"
        "}}"
        ", true);"
        "})();"
    )
    try:
        chart.run_script(script)                 # show() 前 → 进页面 _html
    except Exception:
        pass


# --------------------------------------------------------------------- 引擎补丁
def _patch_pylightcharts() -> None:
    """pylightcharts：统一成网页版**活图**（可嵌进 VS Code）✓。"""
    from pylightcharts.widgets import BrowserChart

    original_show = BrowserChart.show

    def show(self, block=None, path=None, open_browser=None, port=None):
        # 先注入 Ctrl+C 热键（此刻还没 streaming，run_script 会进页面 HTML）
        if not getattr(self, '_minibt_stop_hotkey', False):
            self._minibt_stop_hotkey = True
            _install_stop_hotkey(self)
        # 图要嵌在 VS Code 里，绝不弹系统浏览器
        # 先**不阻塞**：拿到图表真正用的 URL（或静态页面路径）报给扩展，再自己
        # 阻塞。为什么不能自己猜端口：`btplot` 那条路根本不会把我们挑好的端口
        # 传进来，图表会自己另挑一个 —— 猜出来的 URL 必然连不上
        # （ERR_CONNECTION_REFUSED）；静态图（live=False）更是压根没有服务。
        want_block = block is not False and bool(getattr(self, 'live', False))
        result = original_show(self, block=False, path=path,
                               open_browser=False, port=port)
        if isinstance(result, str):
            if result.startswith('http'):
                print(f'MINIBT_URL={result}', flush=True)
            elif result.endswith('.html'):
                # 静态图没有服务，但它写出了自包含页面：报给扩展，让它开一个
                # 快照页签，而不是一个连不上的 iframe。
                print(f'MINIBT_HTML={result}', flush=True)
        if want_block:
            server = getattr(self, '_server', None)
            if server is not None:
                try:
                    while getattr(server, 'running', False):
                        time.sleep(0.2)
                except KeyboardInterrupt:
                    pass
        return result

    BrowserChart.show = show                      # type: ignore[method-assign]

    # 所有走 RealtimeChart 的路径（Bt.run 的回测 / 实时、btplot 快速出图、
    # 回测展示）统一变成"网页版活图"：btplot 里写死了 `live=False`（只写文件、
    # 不起服务），不接管就会出现"有 URL 但没有服务"的连接被拒。
    from minibt.strategy.realtime import RealtimeChart

    original_chart_init = RealtimeChart.__init__

    def chart_init(self, *args, **kwargs):
        kwargs['browser'] = True
        kwargs['live'] = True
        return original_chart_init(self, *args, **kwargs)

    RealtimeChart.__init__ = chart_init           # type: ignore[method-assign]


def _patch_bokeh(hooks: dict, verbose: bool = False) -> None:
    """bokeh：不弹浏览器；server 真的起来后把**真实地址**报给扩展。"""
    # 图表被嵌在 VS Code 的 webview 里，WebSocket 的 Origin 不是 localhost
    # （是 vscode-webview://... 或 null），bokeh 默认白名单会把它拒掉。
    os.environ.setdefault('BOKEH_ALLOW_WS_ORIGIN', '*')
    try:
        import bokeh.server.server as _server_module

        original_server = _server_module.Server

        def Server(*a, **k):                      # noqa: N802
            k.setdefault('allow_websocket_origin', ['*'])
            port = k.get('port')
            server = original_server(*a, **k)
            if port:
                original_start = server.start

                def start(*sa, **sk):
                    result = original_start(*sa, **sk)
                    # 监听了才报地址：bokeh 的回测根本没有 server，不能瞎报
                    print(f'MINIBT_URL=http://127.0.0.1:{port}/', flush=True)
                    return result

                server.start = start              # type: ignore[method-assign]
            return server

        Server.show = lambda *a, **k: None        # type: ignore[attr-defined]
        _server_module.Server = Server            # type: ignore[assignment]
    except Exception as error:                    # noqa: BLE001
        if verbose:
            print(f'[minibt] 准备 bokeh server 失败：{error}', file=sys.stderr)

    def watch() -> None:
        """bokeh 静态回测会把自包含 HTML 写进临时文件，发现后报给扩展。"""
        tmp = tempfile.gettempdir()
        seen: dict = {}
        deadline = time.time() + 6 * 3600
        while not hooks['done'].is_set() and time.time() < deadline:
            time.sleep(0.4)
            path = _find_bokeh_html(tmp)
            if not path:
                continue
            try:
                stamp = os.path.getmtime(path)
            except OSError:
                continue
            if seen.get(path) != stamp:      # 同名文件被重写也要重新报
                seen[path] = stamp
                print(f'MINIBT_HTML={path}', flush=True)

    threading.Thread(target=watch, daemon=True).start()


def _find_bokeh_html(tmp: str) -> str:
    """本次进程写出的 bokeh 页面（大小稳定 = 写完，且是本次运行新写的）。"""
    candidates = [os.path.join(tmp, f'minibt_bokeh_{os.getpid()}.html')]
    candidates += sorted(glob.glob(os.path.join(tmp, 'minibt_bokeh_*.html')),
                         key=os.path.getmtime, reverse=True)
    for path in candidates:
        try:
            if os.path.getmtime(path) < _RUN_SINCE:
                continue                     # 上一次运行留下的旧文件，跳过
            size = os.path.getsize(path)
        except OSError:
            continue
        time.sleep(0.2)
        try:
            if size > 4096 and os.path.getsize(path) == size:
                return path
        except OSError:
            continue
    return ''


def _map_gui(value, engine: str) -> str:
    """把策略里写的 ``gui`` 映射成**能嵌进 VS Code**的引擎。

    * ``--engine bokeh`` / ``--engine pylightcharts`` 直接强制；
    * ``--engine auto``（默认）**跟随策略**：``Gui.Bokeh`` → bokeh；
      ``Gui.Pylightcharts`` / ``Gui.PylightchartsWeb`` / 没写 → 网页版
      （原生窗口是独立操作系统窗口，嵌不进 webview；网页版是同一个渲染器）。
    """
    if engine == 'bokeh':
        chosen = 'bokeh'
    elif engine == 'pylightcharts':
        chosen = 'pylightcharts_web'
    else:
        name = str(getattr(value, 'value', value) or '').strip().lower()
        chosen = 'bokeh' if name == 'bokeh' else 'pylightcharts_web'
    label = getattr(value, 'value', value)
    label = str(label).strip() if label else '（未指定）'
    print(f'[minibt] gui={label} → {chosen}（engine={engine}）', flush=True)
    return chosen


def _patch_theme(vscode_theme: str) -> None:
    """扩展模式：用户没显式传 theme / black_style 时，用 VS Code 的主题。

    `minibt` 里所有图表（Bt.run / btplot / bokeh / 实时）最终都经
    `minibt.utils.resolve_theme` 解析主题（而且都是函数内导入、晚绑定），
    所以在这里包一层就全覆盖；用户显式传了 theme / black_style 则原样放行。
    """
    if not vscode_theme:
        return
    import minibt.utils as _utils

    original = getattr(_utils, 'resolve_theme', None)
    if original is None:
        # ★ 旧版 minibt（如 1.2.6）没有 resolve_theme —— 不能因为它把整个
        #   建图流程搞崩 ✗。跳过“跟随 VS Code 主题”即可，图表照常出（用
        #   策略自己的默认主题）。升级 minibt（>=1.3.x）后自动恢复 ✓。
        print('[minibt] 当前 minibt 版本较旧（缺少 minibt.utils.resolve_theme），'
              '跳过“跟随 VS Code 主题”；图表仍会正常显示。', file=sys.stderr)
        return

    def resolve_theme(theme=None, black_style=None, strategy=None,
                      default: str = 'light'):
        if theme is None and black_style is None:
            return vscode_theme
        return original(theme, black_style, strategy, default)

    _utils.resolve_theme = resolve_theme        # type: ignore[assignment]


def _patch_minibt(engine: str, port: int,
                  hooks: dict, vscode_theme: str = '') -> None:
    from minibt import Bt

    original_run = Bt.run

    def run(self, *a, **kwargs):
        # 跟随策略里写的 gui（Gui.Bokeh → bokeh；原生 / 网页版 → 网页版）。
        kwargs['gui'] = _map_gui(kwargs.get('gui'), engine)
        kwargs['port'] = port
        return original_run(self, *a, **kwargs)

    Bt.run = run                                  # type: ignore[method-assign]
    _patch_theme(vscode_theme)

    # `btplot` 的 gui 有一个统一出入口 `_resolve_btplot_gui`，在它上面挂映射
    # 就能覆盖 btplot 的所有调用方式（模块函数 / 访问器方法 / 指标对象方法）。
    try:
        import minibt.btplot                    # noqa: F401

        module = sys.modules['minibt.btplot']
        original_resolve = module._resolve_btplot_gui

        def resolve(gui=None):
            return _map_gui(original_resolve(gui), engine)

        module._resolve_btplot_gui = resolve     # type: ignore[assignment]
    except Exception as error:                   # noqa: BLE001
        print(f'[minibt] 接管 btplot 的 gui 失败：{error}', file=sys.stderr)

    # 两边都装上：auto 模式下由策略自己决定走哪个引擎。
    _patch_pylightcharts()
    _patch_bokeh(hooks, verbose=engine == 'bokeh')


def _find_local_minibt(script: str, workdir: str) -> str | None:
    """从脚本目录 / 工作区**逐级向上**找含 ``minibt/__init__.py`` 的目录。

    这样 ``tutorials/test.py`` 也能用仓库根的 ``minibt``（当前目录的上一级），
    而不是只看脚本目录本身 ✓。
    """
    roots: list[str] = []
    for start in (os.path.dirname(script), workdir):
        current = os.path.abspath(start)
        while True:
            if current not in roots:
                roots.append(current)
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    for folder in roots:
        if os.path.isfile(os.path.join(folder, 'minibt', '__init__.py')):
            return folder
    return None


def _prefer_local_minibt(script: str, workdir: str) -> str | None:
    """优先使用本地 minibt；没有才回退到解释器里安装的 minibt（site-packages）。

    用户要求：当前目录有 minibt 就用当前目录的；当前目录没有，才用系统安装的。
    本地目录放在 ``sys.path[0]``，因此会压过 site-packages ✓。
    """
    folder = _find_local_minibt(script, workdir)
    if folder is None:
        print('[minibt] 本地（脚本目录 / 工作区 / 上级目录）没有 minibt，'
              '改用解释器里安装的 minibt', flush=True)
        return None
    try:
        sys.path.remove(folder)
    except ValueError:
        pass
    sys.path.insert(0, folder)
    print(f'[minibt] 使用本地 minibt：{os.path.join(folder, "minibt")}',
          flush=True)
    return folder


def main(argv=None) -> int:
    global _RUN_SINCE
    _RUN_SINCE = time.time()                 # 本次运行开始（过滤旧临时文件用）
    args = parse_args(argv if argv is not None else sys.argv[1:])
    script = os.path.abspath(args.script)
    if not os.path.isfile(script):
        print(f'[minibt] 找不到策略脚本：{script}', file=sys.stderr)
        return 2

    workdir = os.path.abspath(args.cwd) if args.cwd else os.path.dirname(script)
    os.makedirs(workdir, exist_ok=True)
    os.chdir(workdir)
    # ★ 让**脚本所在目录**优先于 VS Code 工作区根目录：
    #   否则工作区里如果有一份旧 minibt（或缺 minibt），会盖掉脚本旁边
    #   仓库里的新版 minibt → 报 “module 'minibt.utils' has no attribute
    #   'resolve_theme'” ✗。脚本目录放最后 insert(0) → 最终排在最前 ✓
    for entry in (workdir, os.path.dirname(script)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    # ★ 用户要求：当前目录（含上级）有 minibt → 优先用本地的；
    #   没有才回退到系统安装的 minibt。
    _prefer_local_minibt(script, workdir)

    # 1) 不要弹系统浏览器（除非显式 --open）
    if not args.open:
        webbrowser.open = lambda *a, **k: False      # type: ignore[assignment]

    port = int(args.port) or free_port()
    hooks = {'done': threading.Event()}

    # 2) 导入 minibt 并接管图表引擎
    try:
        _patch_minibt(args.engine, port, hooks, vscode_theme=args.theme)
    except Exception as error:                       # noqa: BLE001
        print(f'[minibt] 准备图表引擎失败：{type(error).__name__}: {error}',
              file=sys.stderr)
        print(f'[minibt] 当前解释器：{sys.executable}', file=sys.stderr)
        try:
            import minibt as _m
            print(f'[minibt] 实际导入的 minibt：{_m.__file__} '
                  f'(版本 {getattr(_m, "__version__", "?")}）',
                  file=sys.stderr)
        except Exception:                            # noqa: BLE001
            pass
        missing = (getattr(error, 'name', None)
                   if isinstance(error, ModuleNotFoundError) else None)
        if missing == 'minibt':
            print('[minibt] 本地（脚本目录 / 工作区 / 上级目录）也没有 minibt。',
                  file=sys.stderr)
        if missing:
            print(f'[minibt] 这个解释器缺依赖 `{missing}`（minibt 的依赖）。'
                  f'装上它："{sys.executable}" -m pip install {missing}',
                  file=sys.stderr)
        if 'resolve_theme' in str(error):
            print('[minibt] 这是**旧版 minibt**（缺 resolve_theme）：请升级 '
                  f'"{sys.executable}" -m pip install -U minibt，或把 '
                  '`minibt.cwd` 指向含最新 minibt 源码的仓库根目录。',
                  file=sys.stderr)
        print('[minibt] 或者把 VS Code 设置 `minibt.pythonPath` 指向装了 '
              'minibt / pylightcharts 的解释器（例如装了 rich 的那个）。',
              file=sys.stderr)
        return 3

    engine_name = {'pylightcharts': 'pylightcharts 网页版（强制）',
                   'bokeh': 'bokeh（强制）'}.get(
        args.engine, 'auto（Gui.Bokeh → bokeh，其余 → pylightcharts 网页版）')
    print(f'[minibt] 工作目录：{workdir}', flush=True)
    print(f'[minibt] 策略：{script}', flush=True)
    print(f'[minibt] 图表引擎：{engine_name}', flush=True)
    if args.theme:
        print(f'[minibt] VS Code 主题：{args.theme}（用户未显式指定时作为默认）',
              flush=True)
    # URL / HTML 都不在这里猜：pylightcharts 由 BrowserChart.show 的包装报真实
    # 地址（btplot 会自己另挑端口），bokeh 由 Server.start 之后报。

    # 4) 执行策略（它自己的 `if __name__ == '__main__':` 会照常触发）
    code = 0
    try:
        runpy.run_path(script, run_name='__main__')
    except KeyboardInterrupt:
        print('[minibt] 已中断', flush=True)
    except Exception as error:                       # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(f'[minibt] 策略异常退出：{type(error).__name__}: {error}',
              file=sys.stderr)
        code = 1

    hooks['done'].set()

    # 5) 运行模式：进程一退本地服务就没了 —— 保持存活，等扩展关页签时结束
    print('[minibt] 图表已就绪（关闭 VS Code 页签即停止）', flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print('[minibt] 已停止', flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())

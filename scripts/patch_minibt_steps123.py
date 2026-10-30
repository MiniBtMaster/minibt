"""Apply steps 1-3 to minibt's two light_chart modules.

1. cleanup: dead code + duplicated method definitions
2. keyboard: focus + a filter that actually sees the webview's keys
3. a startup self-check that prints which pylightcharts/bundle is in use

Run from the repo root:  python _patch_minibt.py
"""
import ast
import pathlib
import sys

REPO = pathlib.Path('minibt/strategy')
DESKTOP = pathlib.Path('C:/Users/Lenovo/Desktop/minibt/strategy')
FILES = ('light_chart.py', 'light_chart_replay.py')


def sub(text, old, new, label):
    assert text.count(old) == 1, f'{label}: found {text.count(old)}'
    return text.replace(old, new, 1)


# --------------------------------------------------------------- shared bits
SELF_CHECK = '''
def check_environment(verbose: bool = True) -> dict:
    """启动自检：确认在用哪一份 pylightcharts、键盘功能在不在 bundle 里。

    以前踩过的坑：跑的是另一个目录里的 minibt 副本 /（更早的）lightweight_charts，
    于是"明明改好了却没反应"。这里把关键事实打出来，出问题一眼可见：

    * ``pylightcharts``、``minibt`` 实际来自哪个文件；
    * bundle 里有没有 ``_handleArrowKey`` / ``removePane``（键盘与 pane 支持）；
    * 图表建好后 ``chart.keyboardNavigation`` 是否为真（见 ``Chart.__init__``）。
    """
    import pathlib as _pathlib

    import pylightcharts
    info = {
        'pylightcharts': getattr(pylightcharts, '__file__', '?'),
        'version': getattr(pylightcharts, '__version__', '?'),
    }
    try:
        import minibt as _minibt
        info['minibt'] = getattr(_minibt, '__file__', '?')
    except Exception:                      # 单文件运行时没有包
        info['minibt'] = __file__
    bundle = _pathlib.Path(str(info['pylightcharts'])).parent / 'js' / 'bundle.js'
    info['bundle'] = str(bundle)
    try:
        text = bundle.read_text(encoding='utf-8', errors='replace')
    except OSError:
        text = ''
    info['keyboard'] = '_handleArrowKey' in text
    info['panes'] = 'removePane' in text
    if verbose:
        print('[pylightcharts]', info)
    return info


'''


def _is_property_accessor(node: ast.FunctionDef) -> bool:
    """`@property`, `@x.setter`, `@x.getter` or `@x.deleter`?"""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == 'property':
            return True
        if (isinstance(decorator, ast.Attribute)
                and decorator.attr in ('setter', 'getter', 'deleter')):
            return True
    return False


def dedupe_chart_methods(src: str, class_name: str = 'Chart') -> str:
    """Drop every method of `class_name` except its last definition.

    Python keeps the last one, so the earlier copies are dead code (the audit
    found 13 of them in `Chart`).
    """
    tree = ast.parse(src)
    lines = src.split('\n')
    drop = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue
        seen = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                seen.setdefault(item.name, []).append(item)
        for name, defs in seen.items():
            # a property (`@property` + `@name.setter`) legitimately defines the
            # same name several times - dropping the getter breaks the setter's
            # decorator, so keep every accessor
            if any(_is_property_accessor(dead) for dead in defs):
                continue
            for dead in defs[:-1]:
                start = min([dead.lineno] + [d.lineno for d in dead.decorator_list])
                # keep the preceding comment block with the dead method
                while start > 1 and lines[start - 2].lstrip().startswith('#'):
                    start -= 1
                drop.append((start, dead.end_lineno, name))
    for start, end, _ in sorted(drop, reverse=True):
        del lines[start - 1:end]
    return '\n'.join(lines), drop


def patch_light_chart(path: pathlib.Path) -> None:
    src = path.read_text(encoding='utf-8')
    src, dropped = dedupe_chart_methods(src)
    print(f'  {path.name}: dropped {len(dropped)} dead methods '
          f'({", ".join(sorted({name for _, _, name in dropped}))})')

    # --- step 2: keyboard focus + a filter that sees the webview -----------
    src = sub(
        src,
        """        webview = self.get_webview()
        webview.page().loadFinished.connect(self._on_webview_loaded)
        webview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        webview.customContextMenuRequested.connect(
            self._on_webview_custom_context_menu)""",
        """        webview = self.get_webview()
        webview.page().loadFinished.connect(self._on_webview_loaded)
        webview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        webview.customContextMenuRequested.connect(
            self._on_webview_custom_context_menu)
        # 键盘：pylightcharts 的方向键是页面内监听 keydown，只有 webview 有焦点
        # 才收得到。窗口原来把 eventFilter 装在自己身上，而 Qt 把按键发给焦点控件，
        # 所以 "obj == webview" 那一支永远不成立（死代码）。这里把过滤器装到
        # webview 上，并让 webview 默认拿到焦点；方向键交给页面（见 eventFilter）。
        webview.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if self.light_chart_window is not None:
            webview.installEventFilter(self.light_chart_window)
        webview.setFocus()""",
        'keyboard focus')

    src = sub(
        src,
        """            # 确保事件来自webview或者窗口本身
            if obj == webview or obj == self:
                key = event.key()
                # modifiers = event.modifiers()

                # ========== 完善键盘事件映射 ==========
                # 放大：上箭头 或 + 键
                if key == Qt.Key.Key_Up or key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
                    self.chart_window.zoom_in()
                    return True  # 拦截事件，避免传递给其他组件
                # 缩小：下箭头 或 - 键
                elif key == Qt.Key.Key_Down or key == Qt.Key.Key_Minus:
                    self.chart_window.zoom_out()
                    return True
                # 向左平移：左箭头
                elif key == Qt.Key.Key_Left:
                    self.chart_window.pan_left()
                    return True
                # 向右平移：右箭头
                elif key == Qt.Key.Key_Right:
                    self.chart_window.pan_right()
                    return True
                elif key == Qt.Key.Key_Space:
                    self.chart_window.center_on_latest()
                    return True""",
        """            # 确保事件来自webview或者窗口本身
            if obj == webview or obj == self:
                key = event.key()
                # 方向键留给 pylightcharts 的内置导航（页面内监听 keydown，
                # 缩放锚在窗口中心、平移按 keyboard_step，行为一致），这里只补
                # 它没有的键；返回 True 会吞掉事件，所以不能拦方向键。
                if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
                    self.chart_window.zoom_in()
                    return True
                elif key == Qt.Key.Key_Minus:
                    self.chart_window.zoom_out()
                    return True
                elif key == Qt.Key.Key_Space:
                    self.chart_window.center_on_latest()
                    return True""",
        'eventFilter narrowing')

    # --- step 3: the self-check -------------------------------------------
    anchor = '\n# 延迟导入QtChart类\n'
    assert src.count(anchor) == 1
    src = src.replace(anchor, SELF_CHECK + '# 延迟导入QtChart类\n', 1)

    src = sub(
        src,
        """        from pylightcharts.qt import prepare_qt
        prepare_qt('PyQt6')
        from PyQt6.QtWebEngineWidgets import QWebEngineView""",
        """        check_environment()
        from pylightcharts.qt import prepare_qt
        prepare_qt('PyQt6')
        from PyQt6.QtWebEngineWidgets import QWebEngineView""",
        'main self-check')
    path.write_text(src, encoding='utf-8')


def patch_replay(path: pathlib.Path) -> None:
    src = path.read_text(encoding='utf-8')

    # --- step 1: drop the dead monkey-patch and the unused toolbox --------
    start = src.index('# ---- Monkey-patch: NaN 断线处理（多系列分割法）----')
    end = src.index('# SeriesCommon.set = _patched_series_set\n')
    end += len('# SeriesCommon.set = _patched_series_set\n')
    removed = src[start:end].count('\n')
    src = src[:start] + src[end:]
    print(f'  {path.name}: removed the dead SeriesCommon.set patch '
          f'({removed} lines)')

    src = sub(
        src,
        'from pylightcharts.abstract import Line, Candlestick, AbstractChart, SeriesCommon\n',
        'from pylightcharts.abstract import Line, Candlestick, AbstractChart\n',
        'SeriesCommon import')
    src = sub(
        src,
        'from pylightcharts.toolbox import ToolBox, json as lw_json\n',
        '',
        'toolbox import')

    # keep the comment block above the class with it
    start = src.index('# CustomToolBox - 画线工具箱（保持原有逻辑）')
    end = src.index('class ReplayChart:')
    removed = src[start:end].count('\n')
    src = src[:start] + src[end:]
    print(f'  {path.name}: removed the unused CustomToolBox ({removed} lines)')
    # `toolbox: CustomToolBox = None` was the only other reference
    src = sub(
        src,
        '    toolbox: CustomToolBox = None',
        '    # 工具箱已移除：replay 从不创建 CustomToolBox，self.toolbox 始终为 None\n'
        '    toolbox = None',
        'toolbox annotation')
    tree = ast.parse(src)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree)
              if isinstance(node, ast.Attribute)}
    leftover = names & {'CustomToolBox', 'SeriesCommon', 'ToolBox', 'lw_json'}
    assert not leftover, f'still referenced: {sorted(leftover)}'

    # --- step 2: keyboard focus -------------------------------------------
    src = sub(
        src,
        """                    self.all_charts[chart_key] = chart
                    self.chart_stack.addWidget(chart.get_webview())""",
        """                    self.all_charts[chart_key] = chart
                    _webview = chart.get_webview()
                    # 键盘：方向键由 pylightcharts 在页面内处理，webview 有焦点
                    # 才会收到按键（replay 里没有别的键盘入口）
                    _webview.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    _webview.setFocus()
                    self.chart_stack.addWidget(_webview)""",
        'replay focus')

    # --- step 3: the self-check -------------------------------------------
    anchor = '\nclass CustomTitleBar'
    assert src.count(anchor) == 1
    src = src.replace(anchor, SELF_CHECK + 'class CustomTitleBar', 1)
    src = sub(
        src,
        """        from pylightcharts.qt import prepare_qt
        prepare_qt('PyQt6')
        from PyQt6.QtWebEngineWidgets import QWebEngineView""",
        """        check_environment()
        from pylightcharts.qt import prepare_qt
        prepare_qt('PyQt6')
        from PyQt6.QtWebEngineWidgets import QWebEngineView""",
        'replay main self-check')
    path.write_text(src, encoding='utf-8')


def main() -> int:
    for folder in (REPO, DESKTOP):
        if not folder.is_dir():
            print('skip (missing):', folder)
            continue
        print('patching', folder)
        for name in FILES:
            path = folder / name
            (patch_light_chart if name == 'light_chart.py'
             else patch_replay)(path)
    # everything must still parse
    for folder in (REPO, DESKTOP):
        if not folder.is_dir():
            continue
        for name in FILES:
            ast.parse((folder / name).read_text(encoding='utf-8'))
    print('RESULT_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

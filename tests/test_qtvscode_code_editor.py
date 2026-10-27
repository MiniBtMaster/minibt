"""静态 Python 代码编辑器（`qtvscode.code_editor`）读写测试 ✓。

`CodeEditor` 是**纯 Qt**（无 Node / VS Code server）的 ``.py`` 读写 / 浏览控件，
所以离屏 + 子进程就能直接跑 ✓。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CODE_EDITOR = REPO / 'qtvscode' / 'qtvscode' / 'code_editor.py'
CODE_EDITOR_APP = (REPO / 'qtvscode' / 'qtvscode' / 'examples'
                   / 'code_editor_app.py')

pytestmark = pytest.mark.skipif(
    not CODE_EDITOR.exists(), reason='需要仓库里的 qtvscode 源码')


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8')


def _run(script: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=str(REPO), env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=120)
    if result.returncode != 0:
        pytest.fail(f'子进程失败（{result.returncode}）:\n'
                    f'{result.stdout}\n{result.stderr}')
    return result


def test_code_editor_module_is_static_and_has_read_write():
    source = _read(CODE_EDITOR)
    assert 'class CodeEditor' in source
    assert 'class PythonHighlighter' in source
    # 读 / 写 / 写入 / 读取 / 深浅主题 ✓
    for api in ('def read_file', 'def write_file', 'def set_code',
                'def code', 'def set_read_only', 'def set_dark',
                'def is_dark', 'def apply_theme'):
        assert api in source, api
    # 纯 Qt：不能依赖 server / webengine 的 QtVscodeWidget
    assert 'QtVscodeWidget' not in source
    assert 'QWebEngine' not in source
    # pandas / numpy 的类 / 方法也要高亮 ✓
    assert '_PANDAS_TYPES' in source and '_PANDAS_METHODS' in source
    assert '_NUMPY_TYPES' in source and '_NUMPY_METHODS' in source
    # 代码折叠 / 展开（按缩进 + 行号栏点击 + 快捷键）✓
    for api in ('def fold', 'def unfold', 'def toggle_fold', 'def fold_all',
                'def unfold_all', 'def fold_regions', 'def is_folded',
                'def folded_blocks', 'def _compute_fold_regions'):
        assert api in source, api
    assert 'setVisible(False)' in source          # 隐藏折叠区域 ✓
    assert 'FOLD_MARKER_WIDTH' in source          # 行号栏折叠标记 ✓


def test_code_editor_example_uses_the_editor():
    source = _read(CODE_EDITOR_APP)
    assert 'CodeEditor' in source
    assert 'set_code(' in source
    assert '.code()' in source
    assert 'write_file(' in source
    assert '--selftest' in source
    assert '--read-only' in source


def test_code_editor_highlights_minibt_and_python():
    """Python 关键字 + minibt 类 / 方法 / 属性都上色（子进程真高亮 ✓）。"""
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(REPO / 'qtvscode')!r})
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from qtvscode import (ensure_qtwebengine_attributes, QApplication,
                              CodeEditor)
        ensure_qtwebengine_attributes()
        app = QApplication([])
        e = CodeEditor()
        e.set_code('from minibt import BtIndicator, BandStyle\\n'
                   'class Sma(BtIndicator):\\n'
                   '    def next(self):\\n'
                   '        self.lines.sma1 = self.close.sma(5)\\n'
                   '        self.kline.buy()\\n')
        e._highlighter.rehighlight()
        doc = e.document()
        colors = {{}}
        for i in range(doc.blockCount()):
            b = doc.findBlockByNumber(i)
            for r in b.layout().formats():
                txt = b.text()[r.start:r.start + r.length]
                colors[txt] = r.format.foreground().color().name()
        print('TYPE', colors.get('BtIndicator'))
        print('METHOD', colors.get('sma'))
        print('ACTION', colors.get('buy'))
        print('PROP', colors.get('lines'))
        print('KW', colors.get('def'))
        print('STRING', colors.get(chr(39) + 'ma1' + chr(39)))
    """)
    result = _run(script)
    assert 'TYPE #4ec9b0' in result.stdout          # minibt 类 ✓
    assert 'METHOD #dcdcaa' in result.stdout        # minibt 方法 ✓
    assert 'ACTION #dcdcaa' in result.stdout        # buy 也是方法色 ✓
    assert 'PROP #9cdcfe' in result.stdout          # minibt 属性 / 数据列 ✓
    assert 'KW #569cd6' in result.stdout            # Python 关键字 ✓


def test_code_editor_highlights_pandas_numpy():
    """pandas / numpy 的类 / 方法也上色（常用库 ✓）。"""
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(REPO / 'qtvscode')!r})
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from qtvscode import (ensure_qtwebengine_attributes, QApplication,
                              CodeEditor)
        ensure_qtwebengine_attributes()
        app = QApplication([])
        e = CodeEditor()
        e.set_code('df = pd.DataFrame(np.array([1.0]))\\n'
                   's = df.close.rolling(5).mean()\\n'
                   'x = np.where(s > 0, s, np.nan)\\n'
                   'dt = pd.to_datetime("2024-01-01")\\n'
                   'a = np.zeros(3, dtype=np.float64).reshape(3, 1)\\n')
        e._highlighter.rehighlight()
        doc = e.document()
        colors = {{}}
        for i in range(doc.blockCount()):
            b = doc.findBlockByNumber(i)
            for r in b.layout().formats():
                colors.setdefault(b.text()[r.start:r.start + r.length],
                                  r.format.foreground().color().name())
        print('PD_TYPE', colors.get('DataFrame'))
        print('NP_TYPE', colors.get('float64'))
        print('PD_FUNC', colors.get('to_datetime'))
        print('PD_METHOD', colors.get('rolling'))
        print('NP_FUNC', colors.get('where'))
        print('NP_METHOD', colors.get('reshape'))
        print('NAN', colors.get('nan'))
        print('DTYPE', colors.get('dtype'))
    """)
    result = _run(script)
    assert 'PD_TYPE #4ec9b0' in result.stdout       # pandas 类 ✓
    assert 'NP_TYPE #4ec9b0' in result.stdout       # numpy 标量类型 ✓
    assert 'PD_FUNC #dcdcaa' in result.stdout       # pd.to_datetime ✓
    assert 'PD_METHOD #dcdcaa' in result.stdout     # df.rolling ✓
    assert 'NP_FUNC #dcdcaa' in result.stdout       # np.where ✓
    assert 'NP_METHOD #dcdcaa' in result.stdout     # arr.reshape ✓
    assert 'NAN #4ec9b0' in result.stdout
    assert 'DTYPE #4ec9b0' in result.stdout


def test_code_editor_folds_and_unfolds_blocks():
    """代码折叠 / 展开：按缩进识别区域 + 行号栏点击 + 全部折 / 展 ✓。"""
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(REPO / 'qtvscode')!r})
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from qtvscode import (ensure_qtwebengine_attributes, QApplication,
                              CodeEditor)
        from qtvscode.qtcompat import QPointF
        ensure_qtwebengine_attributes()
        app = QApplication([])
        e = CodeEditor()
        e.set_code('class A:\\n'
                   '    def m(self):\\n'
                   '        x = 1\\n'
                   '    z = 2\\n'
                   '\\n'
                   'def f():\\n'
                   '    return 1\\n'
                   'last = 0\\n')
        doc = e.document()

        def vis():
            return [doc.findBlockByNumber(i).isVisible()
                    for i in range(doc.blockCount())]

        print('REGIONS', sorted(e.fold_regions().items()))
        print('ALL_VISIBLE', all(vis()))
        print('FOLD', e.fold(0), e.is_folded(0))
        print('VIS_FOLD', vis())
        print('UNFOLD', e.unfold(0), all(vis()))
        print('TOGGLE', e.toggle_fold(0), e.is_folded(0))
        e.unfold_all()
        print('FOLD_ALL', e.fold_all() > 0, e.folded_blocks())
        print('UNFOLD_ALL', e.unfold_all() > 0, e.folded_blocks())
        # 行号栏点折叠列 → 折叠 / 展开 ✓
        e.resize(600, 300)
        e.show()
        app.processEvents()
        rect = e.blockBoundingGeometry(
            doc.findBlockByNumber(0)).translated(e.contentOffset())
        y = int(rect.top() + 5)

        class Ev:
            def position(self):
                return QPointF(3, y)

        print('CLICK_HANDLED', e.line_number_area_mouse_press(Ev()))
        print('CLICK_FOLDED', e.folded_blocks())
    """)
    result = _run(script)
    assert 'REGIONS [(0, 3), (1, 2), (5, 6)]' in result.stdout
    assert 'ALL_VISIBLE True' in result.stdout
    assert 'FOLD True True' in result.stdout
    assert ('VIS_FOLD [True, False, False, False, True, True, True, '
            'True, True]') in result.stdout
    assert 'UNFOLD True True' in result.stdout
    assert 'TOGGLE True True' in result.stdout
    assert 'FOLD_ALL True [0, 1, 5]' in result.stdout
    assert 'UNFOLD_ALL True []' in result.stdout
    assert 'CLICK_HANDLED True' in result.stdout
    assert 'CLICK_FOLDED [0]' in result.stdout


def test_code_editor_switches_dark_light_theme():
    """深 / 浅两套主题：底色 + 高亮色一起换，且可运行时切换 ✓。"""
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(REPO / 'qtvscode')!r})
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from qtvscode import (ensure_qtwebengine_attributes, QApplication,
                              CodeEditor)
        ensure_qtwebengine_attributes()
        app = QApplication([])

        def colors(e):
            e._highlighter.rehighlight()
            out = {{}}
            doc = e.document()
            for i in range(doc.blockCount()):
                b = doc.findBlockByNumber(i)
                for r in b.layout().formats():
                    out[b.text()[r.start:r.start + r.length]] = \\
                        r.format.foreground().color().name()
            return out

        e = CodeEditor(dark=True)
        e.set_code('class Sma(BtIndicator):\\n    x = self.close.sma(5)\\n')
        print('START_DARK', e.is_dark())
        d = colors(e)
        print('DARK_COLORS', d.get('class'), d.get('BtIndicator'), d.get('sma'))
        e.set_dark(False)
        print('AFTER_LIGHT', e.is_dark())
        light = colors(e)
        print('LIGHT_COLORS', light.get('class'), light.get('BtIndicator'),
              light.get('sma'))
        e.apply_theme('dark')
        print('APPLY_DARK', e.is_dark())
        e.apply_theme('\u6d45\u8272')
        print('APPLY_LIGHT', e.is_dark())
    """)
    result = _run(script)
    assert 'START_DARK True' in result.stdout
    assert 'DARK_COLORS #569cd6 #4ec9b0 #dcdcaa' in result.stdout
    assert 'AFTER_LIGHT False' in result.stdout
    assert 'LIGHT_COLORS #0000ff #267f99 #795e26' in result.stdout
    assert 'APPLY_DARK True' in result.stdout
    assert 'APPLY_LIGHT False' in result.stdout


def test_code_editor_read_write_roundtrip(tmp_path):
    """子进程真建控件：写入 → 读取 → 落盘 → 再读回 → 只读切换 ✓。"""
    target = tmp_path / 'indicator.py'
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(REPO / 'qtvscode')!r})
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from qtvscode import (ensure_qtwebengine_attributes, QApplication,
                              CodeEditor)
        ensure_qtwebengine_attributes()
        app = QApplication([])

        source = 'class Sma:\\n    overlap = True\\n'
        editor = CodeEditor()
        editor.set_code(source)                       # 写入 ✓
        print('CODE_OK', editor.code() == source)     # 读取 ✓
        print('DIRTY_AFTER_SET', editor.is_dirty())
        editor.write_file({str(target)!r})            # 落盘 ✓
        print('SAVED', editor.is_dirty() is False)

        again = CodeEditor(read_only=True)
        again.read_file({str(target)!r})              # 读文件 ✓
        print('READ_OK', again.code() == source)
        print('RO', again.isReadOnly())
        again.set_read_only(False)
        print('RO2', again.isReadOnly())
        print('GOTO', end=' ')
        again.goto_line(2)
        print('ok')
    """)
    result = _run(script)
    assert 'CODE_OK True' in result.stdout
    assert 'SAVED True' in result.stdout
    assert 'READ_OK True' in result.stdout
    assert 'RO True' in result.stdout
    assert 'RO2 False' in result.stdout
    assert 'GOTO ok' in result.stdout
    # 文件真的写出来了 ✓
    assert target.read_text(encoding='utf-8').startswith('class Sma:')

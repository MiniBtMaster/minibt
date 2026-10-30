"""P62：合并按钮后「代码」页签也能正常打开（懒加载）✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / 'jslib' / 'src' / 'desk' / 'chart-page.ts'


def test_editor_created_on_code_tab():
    page = PAGE.read_text(encoding='utf-8')
    # 惰性创建抽成 _ensureEditor（openEditor + 页签回调都用它 ✓）
    assert 'private _ensureEditor(): EditorPanel {' in page
    # 构造时就接上「切到代码页签 → 建编辑器」的钩子（否则点 tab 是空白 ✗）
    construct = page.split('this.dock = new AccountDock(', 1)[1][:1400]
    assert 'this.dock.onEditorOpen = () => {' in construct
    assert '_ensureEditor().show()' in construct
    assert "if (tab === 'code') this._ensureEditor().show();" in construct
    # openEditor 不再自己建（避免两处逻辑不一致 ✓）
    opener = page.split('openEditor(): void {', 1)[1].split('\n    }', 1)[0]
    assert '_ensureEditor();' in opener
    assert 'new EditorPanel(' not in opener


def test_editor_is_lazy_until_file_opened():
    """没点开文件时不该初始化 CodeMirror（懒加载 ✓）"""
    panel = (ROOT / 'jslib' / 'src' / 'desk' / 'editor-panel.ts').read_text(
        encoding='utf-8')
    body = panel.split('setFile(', 1)[1][:1200]
    assert 'new CodeEditor(' in body

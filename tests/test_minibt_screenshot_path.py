"""页面内「截图路径」输入框的交互（源码约束）。

历史问题：原生目录选择不可用时会退回页面内输入框；但该框**只能**点「确定」
（或回车）才消失 —— 用户误点「截图路径设置」、又不想填路径时，弹窗关不掉 ✗。
现在补上：**ESC / 取消** 直接退出，且不改设置、不截图 ✓。
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
WINDOW = REPO / 'minibt' / 'strategy' / 'strategy_window.py'


def _source() -> str:
    return WINDOW.read_text(encoding='utf-8')


def test_screenshot_path_input_has_escape_and_cancel():
    source = _source()
    # 页面内输入框还在（原生弹窗不可用时的兜底）
    assert 'def _prompt_screenshot_path_input' in source
    assert "pylightcharts-shot-path" in source
    # ESC / 取消 都能退出
    assert "event.key === 'Escape'" in source
    assert 'cancel.onclick = close' in source
    assert "cancel.textContent = '取消'" in source
    # capture 阶段监听：焦点不在输入框也能退出
    assert "document.addEventListener('keydown', onKey, true)" in source
    # 关闭时移除监听，避免重复弹框后残留
    assert "document.removeEventListener('keydown', onKey, true)" in source


def test_screenshot_path_cancel_does_not_save_or_shoot():
    """取消只 `box.remove()`，不回调 → 不改路径、不截图 ✓。"""
    source = _source()
    assert 'const close = () => {' in source
    # close 只移除监听 + 移除节点
    assert 'document.removeEventListener' in source
    # done 才回调（close 里没有 callbackFunction）
    start = source.index('const close = () => {')
    end = source.index('const done = () => {', start)
    close_body = source[start:end]
    assert 'callbackFunction' not in close_body
    assert 'window.callbackFunction' in source

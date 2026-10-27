"""P41：浅色主题的图例 / 工具栏 / 撤单按钮配色 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def _read(path):
    return (ROOT / path).read_text(encoding='utf-8')


# ------------------------------------------------------- ① 图例跟随主题
def test_legend_colors_follow_theme():
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    assert 'private _applyLegendColors(): void' in page
    # 切主题时要重刷（以前只在建格时设一次 ✗）
    apply_theme = page.split('applyTheme(theme: \'light\' | \'dark\'): void {', 1)[1]
    assert '_applyLegendColors();' in apply_theme.split('}', 1)[0]
    # 眼睛 / 齿轮用 currentColor → 改这一处整套图标都亮 ✓
    legend = (ROOT / 'jslib/src/general/legend.ts').read_text(encoding='utf-8')
    assert 'stroke:currentColor' in legend


# ------------------------------------------------------- ② 工具栏图标
def test_toolbar_icons_are_monochrome_svg():
    icons = (DESK_TS / 'icons.ts').read_text(encoding='utf-8')
    for name in ('ICON_TRASH', 'ICON_ERASER', 'ICON_PENCIL', 'ICON_CAMERA',
                 'ICON_BELL', 'ICON_REWIND'):
        assert f'export const {name}' in icons, name
    assert 'stroke="currentColor"' in icons
    page = (DESK_TS / 'chart-page.ts').read_text(encoding='utf-8')
    # emoji 全换掉了（浅色主题下又淡又花 ✗）—— 只看**按钮文本**那一行，
    # 注释里提到旧名字没关系 ✓
    for emoji, icon in (('🗑', 'ICON_TRASH'), ('🧹', 'ICON_ERASER'),
                        ('✏️', 'ICON_PENCIL'), ('📷', 'ICON_CAMERA'),
                        ('🔔', 'ICON_BELL')):
        assert f"_toolButton('{emoji}'" not in page, emoji
        assert f'innerHTML = {icon};' in page, icon
    css = (DESK_TS / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-tool > svg { display: block;' in css


# ------------------------------------------------------- ③ 撤单按钮
def test_plain_button_is_theme_aware():
    css = (DESK_TS / 'desk.css').read_text(encoding='utf-8')
    body = css.split('.desk-book-btn.plain {', 1)[1].split('}', 1)[0]
    assert 'var(--desk-hover)' in body            # 有背景色了 ✓
    assert 'var(--desk-text)' in body             # 字色跟主题 ✓
    light = css.split('.theme-light .desk-book-btn.plain {', 1)[1].split('}', 1)[0]
    assert '#f2f4f7' in light and '#1f2329' in light
    panel = (DESK_TS / 'replay-ticket.ts').read_text(encoding='utf-8')
    assert "['cancel', '撤单', 'plain'" in panel


def test_light_theme_asset_is_built():
    """构建产物要带上这些修复（desk.js / desk.css 里能查到）✓"""
    css = (ROOT / 'pylightcharts' / 'js' / 'desk.css').read_text(encoding='utf-8')
    assert '.desk-book-btn.plain' in css
    script = (ROOT / 'pylightcharts' / 'js' / 'desk.js').read_text(
        encoding='utf-8', errors='ignore')
    assert '_applyLegendColors' in script or 'applyLegendColors' in script

"""P73：权益曲线 / 累计盈亏图的坐标轴字体跟「各品种统计」表格一致 ✓"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK_TS = ROOT / 'jslib' / 'src' / 'desk'


def test_axis_text_matches_table_text():
    page = (DESK_TS / 'settings-page.ts').read_text(encoding='utf-8')
    # 表格正文：12px + 默认文字色 ✓
    assert '.desk-settings-table-row {' in page
    table = page.split('.desk-settings-table-row {', 1)[1].split('}', 1)[0]
    assert 'font-size: 12px;' in table
    # 坐标轴刻度：同字号 / 同颜色（以前 10px + muted 灰 ✗）
    axis = page.split('.desk-mini-chart-axis {', 1)[1].split('}', 1)[0]
    assert 'font-size: 12px;' in axis
    assert 'fill: var(--desk-text);' in axis
    assert 'font-family: inherit;' in axis


def test_axis_label_space_widened():
    chart = (DESK_TS / 'mini-chart.ts').read_text(encoding='utf-8')
    # 12px 字号下左边距要给够，长数字不贴边 ✓
    assert 'const left = 76;' in chart

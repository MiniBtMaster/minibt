"""多布局主题 / VP 回归：每格独立 chart，切主题/回放都要更新。"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / 'jslib' / 'src' / 'desk' / name).read_text(
        encoding='utf-8')


def test_new_cells_apply_current_theme():
    for name in ('chart-page.ts', 'local-chart-page.ts'):
        page = _read(name)
        assert 'chartOptions(' in page
        assert 'this.cells' in page


def test_vp_overlay_is_per_cell_and_updates_with_bars():
    page = _read('local-chart-page.ts')
    assert 'const handler = this.cells[cell]' in page
    assert 'this.cellElements[cell] || this.host' in page
    assert 'this.vpOverlays[index]?.setBars(data as never)' in page
    assert 'overlay?.draw()' in page

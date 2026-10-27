"""Whole-UI themes: `chart.win.theme('light')` / `chart.theme('dark')`."""
import pathlib

import pandas as pd
import pytest

from pylightcharts import Window
from pylightcharts.abstract import AbstractChart
from pylightcharts.themes import DARK, LIGHT, THEMES, resolve


@pytest.fixture()
def frame():
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=5, freq='D'),
        'open': [1.0, 2.0, 3.0, 4.0, 5.0],
        'high': [2.0, 3.0, 4.0, 5.0, 6.0],
        'low': [0.0, 1.0, 2.0, 3.0, 4.0],
        'close': [1.5, 2.5, 3.5, 4.5, 5.5],
        'volume': [10.0, 11.0, 12.0, 13.0, 14.0],
    })


@pytest.fixture()
def chart(frame):
    captured = []
    window = Window(script_func=captured.append)
    window.loaded = True
    chart = AbstractChart(window)
    chart.captured = captured
    chart.set(frame)
    chart.captured.clear()
    return chart


# --------------------------------------------------------------------------
# the palettes
# --------------------------------------------------------------------------

def test_the_two_palettes_cover_the_same_colours():
    assert sorted(LIGHT) == sorted(DARK)
    assert set(THEMES) == {'light', 'dark'}


def test_resolve_accepts_a_name_a_dict_and_overrides():
    assert resolve('light')['background'] == '#ffffff'
    assert resolve('DARK')['background'] == DARK['background']
    # a dict starts from dark and overrides what it names
    spec = resolve({'background': '#101010'})
    assert spec['background'] == '#101010'
    assert spec['text'] == DARK['text']
    assert resolve('light', {'up': '#123456'})['up'] == '#123456'


def test_resolve_rejects_unknown_names_and_colours():
    with pytest.raises(ValueError, match='unknown theme'):
        resolve('solarized')
    with pytest.raises(ValueError, match='unknown theme colours'):
        resolve('light', {'nope': '#fff'})


# --------------------------------------------------------------------------
# applying a theme
# --------------------------------------------------------------------------

def test_window_theme_styles_the_root_css_and_the_chart(chart):
    chart.win.theme('light')
    js = '\n'.join(chart.captured)

    # the root variables drive the top bar, legend, menus and hover states
    assert 'setRootStyles' in js
    assert '#ffffff' in js
    assert '#131722' in js
    # ... and the chart options: background, grid, crosshair, candles,
    # volume, pane separator, scale borders
    assert '"upColor":"#089981"' in js
    assert '"downColor":"#f23645"' in js
    assert '"pane_separator":' not in js          # not a JS key
    assert '#e0e3eb' in js
    assert '"textColor":"#131722"' in js
    assert '8, 153, 129' in js                    # light volume
    assert chart.win._theme['background'] == '#ffffff'


def test_chart_theme_is_a_shortcut_for_the_window(chart):
    assert chart.theme('light') is chart
    assert chart.win._theme['text'] == '#131722'


def test_switching_back_to_dark_restores_the_defaults(chart):
    chart.win.theme('light')
    chart.captured.clear()
    chart.win.theme('dark')
    js = '\n'.join(chart.captured)
    assert '"upColor":"rgba(39, 157, 130, 100)"' in js
    assert chart.win._theme == DARK


def test_a_chart_created_later_inherits_the_theme(chart):
    chart.win.theme('light')
    chart.captured.clear()
    chart.create_subchart(position='right', width=0.5, height=0.5)
    js = '\n'.join(chart.captured)
    assert '#ffffff' in js
    assert '"upColor":"#089981"' in js


def test_theme_overrides_reach_the_chart(chart):
    chart.win.theme('light', up='#123456', background='#fafafa')
    js = '\n'.join(chart.captured)
    assert '"upColor":"#123456"' in js
    assert '#fafafa' in js


def test_theming_a_chart_that_already_has_bars_recolours_the_volume(chart):
    chart.captured.clear()
    chart.win.theme('light')
    js = '\n'.join(chart.captured)
    # per-bar colours travel with the data, so it has to be re-sent
    assert 'volumeSeries.setData' in js
    assert '#089981' in js or '#f23645' in js


def test_table_colours_follow_the_theme(chart):
    chart.win.theme('light')
    chart.captured.clear()
    chart.create_table(width=340, height=180, headings=('a',),
                       draggable=True)
    assert '#ffffff' in '\n'.join(chart.captured)


def test_explicit_table_colours_win_over_the_theme(chart):
    chart.win.theme('light')
    chart.captured.clear()
    chart.create_table(width=340, height=180, headings=('a',),
                       background_color='#111111', draggable=True)
    js = '\n'.join(chart.captured)
    assert '#111111' in js
    assert '"background_color":"#ffffff"' not in js


def test_themed_charts_lists_every_chart_of_the_window(chart):
    assert chart.win._themed_charts() == [chart]
    sub = chart.create_subchart(position='right', width=0.5, height=0.5)
    assert sub in chart.win._themed_charts()


# --------------------------------------------------------------------------
# the legend and existing tables follow a theme switch
# --------------------------------------------------------------------------

def test_the_legend_text_colour_follows_the_theme(chart):
    # the legend paints its colour as an inline style, so the CSS variables
    # do not reach it - and the default is a light grey that vanishes on white
    chart.legend(visible=True, font_size=12, text='THEME')
    chart.captured.clear()
    chart.win.theme('light')
    js = '\n'.join(chart.captured)

    assert "div.style.color = '#131722'" in js
    # restyling must not reset the rest of the legend
    assert "div.style.display = 'flex'" in js
    assert "fontSize = '12px'" in js
    assert "text.innerText = 'THEME'" in js


def test_a_hidden_legend_is_not_shown_by_the_theme(chart):
    chart.captured.clear()
    chart.win.theme('light')
    assert "legend.div.style.display = 'flex'" not in '\n'.join(chart.captured)


def test_an_existing_table_is_recoloured_on_a_theme_switch(chart):
    chart.win.theme('dark')
    table = chart.create_table(width=250, height=90, headings=('a',),
                               draggable=True)
    chart.captured.clear()

    chart.win.theme('light')

    js = '\n'.join(chart.captured)
    assert 'setColors' in js
    assert '#ffffff' in js and '#e0e3eb' in js
    assert '#f0f3fa' in js                      # header/footer sections
    assert table.background_color == '#ffffff'


def test_a_table_with_explicit_colours_ignores_the_theme(chart):
    table = chart.create_table(width=250, height=90, headings=('a',),
                               background_color='#111111', draggable=True)
    chart.captured.clear()
    chart.win.theme('light')
    js = '\n'.join(chart.captured)

    assert table.theme_follows is False
    assert 'setColors' not in js


def test_tables_are_registered_on_the_window(chart):
    table = chart.create_table(width=250, height=90, headings=('a',),
                               draggable=True)
    assert chart.win._tables == [table]
    assert table in chart.win._tables


def test_the_legend_eye_is_not_hard_coded_white():
    """The eye icon is drawn by the bundle with `stroke: currentColor`.

    A hard-coded white (#FFF) eye was invisible on the light theme's white
    chart - it has to inherit the legend's text colour instead.
    """
    bundle = (pathlib.Path(__file__).resolve().parents[1]
              / 'pylightcharts' / 'js' / 'bundle.js').read_text(encoding='utf-8')
    assert 'stroke:currentColor' in bundle
    assert 'stroke:#FFF' not in bundle

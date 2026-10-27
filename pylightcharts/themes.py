"""Whole-UI colour themes: :meth:`Window.theme`.

The widgets of this package are styled through two layers - the root
CSS variables (top bar, legend, tables, menus, hover states) and the chart options
themselves (background, grid, crosshair, candles, volume, price scale, pane
separators) - so a "dark theme" is a coherent set of both. These palettes are
that set; applying one is the same as calling `win.style(...)`, `layout(...)`,
`candle_style(...)` and friends yourself, only in one go:

    chart.win.theme('light')
    chart.win.theme('light', up='#0a7d5a')     # tweak one colour
    chart.win.theme({'background': '#111'})    # start from dark and override

Anything set *after* the theme wins, so a theme is a starting point, not a lock.
Charts created later inherit it, and so do floating tables (existing ones are
recoloured, unless they were given explicit colours).

"""
from typing import Dict, Optional

__all__ = ['LIGHT', 'DARK', 'THEMES', 'resolve']

#: light palette (TradingView's light defaults as the reference)
LIGHT: Dict[str, str] = {
    'background': '#ffffff',
    'text': '#131722',
    'grid': '#f0f3fa',
    'crosshair': '#9598a1',
    'crosshair_label': '#131722',
    'up': '#089981',
    'down': '#f23645',
    'volume_up': 'rgba(8, 153, 129, 0.45)',
    'volume_down': 'rgba(242, 54, 69, 0.45)',
    'pane_separator': '#B6C4D6',
    'separator_hover': '#8296B0',
    'scale_border': '#e0e3eb',
    'border_color': '#e0e3eb',
    'hover_background': '#f0f3fa',
    'click_background': '#e0e3eb',
    'active_background': 'rgba(41, 98, 255, 0.70)',
    'muted_background': 'rgba(41, 98, 255, 0.30)',
    'active_text': '#ffffff',
    'table_background': '#ffffff',
    'table_border': '#e0e3eb',
    'table_section_background': '#f0f3fa',
}

#: the palette the package uses by default
DARK: Dict[str, str] = {
    'background': '#000000',
    'text': '#d8d9db',
    'grid': 'rgba(29, 30, 38, 5)',
    'crosshair': '#758696',
    'crosshair_label': '#2e2e2e',
    'up': 'rgba(39, 157, 130, 100)',
    'down': 'rgba(200, 97, 100, 100)',
    'volume_up': 'rgba(83, 141, 131, 0.8)',
    'volume_down': 'rgba(200, 127, 130, 0.8)',
    'pane_separator': '#3E5468',
    'separator_hover': '#6E8FAD',
    'scale_border': '#2B2B43',
    'border_color': '#3C434C',
    'hover_background': '#3c434c',
    'click_background': '#50565E',
    'active_background': 'rgba(0, 122, 255, 0.7)',
    'muted_background': 'rgba(0, 122, 255, 0.3)',
    'active_text': '#ececed',
    'table_background': '#121417',
    'table_border': 'rgb(70, 70, 70)',
    'table_section_background': 'rgb(30, 30, 30)',
}

THEMES: Dict[str, Dict[str, str]] = {'light': LIGHT, 'dark': DARK}


def resolve(theme='dark', overrides: Optional[dict] = None) -> Dict[str, str]:
    """The full colour spec for `theme` (a name or a dict) plus `overrides`.

    Unknown colour names raise :class:`ValueError` with the list of valid ones,
    so a typo cannot silently do nothing.
    """
    if isinstance(theme, dict):
        spec = dict(DARK)
        spec.update(theme)
    else:
        name = str(theme).strip().lower()
        if name not in THEMES:
            raise ValueError(
                f"unknown theme {theme!r}; known themes: {sorted(THEMES)} "
                '(or pass a dict of colours)')
        spec = dict(THEMES[name])
    overrides = dict(overrides or {})
    unknown = sorted(set(overrides) - set(spec))
    if unknown:
        raise ValueError(
            f'unknown theme colours {unknown}; available: {sorted(spec)}')
    spec.update(overrides)
    return spec

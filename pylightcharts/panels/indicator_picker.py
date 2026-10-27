"""pylightcharts 插件：``IndicatorPicker``（指标、衡量标准和策略）+ ``TemplatePicker``（指标模板）。

```python
from pylightcharts.panels import IndicatorPicker, TemplatePicker

picker = IndicatorPicker(chart.win, groups=GROUPS, items=items)
picker.on_pick(lambda item: add_indicator(item['key']))
picker.on_favorite(lambda item, on: save_favorite(item['key'], on))
picker.open('favorites')            # 打开时停在「收藏」

templates = TemplatePicker(chart.win, templates=[{'key': 't1', 'name': '我的模板',
                                                  'count': 2}])
templates.on_apply(lambda item: apply_template(item['key']))
templates.on_delete(lambda key: delete_template(key))
templates.on_save(lambda name: save_template(name))
templates.open()
```

事件（``;;;`` 分隔）：

* ``IndicatorPicker``：``pick;;;<key>`` / ``favorite;;;<key>;;;<0|1>``
* ``TemplatePicker``：``apply;;;<key>`` / ``delete;;;<key>`` / ``save;;;<name>``
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from .base import Panel, _derived_theme_colors

_SEP = ';;;'


class _DispatchMixin:
    def _dispatch(self, *args) -> None:            # pragma: no cover - 子类实现
        raise NotImplementedError


class IndicatorPicker(Panel):
    """「指标、衡量标准和策略」选择器（左树 + 右列表 + ★ 收藏）。"""

    def __init__(
        self,
        window,
        *,
        groups: Optional[Iterable[dict]] = None,
        items: Optional[Iterable[dict]] = None,
        title: str = '指标、衡量标准和策略',
        section: str = 'favorites',
        theme: str = 'dark',
    ):
        super().__init__(window)
        options = {
            'title': str(title),
            'groups': list(groups or []),
            'items': [_item(row) for row in (items or [])],
            'section': str(section or 'favorites'),
        }
        self._create('IndicatorPicker', options)
        self._bind_callback(self._dispatch)
        self.set_theme(theme)

        self._on_pick: Optional[Callable] = None
        self._on_favorite: Optional[Callable] = None

    # ------------------------------------------------------------- 交互
    def open(self, section: str = 'favorites') -> 'IndicatorPicker':
        self._set('open', str(section or 'favorites'))
        return self

    def close(self) -> 'IndicatorPicker':
        self._set('close')
        return self

    def set_items(self, items: Iterable[dict]) -> 'IndicatorPicker':
        self._set('setItems', [_item(row) for row in (items or [])])
        return self

    def set_groups(self, groups: Iterable[dict]) -> 'IndicatorPicker':
        self._set('setGroups', list(groups or []))
        return self

    def set_favorites(self, keys: Iterable[str]) -> 'IndicatorPicker':
        self._set('setFavorites', [str(key) for key in (keys or [])])
        return self

    def set_theme(self, theme: str) -> 'IndicatorPicker':
        self._set('setTheme', 'light' if str(theme) == 'light' else 'dark')
        return self

    def apply_theme(self, spec: dict) -> None:
        spec = spec or {}
        self.set_theme('light' if _derived_theme_colors(spec)['light']
                       else 'dark')

    # ------------------------------------------------------------- 事件
    def on_pick(self, func: Callable[[dict], None]) -> 'IndicatorPicker':
        self._on_pick = func
        return self

    def on_favorite(self, func: Callable[[dict, bool], None]) -> 'IndicatorPicker':
        """``func(item, on)`` —— ★ / ☆"""
        self._on_favorite = func
        return self

    def _dispatch(self, *args) -> None:
        message = str(args[0]) if args else ''
        parts = message.split(_SEP)
        if len(parts) < 2:
            return
        kind, key = parts[0], parts[1]
        if kind == 'pick' and self._on_pick is not None:
            self._on_pick({'key': key})
        elif kind == 'favorite' and self._on_favorite is not None:
            on = len(parts) > 2 and parts[2] in ('1', 'true', 'True')
            self._on_favorite({'key': key}, on)


class TemplatePicker(Panel):
    """「指标模板」对话框（列表 + 应用 + 删除 + 保存当前）。"""

    def __init__(
        self,
        window,
        *,
        templates: Optional[Iterable[dict]] = None,
        groups: Optional[Iterable[dict]] = None,
        theme: str = 'dark',
    ):
        super().__init__(window)
        options: dict = {'templates': [_template(row) for row in
                                       (templates or [])]}
        if groups:
            options['groups'] = list(groups)
        self._create('TemplatePicker', options)
        self._bind_callback(self._dispatch)
        self.set_theme(theme)

        self._on_apply: Optional[Callable] = None
        self._on_delete: Optional[Callable] = None
        self._on_save: Optional[Callable] = None

    # ------------------------------------------------------------- 交互
    def open(self) -> 'TemplatePicker':
        self._set('open')
        return self

    def close(self) -> 'TemplatePicker':
        self._set('close')
        return self

    def set_templates(self, templates: Iterable[dict]) -> 'TemplatePicker':
        self._set('setTemplates', [_template(row) for row in (templates or [])])
        return self

    def set_theme(self, theme: str) -> 'TemplatePicker':
        self._set('setTheme', 'light' if str(theme) == 'light' else 'dark')
        return self

    def apply_theme(self, spec: dict) -> None:
        spec = spec or {}
        self.set_theme('light' if _derived_theme_colors(spec)['light']
                       else 'dark')

    # ------------------------------------------------------------- 事件
    def on_apply(self, func: Callable[[dict], None]) -> 'TemplatePicker':
        self._on_apply = func
        return self

    def on_delete(self, func: Callable[[str], None]) -> 'TemplatePicker':
        self._on_delete = func
        return self

    def on_save(self, func: Callable[[str], None]) -> 'TemplatePicker':
        self._on_save = func
        return self

    def _dispatch(self, *args) -> None:
        message = str(args[0]) if args else ''
        parts = message.split(_SEP)
        if len(parts) < 2:
            return
        kind, value = parts[0], parts[1]
        if kind == 'apply' and self._on_apply is not None:
            self._on_apply({'key': value})
        elif kind == 'delete' and self._on_delete is not None:
            self._on_delete(value)
        elif kind == 'save' and self._on_save is not None:
            self._on_save(value)


def _item(row) -> dict:
    if isinstance(row, dict):
        return {
            'key': str(row.get('key') or ''),
            'label': str(row.get('label') or row.get('name') or ''),
            'desc': str(row.get('desc') or ''),
            'provider': str(row.get('provider') or row.get('group') or ''),
            'section': str(row.get('section') or ''),
            'favorite': bool(row.get('favorite')),
            'strategy': bool(row.get('strategy')),
            'params': list(row.get('params') or []),
        }
    return {'key': str(row), 'label': str(row), 'desc': '', 'provider': '',
            'section': '', 'favorite': False, 'strategy': False, 'params': []}


def _template(row) -> dict:
    if isinstance(row, dict):
        return {'key': str(row.get('key') or row.get('name') or ''),
                'name': str(row.get('name') or ''),
                'count': int(row.get('count') or 0),
                'items': list(row.get('items') or [])}
    return {'key': str(row), 'name': str(row), 'count': 0, 'items': []}

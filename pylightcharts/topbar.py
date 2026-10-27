import asyncio
import sys
from typing import Dict, Literal

from .util import jbool, Pane


ALIGN = Literal['left', 'right']


class Widget(Pane):
    def __init__(self, topbar, value, func: callable = None, convert_boolean=False):
        super().__init__(topbar.win)
        self.value = value

        def wrapper(v):
            if convert_boolean:
                self.value = False if v == 'false' else True
            else:
                self.value = v
            # ★ 顶栏回调（播放/单步/速度…）出错不能往外抛：外层事件循环虽然也
            #   兜底，但这里就能把“哪个控件挂了”打出来，且不会影响别的控件
            try:
                func(topbar._chart)
            except Exception as error:
                print(f'[pylightcharts] 顶栏控件 {self.id} 回调失败（已忽略）: '
                      f'{error}', file=sys.stderr)

        async def async_wrapper(v):
            self.value = v
            try:
                await func(topbar._chart)
            except Exception as error:
                print(f'[pylightcharts] 顶栏控件 {self.id} 回调失败（已忽略）: '
                      f'{error}', file=sys.stderr)

        self.win.handlers[self.id] = async_wrapper if asyncio.iscoroutinefunction(func) else wrapper


class TextWidget(Widget):
    def __init__(self, topbar, initial_text, align, func):
        super().__init__(topbar, value=initial_text, func=func)

        callback_name = f'"{self.id}"' if func else ''

        self.run_script(f'{self.id} = {topbar.id}.makeTextBoxWidget("{initial_text}", "{align}", {callback_name})\nnull')

    def set(self, string):
        self.value = string
        self.run_script(f'{self.id}.innerText = "{string}"')


class SwitcherWidget(Widget):
    def __init__(self, topbar, options, default, align, func):
        super().__init__(topbar, value=default, func=func)
        self.options = list(options)
        self.run_script(f'{self.id} = {topbar.id}.makeSwitcher({self.options}, "{default}", "{self.id}", "{align}")\nnull')

    def update_items(self, *items: str):
        """原地重建选项（按钮行重画，当前项尽量保留）。

        用在"随上层选择而变化"的顶栏上，例如按策略切换的合约栏：

            chart.topbar['contract'].update_items('pp2601', 'pp2605', '回测信息')
        """
        items = tuple(item for item in items if item)
        if not items:
            return
        keep = self.value if self.value in items else items[0]
        self.options = list(items)
        self.value = keep
        self.run_script(f'{self.id}.updateItems({list(items)}, "{keep}")')

    def set(self, option):
        if option not in self.options:
            raise ValueError(f"option '{option}' does not exist within {self.options}.")
        # Click the matching button: the JS `onItemClicked` takes the button
        # *element* (it sets the active class and reads innerText), and a click
        # is exactly what a user does - the callback fires too.
        index = self.options.index(option)
        self.run_script(f'{self.id}.intervalElements[{index}].click()')
        self.value = option


class MenuWidget(Widget):
    def __init__(self, topbar, options, default, separator, align, func):
        super().__init__(topbar, value=default, func=func)
        self.options = list(options)
        self.run_script(f'''
        {self.id} = {topbar.id}.makeMenu({list(options)}, "{default}", {jbool(separator)}, "{self.id}", "{align}")
        null
        ''')

    def set(self, option):
        """Select a menu item (labels the button and fires the callback)."""
        if option not in self.options:
            raise ValueError(f"Option {option} not in menu options ({self.options})")
        self.value = option
        self.run_script(f'{self.id}._clickHandler("{option}")')

    def update_items(self, *items: str):
        self.options = list(items)
        self.run_script(f'{self.id}.updateMenuItems({self.options})')


class ButtonWidget(Widget):
    def __init__(self, topbar, button, separator, align, toggle, func):
        super().__init__(topbar, value=False, func=func, convert_boolean=toggle)
        self.run_script(
            f'{self.id} = {topbar.id}.makeButton("{button}", "{self.id}", {jbool(separator)}, true, "{align}", {jbool(toggle)})\nnull')

    def set(self, string):
        # self.value = string
        self.run_script(f'{self.id}.elem.innerText = "{string}"')


class TopBar(Pane):
    """A row of widgets above a chart (or above the whole window).

    Widget callbacks receive the object the bar was created from: the chart
    for :attr:`AbstractChart.topbar`, the :class:`Window` for a page-level bar
    (:meth:`Window.page_topbar`), which spans the window and stays in place
    when charts are added below it.
    """

    def __init__(self, chart, page: bool = False):
        # a chart carries its window in `.win`; a Window is its own window
        window = chart.win if hasattr(chart, 'win') else chart
        super().__init__(window)
        self._chart = chart
        self._page = page
        self._widgets: Dict[str, Widget] = {}
        self._created = False

    def _create(self):
        if self._created:
            return
        self._created = True
        if self._page:
            # page-level bar: spans the window, above every chart
            self.run_script(f'{self.id} = Lib.createPageTopBar()\nnull')
            # 顶栏顶部与窗口标题栏之间加一条分隔线：浅色主题下两者都是白底，
            # 没有这条线会糊成一体
            self.run_script(
                f"{self.id}._div.style.borderTop = '2px solid var(--border-color)'")
        else:
            self.run_script(f'{self.id} = {self._chart.id}.createTopBar()\nnull')

    def __getitem__(self, item):
        if widget := self._widgets.get(item):
            return widget
        raise KeyError(f'Topbar widget "{item}" not found.')

    def get(self, widget_name):
        return self._widgets.get(widget_name)

    def switcher(self, name, options: tuple, default: str = None,
                 align: ALIGN = 'left', func: callable = None):
        self._create()
        self._widgets[name] = SwitcherWidget(self, options, default if default else options[0], align, func)

    def menu(self, name, options: tuple, default: str = None, separator: bool = True,
             align: ALIGN = 'left', func: callable = None):
        self._create()
        self._widgets[name] = MenuWidget(self, options, default if default else options[0], separator, align, func)

    def textbox(self, name: str, initial_text: str = '',
                align: ALIGN = 'left', func: callable = None):
        self._create()
        self._widgets[name] = TextWidget(self, initial_text, align, func)

    def button(self, name, button_text: str, separator: bool = True,
               align: ALIGN = 'left', toggle: bool = False, func: callable = None):
        self._create()
        self._widgets[name] = ButtonWidget(self, button_text, separator, align, toggle, func)

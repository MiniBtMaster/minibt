"""生成 / 校验 minibt 的 API 参考（``minibt_docs/docs/api/*.md``）。

用法::

    python scripts/gen_minibt_api_docs.py            # 写入 AUTO 区间
    python scripts/gen_minibt_api_docs.py --check    # 只检查（过期/缺页 → 退出码 1）

约定
----
* 每个页面的自动内容放在 ``<!-- AUTO:BEGIN -->`` / ``<!-- AUTO:END -->`` 之间，
  **区间外是手写内容，脚本不碰**；
* 只统计**手写方法**：``KLine`` / ``IndFrame`` / ``IndSeries`` / ``Line`` /
  ``BtIndicator`` 上从 12 个指标库代理来的 600+ 成员会被过滤掉
  （见 ``PROXY_OWNERS``），否则一页几千行；
* 同时生成 ``api/_coverage.md``：每个公开类落在哪一页、有多少字段/方法。

新增公开类时：在 ``PAGES`` 里给它分配页面 → 跑一次脚本 → 提交。
忘了分配 / 忘了重跑，``--check`` 会失败。
"""
from __future__ import annotations

import argparse
import dataclasses
import inspect
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
DOCS = REPO / 'minibt_docs' / 'docs' / 'api'

BEGIN = '<!-- AUTO:BEGIN -->'
END = '<!-- AUTO:END -->'

#: 这些类的方法是从第三方指标库**代理**来的，不逐条列（见 9.7）。
PROXY_OWNERS = {
    'PandasTa', 'TaLib', 'TuLip', 'FinTa', 'BtInd', 'Pine', 'TqTa', 'TqFunc',
    'Pair', 'Factors', 'TradingView', 'IndicatorsBase', 'CoreIndicators',
    'CoreFunc', 'AnalysisIndicators', 'SeriesIndicators',
}

#: 指标库本身不展开成员（只列类 + 一句话 + 代理入口）。
LIB_CLASSES = PROXY_OWNERS - {'IndicatorsBase', 'CoreIndicators', 'CoreFunc',
                              'AnalysisIndicators', 'SeriesIndicators'}

#: 每个页面收哪些类（顺序即页面里的顺序）。
PAGES: dict[str, list[str]] = {
    '01_framework.md': [
        'Bt', 'Strategy', 'Config', 'OptunaConfig', 'OptimizeConfig',
        'OpConfig', 'Gui', 'LogLevel', 'Multiply', 'IndicatorClass',
        'tq_auth', 'tq_account', 'options',
    ],
    '02_data.md': [
        'LocalDatas', 'KLine', 'IndFrame', 'IndSeries', 'Line', 'SeriesType',
        'FILED', 'StockApi', 'StockTargetPosTask',
    ],
    '03_custom_indicators.md': ['BtIndicator', 'Stop', 'stop_callback'],
    '04_indicator_libs.md': [
        'PandasTa', 'TaLib', 'TuLip', 'FinTa', 'BtInd', 'Pine',
        'TqTa', 'TqFunc', 'TradingView', 'Pair', 'Factors', 'CoreIndicators',
    ],
    '05_order_and_stop.md': [
        'OrderType', 'SizeType', 'CommissionType', 'TradeTimeFilter', 'BtStop',
        'TqAccountStore',
    ],
    '06_trade_and_viz.md': [
        'Desk',
        'PlotInfo', 'LineStyle', 'CandleStyle', 'SignalStyle', 'SpanStyle',
        'BandStyle', 'TradeStyle', 'TradeMarkerStyle', 'WaterMark',
        'SignalLabel', 'LineDash', 'Colors', 'Markers',
    ],
    '07_constants.md': ['FILED', 'MaType', 'LineDash', 'Colors', 'Markers',
                        'LogLevel', 'OrderType', 'SizeType', 'CommissionType',
                        'Gui'],
    '08_rl.md': ['Agents', 'BestAgents'],
}

PAGE_TITLES = {
    '01_framework.md': '核心框架',
    '02_data.md': '数据层',
    '03_custom_indicators.md': '自定义指标',
    '04_indicator_libs.md': '第三方指标库',
    '05_order_and_stop.md': '订单与止损',
    '06_trade_and_viz.md': '交易与可视化',
    '07_constants.md': '常量与工具',
    '08_rl.md': '强化学习',
}


# ---------------------------------------------------------------- 反射工具
def _load_minibt():
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import minibt
    return minibt


def _one_line(text: str | None, limit: int = 100) -> str:
    if not text:
        return ''
    for line in text.strip().splitlines():
        line = line.strip()
        if line and not line.startswith(('#', '```')):
            return line[:limit]
    return ''


def _clean_default(value) -> str:
    if value is dataclasses.MISSING or value is inspect.Parameter.empty:
        return '—'
    text = repr(value)
    if len(text) > 40:
        text = text[:37] + '…'
    return f'`{text}`'


def _signature(obj) -> str:
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return ''
    params = []
    for name, param in sig.parameters.items():
        if name in ('self', 'cls'):
            continue
        text = name
        if param.default is not inspect.Parameter.empty:
            text += '=' + _clean_default(param.default).strip('`')
        params.append(text)
    out = '(' + ', '.join(params) + ')'
    return out if len(out) <= 110 else out[:107] + '…)'


def _fields(cls) -> list[tuple[str, str]]:
    """(字段名, 默认值) —— dataclass 优先，否则读 __annotations__。"""
    out = []
    try:
        for f in dataclasses.fields(cls):
            out.append((f.name, _clean_default(f.default)))
    except TypeError:
        for name in getattr(cls, '__annotations__', {}):
            out.append((name, _clean_default(getattr(cls, name, dataclasses.MISSING))))
    return out


def _members(cls) -> list[tuple[str, str, str, str]]:
    """(名字, 类型, 签名, 说明) —— 沿 MRO 收集**框架自己写**的成员。

    * 只看 ``minibt.*`` 里的基类（pandas / 三方基类跳过）；
    * 派生类优先（``seen`` 去重），所以重写的方法以子类为准；
    * 代理来的指标方法（``PROXY_OWNERS``）不列。
    """
    out = []
    seen: set[str] = set()
    for base in cls.__mro__:
        if base is object:
            continue
        module = getattr(base, '__module__', '')
        if not module.startswith('minibt'):
            continue
        if base.__name__ in PROXY_OWNERS and cls.__name__ not in LIB_CLASSES:
            continue
        for name, raw in vars(base).items():
            if name.startswith('_') or name in seen:
                continue
            obj = raw
            if isinstance(obj, (staticmethod, classmethod)):
                obj = obj.__func__
            if isinstance(obj, property):
                seen.add(name)
                out.append((name, '属性', '', _one_line(obj.__doc__)))
                continue
            if not inspect.isfunction(obj):
                continue
            owner = getattr(obj, '__qualname__', '').split('.')[0]
            if owner in PROXY_OWNERS:
                continue
            seen.add(name)
            out.append((name, '方法', _signature(obj), _one_line(obj.__doc__)))
    out.sort(key=lambda item: item[0])
    return out


def render_export(obj, name: str) -> str:
    """函数 / 实例 / 类 三种导出都能渲染。"""
    if inspect.isclass(obj):
        return render_class(obj, name)
    lines = [f'### `{name}`', '']
    if callable(obj):
        doc = _one_line(getattr(obj, '__doc__', ''), 140)
        lines.append(f'函数：`{name}{_signature(obj)}`'
                     + (f' · {doc}' if doc else ''))
        lines.append('')
        return '\n'.join(lines)
    # 实例（如 LocalDatas）：列出公开属性
    doc = _one_line(getattr(type(obj), '__doc__', ''), 140)
    lines.append(f'实例：`{type(obj).__module__}.{type(obj).__name__}`'
                 + (f' · {doc}' if doc else ''))
    lines.append('')
    attrs = [a for a in dir(obj) if not a.startswith('_')]
    if attrs:
        lines.append('公开属性 / 方法：' + '、'.join(f'`{a}`' for a in attrs))
        lines.append('')
    return '\n'.join(lines)


def _cell(text: str) -> str:
    return (text or '').replace('|', '\\|').replace('\n', ' ')


# ---------------------------------------------------------------- 生成
def render_class(obj, name: str) -> str:
    target = obj if inspect.isclass(obj) else type(obj)
    module = getattr(target, '__module__', '')
    lines = [f'### `{name}`', '']
    doc = _one_line(getattr(target, '__doc__', ''), 140)
    lines.append(f'> `{module}`' + (f' · {doc}' if doc else ''))
    lines.append('')

    if name in LIB_CLASSES:
        lines.append('指标库门面：方法来自第三方库，**不逐条展开**'
                     '（见 [9.7 指标代理机制](../minibt_data/9.7_proxy.md)）。')
        lines.append('')
        return '\n'.join(lines)

    fields = _fields(target)
    members = _members(target)
    if fields:
        lines += ['| 字段 | 默认 |', '| --- | --- |']
        lines += [f'| `{n}` | {d} |' for n, d in fields]
        lines.append('')
    if members:
        lines += ['| 成员 | 类型 | 签名 | 说明 |', '| --- | --- | --- | --- |']
        for mname, kind, sig, doc in members:
            lines.append(f'| `{mname}` | {kind} | `{_cell(sig)}` | {_cell(doc)} |')
        lines.append('')
    if not fields and not members:
        lines += ['（无自有公开字段/方法；行为见基类或相关章节。）', '']
    return '\n'.join(lines)


def render_page(page: str, minibt, page_map: dict[str, list[str]]) -> str:
    names = page_map[page]
    parts = [f'## 自动生成的成员表（{PAGE_TITLES.get(page, page)}）', '',
             f'> 共 {len(names)} 个导出。由 `scripts/gen_minibt_api_docs.py` 生成，'
             '**不要手改本区间**。', '']
    for name in names:
        obj = getattr(minibt, name, None)
        if obj is None:
            parts.append(f'### `{name}`\n\n> ⚠ 当前版本未导出（检查 `minibt.__all__`）。\n')
            continue
        parts.append(render_export(obj, name))
    return '\n'.join(parts).rstrip() + '\n'


def update_page(page: str, block: str) -> None:
    path = DOCS / page
    if path.exists():
        text = path.read_text(encoding='utf-8')
    else:
        title = PAGE_TITLES.get(page, page)
        text = f'# {title}\n\n'

    wrapped = f'{BEGIN}\n{block}{END}\n'
    if BEGIN in text and END in text:
        text = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END),
                      lambda _m: wrapped.rstrip(), text, flags=re.S)
    else:
        text = text.rstrip() + '\n\n' + wrapped
    path.write_text(text, encoding='utf-8')


def _class_names(minibt) -> list[str]:
    names = [n for n in getattr(minibt, '__all__', [])]
    for extra in ('Agents', 'BestAgents'):
        if hasattr(minibt, extra) and extra not in names:
            names.append(extra)
    return names


def check(minibt) -> int:
    errors = []
    all_names = _class_names(minibt)
    assigned = {n for names in PAGES.values() for n in names}
    for name in all_names:
        obj = getattr(minibt, name, None)
        if inspect.isclass(obj) and name not in assigned:
            errors.append(f'公开类 {name} 没有分配页面（改 PAGES）')
    for page, names in PAGES.items():
        path = DOCS / page
        if not path.exists():
            errors.append(f'缺少页面 {page}')
            continue
        text = path.read_text(encoding='utf-8')
        if BEGIN not in text or END not in text:
            errors.append(f'{page} 缺少 AUTO 区间（先跑一次生成）')
            continue
        block = render_page(page, minibt, PAGES)
        match = re.search(re.escape(BEGIN) + r'(.*?)' + re.escape(END), text, re.S)
        if match and match.group(1).strip() != block.strip():
            errors.append(f'{page} 的自动区已过期（重跑脚本）')
        for name in names:
            if f'### `{name}`' not in text:
                errors.append(f'{page} 缺少 `{name}`')
    if errors:
        print('API 文档检查失败：')
        for e in errors:
            print(' -', e)
        return 1
    print(f'API 文档检查通过（{len(PAGES)} 页 / '
          f'{sum(len(v) for v in PAGES.values())} 个条目）')
    return 0


def write_coverage(minibt) -> None:
    lines = ['# API 覆盖率（自动生成）', '',
             '> 由 `scripts/gen_minibt_api_docs.py` 生成；`--check` 用它防止回退。', '',
             '| 类 / 导出 | 页面 | 字段 | 公开方法 |', '| --- | --- | --- | --- |']
    total_m = 0
    for page, names in PAGES.items():
        for name in names:
            obj = getattr(minibt, name, None)
            if obj is None or not inspect.isclass(obj):
                lines.append(f'| `{name}` | [{page}]({page}) | — | — |')
                continue
            if name in LIB_CLASSES:
                lines.append(f'| `{name}` | [{page}]({page}) | — | （代理） |')
                continue
            nf = len(_fields(obj))
            nm = len(_members(obj))
            total_m += nm
            lines.append(f'| `{name}` | [{page}]({page}) | {nf} | {nm} |')
    lines += ['', f'合计：{sum(len(v) for v in PAGES.values())} 个条目 / '
              f'{total_m} 个手写公开方法。', '']
    (DOCS / '_coverage.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='生成 minibt API 参考')
    parser.add_argument('--check', action='store_true', help='只检查，不写文件')
    args = parser.parse_args(argv)

    minibt = _load_minibt()
    if args.check:
        return check(minibt)

    DOCS.mkdir(parents=True, exist_ok=True)
    for page, names in PAGES.items():
        block = render_page(page, minibt, PAGES)
        update_page(page, block)
    write_coverage(minibt)
    print(f'已更新 {len(PAGES)} 个页面 + _coverage.md')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

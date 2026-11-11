"""技术分析（TA）自定义指标 + 模板（v1.3.7-73，P1）。

用户 2026-11-08：技术分析插件里除了内置默认模板，还能选**带 `signals` 声明**
的指标（内置 / 用户），并在「震荡 / 趋势 / 其他」三类里给出 1 / 0 / -1。

* 目录里 `has_signal` 的指标才会出现在选择器（来自 `@tobtind(signals=...)`）；
* 模板存 `user_prefs.ta_template`（单模板；空 = 用内置默认 ✓）；
* 评估复用 :mod:`minibt.signals`（和技术分析 / 圆点 / 预警同一套）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from . import indicator_catalog as _catalog

#: 设置键（`user_prefs` 白名单里也要有 ✓）
SETTING = 'ta_template'

#: 分组顺序（前端展示用）
GROUP_ORDER = ('oscillator', 'trend', 'other')
GROUP_LABELS = {'oscillator': '震荡指标', 'trend': '趋势指标',
                'other': '其他指标'}


# ---------------------------------------------------------------- 模板（多套）
def _read(name: str, default):
    try:
        from . import user_prefs as _prefs
        return _prefs.settings().get(name, default)
    except Exception:                                        # noqa: BLE001
        return default


def templates() -> Dict[str, List[Dict[str, Any]]]:
    """全部命名模板 `{名字: [条目]}`（v1.3.7-74 ✓）"""
    rows = _read('ta_templates', {})
    out: Dict[str, List[Dict[str, Any]]] = {}
    for name, items in (rows or {}).items():
        cleaned = [dict(item or {}) for item in (items or [])
                   if str((item or {}).get('key') or '')]
        if cleaned:
            out[str(name)] = cleaned
    return out


def active_name() -> str:
    return str(_read('ta_template_name', '') or '')


def activate(name: str) -> Dict[str, Any]:
    """切换到某一套模板（空 = 内置默认 ✓）"""
    from . import user_prefs as _prefs
    name = str(name or '')
    if name and name not in templates():
        return {'ok': False, 'error': f'没有这套模板：{name}'}
    _prefs.set_setting('ta_template_name', name)
    return {'ok': True, 'name': name, 'items': template(),
            'templates': sorted(templates())}


def save_named(name: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """保存（或覆盖）一套命名模板，并设为当前 ✓"""
    from . import user_prefs as _prefs
    name = str(name or '').strip() or '默认'
    current = templates()
    cleaned = []
    for row in rows or []:
        item = dict(row or {})
        key = str(item.get('key') or '').strip()
        if not key:
            continue
        cleaned.append({'key': key, 'params': dict(item.get('params') or {}),
                        'group': str(item.get('group') or 'other'),
                        'signal': dict(item.get('signal') or {}),
                        'label': str(item.get('label') or ''),
                        'line': str(item.get('line') or '')})
    current[name] = cleaned
    _prefs.set_setting('ta_templates', current)
    _prefs.set_setting('ta_template_name', name)
    return {'ok': True, 'name': name, 'count': len(cleaned),
            'templates': sorted(current)}


def delete_named(name: str) -> Dict[str, Any]:
    from . import user_prefs as _prefs
    name = str(name or '')
    current = templates()
    current.pop(name, None)
    _prefs.set_setting('ta_templates', current)
    if active_name() == name:
        _prefs.set_setting('ta_template_name', '')
    return {'ok': True, 'name': name, 'templates': sorted(current),
            'items': template()}


# ---------------------------------------------------------------- 模板
def template() -> List[Dict[str, Any]]:
    """当前模板（空列表 = 用 pylightcharts 内置默认 ✓）"""
    name = active_name()
    if name:
        rows = templates().get(name) or []
    else:
        try:
            from . import user_prefs as _prefs
            rows = _prefs.settings().get(SETTING) or []
        except Exception:                                    # noqa: BLE001
            rows = []
    out: List[Dict[str, Any]] = []
    for row in rows if isinstance(rows, (list, tuple)) else []:
        item = dict(row or {})
        if str(item.get('key') or ''):
            out.append(item)
    return out


def save_template(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """保存模板（非法条目丢掉；返回保存后的模板 ✓）"""
    cleaned: List[Dict[str, Any]] = []
    for row in rows or []:
        item = dict(row or {})
        key = str(item.get('key') or '').strip()
        if not key:
            continue
        cleaned.append({
            'key': key,
            'params': dict(item.get('params') or {}),
            'group': str(item.get('group') or 'other'),
            'signal': dict(item.get('signal') or {}),
            'label': str(item.get('label') or ''),
            'line': str(item.get('line') or ''),
        })
    from . import user_prefs as _prefs
    _prefs.set_setting(SETTING, cleaned)
    _prefs.set_setting('ta_template_name', '')
    return {'ok': True, 'count': len(cleaned), 'items': cleaned,
            'templates': sorted(templates())}


def reset_template() -> Dict[str, Any]:
    """恢复默认（= 内置 RSI / MA 全家）；命名模板**保留**，只取消激活 ✓"""
    from . import user_prefs as _prefs
    _prefs.set_setting(SETTING, [])
    _prefs.set_setting('ta_template_name', '')
    return {'ok': True, 'count': 0, 'items': [],
            'templates': sorted(templates())}


# ---------------------------------------------------------------- 选择器
def options(only_signal: bool = True) -> Dict[str, Any]:
    """目录里的指标（技术分析设置用 ✓）

    `only_signal=True`（默认）只列**已声明信号**的；
    传 False 列全部（没声明的给一个**建议信号**，用户可在对话框里改 ✓）。
    """
    try:
        items = _catalog.catalog()
    except Exception:                                        # noqa: BLE001
        items = []
    rows = []
    for item in items:
        spec = dict(item.get('signal_spec') or {})
        if not spec:
            if only_signal:
                continue
            # 没声明信号 → 给建议值（叠加类用「与前一根比较」，其余用 0 轴）
            from ..signals import Compare, Threshold, spec_of
            line = str(item.get('name') or 'value')
            suggested = (Compare(-2, 1) if item.get('overlap')
                         else Threshold(0, 1))
            spec = {line: spec_of(suggested)}
        for line, signal in spec.items():
            rows.append({
                'key': item.get('key'),
                'label': item.get('label') or item.get('name'),
                'name': item.get('name'),
                'group': str((signal or {}).get('group') or
                             ('trend' if str((signal or {}).get('kind'))
                              == 'compare' else 'oscillator')),
                'line': line,
                'signal': signal,
                'params': item.get('params') or [],
            })
    return {'ok': True, 'count': len(rows), 'items': rows,
            'groups': [{'key': key, 'label': GROUP_LABELS[key]}
                       for key in GROUP_ORDER],
            'templates': sorted(templates()), 'active': active_name()}


# ---------------------------------------------------------------- 快照
def _values_of(item: Dict[str, Any], line: str = '') -> List[float]:
    """目录 item → 数值列表（`data` = [[stamp, value], …]）"""
    data = item.get('data') or []
    out: List[float] = []
    for point in data:
        try:
            out.append(float(point[1]))
        except (TypeError, ValueError, IndexError):
            out.append(float('nan'))
    return out


def snapshot(frame, rows: Optional[Sequence[Dict[str, Any]]] = None,
             symbol: str = '') -> Dict[str, Any]:
    """按模板算指标 → 每行一个信号（1 / 0 / -1）→ groups ✓"""
    from ..signals import (evaluate_values, resolve_signal, signal_from_spec,
                           summarize)
    rows = list(rows if rows is not None else template())
    if not rows:
        # 没有自定义模板 → 用 pylightcharts 内置默认（含 RSI / MA 全家 ✓）
        from pylightcharts.panels.technical import ta_summary
        if frame is None or len(frame) == 0:
            return {'score': 0.0, 'counts': {'buy': 0, 'neutral': 0,
                                             'sell': 0},
                    'groups': [{'key': key, 'label': GROUP_LABELS[key],
                                'rows': []} for key in GROUP_ORDER],
                    'template': 'default'}
        summary = ta_summary(frame)
        summary['template'] = 'default'
        return summary
    keys = [str(row.get('key')) for row in rows]
    params = {str(row.get('key')): dict(row.get('params') or {})
              for row in rows}
    errors: Dict[str, str] = {}
    try:
        computed = _catalog.compute(frame, keys, params, limit=400,
                                    errors=errors) if frame is not None else []
    except Exception as error:                               # noqa: BLE001
        computed = []
        errors['*'] = f'{type(error).__name__}: {error}'
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for item in computed:
        raw = str((item or {}).get('key') or '')
        # 目录返回的 key 可能带线名（`pta_rsi:rsi`）→ 归到指标 key 上 ✓
        base = raw.split(':', 1)[0]
        by_key.setdefault(base, []).append(item)
    signal_rows: List[Dict[str, Any]] = []
    for row in rows:
        key = str(row.get('key'))
        group = str(row.get('group') or 'other')
        line = str(row.get('line') or '')
        spec = dict(row.get('signal') or {})
        signal = signal_from_spec(spec, group=group) if spec else None
        label = str(row.get('label') or key)
        note = ''
        items = by_key.get(key) or []
        target = None
        for item in items:
            if line and str(item.get('label') or '') == line:
                target = item
                break
        if target is None and items:
            target = items[0]
        if target is None:
            # ★ v1.3.7-104：**别把异常原文塞进 note**（用户截图看到
            #   「AssertionError: 指标返回非法数据类型…」很难看 ✗）
            #   常见原因：K 线还不够（ADX 要 2×周期）→ 短句 + 标记稍后重试
            detail = str(errors.get(key) or '')
            friendly = '数据不足' if ('NoneType' in detail
                                     or '非法数据' in detail
                                     or '没有数据' in detail)                 else ('计算失败' if detail else '没有数据')
            signal_rows.append({'key': key, 'name': label, 'value': None,
                                'signal': 0, 'group': group,
                                'note': friendly, 'error': detail[:200]})
            continue
        values = _values_of(target, line)
        latest = values[-1] if values else None
        if signal is None:
            value = 0
            note = '没有声明信号'
        else:
            value = evaluate_values(signal, values)
            note = signal.describe()
        label = str(target.get('label') or label)
        signal_rows.append({'key': key, 'name': label,
                             'value': None if latest != latest else
                             (round(latest, 4) if latest is not None
                              else None),
                             'signal': value, 'group': group, 'note': note,
                             'weight': float(getattr(signal, 'weight', 1.0)
                                             if signal else 1.0)})
    summary = summarize(signal_rows)
    groups = {key: [] for key in GROUP_ORDER}
    for row in signal_rows:
        groups[row['group'] if row['group'] in groups else 'other'].append(row)
    retry = any(str(row.get('error') or '') for row in signal_rows)
    return {
        'score': summary['score'], 'counts': summary['counts'],
        'label': summary['label'], 'retry': retry,
        'groups': [{'key': key, 'label': GROUP_LABELS[key],
                    'rows': groups[key]} for key in GROUP_ORDER],
        'template': 'custom', 'errors': errors,
    }

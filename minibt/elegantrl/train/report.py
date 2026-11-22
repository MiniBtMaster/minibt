"""Walk-forward 结果报告：Markdown / CSV 汇总。

只依赖 pandas；不引入 matplotlib / tabulate 的强制依赖。
"""
from __future__ import annotations

import os
from typing import Iterable

from .walk_forward import WalkForwardRun, runs_to_frame, summarize_runs


def _markdown_table(df) -> str:
    if df is None or df.empty:
        return '（暂无数据）'
    try:
        return df.to_markdown()
    except Exception:
        # tabulate 未安装时退回文本表
        return '```text\n' + df.to_string() + '\n```'


def walk_forward_report(runs: Iterable[WalkForwardRun],
                        *, title: str = 'Walk-forward report') -> str:
    """生成 Markdown 文本报告（逐 fold / seed + 按 seed 汇总）。"""
    runs = list(runs)
    df = runs_to_frame(runs)
    summary = summarize_runs(runs)
    lines = [
        f'# {title}',
        '',
        f'- runs: **{len(runs)}**',
        f'- seeds: **{sorted({r.seed for r in runs})}**',
        '',
        '## 按 seed 汇总',
        '',
        _markdown_table(summary),
        '',
        '## 逐 fold / seed',
        '',
        _markdown_table(df),
        '',
    ]
    return '\n'.join(lines)


def save_walk_forward_report(runs: Iterable[WalkForwardRun], path: str,
                             *, title: str = 'Walk-forward report') -> str:
    """保存 Markdown 报告，父目录自动创建。"""
    text = walk_forward_report(runs, title=title)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path


__all__ = ['walk_forward_report', 'save_walk_forward_report',
           'best_runs', 'best_seed', 'walk_forward_html',
           'save_walk_forward_html', 'sparkline_svg']


def best_runs(runs: Iterable[WalkForwardRun], *, metric: str = 'sharpe',
              n: int = 5, maximize: bool = True) -> list[WalkForwardRun]:
    """按某个净指标挑前 N 个 run；缺少该指标的结果排在最后。"""
    runs = list(runs)
    n = max(1, int(n))

    def key(run):
        value = run.metrics.get(metric)
        if value is None:
            return -float('inf') if maximize else float('inf')
        return float(value)

    return sorted(runs, key=key, reverse=maximize)[:n]


def best_seed(runs: Iterable[WalkForwardRun], *, metric: str = 'sharpe',
              maximize: bool = True) -> int | None:
    """按 seed 的 metric 均值选一个 seed。"""
    runs = list(runs)
    if not runs:
        return None
    scores = {}
    for run in runs:
        value = run.metrics.get(metric)
        if value is None:
            continue
        scores.setdefault(run.seed, []).append(float(value))
    if not scores:
        return None
    avg = {seed: sum(vals) / len(vals) for seed, vals in scores.items()}
    return max(avg, key=avg.get) if maximize else min(avg, key=avg.get)


def _equity_values(equity) -> list[float]:
    try:
        values = list(equity)
    except TypeError:
        return []
    out = []
    for value in values:
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value == value and value not in (float('inf'), float('-inf')):
            out.append(value)
    return out


def sparkline_svg(equity, *, width: int = 280, height: int = 64) -> str:
    """权益曲线 → 内联 SVG（不依赖 matplotlib）。"""
    values = _equity_values(equity)
    if len(values) < 2:
        return ''
    # 最多 240 点，避免报告文件过大
    if len(values) > 240:
        step = len(values) / 240
        values = [values[int(i * step)] for i in range(240)]
    low, high = min(values), max(values)
    span = high - low
    if span <= 0:
        span = 1.0
    points = []
    for index, value in enumerate(values):
        x = index * (width - 2) / (len(values) - 1) + 1
        y = height - 2 - (value - low) / span * (height - 4)
        points.append(f'{x:.1f},{y:.1f}')
    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<polyline fill="none" stroke="#2563eb" stroke-width="1.5" '
        f'points="{" ".join(points)}"/></svg>'
    )


def walk_forward_html(runs: Iterable[WalkForwardRun],
                      *, title: str = 'Walk-forward report') -> str:
    """简单 HTML 报告（汇总表 + 逐 run 表），不依赖 matplotlib。"""
    runs = list(runs)
    df = runs_to_frame(runs)
    summary = summarize_runs(runs)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>{title}</title>'
        '<style>body{font-family:system-ui,sans-serif;margin:24px}'
        'table{border-collapse:collapse;margin:12px 0}'
        'th,td{border:1px solid #ddd;padding:4px 8px;font-size:13px}'
        'th{background:#f3f4f6}</style></head><body>'
        f'<h1>{title}</h1><p>runs: {len(runs)}</p>'
        '<h2>按 seed 汇总</h2>'
        + (summary.to_html() if not summary.empty else '（暂无数据）')
        + '<h2>逐 fold / seed</h2>'
        + (df.to_html(index=False) if not df.empty else '（暂无数据）')
        + '<h2>权益曲线</h2>'
        + ''.join(
            f'<div style="margin:8px 0"><b>fold {i} / seed {run.seed}</b>'
            f'{sparkline_svg(run.equity)}</div>'
            for i, run in enumerate(runs) if run.equity is not None
        )
        + '</body></html>'
    )


def save_walk_forward_html(runs: Iterable[WalkForwardRun], path: str,
                           *, title: str = 'Walk-forward report') -> str:
    text = walk_forward_html(runs, title=title)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path

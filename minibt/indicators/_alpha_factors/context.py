"""Alpha101 / Alpha191 因子的**执行环境**（数据源 = 调用方传进来的 IndFrame ✓）

设计：

* **数据就是数据**：调用方给什么就用什么 —— `IndFrame` / K 线里如果有
  `securityid` / `tradetime` / `indclass` / `cap` 等**面板列**，直接交给上游
  `alpha.context.ExecContext`（多标的横截面因子就能算）；没有就按**单标的**
  处理（`securities = 1`，纯时序因子照常算）；
* **不预判、不拦错**：因子需要哪些列用户自己准备，缺了 / 用错了由 alpha
  抛**原生错误**（框架不做额外封装）✓；
* `alpha` 的上下文是**线程全局**的 → 一律在 `Context(groups=标的数)` 里跑，
  跑完还原（不污染别的调用 ✓）。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

__all__ = ['factor_frame', 'compute_values', 'compute_series', 'panel_values',
           'factor_info', 'available']

#: 面板列（有就透传给上游 `ExecContext` ✓）
PANEL_COLUMNS = ('securityid', 'tradetime', 'open', 'high', 'low', 'close',
                 'vol', 'vwap', 'amount', 'indclass', 'cap')

NOT_INSTALLED = ('Alpha101 / Alpha191 因子需要安装 py-alpha-lib：'
                 'py -3.12 -m pip install py-alpha-lib')


def _require_alpha():
    try:
        import alpha  # noqa: F401
        from alpha.context import Context, ExecContext
    except Exception as error:                                   # noqa: BLE001
        raise RuntimeError(NOT_INSTALLED) from error
    return Context, ExecContext


def _as_frame(data) -> pd.DataFrame:
    """任意入口（K 线 / IndFrame / CoreFunc 自己）→ DataFrame（小写列 ✓）"""
    if isinstance(data, pd.DataFrame):
        frame = data
    else:
        for attr in ('_df', 'pandas_object', 'kline_object'):
            candidate = getattr(data, attr, None)
            if isinstance(candidate, pd.DataFrame):
                frame = candidate
                break
        else:
            frame = pd.DataFrame(data)
    if any(str(column).islower() for column in frame.columns):
        return frame
    return frame.rename(columns={column: str(column).lower()
                                 for column in frame.columns})


def _column(data, *names) -> np.ndarray | None:
    """取一列（缺了返回 None ✓）"""
    for name in names:
        try:
            value = data[name]
        except Exception:                                        # noqa: BLE001
            continue
        array = np.asarray(getattr(value, 'to_numpy', lambda: value)(),
                           dtype=np.float64)
        if array.ndim == 2 and array.shape[1] == 1:
            array = array.ravel()
        if array.ndim == 1 and array.size:
            return array
    return None


def factor_frame(data) -> pd.DataFrame:
    """`IndFrame` / K 线 → 上游 `ExecContext` 需要的面板 DataFrame ✓

    * **有 `securityid` + `tradetime` 就原样用**（多标的横截面因子 ✓）；
    * 没有就补成**单标的**（`securityid = 0`，`tradetime = 0..n-1`）；
    * `vol` 取 `volume` / `vol`；`vwap` 有 `amount` + `volume` 就用
      `amount / volume`，否则退回典型价 `(high + low + close) / 3`；
    * `indclass` / `cap` / `amount` 等列**有就透传**（横截面因子要用）✓
    """
    frame = _as_frame(data)
    close = _column(frame, 'close')
    if close is None or close.size == 0:
        raise ValueError('Alpha 因子需要 close 序列（IndFrame / K 线）')
    length = close.size
    high = _column(frame, 'high')
    low = _column(frame, 'low')
    open_ = _column(frame, 'open')
    volume = _column(frame, 'volume', 'vol')
    amount = _column(frame, 'amount', 'turnover')

    if high is None:
        high = close
    if low is None:
        low = close
    if open_ is None:
        open_ = close
    if volume is None:
        volume = np.ones(length, dtype=np.float64)

    vwap = _column(frame, 'vwap')
    if vwap is None:
        if amount is not None:
            safe = np.where(volume > 0, volume, np.nan)
            candidate = amount / safe
            vwap = candidate if np.isfinite(candidate).sum() > length // 2 \
                else (high + low + close) / 3.0
        else:
            vwap = (high + low + close) / 3.0

    out = pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': close,
        'vol': volume, 'vwap': vwap,
    })
    security = _column(frame, 'securityid')
    trade = _column(frame, 'tradetime')
    out['securityid'] = (security.astype(np.int64) if security is not None
                         else np.zeros(length, dtype=np.int64))
    out['tradetime'] = (trade.astype(np.int64) if trade is not None
                        else np.arange(length, dtype=np.int64))
    for name in ('amount', 'indclass', 'cap'):
        values = _column(frame, name)
        if values is not None:
            out[name] = values
    out.index = frame.index                 # 保留时间索引 ✓
    return out


def _context(frame: pd.DataFrame):
    """面板 → 上游 `ExecContext`（`AMOUNT` 用真实成交额，没有就退回成交量 ✓）"""
    Context, ExecContext = _require_alpha()

    class _PanelContext(ExecContext):
        """上游 ctx 的小补丁（两处，都是为了**别让一条线整条消失** ✓）

        1. `AMOUNT` 字段优先用真实成交额（GTJA 191 用得到）；
        2. **递归 `SMA` 跳过非有限样本**：通达信式 `SMA(x,n,m)` 是
           `y = (m·x + (n-m)·y_prev)/n`，一旦有一个 `NaN` / `±inf` 进来
           就**永久中毒**（后面永远 NaN / inf）→ 图上没有线（用户实测
           `Alpha191.alpha028` 就是这种情况，公式里 `H-L` 在平价 K 线上
           会除零）。这里只在该样本**缺失**时保持上一个值，输入全有限时
           仍然直接交给上游（数值完全一致 ✓）。
        """

        def __init__(self, data):
            super().__init__(data)
            try:
                self._amount = np.asarray(data['amount'], dtype=np.float64)
            except Exception:                                    # noqa: BLE001
                self._amount = None

        def __call__(self, name: str):
            if name == 'AMOUNT' and self._amount is not None:
                return self._amount
            return super().__call__(name)

        def SMA(self, a, *args):
            """通达信式 `SMA(x, n, m)`；**非有限样本跳过**（保持上一个值）✓"""
            values = np.asarray(a, dtype=np.float64)
            if len(args) < 2 or np.isfinite(values).all():
                return super().SMA(a, *args)
            window, weight = int(args[0]), int(args[1])
            out = np.full(values.shape, np.nan, dtype=np.float64)
            previous = None
            for index, value in enumerate(values):
                if not np.isfinite(value):
                    out[index] = (previous if previous is not None
                                  else np.nan)
                    continue
                if previous is None or not np.isfinite(previous):
                    previous = float(value)                     # 首个有效值做种子
                else:
                    previous = (weight * float(value)
                                + (window - weight) * previous) / window
                out[index] = previous
            return out

    return _PanelContext(frame)


def _registry():
    from .registry import FAMILIES, FACTORS          # noqa: PLC0415

    return FAMILIES, FACTORS


def factor_info(family: str, no: int) -> dict:
    """编号 → 元数据（`func` / `kind` / `formula`）；越界抛 `ValueError` ✓"""
    families, factors = _registry()
    if family not in factors:
        raise ValueError(f'未知因子家族 {family!r}：可选 '
                         f'{", ".join(sorted(factors))}')
    numbers = factors[family]
    try:
        number = int(no)
    except (TypeError, ValueError) as error:
        raise ValueError(f'因子编号必须是整数：{no!r}') from error
    if number not in numbers:
        upper = families[family]['count']
        raise ValueError(f'{families[family]["label"]} 只有 1~{upper}：{number}')
    meta = dict(numbers[number])
    meta['no'] = number
    meta['family'] = family
    return meta


def _module(family: str):
    """`_alpha_factors.<family>`（用**包名**拼，别用 `__name__` ✗）"""
    import importlib

    return importlib.import_module(f'minibt.indicators._alpha_factors.{family}')


def compute_values(frame: pd.DataFrame, family: str, no: int) -> np.ndarray:
    """面板 DataFrame → 因子值数组（**单标的 / 多标的都行** ✓）"""
    Context, _ = _require_alpha()
    meta = factor_info(family, no)
    func = getattr(_module(family), meta['func'])
    try:
        securities = int(pd.Series(frame['securityid']).nunique())
    except Exception:                                            # noqa: BLE001
        securities = 1
    # ⚠ 面板要在 `with` **里面**建：`ExecContext.__init__` 会 apply 一次
    #   线程上下文（groups=标的数），先建就漏到外面去了 ✗
    with Context(groups=max(1, securities)):
        context = _context(frame)
        values = np.asarray(func(context), dtype=np.float64)
    return values


def _clean(values: np.ndarray) -> np.ndarray:
    """`±inf` → `NaN`（除零等极端值按「缺失」处理，图表才能画 ✓）"""
    out = np.asarray(values, dtype=np.float64)
    if np.isinf(out).any():
        out = np.where(np.isinf(out), np.nan, out)
    return out


def compute_series(data, family: str, no: int):
    """`IndFrame` / K 线 → `pd.Series`（数据不对就让 alpha 抛原生错误 ✓）"""
    frame = factor_frame(data)
    values = _clean(compute_values(frame, family, no))
    return pd.Series(values, index=frame.index)


def panel_values(data, family: str, no: int) -> pd.Series:
    """多标的 DataFrame → 因子值（保持原行数，`minibt.factor.panel()` 用 ✓）"""
    frame = _as_frame(data)
    values = _clean(compute_values(factor_frame(frame), family, no))
    if len(values) != len(frame):
        raise ValueError(f'{family} #{no} 输出长度 {len(values)} 和输入 '
                         f'{len(frame)} 不一致')
    return pd.Series(values, index=frame.index)


def available(family: str | None = None) -> dict[str, Any]:
    """可用的因子清单（编号 / 公式 / 类型 ✓），`minibt.factor.available()` 用"""
    families, factors = _registry()
    keys = [family] if family else list(factors)
    out: dict[str, Any] = {}
    for key in keys:
        if key not in factors:
            raise ValueError(f'未知因子家族 {key!r}')
        out[key] = {
            'label': families[key]['label'],
            'count': families[key]['count'],
            'factors': {no: {'kind': meta['kind'],
                             'formula': meta['formula']}
                        for no, meta in sorted(factors[key].items())},
        }
    return out

"""时间序列切分 / walk-forward 工具（RL 样本外改造）。

金融数据不能随机切分：相邻 K 线高度相关，随机验证会泄漏。这里的工具只做
**按时间顺序**的切分，并支持 purge（训练/验证/测试之间丢弃若干根）。

用法::

    from minibt.elegantrl.train.splits import split_dataframe

    train_df, val_df, test_df = split_dataframe(
        df, train=0.6, val=0.2, purge=60)

    for window in walk_forward_windows(
            len(df), train_size=1200, val_size=300,
            test_size=300, step=300, purge=60):
        train = df.iloc[window.train]
        val = df.iloc[window.val]
        test = df.iloc[window.test]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TimeWindow:
    """一个按位置切分的时间窗口（半开区间 ``[start, end)``）。"""

    train_start: int
    train_end: int
    val_start: int
    val_end: int
    test_start: int
    test_end: int

    @property
    def train(self) -> slice:
        return slice(self.train_start, self.train_end)

    @property
    def val(self) -> slice:
        return slice(self.val_start, self.val_end)

    @property
    def test(self) -> slice:
        return slice(self.test_start, self.test_end)


def split_indices(n_samples: int, *, train: float = 0.6,
                  val: float = 0.2, purge: int = 0) -> TimeWindow:
    """按比例切 train / val / test，并在相邻段之间 purge。"""
    n_samples = int(n_samples)
    if n_samples < 3:
        raise ValueError('至少需要 3 个样本')
    if not (0 < train < 1):
        raise ValueError('train 必须在 (0, 1)')
    if not (0 < val < 1) or train + val >= 1:
        raise ValueError('val 必须在 (0, 1)，且 train + val < 1')
    purge = max(0, int(purge))

    train_end = max(1, int(n_samples * train))
    val_start = min(n_samples, train_end + purge)
    # train / val 保持目标数量，purge 只增加间隔；test 使用剩余尾部
    val_end = min(n_samples, val_start + max(1, int(n_samples * val)))
    test_start = min(n_samples, val_end + purge)
    if train_end <= 0 or val_end <= val_start or test_start >= n_samples:
        raise ValueError(
            f'切分后没有足够数据: n={n_samples}, train_end={train_end}, '
            f'val=[{val_start},{val_end}), test_start={test_start}')
    return TimeWindow(0, train_end, val_start, val_end,
                      test_start, n_samples)


def split_dataframe(df, *, train: float = 0.6, val: float = 0.2,
                    purge: int = 0):
    """返回 ``(train_df, val_df, test_df)``，均按时间顺序。"""
    window = split_indices(len(df), train=train, val=val, purge=purge)
    def take(sl):
        part = df.iloc[sl] if hasattr(df, 'iloc') else df[sl]
        return part.copy() if hasattr(part, 'copy') else part
    return (take(window.train), take(window.val), take(window.test))


def walk_forward_windows(n_samples: int, *, train_size: int,
                         val_size: int, test_size: int,
                         step: int | None = None,
                         purge: int = 0) -> Iterator[TimeWindow]:
    """滚动生成 train / validation / test 窗口。

    ``step`` 默认等于 ``test_size``；每滚动一次，窗口整体向前移动。
    """
    n_samples = int(n_samples)
    train_size = int(train_size)
    val_size = int(val_size)
    test_size = int(test_size)
    purge = max(0, int(purge))
    step = int(step or test_size)
    if min(train_size, val_size, test_size, step) <= 0:
        raise ValueError('train_size / val_size / test_size / step 必须 > 0')
    total = train_size + purge + val_size + purge + test_size
    if total > n_samples:
        return
    for start in range(0, n_samples - total + 1, step):
        train_start = start
        train_end = train_start + train_size
        val_start = train_end + purge
        val_end = val_start + val_size
        test_start = val_end + purge
        test_end = test_start + test_size
        yield TimeWindow(train_start, train_end, val_start, val_end,
                         test_start, test_end)


__all__ = ['TimeWindow', 'split_indices', 'split_dataframe',
           'walk_forward_windows']

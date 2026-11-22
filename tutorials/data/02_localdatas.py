"""9.2 · LocalDatas —— 本地数据源

演示要点
--------
``LocalDatas`` 是**数据索引**：每个内置/用户数据集是一个 ``DataString``
（`str` 子类），名字就是数据集名。

| 用法 | 返回 | 说明 |
| --- | --- | --- |
| ``LocalDatas.test`` | `DataString` | 数据集名字对象 |
| ``LocalDatas.test.kline`` | `KLine` | 直接拿可用的 K 线 |
| ``LocalDatas.test.dataframe`` | `DataFrame` | 原始 13 列 |
| ``LocalDatas.get(name)`` | `DataString` | 按字符串取 |
| ``LocalDatas.get_dataframe(name)`` | `DataFrame` | 按名字取原始表 |
| ``LocalDatas.get_path(name)`` | `str` | CSV 文件路径 |
| ``LocalDatas.keep(*names)`` | `LocalDatas` | 只保留这些，删掉用户目录其余 |
| ``LocalDatas.deleter(*names)`` | `LocalDatas` | 删除用户目录里的文件 |
| ``LocalDatas.rename(old, new)`` | `LocalDatas` | 重命名（先懒拷贝到用户目录） |
| ``LocalDatas.update()`` / ``rewrite()`` | — | 重建索引 / 重新扫描 CSV |

⚠️ ``keep`` / ``deleter`` / ``rename`` 会**改动磁盘文件**（只在 ``~/.minibt/datas``
用户目录；包内基础数据不受影响）—— 本例只打印说明，不真的执行。

运行：``python tutorials/data/02_localdatas.py``
文档：``minibt_docs/docs/minibt_data/9.2_localdatas.md``
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    names = [n for n in dir(LocalDatas) if not n.startswith('_')]
    print('① LocalDatas 上的名字:', names)

    datasets = [n for n in names
                if not callable(getattr(LocalDatas, n, None))]
    for name in datasets:
        d = getattr(LocalDatas, name)
        print(f'② {name:10s} -> {type(d).__name__}, str()={str(d)!r}')
        print('   path      =', LocalDatas.get_path(name))
        df = LocalDatas.get_dataframe(name)
        print('   dataframe =', df.shape,
              '|', df['datetime'].iloc[0], '→', df['datetime'].iloc[-1])

    d = LocalDatas.get('test')            # 按字符串取
    print('③ LocalDatas.get("test") ->', type(d).__name__, '| str():', str(d))
    print('   d.kline      ->', type(d.kline).__name__, '| len:', len(d.kline))
    print('   d.dataframe  ->', d.dataframe.shape)

    df = LocalDatas.get_dataframe('test')
    print('④ 原始 13 列:', list(df.columns))
    print('   dtypes:', {k: str(v) for k, v in df.dtypes.items()})

    # ⑤ 会改磁盘文件的接口（这里只说明，不执行）
    print('⑤ keep/deleter/rename 会改 ~/.minibt/datas 里的文件，本例不执行')
    print('   LocalDatas.keep("test")            # 只留 test')
    print('   LocalDatas.rename("test", "x")     # 改名')
    print('   LocalDatas.update()                # 重建索引')


if __name__ == '__main__':
    main()

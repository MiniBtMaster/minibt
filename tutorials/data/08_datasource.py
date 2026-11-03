"""9.8 · 数据源 —— CSV / DataFrame / tqsdk / 股票 / 随机数据

演示要点
--------
`Strategy` 上有一组 `kline_from_*`，`get_kline()` 是**统一入口**（按 symbol 类型
自动选源）。优先级（回测模式）：

```text
① 本地 CSV（~/.minibt/datas 优先，包内 minibt/data/test 兜底）
② symbol 直接是文件路径
③ TQSDK 在线（期货，需账号）
④ 外部 pd.DataFrame（缺 OHLCV 会报错；缺合约字段自动补默认）
⑤ 股票在线（akshare / pytdx / baostock，data_source 切换）
⑥ 已缓存的 _api（天勤）
⑦ _datas 里已加载的数据
```

本例只跑**离线**的几种（内置 / CSV / DataFrame / 随机），在线的只打印签名。

运行：``python tutorials/data/08_datasource.py``
文档：``minibt_docs/docs/minibt_data/9.8_datasource.md``
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from minibt import *


def main(gui=None):
    strategy = Strategy()

    # ① 内置数据
    k1 = LocalDatas.test.kline
    print('① 内置:', type(k1).__name__, '|', len(k1), '根 |',
          k1.symbol, '| cycle', k1.cycle)

    # ② CSV 路径
    path = LocalDatas.get_path('test')
    k2 = strategy.kline_from_path(path)
    print('② kline_from_path:', len(k2), '根 |', path)

    # ③ 外部 DataFrame
    df = LocalDatas.get_dataframe('test')
    k3 = strategy.kline_from_dataframe(df)
    print('③ kline_from_dataframe:', df.shape, '->', len(k3), '根 |',
          k3.symbol)

    # ④ 随机数据（离线、不用账号）
    k4 = strategy.kline_random(symbol='demo', duration_seconds=60,
                               data_length=200)
    print('④ kline_random:', len(k4), '根 |', k4.symbol, '| cycle', k4.cycle)

    # ⑤ 统一入口 get_kline
    k5 = strategy.get_kline(df, duration_seconds=300)
    print('⑤ get_kline(DataFrame):', len(k5), '根 |', k5.symbol)
    k6 = strategy.get_kline(LocalDatas.test, duration_seconds=300,
                            data_length=500)
    print('   get_kline(LocalDatas.test, data_length=500):', len(k6), '根')

    # ⑥ 在线数据源（只打印签名，不联网）
    for name in ('kline_from_tqsdk', 'kline_from_baostock', 'kline_from_pytdx',
                 'kline_futures_from_akshare', 'kline_stock_from_akshare'):
        fn = getattr(Strategy, name)
        print(f'⑥ {name}{inspect.signature(fn)}')

    print('⑦ 股票数据源切换：get_kline("600000", data_source="akshare"'
          ' / "pytdx" / "baostock")')


if __name__ == '__main__':
    main()

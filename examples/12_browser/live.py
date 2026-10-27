"""浏览器查看（实时）：本地标准库服务 + SSE，边算边推。

    python examples/12_browser/live.py

构图与 `static.py` 完全一样（主图 SMA 20、副图 RSI 14），区别只在
`live=True`：

- `show(block=False)` 起一个**标准库** HTTP 服务并打开标签页，返回 URL；
- 示例固定用 8123 端口（端口被占用时会自动换一个空闲端口并给出警告，
  `chart.url` 始终是真实地址）：地址不变，浏览器里按 F5 就能重连，适合长期开着；
- 之后每次 `chart.update(bar)` 都会立刻推到所有打开的标签页 —— 走
  Server-Sent Events，指标（SMA / RSI）由框架自己增量重算，无需手动处理；
- **不写磁盘**：数据一直在内存（`candle_data` / 各 `series.data`）；
- 新标签页或按 F5 会收到一次当前数据（`resync=True`），随后只收增量；
- 页面顶栏的"暂停"按钮演示控件回调：浏览器 POST 回来，在 Python 里执行。

readback（`chart_options()` / `screenshot()` / `constants.verify()` 等）在实时
模式不可用：浏览器标签没有同步回执通道（和 `HeadlessChart` 一样）。
"""
import math
import time

import numpy as np
import pandas as pd

from pylightcharts import BrowserChart

ROWS = 300


def make_data(rows: int = ROWS, seed: int = 1213) -> pd.DataFrame:
    """已经走完的历史（预热指标用）。"""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(rows) * 0.7)
    open_ = close + rng.standard_normal(rows) * 0.4
    return pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=rows, freq='min'),
        'open': open_,
        'high': np.maximum(open_, close) + 0.5,
        'low': np.minimum(open_, close) - 0.5,
        'close': close,
        'volume': rng.integers(100, 900, rows),
    })


def next_bar(last: pd.Series, index: int) -> pd.Series:
    """生成下一条分钟线（真实项目里换成行情推送即可）。

    注意 `last` 来自 `chart.candle_data`：那里的 `time` 已经是 **epoch 秒**
    （框架给引擎的格式），所以这里直接 +60 秒 —— 千万不要再套
    `pd.Timestamp(...)`（它会把整数当纳秒，结果落到 1970 年，图表就"停住"了）。
    """
    close = float(last['close'])
    value = close + 0.5 * math.sin(index / 4) + 0.05
    return pd.Series({
        'time': int(last['time']) + 60,
        'open': close,
        'high': max(close, value) + 0.4,
        'low': min(close, value) - 0.4,
        'close': value,
        'volume': 200 + (index % 5) * 100,
    })


def build(chart) -> None:
    """和 static.py 一样的构图：主图 SMA 20 + 副图 RSI 14。"""
    chart.set(make_data())
    chart.legend(True)
    chart.add_sma('close', 20, color='#FF9800')       # 主图
    chart.add_rsi(14, pane_index='new')               # 副图


def main() -> None:
    # port=8123：固定地址（占用时自动回退到空闲端口并报警告）
    chart = BrowserChart(width=1200, height=760, live=True, port=8123)
    build(chart)

    state = {'paused': False}

    def on_pause(target):
        # 浏览器里的按钮点一下就回到这里（POST /callback）
        state['paused'] = not state['paused']
        chart.topbar['pause'].set('继续' if state['paused'] else '暂停')
        print('[topbar] paused ->', state['paused'])

    chart.topbar.button('pause', '暂停', func=on_pause)

    url = chart.show(block=False)                 # 打开标签页，主线程继续喂数据
    print('实时图表已启动：', url)
    print('（F5 会重新同步当前数据；Ctrl+C 结束）')
    print('页面右下角有个 "live · N" 角标：N 每秒 +1 就是真的在实时刷新，'
          '断开会变红并说明原因（status=False 可关掉）。')
    print('示例固定 8123：show() 会新开一个标签页（避免看到旧页面），'
          '也可以长期用上面打印的地址 + F5；端口被占用会自动回退到空闲端口。')

    frame = chart.candle_data
    last, index = frame.iloc[-1], 0
    try:
        while True:
            if not state['paused']:
                bar = next_bar(last, index)
                chart.update(bar)                 # 主图与两个指标一起实时更新
                last, index = bar, index + 1
                if index % 15 == 0:
                    print(f'[{index:4d}] close={bar["close"]:.2f} '
                          f'clients={chart.clients}')
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n停止服务')
    finally:
        chart.stop()


if __name__ == '__main__':
    main()

"""11.5 · 断线重连与容错（非 tqsdk 源）

演示要点
--------
⚠ **tqsdk 会自动重连**（`ReconnectTimer` + `MdReconnectHandler`）：
用 `Bt(live=True)` 时**不要**自己重建 `TqApi`，看 11.5 的「tqsdk：自动重连」一节。
本例的退避循环适用于 **futu / 自建 ws / REST** 等没有自动重连的数据源：

```python
while True:
    try:
        if not api.wait_update():
            break
        ...                      # 处理行情
    except Exception as error:
        print('断线：', error)
        time.sleep(backoff)
        api = reconnect()        # 非 tqsdk 源：重建客户端
```

本例用**假 api** 演示"指数退避重连"的写法（不联网）。

运行：``python tutorials/realtime/05_reconnect.py``
文档：``minibt_docs/docs/minibt_realtime/11.5_reconnect.md``
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


class FakeApi:
    """模拟一个会断线 N 次的 api。"""

    def __init__(self, fails: int):
        self.fails = fails
        self.calls = 0

    def wait_update(self):
        self.calls += 1
        if self.fails > 0:
            self.fails -= 1
            raise ConnectionError('模拟断线')
        return True


def run_with_retry(api, max_retry: int = 5, backoff: float = 0.01):
    """指数退避重连：0.01s / 0.02s / 0.04s …"""
    for attempt in range(1, max_retry + 1):
        try:
            return api.wait_update(), attempt
        except ConnectionError as error:
            delay = backoff * 2 ** (attempt - 1)
            print(f'   第 {attempt} 次断线：{error} → {delay:.3f}s 后重试')
            time.sleep(delay)
    raise RuntimeError(f'{max_retry} 次重连都失败')


def main(gui=None):
    # ① 断 3 次后恢复
    api = FakeApi(fails=3)
    ok, attempt = run_with_retry(api)
    print('① 恢复:', ok, '| 总共尝试', attempt, '次 | '
          'wait_update 调用', api.calls, '次')

    # ② 一直断线 → 放弃
    api = FakeApi(fails=99)
    try:
        run_with_retry(api, max_retry=3)
    except RuntimeError as error:
        print('② 放弃:', error)

    # ③ 实盘里还要注意
    print('③ 其它容错：')
    print('   - 非交易时段 wait_update 会长时间阻塞（用 deadline）')
    print('   - 断线期间**不要**再下单；恢复后先同步持仓（api.get_position）')
    print('   - 记录断线时间点，回补缺失 K 线（get_kline_serial 重取）')


if __name__ == '__main__':
    main()

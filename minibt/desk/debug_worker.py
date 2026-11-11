# coding: utf-8
"""调试 worker 入口：`python -u -m minibt.desk.debug_worker <script.py> [行号...]`

单独成模块是为了 `python -m` 能直接跑（`debugger.py` 里同时有 desk 侧会话类，
直接 `-m` 会连带 import 一堆 desk 依赖 ✓）。
"""
from __future__ import annotations

import sys


def main() -> int:
    from .debugger import main as worker_main
    return worker_main(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())

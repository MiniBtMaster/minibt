"""``python -m minibt <子命令>``（等价于安装后的 ``minibt`` 命令 ✓）。

    python -m minibt desk --offline
    python -m minibt desk --user 账号 --password 密码

> 用模块方式跑**不需要**安装命令行入口，仓库里直接就能用。
"""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())

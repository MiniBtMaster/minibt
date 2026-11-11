"""`minibt.desk.info` —— 资讯 / 财经日历 / 宏观（P0，v1.3.7-62）。

用法：

    from minibt.desk import info
    info.news('flash')                      # 读缓存（立刻返回）
    info.refresh_news('flash', on_done=cb)  # 后台抓（OK 后回调）
    info.calendar(days=3)
    info.home_events()                      # 首页两行（含兜底）
    info.status()

依赖 **AkShare（可选）**：`pip install "minibt[news]"`；没装时
`status()['installed']` 为 False，页面会提示一条安装命令。
"""
from . import cache, providers, service
from .service import (calendar, clear, home_events, macro, news,
                      refresh_calendar, refresh_news, refresh_symbol,
                      refresh_symbol_news, status, symbol_events,
                      symbol_info, symbol_news)

__all__ = ['calendar', 'clear', 'home_events', 'macro', 'news',
           'refresh_calendar', 'refresh_news', 'refresh_symbol',
           'refresh_symbol_news', 'status', 'symbol_events', 'symbol_info',
           'symbol_news', 'cache', 'providers', 'service']

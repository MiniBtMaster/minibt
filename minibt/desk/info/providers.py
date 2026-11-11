"""资讯 / 日历 / 宏观 **数据源适配层**（v1.3.7-62，P0）。

设计要点（用户 2026-11-08 确认）：

* **AkShare 是可选依赖**（`pip install minibt[news]`）：没装时页面 / 工具回
  `need_install`，desk 照常启动；
* **不要裸爬**：新闻 / 日历 / 宏观 / 财务全部走封装库（库自带会话与反爬）；
* 每个数据类有**主接口 + 备接口**，单接口失效只降级该模块；
* 全局限速（默认 0.6s 一次）+ 失败重试（2 次，指数退避）；
* 结果一律落到 :mod:`cache`（SQLite），页面优先用缓存，抓取在后台线程。

对外只暴露 :mod:`service` 里的函数；本模块只负责「抓 + 归一化」。
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
import warnings
from typing import Any, Dict, List, Optional

# ★ v1.3.7-76：AkShare 内部实现会 `frame.insert` 几十次 →
#   pandas 抛 `PerformanceWarning`，Qt / 终端日志被刷屏 ✗
#   这里在**调用 AkShare 的线程**里统一静音（不影响其它代码 ✓）
try:                                                    # pragma: no cover
    from pandas.errors import PerformanceWarning as _PW
except Exception:                                       # noqa: BLE001
    class _PW(Warning):                                 # type: ignore
        pass

#: （动作, 警告类）—— AkShare 内部 pandas / numpy 噪声 ✓
_WARN_FILTERS = [('ignore', _PW), ('ignore', FutureWarning)]

#: AkShare 内部 tqdm 进度条（`0%| | 0/16 …`）→ 用环境变量关掉 ✓
os.environ.setdefault('TQDM_DISABLE', '1')

#: 两次抓取之间的最小间隔（秒）——库内部会发真实请求，别打太快 ✓
MIN_INTERVAL = 0.6

#: 失败重试次数 / 退避基数
RETRIES = 2
BACKOFF = 0.8

_LOCK = threading.Lock()
_LAST_CALL = [0.0]
_LAST_ERROR = ['']


class ProviderError(RuntimeError):
    """数据源不可用（未安装 / 网络 / 接口失效）"""


def _throttle() -> None:
    with _LOCK:
        wait = MIN_INTERVAL - (time.monotonic() - _LAST_CALL[0])
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL[0] = time.monotonic()


def last_error() -> str:
    return _LAST_ERROR[0]


def akshare_info() -> Dict[str, Any]:
    """AkShare 装了没（version / import 错误）✓"""
    try:
        import akshare  # noqa: F401
        return {'installed': True,
                'version': str(getattr(akshare, '__version__', '') or ''),
                'error': ''}
    except Exception as error:                               # noqa: BLE001
        return {'installed': False, 'version': '',
                'error': f'{type(error).__name__}: {error}',
                'hint': 'pip install akshare（或 pip install "minibt[news]"）'}


def _ak():
    try:
        import akshare
    except Exception as error:                               # noqa: BLE001
        raise ProviderError('没装 AkShare：pip install minibt[news]') from error
    return akshare


def _call(name: str, *args, **kwargs):
    """调用 AkShare 接口：限速 + 重试 + 统一错误（静音警告噪声 ✓）"""
    ak = _ak()
    fn = getattr(ak, name, None)
    if fn is None:
        raise ProviderError(f'AkShare 没有接口 {name}（版本太旧？）')
    error: Optional[Exception] = None
    for attempt in range(RETRIES + 1):
        _throttle()
        try:
            with warnings.catch_warnings():
                for action, category in _WARN_FILTERS:
                    warnings.filterwarnings(action, category=category)
                frame = fn(*args, **kwargs)
            _LAST_ERROR[0] = ''
            return frame
        except Exception as exc:                             # noqa: BLE001
            error = exc
            _LAST_ERROR[0] = f'{name}: {type(exc).__name__}: {exc}'
            if attempt < RETRIES:
                time.sleep(BACKOFF * (attempt + 1))
    raise ProviderError(_LAST_ERROR[0]) from error


# ---------------------------------------------------------------- 归一化
def _text(value: Any, limit: int = 400) -> str:
    text = str(value if value is not None else '').strip()
    if text.lower() in ('nan', 'none', 'nat'):
        return ''
    return text[:limit]


def _stamp(value: Any) -> str:
    """各种时间写法 → `YYYY-MM-DD HH:MM`（排序 / 去重都用它 ✓）"""
    text = _text(value, 40)
    if not text:
        return ''
    text = text.replace('/', '-').replace('T', ' ')
    if len(text) == 16 and text[4] == '-':
        return text
    if len(text) == 10:
        return text + ' 00:00'
    return text[:16]


def _hash(*parts: Any) -> str:
    raw = '|'.join(_text(item, 200) for item in parts)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def _news_item(kind: str, symbol: str, title: str, summary: str,
               source: str, url: str, published: str) -> Dict[str, Any]:
    item = {
        'id': _hash(kind, symbol, title, published),
        'kind': kind, 'symbol': symbol,
        'title': _text(title, 120), 'summary': _text(summary, 300),
        'source': _text(source, 40), 'url': _text(url, 400),
        'published': _stamp(published),
    }
    if not item['title']:
        item['title'] = item['summary'][:60]
    return item


def _rows(frame) -> List[Dict[str, Any]]:
    if frame is None:
        return []
    try:
        if not len(frame):
            return []
        return [dict(row) for row in frame.to_dict('records')]
    except Exception:                                        # noqa: BLE001
        return []


# ---------------------------------------------------------------- 日历
def fetch_calendar(days: int = 3) -> List[Dict[str, Any]]:
    """财经日历（百度股市通）：今天 + 未来 N-1 天 ✓

    ★ 默认参数是**写死的旧日期**（实测 `20251126`）→ 必须显式传 `date`。
    """
    import datetime as _dt

    out: List[Dict[str, Any]] = []
    today = _dt.date.today()
    errors: List[str] = []
    for offset in range(max(1, min(int(days or 3), 7))):
        day = (today + _dt.timedelta(days=offset)).strftime('%Y%m%d')
        try:
            frame = _call('news_economic_baidu', date=day)
        except ProviderError as error:
            errors.append(f'{day}: {error}')
            continue
        for row in _rows(frame):
            name = _text(row.get('事件'), 120)
            if not name:
                continue
            out.append({
                'id': _hash(day, row.get('时间'), row.get('地区'), name),
                'day': f'{day[:4]}-{day[4:6]}-{day[6:]}',
                'time': _text(row.get('时间'), 8) or '--:--',
                'region': _text(row.get('地区'), 16),
                'event': name,
                'actual': _text(row.get('公布'), 24),
                'forecast': _text(row.get('预期'), 24),
                'previous': _text(row.get('前值'), 24),
                'importance': int(row.get('重要性') or 0)
                if str(row.get('重要性') or '').strip().isdigit() else 0,
            })
    # 全部失败（没装 AkShare / 断网）→ 明确报错，别让界面以为「今天没事件」✗
    if not out and errors:
        raise ProviderError(errors[0])
    return out


# ---------------------------------------------------------------- 新闻
def fetch_news(kind: str = 'flash', symbol: str = '',
               limit: int = 40) -> List[Dict[str, Any]]:
    """快讯 / 要闻 / 个股 / 期货新闻（主接口 + 备接口 ✓）"""
    kind = str(kind or 'flash').lower()
    limit = max(1, min(int(limit or 40), 200))
    items: List[Dict[str, Any]] = []
    if kind == 'symbol':
        code = str(symbol or '').strip()
        if not code:
            raise ProviderError('个股新闻需要 symbol（如 600519 / 000001）')
        for row in _rows(_call('stock_news_em', symbol=code))[:limit]:
            items.append(_news_item(
                'symbol', code,
                title=row.get('新闻标题') or row.get('关键词'),
                summary=row.get('新闻内容'),
                source=row.get('文章来源') or '东方财富',
                url=row.get('新闻链接'), published=row.get('发布时间')))
    elif kind == 'futures':
        for row in _rows(_call('futures_news_shmet'))[:limit]:
            items.append(_news_item(
                'futures', '', title=row.get('内容'),
                summary=row.get('内容'), source='上期能源',
                url='', published=row.get('发布时间')))
    elif kind == 'market':
        # ★ v1.3.7-70：财新 + 同花顺 **合并去重**（以前只有财新 ✓）
        items = fetch_market_news(limit=limit)
        if not items:                     # 备用：新浪 7×24
            items = fetch_news('flash', limit=limit)
    else:                                 # flash：新浪 7×24 快讯
        source = '新浪财经'
        try:
            frame = _call('stock_info_global_sina')
            for row in _rows(frame)[:limit]:
                items.append(_news_item(
                    'flash', '', title=row.get('内容'),
                    summary=row.get('内容'), source=source,
                    url='', published=row.get('时间')))
        except ProviderError:
            # 备用：东财全球快讯
            frame = _call('stock_info_global_em')
            for row in _rows(frame)[:limit]:
                items.append(_news_item(
                    'flash', '', title=row.get('标题') or row.get('摘要'),
                    summary=row.get('摘要'), source='东方财富',
                    url=row.get('链接'), published=row.get('发布时间')))
    return [item for item in items if item.get('title')]


# ---------------------------------------------------------------- 搜索
def search_news(query: str, limit: int = 40) -> List[Dict[str, Any]]:
    """本地缓存里的关键词搜索（不联网；P2 再上 FTS5 ✓）"""
    from . import cache as _cache
    return _cache.search_news(str(query or ''), limit=limit)


# ---------------------------------------------------------------- 宏观
#: 宏观序列定义：`key -> (AkShare 接口, 名称, 周期列, 数值列, 单位)`
#:
#: 数据源一律是**新数据在前**（实测 tail 是 2008 年）→ 统一 reverse 成升序 ✓
MACRO_SERIES: Dict[str, Dict[str, Any]] = {
    'gdp': {'api': 'macro_china_gdp', 'name': 'GDP（绝对值）',
            'period': '季度', 'value': '国内生产总值-绝对值', 'unit': '亿元'},
    'gdp_yoy': {'api': 'macro_china_gdp', 'name': 'GDP 同比',
                'period': '季度', 'value': '国内生产总值-同比增长', 'unit': '%'},
    'cpi': {'api': 'macro_china_cpi', 'name': 'CPI 同比',
            'period': '月份', 'value': '全国-同比增长', 'unit': '%'},
    'pmi': {'api': 'macro_china_pmi', 'name': '制造业 PMI',
            'period': '月份', 'value': '制造业-指数', 'unit': ''},
    'ppi': {'api': 'macro_china_ppi', 'name': 'PPI 同比',
            'period': '月份', 'value': '当月同比增长', 'unit': '%'},
    'm2': {'api': 'macro_china_money_supply', 'name': 'M2 同比',
           'period': '月份', 'value': '货币和准货币(M2)-同比增长', 'unit': '%'},
}


def macro_names() -> List[str]:
    return list(MACRO_SERIES)


def fetch_macro(names: Optional[List[str]] = None,
                limit: int = 12) -> List[Dict[str, Any]]:
    """宏观指标（GDP / CPI / PMI / PPI / M2）：最近 N 期，升序 ✓"""
    wanted = [str(item) for item in (names or macro_names())
              if str(item) in MACRO_SERIES]
    limit = max(1, min(int(limit or 12), 60))
    out: List[Dict[str, Any]] = []
    cache_by_api: Dict[str, Any] = {}
    for key in wanted:
        spec = MACRO_SERIES[key]
        api = str(spec['api'])
        if api not in cache_by_api:
            try:
                cache_by_api[api] = _call(api)
            except ProviderError:
                cache_by_api[api] = None
        frame = cache_by_api[api]
        rows = _rows(frame)
        points: List[List[Any]] = []
        for row in rows:
            period = _text(row.get(spec['period']), 24)
            try:
                value = float(row.get(spec['value']))
            except (TypeError, ValueError):
                continue
            if value != value:                                # NaN
                continue
            points.append([period, round(value, 4)])
        # 源数据新在前 → 反成升序，再取最后 N 期 ✓
        points.reverse()
        points = points[-limit:]
        out.append({
            'key': key, 'name': spec['name'], 'unit': spec['unit'],
            'points': points, 'count': len(points),
            'latest': points[-1] if points else None,
        })
    return out


# ---------------------------------------------------------------- 期货信息
def variety_of(symbol: str) -> str:
    """`SHFE.ag2612` → `ag`；`ag2612` / `AG` → `ag`（小写字母 ✓）"""
    text = str(symbol or '').strip()
    if not text:
        return ''
    if '.' in text:
        text = text.split('.', 1)[1]
    letters = ''
    for char in text:
        if char.isalpha():
            letters += char
        else:
            break
    return letters.lower()


def exchange_of(symbol: str) -> str:
    text = str(symbol or '')
    return text.split('.', 1)[0].upper() if '.' in text else ''


def _rule_rows() -> List[Dict[str, Any]]:
    """合约规则（按今天查，取不到用昨天再试一次 ✓）"""
    import datetime as _dt
    today = _dt.date.today()
    for offset in (0, -1, -2):
        day = (today + _dt.timedelta(days=offset)).strftime('%Y%m%d')
        try:
            return _rows(_call('futures_rule', date=day))
        except ProviderError:
            continue
    return []


def fetch_contract(variety: str) -> Dict[str, Any]:
    """合约规则：保证金 / 涨跌停 / 合约乘数 / 最小变动 ✓"""
    code = str(variety or '').upper()
    if not code:
        return {'code': '', 'items': []}
    rows = [row for row in _rule_rows()
            if str(row.get('代码') or '').upper() == code]
    items = []
    for row in rows:
        items.append({
            'exchange': _text(row.get('交易所'), 16),
            'variety': _text(row.get('品种'), 24),
            'code': _text(row.get('代码'), 12),
            'margin': _text(row.get('交易保证金比例'), 12),
            'limit': _text(row.get('涨跌停板幅度'), 12),
            'multiple': _text(row.get('合约乘数'), 12),
            'tick': _text(row.get('最小变动价位'), 12),
            'max_order': _text(row.get('限价单每笔最大下单手数'), 12),
            'note': _text(row.get('特殊合约参数调整'), 300),
        })
    return {'code': code, 'items': items}


def fetch_inventory(variety: str) -> Dict[str, Any]:
    """期货库存（东方财富，按品种代码 ✓）"""
    code = str(variety or '').lower()
    if not code:
        return {'code': '', 'items': []}
    frame = _call('futures_inventory_em', symbol=code)
    items = []
    for row in _rows(frame)[:60]:
        items.append({
            'date': _stamp(row.get('日期')),
            'inventory': _text(row.get('库存'), 20),
            'change': _text(row.get('增减'), 20),
        })
    # 源数据时升时降 → 按日期**排序**成升序（最新在末尾 ✓）
    items.sort(key=lambda row: str(row.get('date') or ''))
    return {'code': code, 'items': items,
            'latest': items[-1] if items else None}


def fetch_basis(variety: str) -> Dict[str, Any]:
    """现货基差（`futures_spot_price`，按品种代码大写匹配 ✓）"""
    code = str(variety or '').upper()
    import datetime as _dt
    today = _dt.date.today()
    rows: List[Dict[str, Any]] = []
    for offset in (0, -1, -2, -3):
        day = (today + _dt.timedelta(days=offset)).strftime('%Y%m%d')
        try:
            rows = _rows(_call('futures_spot_price', date=day))
        except ProviderError:
            rows = []
        if rows:
            break
    for row in rows:
        if str(row.get('symbol') or '').upper() != code:
            continue
        return {
            'code': code, 'date': _stamp(row.get('date')),
            'spot_price': _text(row.get('spot_price'), 20),
            'near_contract': _text(row.get('near_contract'), 16),
            'near_price': _text(row.get('near_contract_price'), 20),
            'dominant_contract': _text(row.get('dominant_contract'), 16),
            'dominant_price': _text(row.get('dominant_contract_price'), 20),
            'near_basis': _text(row.get('near_basis'), 20),
            'dominant_basis': _text(row.get('dom_basis'), 20),
            'near_rate': _text(row.get('near_basis_rate'), 20),
            'dominant_rate': _text(row.get('dom_basis_rate'), 20),
        }
    return {'code': code, 'empty': True}


def fetch_profile(symbol: str) -> Dict[str, Any]:
    """标的简介（股票走东财；期货用合约规则里的品种名 ✓）"""
    code = str(symbol or '')
    digits = ''.join(char for char in code if char.isdigit())
    if code and not variety_of(code) and len(digits) >= 6:
        # 主接口：东财个股资料（item/value 两列 ✓）
        try:
            rows = _rows(_call('stock_individual_info_em', symbol=digits))
            items = [{'label': _text(row.get('item'), 20),
                      'value': _text(row.get('value'), 60)}
                     for row in rows if row.get('item')]
            if items:
                return {'symbol': code, 'items': items}
        except ProviderError:
            pass                      # 主接口挂了 → 走备用 ✓
        # 备用接口：巨潮公司概况（★ v1.3.7-76：AkShare 1.18 把主接口改坏了，
        #          `stock_individual_info_em` 抛 Length mismatch ✗）
        try:
            rows = _rows(_call('stock_profile_cninfo', symbol=digits))
            row = rows[0] if rows else {}
            picks = [('公司名称', '公司名称'), ('所属行业', '所属行业'),
                     ('所属市场', '所属市场'), ('上市日期', '上市日期'),
                     ('主营业务', '主营业务'), ('注册资金', '注册资金'),
                     ('法人代表', '法人代表'), ('官方网站', '官方网站')]
            items = [{'label': label, 'value': _text(row.get(key), 60)}
                     for key, label in picks if _text(row.get(key))]
            if items:
                return {'symbol': code, 'items': items,
                        'source': 'cninfo'}
        except ProviderError as error:
            return {'symbol': code, 'items': [],
                    'error': f'个股资料暂时取不到（{error}）'}
        return {'symbol': code, 'items': [], 'error': '个股资料暂时取不到'}
    variety = variety_of(code)
    if variety:
        contract = fetch_contract(variety)
        first = (contract.get('items') or [{}])[0]
        return {'symbol': code, 'variety': variety,
                'items': [{'label': '品种', 'value': first.get('variety') or ''},
                          {'label': '交易所', 'value': first.get('exchange') or ''},
                          {'label': '合约乘数', 'value': first.get('multiple') or ''},
                          {'label': '最小变动', 'value': first.get('tick') or ''}]}
    return {'symbol': code, 'items': []}


# ---------------------------------------------------------------- 股票（P2）
def is_stock(symbol: str) -> bool:
    """`SSE.600000` / `SZSE.000001` / `HK.00700` / `US.AAPL` 算股票 ✓"""
    head = str(symbol or '').split('.', 1)[0].upper()
    return head in ('SSE', 'SZSE', 'SH', 'SZ', 'HK', 'US', 'BSE')


def stock_code(symbol: str) -> str:
    """取纯数字代码（东财接口要 `600519`；港股 / 美股返回原尾巴 ✓）"""
    text = str(symbol or '')
    return text.split('.', 1)[1] if '.' in text else text


def fetch_stock_financials(symbol: str, limit: int = 8) -> Dict[str, Any]:
    """财务摘要（东财 `stock_financial_abstract`：指标 × 报告期 ✓）"""
    code = stock_code(symbol)
    if not code:
        return {'items': [], 'error': '需要股票代码'}
    frame = _call('stock_financial_abstract', symbol=code)
    rows = _rows(frame)
    if not rows:
        return {'items': [], 'periods': [], 'error': '该股票没有财务摘要'}
    periods: List[str] = [key for key in rows[0].keys()
                          if str(key)[:2].isdigit() or
                          str(key) in ('选项', '指标')]
    periods = [str(key) for key in periods if str(key) not in ('选项', '指标')]
    periods.sort(reverse=True)
    periods = periods[:max(1, min(int(limit or 8), 12))]
    items = []
    for row in rows:
        name = _text(row.get('指标'), 40)
        if not name:
            continue
        values = {period: _text(row.get(period), 24) for period in periods}
        # 东财用 `…` / `--` 表示缺失 → 统一成空串（别让模型当真值 ✓）
        values = {key: ('' if value in ('…', '...', '--', '-')
                        else value) for key, value in values.items()}
        if not any(values.values()):
            continue
        items.append({'name': name, 'values': values})
    return {'symbol': symbol, 'source': 'akshare',
            'periods': periods, 'items': items[:60]}


def fetch_notices(symbol: str, limit: int = 40) -> Dict[str, Any]:
    """公告（东财 `stock_notice_report`；接口较慢 → 由 service 缓存 ✓）"""
    import datetime as _dt
    code = stock_code(symbol)
    if not code:
        return {'items': [], 'error': '需要股票代码'}
    today = _dt.date.today()
    out: List[Dict[str, Any]] = []
    for offset in range(0, 10):
        day = (today - _dt.timedelta(days=offset)).strftime('%Y%m%d')
        try:
            rows = _rows(_call('stock_notice_report', symbol='全部', date=day))
        except ProviderError:
            continue
        hit = [row for row in rows
               if str(row.get('代码') or '').strip() == code]
        if hit:
            for row in hit[:limit]:
                out.append({'date': _stamp(row.get('公告日期')),
                            'title': _text(row.get('公告标题'), 160),
                            'type': _text(row.get('公告类型'), 32),
                            'symbol': symbol})
            break
    return {'symbol': symbol, 'source': 'akshare', 'items': out}


# ---------------------------------------------------------------- 多源合并 / 去重
def _title_key(text: str) -> str:
    """标题归一化 key（去括号标签 / 空格 / 标点 → 同一件事只留一条 ✓）"""
    raw = str(text or '')
    # ★ 「【重磅】央行降准」→「央行降准」：各家前缀标签不同，别因此重复 ✓
    import re as _re
    raw = _re.sub(r'[【\[][^】\]]{0,12}[】\]]', '', raw)
    for token in ('【', '】', '[', ']', '（', '）', '(', ')', '：', ':',
                  '，', ',', '。', '.', '！', '!', '？', '?', '、', ' ',
                  '\u3000', '\n'):
        raw = raw.replace(token, '')
    return raw[:40]


def dedupe_news(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按标题去重（保留**来源更权威 / 更早出现**的那条 ✓）"""
    seen: Dict[str, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    for item in items:
        key = _title_key(item.get('title') or item.get('summary') or '')
        if not key:
            continue
        if key in seen:
            # 同一件事：补上缺的 url / 摘要（信息更全 ✓）
            kept = seen[key]
            for field in ('summary', 'url', 'published', 'source'):
                if not kept.get(field) and item.get(field):
                    kept[field] = item[field]
            continue
        seen[key] = item
        out.append(item)
    return out


def merge_news(*groups: List[Dict[str, Any]],
               limit: int = 40) -> List[Dict[str, Any]]:
    """合并多源 → 去重 → 按时间倒序（没时间的排在后 ✓）"""
    rows: List[Dict[str, Any]] = []
    for group in groups:
        rows.extend(group or [])
    merged = dedupe_news(rows)
    merged.sort(key=lambda item: str(item.get('published') or ''), reverse=True)
    return merged[:max(1, int(limit or 40))]


def _keyword_hit(item: Dict[str, Any], keywords: List[str]) -> bool:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return any(word and word in text for word in keywords)


def fetch_market_news(limit: int = 60) -> List[Dict[str, Any]]:
    """全市场要闻：**财新 + 同花顺**（合并去重 ✓ v1.3.7-70）"""
    groups: List[List[Dict[str, Any]]] = []
    try:
        for row in _rows(_call('stock_news_main_cx'))[:limit]:
            url = str(row.get('url') or '')
            # 财新没有时间字段 → 从 URL 里取日期（`/2026-11-10/`）
            import re as _re
            match = _re.search(r'/(\d{4}-\d{2}-\d{2})/', url)
            groups.append([_news_item(
                'market', '', title=row.get('summary'),
                summary=row.get('summary'), source='财新', url=url,
                published=(match.group(1) + ' 00:00') if match else '')])
    except ProviderError:
        pass
    try:
        items = []
        for row in _rows(_call('stock_info_global_ths'))[:limit]:
            items.append(_news_item(
                'market', '', title=row.get('标题') or row.get('内容'),
                summary=row.get('内容'), source='同花顺',
                url=row.get('链接'), published=row.get('发布时间')))
        groups.append(items)
    except ProviderError:
        pass
    if not groups:
        return fetch_news('flash', limit=limit)
    return merge_news(*groups, limit=limit)


def fetch_symbol_news(symbol: str, name: str = '',
                      variety: str = '', kind: str = 'stock',
                      limit: int = 20) -> List[Dict[str, Any]]:
    """**单个标的**的资讯：专属源 + 全市场按关键词匹配（合并去重 ✓）

    * 股票：东财个股新闻 + 全市场（财新/同花顺）里标题含**名称 / 代码**的；
    * 期货：上期能源新闻 + 全市场里含**品种名 / 合约代码**的。
    """
    code = stock_code(symbol) if kind == 'stock' else ''
    keywords = [word for word in (name, code, variety,
                                  symbol.split('.', 1)[-1]) if word]
    # ★ 期货常用「沪银 / 沪金」写法（白银→沪银、黄金→沪金、铜→沪铜）
    #   取品种名**最后一个字**加「沪」→ 扩大召回 ✓
    if variety:
        keywords.append('沪' + variety[-1])
    own: List[Dict[str, Any]] = []
    if kind == 'stock' and code:
        try:
            for row in _rows(_call('stock_news_em', symbol=code))[:limit]:
                own.append(_news_item(
                    'symbol', code,
                    title=row.get('新闻标题') or row.get('关键词'),
                    summary=row.get('新闻内容'),
                    source=row.get('文章来源') or '东方财富',
                    url=row.get('新闻链接'), published=row.get('发布时间')))
        except ProviderError:
            pass
    elif kind == 'futures':
        try:
            for row in _rows(_call('futures_news_shmet'))[:limit]:
                own.append(_news_item(
                    'futures', '', title=row.get('内容'),
                    summary=row.get('内容'), source='上期能源',
                    url='', published=row.get('发布时间')))
        except ProviderError:
            pass
    market = [item for item in fetch_market_news(limit=80)
              if _keyword_hit(item, keywords)] if keywords else []
    flash = []
    if keywords:
        try:
            for row in _rows(_call('stock_info_global_sina'))[:60]:
                item = _news_item('flash', '', title=row.get('内容'),
                                  summary=row.get('内容'), source='新浪财经',
                                  url='', published=row.get('时间'))
                if _keyword_hit(item, keywords):
                    flash.append(item)
        except ProviderError:
            pass
    return merge_news(own, market, flash, limit=limit)

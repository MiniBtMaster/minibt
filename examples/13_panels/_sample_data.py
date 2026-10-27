"""Shared synthetic futures data for the panel examples.

Replace :func:`make_rows` with a real feed (天勤 ``tq_api.query_quotes`` or
``minibt.LocalDatas``) to use this with live data — the panels only render what
they are given.
"""
from __future__ import annotations

import random

PRODUCTS = [
    ('l', '聚乙烯'), ('pp', '聚丙烯'), ('v', 'PVC'), ('rb', '螺纹钢'),
    ('ru', '橡胶'), ('cu', '沪铜'), ('al', '沪铝'), ('zn', '沪锌'),
    ('ni', '沪镍'), ('au', '沪金'), ('ag', '沪银'), ('i', '铁矿石'),
    ('j', '焦炭'), ('jm', '焦煤'), ('m', '豆粕'), ('y', '豆油'),
    ('p', '棕榈油'), ('c', '玉米'), ('cf', '棉花'), ('sr', '白糖'),
]
EXCHANGES = ['DCE', 'SHFE', 'CZCE']


def make_rows(count: int = 400, seed: int = 7) -> list:
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        code, name = PRODUCTS[i % len(PRODUCTS)]
        last = 1000 + rng.random() * 9000
        change = (rng.random() - 0.5) * 200
        prev = last - change
        spark = []
        value = last
        for _ in range(40):
            value += (rng.random() - 0.5) * last * 0.01
            spark.append(round(value, 1))
        rows.append({
            'symbol': f'{EXCHANGES[i % 3]}.{code}2601',
            'name': name,
            'exchange': EXCHANGES[i % 3],
            'last': round(last),
            'chg': round(change),
            'chg_pct': round(change / prev * 100, 2),
            'open': round(prev + (rng.random() - 0.5) * 30),
            'high': round(last + rng.random() * 40),
            'low': round(last - rng.random() * 40),
            'pre_close': round(prev),
            'volume': rng.randint(0, 300000),
            'open_interest': rng.randint(0, 600000),
            'spark': spark,
        })
    return rows


def group_by_exchange(rows: list) -> dict:
    groups: dict = {}
    for row in rows:
        groups.setdefault(row['exchange'], []).append(row)
    return groups


def make_items(rows: list) -> list:
    return [{'symbol': r['symbol'], 'name': r['name'], 'last': r['last'],
             'chg': r['chg'], 'chg_pct': r['chg_pct']} for r in rows]

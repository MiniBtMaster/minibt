"""分析策略文件需要哪些合约 / 多少组 K 线（用于**自动选布局 + 载入合约**）。

只做**静态解析**（``ast``），不执行用户代码：

* ``self.get_kline(LocalDatas.pp2609_60)`` → ``pp2609_60``
* ``self.get_kline("SHFE.ag2701")`` → ``SHFE.ag2701``
* ``self.klines1 / self.klines2`` → 至少需要 2 组 K 线（没有明确合约名）

返回::

    {'contracts': ['pp2609_60', 'l2609_60'], 'klines': 2,
     'error': ''}
"""
from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List


#: `params` 里哪些键可能是合约（`get_kline(self.params.symbol)` ✓）
PARAM_KEYS = ('symbol', 'contract', 'code', 'instrument', 'instrument_id')


def _constant_strings(tree) -> Dict[str, str]:
    """模块级 ``NAME = 'SHFE.ag2612'`` → ``{'NAME': 'SHFE.ag2612'}`` ✓"""
    out: Dict[str, str] = {}
    for node in getattr(tree, 'body', []) or []:
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[str(target.id)] = str(node.value.value).strip()
    return out


def _param_strings(tree, constants: Dict[str, str] = None) -> Dict[str, str]:
    """类里 ``params = dict(symbol='SHFE.ag2612')`` → ``{'symbol': …}`` ✓

    很多策略把合约写在 `params` 里（`self.get_kline(self.params.symbol)`），
    以前静态分析拿不到 → 自动布局 / 实时图表都以为“没有合约”✗
    """
    out: Dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [str(target.id) for target in node.targets
                 if isinstance(target, ast.Name)]
        if 'params' not in names:
            continue
        pairs: list = []
        value = node.value
        if isinstance(value, ast.Dict):
            pairs = [(key, item) for key, item
                     in zip(value.keys, value.values)]
        elif (isinstance(value, ast.Call)
              and isinstance(value.func, ast.Name)
              and value.func.id in ('dict', 'Dict')):
            pairs = [(ast.Constant(kw.arg) if kw.arg else None, kw.value)
                     for kw in value.keywords]
        for key, item in pairs:
            if not (isinstance(key, ast.Constant)
                    and isinstance(key.value, str)):
                continue
            name = str(key.value)
            text = ''
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                text = str(item.value).strip()
            elif isinstance(item, ast.Name):
                # `params = dict(leg_a=LEG_A)`（模块常量 ✓）
                text = str((constants or {}).get(str(item.id)) or '')
            if text:
                out[name] = text
    return out


def _get_kline_name(node: ast.Call, constants: Dict[str, str] = None,
                    params: Dict[str, str] = None) -> str:
    """``get_kline(...)`` 的第一个参数 → 合约 / 本地数据名 ✓

    支持四种写法：

    * ``get_kline('SHFE.ag2612')``（字面量）
    * ``get_kline(LocalDatas.pp2609_60)``（本地数据）
    * ``SYMBOL = 'SHFE.ag2612'`` → ``get_kline(SYMBOL)``（模块常量）
    * ``params = dict(symbol='…')`` → ``get_kline(self.params.symbol)``
    """
    if not node.args:
        return ''
    constants = constants or {}
    params = params or {}
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return str(arg.value).strip()
    # LocalDatas.pp2609_60
    if (isinstance(arg, ast.Attribute)
            and isinstance(arg.value, ast.Name)
            and arg.value.id == 'LocalDatas'):
        return str(arg.attr or '').strip()
    if isinstance(arg, ast.Name):
        if arg.id == 'LocalDatas':
            return ''
        return str(constants.get(str(arg.id)) or '')
    # self.params.symbol / self.params.leg_a / …
    if isinstance(arg, ast.Attribute):
        name = str(arg.attr or '')
        if name in params:
            return str(params.get(name) or '')
        if name in ('symbol', 'contract', 'code'):
            return str(params.get(name) or '')
    return ''


def analyze(path: str) -> Dict[str, Any]:
    """分析一个策略文件 → ``{'contracts': [...], 'klines': N, 'error': ''}``"""
    out: Dict[str, Any] = {'contracts': [], 'klines': 1, 'error': ''}
    if not path or not os.path.isfile(path):
        out['error'] = '策略文件不存在'
        return out
    try:
        with open(path, encoding='utf-8', errors='ignore') as handle:
            source = handle.read()
        tree = ast.parse(source)
    except Exception as error:                                   # noqa: BLE001
        out['error'] = f'解析策略失败：{type(error).__name__}: {error}'
        return out

    constants = _constant_strings(tree)
    param_strings = _param_strings(tree, constants)
    calls: List[tuple] = []
    klines = 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ''
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name == 'get_kline':
                contract = _get_kline_name(node, constants, param_strings)
                if contract:
                    calls.append((int(getattr(node, 'lineno', 0) or 0),
                                  contract))
        if isinstance(node, ast.Attribute):
            match = re.fullmatch(r'klines([1-9])', str(node.attr or ''))
            if match:
                klines = max(klines, int(match.group(1)))

    contracts: List[str] = []
    for _line, contract in sorted(calls, key=lambda item: item[0]):
        if contract not in contracts:
            contracts.append(contract)
    out['contracts'] = contracts
    out['klines'] = max(klines, len(contracts), 1)
    return out

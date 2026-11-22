# coding: utf-8 # noqa
"""PI 助手后端（v1.3.7-9）：会话 / 模型 / 供应商 / 技能，**零 npm 依赖**。

对应 `Pi-Agent-Web-main`（`@maddie1/pi-agent-web`）的三块能力，全部用 Python 实现：

| pi-agent-web | 这里 |
| --- | --- |
| 会话列表 `~/.pi/agent/sessions/**.jsonl` | 我们自己的 `~/.minibt/ai/sessions/*.json`，**额外支持导入 pi 的 JSONL** |
| 模型 / 供应商 `~/.pi/agent/models.json` | `~/.minibt/ai/models.json`（结构对齐 `{providers: {...}}`） |
| 技能 `~/.pi/agent/skills/<name>/SKILL.md` + `npx skills add` | `~/.minibt/ai/skills/<name>/SKILL.md`；安装改成 **HTTP 搜索 + `git clone`** |
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from . import agent as _agent

#: 模型配置（对齐 pi 的 `models.json`：`{providers: {id: {...}}}`）
MODELS_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'ai',
                           'models.json')

#: 技能目录（每个技能一个文件夹，里面有 `SKILL.md`）
SKILLS_DIR = os.path.join(os.path.expanduser('~'), '.minibt', 'ai', 'skills')

#: 技能的启用状态（`{name: bool}`；没写 = 启用）
SKILL_STATE = os.path.join(os.path.expanduser('~'), '.minibt', 'ai',
                           'skills.json')

#: 没装 pi 时提示怎么装（前端 tooltip / 会话面板都用这句 ✓）
INSTALL_HINT = ('此功能需要安装 pi（npm install -g '
                '@earendil-works/pi-coding-agent）')

#: `pi` 是否可用（缓存 30 秒 —— 每次汇报都 spawn 一条命令太慢 ✓）
_INSTALL_CACHE: dict[str, Any] = {'at': 0.0, 'value': None}
INSTALL_CACHE_SECONDS = 30.0


def install_status(force: bool = False) -> dict[str, Any]:
    """`pi` 装了没：`{installed, command, version, hint}`（前端据此禁用按钮 ✓）

    - 先 `shutil.which('pi')`（便宜、跨平台）；
    - 再跑 `pi --version` 确认不是同名的别的东西（`stdin=DEVNULL`，
      超时 10 秒，**绝不等着读输入** ✓）；
    - 结果缓存 30 秒，`force=True` 立刻重查（设置页「重新检测」用）。
    """
    now = time.time()
    cached = _INSTALL_CACHE.get('value')
    if (not force and isinstance(cached, dict)
            and now - float(_INSTALL_CACHE.get('at') or 0)
            < INSTALL_CACHE_SECONDS):
        return dict(cached)

    command = ''
    try:
        command = shutil.which('pi') or ''
    except Exception:                                        # noqa: BLE001
        command = ''
    version = ''
    ok = False
    if command:
        kwargs: dict[str, Any] = {
            'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT,
            'stdin': subprocess.DEVNULL, 'shell': True, 'timeout': 10,
        }
        if os.name == 'nt':
            kwargs['creationflags'] = getattr(subprocess,
                                              'CREATE_NO_WINDOW', 0)
        try:
            result = subprocess.run('pi --version', **kwargs)  # noqa
            text = _agent.decode_bytes(result.stdout or b'').strip()
            match = re.search(r'\d+\.\d+(?:\.\d+)?', text)
            version = match.group(0) if match else text.splitlines()[0] \
                if text else ''
            ok = bool(version)
        except (OSError, subprocess.SubprocessError):
            ok = False
    value = {'installed': ok, 'command': command, 'version': version,
             'hint': INSTALL_HINT}
    _INSTALL_CACHE['value'] = dict(value)
    _INSTALL_CACHE['at'] = now
    return value


#: pi 的会话目录（导入用 ✓）
PI_SESSIONS_DIR = os.path.join(os.path.expanduser('~'), '.pi', 'agent',
                               'sessions')

#: skills.sh 的搜索接口（`npx skills search` 背后的 HTTP API ✓）
SKILLS_API = os.environ.get('MINIBT_SKILLS_API', 'https://skills.sh')

#: 内置供应商目录（`模型供应商.png` 里那些；`custom` 用来加自定义）
PROVIDERS: list[dict[str, Any]] = [
    {'id': 'deepseek', 'label': 'DeepSeek', 'base': 'https://api.deepseek.com/v1',
     'models': ['deepseek-chat', 'deepseek-reasoner'], 'kind': 'api-key'},
    {'id': 'openai', 'label': 'OpenAI', 'base': 'https://api.openai.com/v1',
     'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1-mini', 'o3-mini'],
     'kind': 'api-key'},
    {'id': 'anthropic', 'label': 'Anthropic / 兼容', 'base': '',
     'models': [], 'kind': 'api-key'},
    {'id': 'dashscope', 'label': '通义千问（DashScope）',
     'base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
     'models': ['qwen-plus', 'qwen-max', 'qwen2.5-coder-32b-instruct'],
     'kind': 'api-key'},
    {'id': 'moonshot', 'label': 'Moonshot AI', 'base': 'https://api.moonshot.cn/v1',
     'models': ['moonshot-v1-8k', 'kimi-k2-0905-preview'], 'kind': 'api-key'},
    {'id': 'groq', 'label': 'Groq', 'base': 'https://api.groq.com/openai/v1',
     'models': ['llama-3.3-70b-versatile'], 'kind': 'api-key'},
    {'id': 'openrouter', 'label': 'OpenRouter',
     'base': 'https://openrouter.ai/api/v1',
     'models': ['openai/gpt-4o-mini', 'deepseek/deepseek-chat'], 'kind': 'api-key'},
    {'id': 'together', 'label': 'Together AI',
     'base': 'https://api.together.xyz/v1', 'models': [], 'kind': 'api-key'},
    {'id': 'xai', 'label': 'xAI', 'base': 'https://api.x.ai/v1',
     'models': ['grok-2-latest'], 'kind': 'api-key'},
    {'id': 'ollama', 'label': 'Ollama（本地）',
     'base': 'http://127.0.0.1:11434/v1',
     'models': ['qwen2.5-coder:7b', 'llama3.1:8b'], 'kind': 'local'},
    {'id': 'lmstudio', 'label': 'LM Studio（本地）',
     'base': 'http://127.0.0.1:1234/v1', 'models': [], 'kind': 'local'},
    {'id': 'custom', 'label': '自定义 OpenAI / Anthropic 兼容', 'base': '',
     'models': [], 'kind': 'custom'},
]


# ------------------------------------------------------------------ 工具
def _read_json(path: str, fallback: Any) -> Any:
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        return data
    except Exception:                                            # noqa: BLE001
        return fallback


def _write_json(path: str, data: Any) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:                                            # noqa: BLE001
        return False


# ------------------------------------------------------------------ 模型
def load_models() -> dict[str, Any]:
    """`{providers: {id: {label, base, apiKey, models: [...]}}, active: {...}}`"""
    data = _read_json(MODELS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    providers = data.get('providers')
    if not isinstance(providers, dict):
        providers = {}
    data['providers'] = providers
    limits = data.get('limits')
    data['limits'] = limits if isinstance(limits, dict) else {}
    return data


def save_models(data: dict[str, Any]) -> bool:
    providers = data.get('providers')
    if not isinstance(providers, dict):
        data['providers'] = {}
    return _write_json(MODELS_FILE, data)


def limits_of(models: dict[str, Any]) -> dict[str, Any]:
    """模型对话框「高级」的当前值（没设过就给默认 ✓）"""
    limits = models.get('limits') or {}
    if not isinstance(limits, dict):
        limits = {}

    def number(name: str, fallback: Any, cast=float) -> Any:
        try:
            return cast(limits.get(name)) if limits.get(name) is not None \
                else cast(fallback)
        except (TypeError, ValueError):
            return cast(fallback)

    return {
        'turns': max(1, min(60, number('turns', _agent.MAX_TURNS, int))),
        'timeout': max(5.0, min(300.0, number('timeout',
                                              _agent.COMMAND_TIMEOUT))),
        'output': max(2000, min(64000,
                                number('output', _agent.MAX_TOOL_OUTPUT, int))),
        'read': max(4000, min(400000,
                              number('read', _agent.MAX_READ_BYTES, int))),
        'window': max(0, min(2_000_000, number('window', 0, int))),
    }


def provider_catalog(models: dict[str, Any]) -> list[dict[str, Any]]:
    """内置目录 + 已配置的供应商（前端画「供应商」网格 ✓）"""
    saved = models.get('providers') or {}
    rows: list[dict[str, Any]] = []
    for item in PROVIDERS:
        entry = dict(item)
        record = saved.get(item['id']) or {}
        entry['configured'] = bool(record.get('apiKey')
                                   or (item['kind'] == 'local' and record))
        # ★ 有保存值就**只用保存值**（以前拼上内置列表 → 界面显示默认那串 ✗）
        saved_models = [str(name) for name in (record.get('models') or [])]
        entry['models'] = saved_models or list(item.get('models') or [])
        entry['base'] = str(record.get('base') or item.get('base') or '')
        entry['label'] = str(record.get('label') or item['label'])
        rows.append(entry)
    for key, record in saved.items():
        if any(row['id'] == key for row in rows):
            continue
        rows.append({
            'id': key,
            'label': str(record.get('label') or key),
            'base': str(record.get('base') or ''),
            'models': list(record.get('models') or []),
            'kind': 'custom',
            'configured': bool(record.get('apiKey')),
        })
    return rows


def active_model(models: dict[str, Any]) -> dict[str, str]:
    """当前选中的 `{provider, model}`（没有就挑第一个已配置的）"""
    active = models.get('active') or {}
    provider = str(active.get('provider') or '')
    model = str(active.get('model') or '')
    saved = models.get('providers') or {}
    if provider and saved.get(provider):
        return {'provider': provider, 'model': model
                or str((saved[provider].get('models') or [''])[0])}
    # ★ 只回退到**已经配置过 Key** 的供应商；本地服务（Ollama / LM Studio）
    #   不一定在跑，自动选中会让用户以为"没反应" ✗ —— 让前端提示去配置 ✓
    for row in provider_catalog(models):
        record = saved.get(row['id']) or {}
        if record.get('apiKey'):
            return {'provider': row['id'],
                    'model': str((record.get('models')
                                  or row.get('models') or [''])[0])}
    return {'provider': '', 'model': ''}


def model_config(models: dict[str, Any], provider: str = '',
                 model: str = '') -> dict[str, Any]:
    """把「供应商 + 模型」变成 `agent.chat_once` 用的配置 ✓"""
    saved = models.get('providers') or {}
    active = active_model(models)
    provider = str(provider or active['provider'])
    model = str(model or active['model'])
    record = saved.get(provider) or {}
    base = str(record.get('base') or '')
    if not base:
        for item in PROVIDERS:
            if item['id'] == provider:
                base = str(item.get('base') or '')
                break
    # ★ 选的模型必须在该供应商的列表里（否则退回第一个）—— 用户手填错了也别
    #   让请求打到不存在的模型上（会 400 且提示不直观 ✗）
    listed = [str(item) for item in (record.get('models') or [])]
    if listed and model not in listed:
        model = listed[0]
    values = {
        'ai_base_url': base,
        'ai_model': model or (listed[0] if listed else _agent.DEFAULT_MODEL),
        'ai_api_key': str(record.get('apiKey') or ''),
        'ai_tools': True,
    }
    config = _agent.settings_of(values)
    # ★ 高级限制（模型对话框底部）：轮数 / 超时 / 输出 / 读取 / 上下文窗口 ✓
    limits = models.get('limits') or {}
    if not isinstance(limits, dict):
        limits = {}

    def number(name: str, fallback: Any, low: float, high: float,
               cast=float) -> Any:
        try:
            value = cast(limits.get(name) if limits.get(name) is not None
                         else fallback)
        except (TypeError, ValueError):
            value = cast(fallback)
        return max(low, min(high, value))

    config['turns'] = number('turns', config.get('turns') or _agent.MAX_TURNS,
                             1, 60, int)
    config['timeout'] = number('timeout', _agent.COMMAND_TIMEOUT, 5, 300)
    config['maxOutput'] = number('output', _agent.MAX_TOOL_OUTPUT,
                                 2000, 64000, int)
    config['maxRead'] = number('read', _agent.MAX_READ_BYTES,
                               4000, 400000, int)
    window = limits.get('window')
    try:
        window_value = int(window) if window else 0
    except (TypeError, ValueError):
        window_value = 0
    if window_value >= 4000:
        config['window'] = window_value
    return config


# ------------------------------------------------------------------ 技能
def _skill_state() -> dict[str, bool]:
    data = _read_json(SKILL_STATE, {})
    return data if isinstance(data, dict) else {}


def _parse_frontmatter(text: str) -> dict[str, str]:
    """解析 `SKILL.md` 的简单 YAML frontmatter（`key: value` ✓）"""
    result: dict[str, str] = {}
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)  # noqa
    if not match:
        return result
    for line in match.group(1).splitlines():
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        result[key.strip()] = value.strip().strip('"\'')
    return result


def list_skills() -> list[dict[str, Any]]:
    """扫描 `~/.minibt/ai/skills/*/SKILL.md`（含启用状态 ✓）"""
    state = _skill_state()
    rows: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(SKILLS_DIR))
    except OSError:
        return rows
    for name in names:
        folder = os.path.join(SKILLS_DIR, name)
        path = os.path.join(folder, 'SKILL.md')
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as handle:
                body = handle.read()
        except OSError:
            continue
        meta = _parse_frontmatter(body)
        rows.append({
            'name': meta.get('name') or name,
            'folder': name,
            'description': meta.get('description') or '',
            'path': path,
            'enabled': state.get(meta.get('name') or name) is not False,
            'chars': len(body),
        })
    return rows


def set_skill_enabled(name: str, enabled: bool) -> list[dict[str, Any]]:
    state = _skill_state()
    state[str(name)] = bool(enabled)
    _write_json(SKILL_STATE, state)
    return list_skills()


def remove_skill(folder: str) -> bool:
    target = os.path.join(SKILLS_DIR, os.path.basename(str(folder or '')))
    if not os.path.isdir(target) or not os.path.abspath(target).startswith(
            os.path.abspath(SKILLS_DIR) + os.sep):
        return False
    try:
        shutil.rmtree(target)
        return True
    except OSError:
        return False


def skill_prompt(limit: int = 8000) -> str:
    """把所有**启用**的技能拼成一段提示词（截断 ✓）"""
    blocks: list[str] = []
    for row in list_skills():
        if not row.get('enabled'):
            continue
        try:
            with open(row['path'], encoding='utf-8', errors='replace') as handle:
                body = handle.read()
        except OSError:
            continue
        blocks.append(f"### 技能：{row['name']}\n{body}")
        if sum(len(item) for item in blocks) > limit:
            break
    return '\n\n'.join(blocks)[:limit]


def _fetch(url: str, timeout: float = 15.0,
           headers: Optional[dict[str, str]] = None,  # noqa
           insecure: bool = False) -> Any:
    """GET → JSON。``insecure=True`` 时不校验证书（只给**公开只读**接口用）✓"""
    request = urllib.request.Request(url, headers={
        'User-Agent': 'minibt-desk', 'Accept': 'application/json',
        **(headers or {})})
    if insecure:
        import ssl
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=context) as response:
            raw = response.read().decode('utf-8', 'replace')
        return json.loads(raw or '{}')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode('utf-8', 'replace')
    return json.loads(raw or '{}')


def _github_fetch(url: str, timeout: float = 15.0) -> Any:
    """GitHub API 专用：证书校验失败时**降级重试一次**（不校验证书）✓

    公司代理 / 缺根证书的 Windows（`CERTIFICATE_VERIFY_FAILED`）会让搜索
    直接失败 —— 这里对**公开只读**接口退一步，用户不至于整个功能不可用。
    `MINIBT_GITHUB_INSECURE=0` 可以关掉这个降级。
    """
    headers = _github_headers()
    try:
        return _fetch(url, timeout=timeout, headers=headers)
    except Exception as error:
        text = f'{type(error).__name__}: {error}'
        allow = os.environ.get('MINIBT_GITHUB_INSECURE', '1') != '0'
        if not allow or 'CERTIFICATE_VERIFY_FAILED' not in text:
            raise
        return _fetch(url, timeout=timeout, headers=headers, insecure=True)


# ---------------------------------------------------------------- GitHub 兜底
#: GitHub API（可用 `MINIBT_GITHUB_API` 指向企业版 / 镜像）
GITHUB_API = os.environ.get('MINIBT_GITHUB_API', 'https://api.github.com')

#: GitHub 搜索缓存（同一个词 10 分钟内不再打接口，免得触发限频）
GITHUB_TTL = 600.0
_GITHUB_CACHE: dict[str, Any] = {}
#: 被 GitHub 限频的时间点（120 秒内不再打，直接给提示 ✓）
_GITHUB_LIMITED_AT = 0.0
GITHUB_LIMIT_COOLDOWN = 120.0


def _github_headers() -> dict[str, str]:
    """有 token 就带上（未登录 60 次/小时，带 token 5000 次/小时）"""
    token = (os.environ.get('MINIBT_GITHUB_TOKEN')
             or os.environ.get('GITHUB_TOKEN') or '').strip()
    return {'Authorization': f'Bearer {token}'} if token else {}


def github_search_skills(query: str, limit: int = 10) -> dict[str, Any]:
    """在 **GitHub 仓库**里搜「带 `SKILL.md` 的项目」（skills.sh 的兜底）✓

    `skills.sh` 只会收录**有人用 `npx skills add` 装过**的仓库（官方 FAQ：
    leaderboard 来自安装 telemetry），所以自己刚发布的 skill 在它索引里
    要等几小时到几天。这里直接用 GitHub 搜索补上：

    1. `GET /search/repositories?q=<词> in:name,description,readme`
    2. 对排名靠前的仓库再确认根目录**真的有 `SKILL.md`**（`/contents/SKILL.md`）；
    3. 返回 `{name, package(owner/repo), source, url, stars, provider:'github'}`。

    没登录时 GitHub 限 60 次/小时 → 结果缓存 10 分钟，且最多确认 `limit` 个仓库。
    """
    needle = str(query or '').strip()
    if not needle:
        return {'ok': True, 'items': []}
    key = f'{needle.lower()}|{max(1, int(limit))}'
    # ★ 用户直接输 `owner/repo`（最常见：装自己的仓库）→ 不用探测，直接给结果
    #   （`git clone` 时如果仓库不存在会自己报错，这里不做网络校验，省限频 ✓）
    if re.fullmatch(r'[\w.-]+/[\w.-]+', needle) and needle.count('/') == 1:
        item = {'name': f'{needle.split("/")[-1]}（GitHub）',
                'package': needle, 'source': needle, 'installs': '',
                'provider': 'github', 'stars': 0,
                'url': f'https://github.com/{needle}',
                'description': ''}
        return {'ok': True, 'items': [item], 'direct': True}
    hit = _GITHUB_CACHE.get(key)
    if isinstance(hit, tuple) and time.time() - hit[0] < GITHUB_TTL:
        return {'ok': True, 'items': hit[1], 'cached': True}

    # 允许直接搜 `owner/repo`（用户多半就是找自己那个仓库）
    # 刚被限频过 → 直接给提示（别让用户等 20 秒还以为卡了 ✓）
    global _GITHUB_LIMITED_AT
    if _GITHUB_LIMITED_AT and time.time() - _GITHUB_LIMITED_AT < GITHUB_LIMIT_COOLDOWN:
        return {'ok': False, 'items': [],
                'error': 'GitHub 搜索被限频（未登录 60 次/小时）——'
                         '可直接输入 `owner/repo` 安装，或设置 '
                         'MINIBT_GITHUB_TOKEN 提高额度'}

    head = f'{GITHUB_API.rstrip("/")}/search/repositories?'
    # ★ 先按**仓库名**搜（命中少、最准）→ 不够再按描述 / README 搜
    #   （只按描述搜会把一堆不相关的仓库排前面，探测 SKILL.md 又费限频）
    queries = [f'{needle} in:name', f'{needle} in:description,readme']

    budget = 8             # 最多探测多少个仓库的 SKILL.md（未登录 60 次/小时）
    seen: set = set()
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for terms in queries:
        if len(items) >= max(1, min(int(limit), 20)) or budget <= 0:
            break
        # ★ 一次多拿点（50）再**本地排序**：优先探测「名字里带这个词、且是派生的
        #   仓库」（`minibt-strategy` 这种 skill 仓库往往 star 很少，排不进前 10）
        url = head + urllib.parse.urlencode({
            'q': terms, 'sort': 'stars', 'order': 'desc', 'per_page': 50})
        try:
            data = _github_fetch(url, timeout=20.0)
        except urllib.error.HTTPError as error:
            hint = ('（GitHub 未登录时限 60 次/小时，'
                    '可设 MINIBT_GITHUB_TOKEN 提高）' if error.code in (403, 429)
                    else '')
            if error.code in (403, 429):
                _GITHUB_LIMITED_AT = time.time()
            errors.append(f'HTTP {error.code}{hint}')
            continue
        except Exception as error:                               # noqa: BLE001
            errors.append(f'连不上 GitHub：{error}')
            continue
        rows = [row for row in ((data.get('items') or [])
                                if isinstance(data, dict) else [])
                if isinstance(row, dict)]
        needle_low = needle.lower()

        def keep_first(row):
            name = str(row.get('name') or '').lower()
            derived = (needle_low in name and name != needle_low)  # noqa
            return (0 if derived else 1,
                    -int(row.get('stargazers_count') or 0))
        rows.sort(key=keep_first)
        for row in rows:
            if budget <= 0:
                break
            if not isinstance(row, dict):
                continue
            full = str(row.get('full_name') or '')
            if not full or full in seen:
                continue
            seen.add(full)
            budget -= 1
            # ★ 必须真的含 SKILL.md（否则不是 skill 仓库，装了也没用）
            probe = f'{GITHUB_API.rstrip("/")}/repos/{full}/contents/SKILL.md'
            unverified = False
            try:
                _github_fetch(probe, timeout=12.0)
            except urllib.error.HTTPError as error:
                if error.code in (404, 451):
                    continue                       # 没 SKILL.md → 不是技能仓库
                if error.code in (403, 429):
                    # 限频：**没法再验证了** —— 只留"看起来像技能仓库"的那条
                    # （名字/描述里有 skill），然后停止探测（别白打 8 次）
                    _GITHUB_LIMITED_AT = time.time()
                    label = (str(row.get('name') or '') + ' '
                             + str(row.get('description') or '')).lower()
                    if 'skill' not in label:
                        break
                    unverified = True
                else:
                    unverified = True
            except Exception:                                    # noqa: BLE001
                unverified = True
            label = str(row.get('name') or full.split('/')[-1])
            items.append({
                'name': f'{label}（GitHub）',
                'package': full,
                'source': full,
                'installs': '',
                'stars': int(row.get('stargazers_count') or 0),
                'provider': 'github',
                'url': str(row.get('html_url') or f'https://github.com/{full}'),
                'description': str(row.get('description') or '')[:160],
            })
            if unverified:
                items[-1]['unverified'] = True
            if len(items) >= max(1, min(int(limit), 20)):
                break
    if not items and errors:
        return {'ok': False, 'error': errors[0], 'items': []}
    _GITHUB_CACHE[key] = (time.time(), items)
    return {'ok': True, 'items': items}


def search_skills(query: str, limit: int = 30) -> dict[str, Any]:
    """技能搜索：**先 `skills.sh`，再用 GitHub 兜底**（纯 HTTP，不用 npx ✓）

    为什么要有兜底：
    `skills.sh` 的目录只收录**有人用 `npx skills add` 装过**的仓库（官方 FAQ：
    leaderboard 来自安装 telemetry），所以刚发布 / 冷门的 skill 搜不到
    （用户实测：搜 `minibt` 搜不到自己的 `minibt-strategy` ✗）。
    现在 skills.sh 没结果（或没命中关键词）时，会去 GitHub 搜「仓库名 / 描述里
    带这个词、且根目录真的有 `SKILL.md`」的项目，直接给出 `owner/repo` 可安装。

    返回：
    ``{'ok': True, 'items': [...], 'source_api': 'skills.sh' | 'github' | 'both',
       'note': '...'}``；两边都失败才是 ``{'ok': False, 'error': ...}``。
    """
    needle = str(query or '').strip()
    if not needle:
        return {'ok': True, 'items': []}
    items: list[dict[str, Any]] = []
    error = ''
    # ① skills.sh（老接口 `/api/skills` 已 404，v1.3.7-104 换成 `/api/search` 会 404）
    url = (f'{SKILLS_API.rstrip("/")}/api/search?'
           + urllib.parse.urlencode({'q': needle, 'limit': limit}))
    try:
        data = _fetch(url)
    except urllib.error.HTTPError as exc:
        error = f'HTTP {exc.code}'
        data = None
    except Exception as exc:                                     # noqa: BLE001
        error = f'连不上 skills.sh：{exc}'
        data = None
    raw = (data.get('skills') or data.get('results')
           or data.get('data') or []) if isinstance(data, dict) else []
    for row in raw[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or row.get('skillId')
                   or row.get('package') or row.get('id') or '')
        # 安装要的是 `owner/repo`（`git clone` 用）→ 优先 source ✓
        package = str(row.get('package') or row.get('source') or name)
        items.append({
            'name': name,
            'package': package,
            'source': str(row.get('source') or ''),
            'installs': str(row.get('installs') or ''),
            'provider': 'skills.sh',
            'url': (f"https://skills.sh/skills/{row.get('id')}"
                    if row.get('id') else ''),
        })

    # ② GitHub 兜底：**只要 GitHub 有结果就补上**
    #   （skills.sh 是模糊检索，经常把不相关的仓库塞前面 —— 用户搜自己的
    #    skill 时，最该看到的就是 GitHub 里那条真的 ✓）
    needle_low = needle.lower()
    matched = any(needle_low in str(item.get('name') or '').lower()
                  or needle_low in str(item.get('package') or '').lower()
                  for item in items)
    #   skills.sh 已经**精确命中**且结果够多时才跳过（省 GitHub 限频）
    gh_error = ''
    if not (matched and len(items) >= max(1, int(limit))):
        extra = github_search_skills(needle, limit=min(10, max(1, int(limit))))
        gh_error = '' if extra.get('ok') else str(extra.get('error') or '')
        for item in extra.get('items') or []:
            if any(str(row.get('package')) == str(item.get('package'))
                   for row in items):
                continue
            items.append(item)
        if not items and not extra.get('ok', True):
            error = error or str(extra.get('error') or '')

    if not items and error:
        return {'ok': False, 'error': error, 'items': [],
                'hint': '也可以从本地文件夹安装技能（「＋ 添加技能」）'}
    if not items:
        return {'ok': True, 'items': [], 'source_api': 'none'}
    providers = {str(item.get('provider') or 'skills.sh') for item in items}
    source_api = 'both' if len(providers) > 1 else next(iter(providers))
    out: dict[str, Any] = {'ok': True, 'items': items,
                           'source_api': source_api}
    if 'github' in providers:
        out['note'] = ('skills.sh 还没收录这些仓库，下面是 GitHub 直接搜到的'
                       '（装完就能用；安装走 git clone）')
    elif gh_error:
        # GitHub 也没成（多半是限频）→ 告诉用户最省事的办法 ✓
        out['note'] = ('GitHub 搜索没成功：' + gh_error
                       + '；可直接输入 `owner/repo` 安装')
    return out


def _copy_skills(source: str, name_hint: str = '') -> list[str]:
    """把 clone 下来的仓库里所有 `SKILL.md` 拷进技能目录 ✓"""
    installed: list[str] = []
    os.makedirs(SKILLS_DIR, exist_ok=True)
    for base, _dirs, files in os.walk(source):
        if 'SKILL.md' not in files:
            continue
        folder_name = os.path.basename(base) or name_hint or 'skill'
        target = os.path.join(SKILLS_DIR, folder_name)
        if os.path.abspath(base) == os.path.abspath(target):
            continue
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(base, target)
            installed.append(folder_name)
        except Exception:                                        # noqa: BLE001
            ...
    return installed


def install_skill(package: str, provider: str = 'github') -> dict[str, Any]:
    """安装技能：`owner/repo` → `git clone` → 拷贝其中的 SKILL.md ✓

    （pi 用 `npx skills add`，这里换成 **git**，不引入 npm ✓）
    """
    text = str(package or '').strip()
    if not text:
        return {'ok': False, 'error': '空包名'}
    # 允许直接给 https URL
    if text.startswith(('http://', 'https://', 'git@')):
        repo = text
    else:
        slug = text.split('#', 1)[0].strip('/')
        repo = f'https://github.com/{slug}.git'
    tmp = tempfile.mkdtemp(prefix='minibt-skill-')
    try:
        result = subprocess.run(  # noqa
            ['git', 'clone', '--depth', '1', repo, os.path.join(tmp, 'repo')],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace')
        if result.returncode != 0:
            return {'ok': False,
                    'error': (result.stderr or result.stdout or 'clone 失败')[-400:]}
        installed = _copy_skills(os.path.join(tmp, 'repo'),
                                 text.split('/')[-1])
        if not installed:
            return {'ok': False, 'error': '仓库里没有找到 SKILL.md'}
        return {'ok': True, 'installed': installed, 'skills': list_skills()}
    except FileNotFoundError:
        return {'ok': False, 'error': '没装 git：只能用「添加本地技能文件夹」'}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'git clone 超时（120s）'}
    except Exception as error:                                   # noqa: BLE001
        return {'ok': False, 'error': f'安装失败：{error!r}'}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_local_skill(path: str) -> dict[str, Any]:
    """从**本地文件夹**安装（离线可用 ✓）"""
    source = os.path.abspath(str(path or ''))
    if not os.path.isdir(source):
        return {'ok': False, 'error': '目录不存在'}
    installed = _copy_skills(source)
    if not installed:
        return {'ok': False, 'error': '目录里没有 SKILL.md'}
    return {'ok': True, 'installed': installed, 'skills': list_skills()}


# ------------------------------------------------------- 会话：pi JSONL 导入
def _pi_message(entry: dict[str, Any]) -> Optional[dict[str, Any]]:  # noqa
    """把 pi 的 JSONL 条目转成我们的消息（`{role, content, ...}` ✓）"""
    kind = str(entry.get('type') or '')
    if kind != 'message':
        return None
    message = entry.get('message') or {}
    role = str(message.get('role') or '')
    content = message.get('content')
    if isinstance(content, str):
        text = content
        calls: list[dict[str, Any]] = []
    elif isinstance(content, list):
        texts: list[str] = []
        calls = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'text':
                texts.append(str(block.get('text') or ''))
            elif block.get('type') == 'toolCall':
                calls.append({
                    'id': str(block.get('toolCallId') or ''),
                    'type': 'function',
                    'function': {
                        'name': str(block.get('toolName') or ''),
                        'arguments': json.dumps(block.get('input') or {},
                                                ensure_ascii=False),
                    },
                })
        text = '\n'.join(item for item in texts if item)
    else:
        text = ''
    if role == 'user':
        return {'role': 'user', 'content': text}
    if role == 'assistant':
        row: dict[str, Any] = {'role': 'assistant', 'content': text}
        if calls:
            row['tool_calls'] = calls
        return row
    if role == 'toolResult':
        return {'role': 'tool', 'tool_call_id': str(message.get('toolCallId')
                                                    or ''),
                'name': str(message.get('toolName') or ''),
                'content': text[:8000]}
    return None


def parse_pi_session(path: str) -> Optional[dict[str, Any]]:  # noqa
    """解析一个 pi 的会话 `.jsonl` ✓"""
    header: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    name = ''
    try:
        with open(path, encoding='utf-8', errors='replace') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                kind = str(entry.get('type') or '')
                if kind == 'session' and not header:
                    header = entry
                elif kind in ('session_info', 'sessionInfo'):
                    name = str(entry.get('name') or name)
                elif kind == 'message':
                    row = _pi_message(entry)
                    if row:
                        messages.append(row)
    except OSError:
        return None
    if not header and not messages:
        return None
    created = header.get('timestamp') or ''  # noqa
    try:
        stamp = float(header.get('timestamp')) if isinstance(
            header.get('timestamp'), (int, float)) else None
    except (TypeError, ValueError):
        stamp = None
    if stamp is None:
        stamp = os.path.getmtime(path)
    first = next((item['content'] for item in messages
                  if item.get('role') == 'user'), '') or '(无消息)'
    return {
        'id': str(header.get('id') or os.path.basename(path).split('.')[0]),
        'name': name or ' '.join(str(first).split())[:40],
        'cwd': str(header.get('cwd') or ''),
        'created': stamp,
        'modified': stamp,
        'messages': messages,
        'piPath': os.path.abspath(path),
        'parentSessionId': str(header.get('parentSession') or ''),
        'source': 'pi',
    }


def import_pi_sessions(limit: int = 200) -> dict[str, Any]:
    """把 `~/.pi/agent/sessions/**.jsonl` 导进我们的会话库（按 piPath 去重 ✓）"""
    if not os.path.isdir(PI_SESSIONS_DIR):
        return {'ok': False, 'error': '没有找到 ~/.pi/agent/sessions', 'count': 0}
    # ⚠ `list_sessions()` 只返回摘要（不带 piPath）→ 直接扫会话文件取 piPath ✓
    known = set()
    folder = _agent.SESSIONS_DIR
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    for name in names:
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(folder, name), encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:                                        # noqa: BLE001
            ...
        if isinstance(data, dict) and data.get('piPath'):
            known.add(os.path.abspath(str(data['piPath'])))
    paths: list[str] = []
    for base, _dirs, files in os.walk(PI_SESSIONS_DIR):
        for entry in files:
            if entry.endswith('.jsonl'):
                paths.append(os.path.join(base, entry))
    paths.sort(key=lambda item: os.path.getmtime(item), reverse=True)
    imported = 0
    for path in paths[:max(1, int(limit))]:
        if os.path.abspath(path) in known:
            continue
        parsed = parse_pi_session(path)
        if not parsed or not parsed['messages']:
            continue
        session = {
            'id': parsed['id'][:12] if parsed['id'] else _agent.create_session(
                parsed['cwd'] or '', parsed['name'])['id'],
            'title': parsed['name'],
            'name': parsed['name'],
            'cwd': parsed['cwd'] or os.getcwd(),
            'created': parsed['created'],
            'updated': parsed['modified'],
            'messages': parsed['messages'],
            'usage': {},
            'piPath': parsed['piPath'],
            'source': 'pi',
            'parentSessionId': parsed['parentSessionId'],
        }
        # 已经存在同名 id → 换个 id，别覆盖用户自己的会话 ✓
        if _agent.load_session(session['id']) is not None:
            session['id'] = _agent.create_session(
                session['cwd'], session['name'])['id']
        _agent.save_session(session)
        imported += 1
    return {'ok': True, 'count': imported,
            'sessions': _agent.list_sessions()}


# ------------------------------------------------- 会话：把摘要合并到当前会话
def merge_into(source_id: str, target_id: str,
               limit: int = 4000) -> dict[str, Any]:
    """把「另一个会话」的**摘要**追加到当前会话（用户 2026-11-08 要求 ✓）

    * 生成本地摘要（标题 / 时间 / 条数 + 最近几条的 User / AI 内容，截断）；
    * 作为一条 `user` 消息追加到目标会话末尾 → 下一轮对话模型就能看到；
    * **不动源会话**（只是"合并摘要"，不是搬移）✓
    """
    source = _agent.load_session(source_id)
    target = _agent.load_session(target_id)
    if source is None or target is None:
        return {'ok': False, 'error': '会话不存在'}
    if str(source_id) == str(target_id):
        return {'ok': False, 'error': '不能合并到自己'}
    messages = source.get('messages') or []
    stamp = time.strftime('%Y-%m-%d %H:%M',
                          time.localtime(float(source.get('updated')
                                               or time.time())))
    lines = [f"[合并自会话「{source.get('title') or '未命名'}」"  # noqa
             f" · {stamp} · {len(messages)} 条消息]"]
    for message in messages[-12:]:
        role = str(message.get('role') or '')
        text = ' '.join(str(message.get('content') or '').split())[:300]
        if not text:
            continue
        who = {'user': '用户', 'assistant': 'AI',
               'tool': '工具'}.get(role, '系统')
        lines.append(f'{who}：{text}')
    summary = chr(10).join(lines)[:max(200, int(limit))]
    target_messages = list(target.get('messages') or [])
    target_messages.append({'role': 'user', 'content': summary})
    target['messages'] = target_messages
    _agent.save_session(target)
    return {'ok': True, 'summary': summary, 'chars': len(summary),
            'target': target,
            'sourceTitle': source.get('title') or ''}

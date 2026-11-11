# coding: utf-8
"""desk 内置 AI 助手（v1.3.7-4）：**不依赖 Node / npm** 的会话 + 对话。

* pi-web / pi-agent-studio 都是 **Node/Next.js 应用**（要求 Node ≥ 22.19 +
  `npm install`），为了一个聊天窗口引入整条 Node 工具链太重 ✗；
* desk 本来就是 Python + Qt WebEngine，**自己实现会话 + 对话**零新增依赖 ✓；
* 走**任意 OpenAI 兼容接口**（官方 / DeepSeek / 通义 / Ollama / LM Studio /
  vLLM…），只要 `POST {base_url}/chat/completions` 能用就行。

能力：

| 能力 | 说明 |
| --- | --- |
| 会话列表 | `~/.minibt/ai/sessions/*.json`，标题 / 时间 / 条数 / 首行摘要 |
| 多开会话 | 前端标签页，一个会话一个标签（可关） |
| 流式输出 | `stream: true` 的 SSE 逐块转成 `ai_delta` 补丁 |
| 工具调用 | `read_file` / `list_dir` / `grep` / `write_file` / `run_command` |
| 沙箱 | 所有文件操作限制在会话的 `cwd`（工作区）内；写文件 ≤ 200 KB |
| 上下文 | 当前文件 / 选中代码 / 运行日志尾 / 回测结果，一键塞进对话 |
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

#: 会话存放目录（`~/.minibt/ai/sessions/`）
SESSIONS_DIR = os.path.join(os.path.expanduser('~'),
                            '.minibt', 'ai', 'sessions')

#: 单个会话最多保留多少条消息（防止文件无限涨 ✓）
MAX_MESSAGES = 400

#: 工具执行限制
MAX_FILE_BYTES = 200_000
MAX_READ_BYTES = 60_000
MAX_TOOL_OUTPUT = 8_000
MAX_TURNS = 12
COMMAND_TIMEOUT = 25.0

#: `grep` / 扫描时跳过的目录（缓存 / 依赖 / 构建产物 ✓）
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', 'dist', 'build',
             '.venv', 'venv', '.mypy_cache', '.pytest_cache', 'site',
             '.ipynb_checkpoints', '.idea', '.vscode', '_bundle_current'}

#: 默认值（都能在「设置 → AI 助手」里改 ✓）
DEFAULT_BASE = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-4o-mini'

#: 工具定义（OpenAI function calling schema ✓）
TOOLS: List[Dict[str, Any]] = [
    {
        'type': 'function',
        'function': {
            'name': 'list_dir',
            'description': '列出工作区某个目录下的文件（默认根目录）',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string',
                                        'description': '相对工作区的目录，空=根'}},
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': '读取工作区内的文本文件（最多 60KB）',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'grep',
            'description': '在工作区里按正则搜索（返回 文件:行:内容）',
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {'type': 'string'},
                    'path': {'type': 'string',
                             'description': '相对目录，空=根'},
                },
                'required': ['pattern'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'write_file',
            'description': '覆盖写入工作区内的文本文件（新建或整体替换）',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string'},
                    'content': {'type': 'string'},
                },
                'required': ['path', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'run_command',
            'description': '在工作区执行 shell 命令（最长 25 秒，返回输出）',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string'},
                    'timeout': {'type': 'number'},
                },
                'required': ['command'],
            },
        },
    },
]

# ★ 「操控 desk」工具（v1.3.7-24）：desk_status / desk_switch_symbol /
#   desk_add_indicator / desk_set_layout … 见 `tools.py` ✓
try:                                                          # noqa: SIM105
    from . import tools as _desk_tools
    TOOLS = TOOLS + list(_desk_tools.SPECS)
except Exception:                                             # noqa: BLE001
    _desk_tools = None


def external_tools(force: bool = False) -> List[Dict[str, Any]]:
    """外部 MCP server 的工具（`mcp__<server>__<tool>`，懒加载 ✓）

    配置在 `~/.minibt/ai/mcp.json`；起不来的 server 自动跳过。
    """
    try:
        from . import mcp_client
        from . import user_prefs
        if user_prefs.settings().get('ai_mcp_tools') is False:
            return []
        return mcp_client.specs(force)
    except Exception:                                         # noqa: BLE001
        return []


def all_tools(force: bool = False) -> List[Dict[str, Any]]:
    """内置 + desk + 外部 MCP 的完整工具表 ✓"""
    return list(TOOLS) + external_tools(force)


#: 模型价格（美元 / 1M tokens；只作**估算**，可在设置里覆盖 ✓）
MODEL_PRICES: Dict[str, Dict[str, float]] = {
    'gpt-4o-mini': {'in': 0.15, 'out': 0.60},
    'gpt-4o': {'in': 2.50, 'out': 10.00},
    'gpt-4.1-mini': {'in': 0.40, 'out': 1.60},
    'deepseek-chat': {'in': 0.27, 'out': 1.10},
    'deepseek-reasoner': {'in': 0.55, 'out': 2.19},
    'qwen2.5-coder:7b': {'in': 0.0, 'out': 0.0},
    'qwen-plus': {'in': 0.40, 'out': 1.20},
}

#: 常见模型的上下文窗口（tokens）；设置里可覆盖 ✓
MODEL_WINDOWS: Dict[str, int] = {
    'gpt-4o-mini': 128000,
    'gpt-4o': 128000,
    'gpt-4.1-mini': 1047576,
    'deepseek-chat': 65536,
    'deepseek-reasoner': 65536,
    'qwen2.5-coder:7b': 32768,
    'qwen-plus': 131072,
}

DEFAULT_WINDOW = 128000

#: 导出目录（会话 Markdown ✓）
EXPORT_DIR = os.path.join(os.path.expanduser('~'), '.minibt', 'ai', 'exports')

#: 工具分组（「权限」选择器用 ✓）
TOOL_GROUPS: Dict[str, List[str]] = {
    # 只读：代码只读 + desk 的**只读**工具（看状态 / 报价 / 数据集 / 画线 ✓）
    'readonly': ['list_dir', 'read_file', 'grep', 'desk_status',
                 'desk_book', 'desk_local_list', 'desk_drawings'],
    'default': ['list_dir', 'read_file', 'grep', 'write_file', 'run_command'],
    # 「操控 desk」：能改界面（切合约 / 加指标 / 布局），但**不动钱** ✓
    'desk': ['list_dir', 'read_file', 'grep', 'write_file', 'run_command']
    + list(_desk_tools.NAMES if _desk_tools else []),
    # 「完全访问（FullAccess）」：对齐 pi-agent-studio 的 permission.mode ——
    # 所有工具放行、**从不询问** → 不需要交互 ✓
    'full': ['list_dir', 'read_file', 'grep', 'write_file', 'run_command']
    + list(_desk_tools.NAMES if _desk_tools else []),
}

#: 推理强度 → (max_tokens, temperature, 提示词后缀)
EFFORT_LEVELS: Dict[str, Dict[str, Any]] = {
    'low': {'max_tokens': 1200, 'temperature': 0.35,
            'hint': '回答尽量简短，只给结论和必要代码。'},
    'medium': {'max_tokens': 4096, 'temperature': 0.2,
               'hint': '先给结论，再给关键步骤；代码要能直接跑。'},
    'high': {'max_tokens': 8192, 'temperature': 0.15,
             'hint': '仔细分析：先说明思路与取舍，再给完整实现和验证方法。'},
}

#: 压缩触发阈值（占窗口比例 ✓）
COMPRESS_AT = 0.60

#: 上下文裁剪阈值（占窗口的比例 ✓）
CONTEXT_WARN = 0.80
CONTEXT_TRIM = 0.95
#: 裁剪后保留的目标比例
CONTEXT_KEEP = 0.55

#: `@文件` 引用最多几个 / 每个多少字
MAX_REFS = 6
MAX_REF_CHARS = 6000


# ---------------------------------------------------------------- 配置
def settings_of(prefs: Dict[str, Any]) -> Dict[str, Any]:
    """从 desk 设置里取 AI 配置（环境变量兜底 ✓）"""
    values = prefs or {}
    key = str(values.get('ai_api_key') or '') or os.environ.get(
        'MINIBT_AI_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
    try:
        turns = int(values.get('ai_max_turns') or MAX_TURNS)
    except (TypeError, ValueError):
        turns = MAX_TURNS
    model = str(values.get('ai_model') or DEFAULT_MODEL)
    default_price = MODEL_PRICES.get(model) or {'in': 0.0, 'out': 0.0}

    def price(name: str) -> float:
        try:
            given = values.get(name)
            if given is None or str(given).strip() == '':
                return float(default_price[name])
            return max(0.0, float(given))
        except (TypeError, ValueError):
            return float(default_price[name])

    try:
        window = int(values.get('ai_context_window')
                     or MODEL_WINDOWS.get(model) or DEFAULT_WINDOW)
    except (TypeError, ValueError):
        window = MODEL_WINDOWS.get(model) or DEFAULT_WINDOW
    return {
        'base': str(values.get('ai_base_url') or DEFAULT_BASE).rstrip('/'),
        'model': model,
        'key': key,
        'tools': values.get('ai_tools') is not False,
        'turns': max(1, min(24, turns)),
        # 成本估算 / 上下文用量（v1.3.7-5 ✓）
        'price_in': price('in'),
        'price_out': price('out'),
        'window': max(1000, window),
    }


def estimate_tokens(text: str) -> int:
    """粗估 token：中文 ≈ 1 字 1 token，英文 ≈ 4 字符 1 token ✓"""
    value = str(text or '')
    if not value:
        return 0
    cjk = sum(1 for ch in value if '一' <= ch <= '鿿')
    others = len(value) - cjk
    return int(cjk + others / 4) + 1


def messages_tokens(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for message in messages or []:
        # 思考过程**不发给模型**（只留在会话里给界面看）→ 不算上下文 ✓
        total += 4 + estimate_tokens(str(message.get('content') or ''))
        for call in message.get('tool_calls') or []:
            function = call.get('function') or {}
            total += estimate_tokens(str(function.get('arguments') or ''))
    return total


def usage_of(usage: Any, messages: List[Dict[str, Any]],
             config: Dict[str, Any]) -> Dict[str, Any]:
    """单轮用量：`{prompt, completion, cached, total, cost}`（界面每轮显示 ✓）

    `cached` 兼容三种写法：OpenAI `prompt_tokens_details.cached_tokens`、
    DeepSeek `prompt_cache_hit_tokens`、Anthropic `cache_read_input_tokens`。
    """
    data = usage if isinstance(usage, dict) else {}
    prompt = int(data.get('prompt_tokens') or 0)
    completion = int(data.get('completion_tokens') or 0)
    details = data.get('prompt_tokens_details') or {}
    if not isinstance(details, dict):
        details = {}
    cached = int(details.get('cached_tokens')
                 or data.get('prompt_cache_hit_tokens')
                 or data.get('cache_read_input_tokens') or 0)
    if not prompt:
        prompt = messages_tokens(messages)
    if not completion:
        content = ''
        for message in reversed(messages or []):
            if str(message.get('role')) == 'assistant':
                content = str(message.get('content') or '')
                break
        completion = estimate_tokens(content)
    total = int(data.get('total_tokens') or (prompt + completion))
    return {'prompt': prompt, 'completion': completion, 'cached': max(0, cached),
            'total': total,
            'cost': round(cost_of({'prompt_tokens': prompt,
                                   'completion_tokens': completion}, config), 6)}


def api_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """只保留 API 认的字段（`thinking` / `usage` / `model` 是给界面看的 ✓）

    ★ 带附件的用户消息 → 转成 OpenAI 兼容的 **content parts**：
      `[{type:'text'}, {type:'image_url', image_url:{url:'data:…'}}]`；
      文本附件直接拼进 `text`（fenced code block，带文件名）。
      其它消息仍是普通字符串 content（旧行为不变 ✓）。
    """
    rows: List[Dict[str, Any]] = []
    for message in messages or []:
        row = dict(message)
        for extra in ('thinking', 'usage', 'model', 'seconds', 'elapsed',
                      'args', 'finish'):
            row.pop(extra, None)
        attachments = row.pop('attachments', None) or []
        if not attachments:
            rows.append(row)
            continue
        text = str(row.get('content') or '')
        parts: List[Dict[str, Any]] = []
        texts: List[str] = []
        images: List[Dict[str, Any]] = []
        for item in attachments:
            if not isinstance(item, dict):
                continue
            if item.get('kind') == 'image' and item.get('data'):
                images.append({
                    'type': 'image_url',
                    'image_url': {
                        'url': f"data:{item.get('mime') or 'image/png'};"
                               f"base64,{item.get('data')}",
                    },
                })
            elif item.get('text'):
                texts.append(f"--- {item.get('name')} ---\n{item['text']}")
        if texts:
            text = (text + '\n\n' + '\n\n'.join(texts)).strip()
        if text:
            parts.append({'type': 'text', 'text': text})
        parts.extend(images)
        row['content'] = parts if parts else ''
        rows.append(row)
    return rows


def cost_of(usage: Dict[str, Any], config: Dict[str, Any]) -> float:
    """按 1M tokens 单价估算花费（美元 ✓）"""
    prompt = float(usage.get('prompt_tokens') or 0.0)
    completion = float(usage.get('completion_tokens') or 0.0)
    price_in = float(config.get('price_in') or 0.0)
    price_out = float(config.get('price_out') or 0.0)
    return (prompt * price_in + completion * price_out) / 1_000_000.0


# ---------------------------------------------------------------- 会话存储
def _ensure_dir() -> str:
    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
    except OSError:
        pass
    return SESSIONS_DIR


def _session_path(session_id: str) -> str:
    safe = re.sub(r'[^0-9A-Za-z_-]', '', str(session_id or ''))
    return os.path.join(_ensure_dir(), f'{safe or "unknown"}.json')


def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    try:
        with open(_session_path(session_id), encoding='utf-8') as handle:
            data = json.load(handle)
    except Exception:                                            # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


#: 会话文件写锁：命令线程和 agent 线程会同时写同一个会话 ✓
_SAVE_LOCK = threading.Lock()


def save_session(session: Dict[str, Any]) -> None:
    session['updated'] = time.time()
    messages = session.get('messages') or []
    if len(messages) > MAX_MESSAGES:
        session['messages'] = messages[-MAX_MESSAGES:]
    path = _session_path(str(session.get('id') or ''))
    with _SAVE_LOCK:
        for attempt in range(5):
            tmp = f'{path}.{os.getpid()}.{attempt}.tmp'
            try:
                with open(tmp, 'w', encoding='utf-8') as handle:
                    json.dump(session, handle, ensure_ascii=False, indent=1)
                os.replace(tmp, path)
                return
            except PermissionError:
                # Windows：另一个线程正在读 / 写 → 等一下再试 ✓
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                time.sleep(0.05 * (attempt + 1))
            except Exception:                                    # noqa: BLE001
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                return


def list_sessions() -> List[Dict[str, Any]]:
    """会话摘要列表（新的在前 ✓）"""
    items: List[Dict[str, Any]] = []
    folder = _ensure_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return items
    for name in names:
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(folder, name), encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:                                        # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        messages = data.get('messages') or []
        preview = ''
        for message in messages:
            if str(message.get('role')) == 'user':
                preview = ' '.join(str(message.get('content') or '').split())
                break
        items.append({
            'id': str(data.get('id') or name[:-5]),
            'title': str(data.get('title') or '新会话'),
            'cwd': str(data.get('cwd') or ''),
            'created': float(data.get('created') or 0),
            'updated': float(data.get('updated') or 0),
            'count': len(messages),
            'preview': preview[:120],
            'usage': data.get('usage') or {},
        })
    items.sort(key=lambda item: item['updated'], reverse=True)
    return items


def _session_signature(data: Dict[str, Any]) -> tuple:
    """内容指纹：标题 + 对话条数 + 首条用户消息（判断「重复会话」✓）"""
    messages = [item for item in (data.get('messages') or [])
                if str(item.get('role')) in ('user', 'assistant')]
    first_user = ''
    for item in messages:
        if str(item.get('role')) == 'user':
            first_user = ' '.join(str(item.get('content') or '').split())
            break
    return (str(data.get('title') or ''), len(messages), first_user[:200])


def cleanup_sessions(empty: bool = True,
                     duplicates: bool = True) -> Dict[str, Any]:
    """清理会话：**空会话** + **内容完全重复**的（每组保留最新一条）✓

    用户 2026-11-08：PI 会话列表里出现了重复记录 —— 同一句话反复发送时每次
    都会新建一个会话（早期 bug 的副作用）。这里给一个可控的清理动作。
    """
    items: List[Dict[str, Any]] = []
    folder = _ensure_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return {'ok': False, 'error': '会话目录读不到', 'removed': 0}
    for name in names:
        if not name.endswith('.json'):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:                                    # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        items.append({'name': name, 'path': path, 'data': data})
    removed = 0
    cleared = 0
    if empty:
        for item in list(items):
            messages = [row for row in (item['data'].get('messages') or [])
                        if str(row.get('role')) in ('user', 'assistant')]
            if messages:
                continue
            try:
                os.remove(item['path'])
                removed += 1
                cleared += 1
            except OSError:
                pass
            items.remove(item)
    if duplicates:
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for item in items:
            groups.setdefault(_session_signature(item['data']), []).append(item)
        for rows in groups.values():
            if len(rows) < 2:
                continue
            rows.sort(key=lambda row: float(
                (row['data'].get('updated') or 0)), reverse=True)
            for item in rows[1:]:            # 保留最新一条 ✓
                try:
                    os.remove(item['path'])
                    removed += 1
                except OSError:
                    pass
    return {'ok': True, 'removed': removed, 'empty': cleared,
            'duplicates': removed - cleared}


def create_session(cwd: str = '', title: str = '') -> Dict[str, Any]:
    session = {
        'id': str(uuid.uuid4())[:8],
        'title': str(title or ''),
        'cwd': os.path.abspath(str(cwd or os.getcwd())),
        'created': time.time(),
        'updated': time.time(),
        'messages': [],
    }
    if not session['title']:
        session['title'] = '新会话'
    save_session(session)
    return session


def trim_messages(messages: List[Dict[str, Any]],
                  config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """上下文太长 → 丢掉**最旧**的消息（保留最近一轮完整对话 ✓）

    规则（尽量不破坏 OpenAI 的 tool 协议）：

    * 只从**最前面**成对丢（user + 它后面的 assistant / tool）；
    * 永远保留最后一条 user 及其之后的消息；
    * 丢完再补一条「（更早的对话已裁剪）」提示，让模型知道上下文不完整 ✓
    """
    window = int(config.get('window') or DEFAULT_WINDOW)
    if messages_tokens(messages) <= window * CONTEXT_KEEP:
        return messages
    keep: List[Dict[str, Any]] = []
    # 从后往前收集，直到达到目标 token
    for message in reversed(messages):
        candidate = [message] + keep
        if messages_tokens(candidate) > window * CONTEXT_KEEP and keep:
            break
        keep = candidate
    # 保证第一条不是 tool（tool 必须有前置 assistant.tool_calls ✓）
    while keep and str(keep[0].get('role')) == 'tool':
        keep.pop(0)
    dropped = len(messages) - len(keep)
    if dropped <= 0:
        return messages
    notice = {'role': 'assistant',
              'content': f'（更早的 {dropped} 条消息已因上下文过长被裁剪）'}
    return [notice] + keep


def transcript_markdown(session: Dict[str, Any]) -> str:
    """把一个会话转成 Markdown（导出 / 复制全文都用它 ✓）"""
    usage = session.get('usage') or {}
    lines = [f"# {session.get('title') or '会话'}", '']
    lines.append(f"- 会话 ID：`{session.get('id')}`")
    lines.append(f"- 工作目录：`{session.get('cwd') or ''}`")
    created = float(session.get('created') or 0)
    updated = float(session.get('updated') or 0)
    if created:
        lines.append('- 创建：' + time.strftime('%Y-%m-%d %H:%M',
                                             time.localtime(created)))
    if updated:
        lines.append('- 更新：' + time.strftime('%Y-%m-%d %H:%M',
                                             time.localtime(updated)))
    if session.get('branchOf'):
        lines.append(f"- 分支自：`{session.get('branchOf')}`")
    if usage:
        lines.append(f"- 用量：{int(usage.get('total') or 0)} tokens · "
                     f"{int(usage.get('calls') or 0)} 次调用 · "
                     f"≈${float(usage.get('cost') or 0):.4f}")
    lines.append('')
    for message in session.get('messages') or []:
        role = str(message.get('role') or '')
        content = str(message.get('content') or '')
        if role == 'user':
            lines += ['## 👤 我', '', content, '']
        elif role == 'assistant':
            calls = message.get('tool_calls') or []
            if content:
                lines += ['## 🤖 AI', '', content, '']
            for call in calls:
                function = call.get('function') or {}
                lines += [f"> 🔧 `{function.get('name')}`"
                          f" `{function.get('arguments')}`", '']
        elif role == 'tool':
            body = content[:2000]
            lines += ['```text', body, '```', '']
    return chr(10).join(lines).rstrip() + chr(10)


def export_markdown(session: Dict[str, Any]) -> Dict[str, Any]:
    """写 `~/.minibt/ai/exports/<title>_<id>.md`，返回路径 + 文本 ✓"""
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
    except OSError as error:
        return {'ok': False, 'error': f'创建目录失败：{error!r}'}
    title = re.sub(r'[\\/:*?"<>|\s]+', '_',
                   str(session.get('title') or '会话'))[:40] or 'session'
    name = f"{title}_{session.get('id')}.md"
    path = os.path.join(EXPORT_DIR, name)
    text = transcript_markdown(session)
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
    except OSError as error:
        return {'ok': False, 'error': f'写入失败：{error!r}'}
    return {'ok': True, 'path': path, 'bytes': len(text.encode('utf-8')),
            'text': text}


def list_project_files(root: str, query: str = '',
                       limit: int = 60) -> List[Dict[str, str]]:
    """`@文件` 补全：在工作区里按名字搜文件（跳过重型目录 ✓）"""
    base = os.path.abspath(str(root or '.'))
    needle = str(query or '').strip().lower().replace('\\', '/')
    skip = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist',
            'build', '.mypy_cache', '.pytest_cache', '.idea', '.vscode',
            'site', '.ipynb_checkpoints'}
    rows: List[Dict[str, str]] = []
    for folder, dirs, files in os.walk(base):
        dirs[:] = [item for item in dirs
                   if item not in skip and not item.startswith('.')]
        for entry in files:
            full = os.path.join(folder, entry)
            rel = os.path.relpath(full, base).replace(os.sep, '/')
            if needle and needle not in rel.lower():
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            rows.append({'path': rel, 'name': entry, 'size': str(size)})
            if len(rows) >= 400:
                break
        if len(rows) >= 400:
            break
    rows.sort(key=lambda item: (len(item['path']), item['path']))
    return rows[:max(1, int(limit))]


#: 附件限制（图片走 OpenAI 兼容的 `image_url`，文本直接内联 ✓）
MAX_ATTACHMENTS = 4
MAX_IMAGE_BYTES = 4 * 1024 * 1024        # 单张 ≤ 4MB
MAX_ATTACH_BYTES = 8 * 1024 * 1024       # 合计 ≤ 8MB
MAX_ATTACH_TEXT = 20_000                 # 文本附件最多带 2 万字
IMAGE_MIMES = {'image/png', 'image/jpeg', 'image/jpg', 'image/webp',
               'image/gif', 'image/bmp'}
TEXT_MIMES = {'text/plain', 'text/markdown', 'text/x-python', 'text/csv',
              'application/json', 'application/x-yaml', 'text/yaml',
              'application/javascript', 'text/html', 'text/x-sh'}
#: 文本附件的扩展名（mime 不可靠时按名字判 ✓）
TEXT_EXTS = ('.txt', '.md', '.markdown', '.py', '.json', '.csv', '.log',
             '.yml', '.yaml', '.toml', '.ini', '.cfg', '.ts', '.js', '.html',
             '.css', '.sql', '.sh', '.bat', '.ps1', '.mql', '.pine')


def sanitize_attachments(items: Any) -> List[Dict[str, Any]]:
    """把前端传来的附件**统一成后端格式**（超限 / 类型不对 → 丢弃 ✓）

    前端给的是 ``[{name, mime, data}]``：

    * 图片：`data` 是 dataURL 或裸 base64 → 保留 base64（请求时拼 `image_url`）；
    * 文本（.py / .md / .txt / .json / .csv…）：前端发 `text`（或 dataURL 文本）
      → 解码成字符串（便于直接塞进 prompt），最多 `MAX_ATTACH_TEXT` 字；
    * 其它一律跳过，并回一条 `skipped` 说明（模型 / 用户都知道没带上 ✓）。
    """
    out: List[Dict[str, Any]] = []
    total = 0
    for raw in list(items or [])[:MAX_ATTACHMENTS]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get('name') or 'attachment').strip()[:120]
        mime = str(raw.get('mime') or '').strip().lower()
        data = str(raw.get('data') or '')
        text = raw.get('text')
        # dataURL → 拆出 mime + base64
        if data.startswith('data:'):
            head, _, body = data.partition(',')
            meta = head[5:]
            if not mime:
                mime = meta.split(';')[0].strip().lower()
            data = body
        if not mime:
            mime = ('image/png' if name.lower().endswith(
                ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'))
                else 'text/plain')
        is_image = mime in IMAGE_MIMES or mime.startswith('image/')
        if is_image:
            try:
                import base64
                size = len(base64.b64decode(data, validate=False))
            except Exception:                                # noqa: BLE001
                continue
            if size <= 0 or size > MAX_IMAGE_BYTES:
                continue
            if total + size > MAX_ATTACH_BYTES:
                continue
            total += size
            out.append({'name': name, 'mime': mime, 'kind': 'image',
                        'data': data, 'size': size})
            continue
        # ★ 非图片、也不是文本类型 → **跳过**（别把二进制当文本塞进 prompt ✗）
        if mime not in TEXT_MIMES and not name.lower().endswith(TEXT_EXTS):
            continue
        body = text
        if body is None:
            try:
                import base64
                body = base64.b64decode(data, validate=False).decode(
                    'utf-8', 'replace')
            except Exception:                                # noqa: BLE001
                body = data
        body = str(body or '')
        if not body.strip():
            continue
        body = body[:MAX_ATTACH_TEXT]
        if total + len(body.encode('utf-8', 'replace')) > MAX_ATTACH_BYTES:
            continue
        total += len(body.encode('utf-8', 'replace'))
        out.append({'name': name, 'mime': mime or 'text/plain',
                    'kind': 'text', 'text': body,
                    'size': len(body.encode('utf-8', 'replace'))})
    return out


def describe_attachments(items: List[Dict[str, Any]]) -> str:
    """附件清单（拼在文本附件前后，让模型知道有哪些文件 ✓）"""
    rows = [item for item in (items or []) if item]
    if not rows:
        return ''
    lines = ['【附件】']
    for item in rows:
        kind = '图片' if item.get('kind') == 'image' else '文本'
        size = int(item.get('size') or 0)
        lines.append(f'- {item.get("name")}（{kind} · {size // 1024 or 1}KB）')
    return chr(10).join(lines)


def read_refs(root: str, refs: List[str]) -> str:
    """把 `@文件` 引用的内容拼成一段（给模型看 ✓）"""
    base = os.path.abspath(str(root or '.'))
    blocks: List[str] = []
    for ref in (refs or [])[:MAX_REFS]:
        try:
            path = _inside(base, ref)
        except ValueError:
            continue
        if not os.path.isfile(path):
            continue
        try:
            body = read_text_smart(path, MAX_REF_CHARS)
        except OSError:
            continue
        blocks.append(f'--- 文件：{ref} ---' + chr(10) + '```'
                      + chr(10) + body + chr(10) + '```')
    return (chr(10) + chr(10)).join(blocks)


def branch_session(session_id: str, upto: int,
                   title: str = '') -> Optional[Dict[str, Any]]:
    """从某条消息**分叉**出一个新会话（`upto` = 消息下标，含该条 ✓）

    * 复制 `messages[:upto+1]`；
    * 末尾的 `tool` 消息如果找不到对应的 `assistant.tool_calls`，一起丢掉
      （否则再发消息时服务会报「tool 消息没有前置调用」✗）；
    * usage **不继承**（新会话从 0 开始算，避免花费看起来翻倍 ✓）。
    """
    session = load_session(session_id)
    if session is None:
        return None
    messages = list(session.get('messages') or [])
    try:
        index = int(upto)
    except (TypeError, ValueError):
        index = len(messages) - 1
    index = max(0, min(len(messages) - 1, index))
    cut = messages[:index + 1]
    while cut and str(cut[-1].get('role')) == 'tool':
        cut.pop()
    # assistant 带 tool_calls 但后面没有 tool 结果 → 也去掉（同上）
    if cut and str(cut[-1].get('role')) == 'assistant' and cut[-1].get('tool_calls'):
        cut.pop()
    base_title = str(title or '').strip() or (
        f"{session.get('title') or '会话'} · 分支"
    )
    branch = {
        'id': str(uuid.uuid4())[:8],
        'title': base_title[:60],
        'cwd': session.get('cwd') or os.getcwd(),
        'created': time.time(),
        'updated': time.time(),
        'messages': cut,
        'usage': {},
        'branchOf': session_id,
    }
    save_session(branch)
    return branch


def delete_session(session_id: str) -> bool:
    try:
        os.remove(_session_path(session_id))
        return True
    except OSError:
        return False


def rename_session(session_id: str, title: str) -> Optional[Dict[str, Any]]:
    session = load_session(session_id)
    if session is None:
        return None
    session['title'] = str(title or '').strip(
    ) or session.get('title') or '新会话'
    save_session(session)
    return session


#: 典型「UTF-8 被当 GBK 解」的乱码字（出现越多说明选错了编码 ✓）
MOJIBAKE_CHARS = '锛銆涓鏄鈥馃鏂鍜鎴璇鍦鍑鍏鍗鍙鍛'


def _decode_one(chunk: bytes) -> str:
    """解一行：候选编码 + 二次解码修复，挑「最不像乱码」的那个 ✓"""
    if not chunk:
        return ''
    best: Optional[tuple] = None
    for codec in ('utf-8', 'gbk', 'gb18030', 'big5'):
        try:
            text = chunk.decode(codec)
        except (UnicodeDecodeError, LookupError):
            continue
        candidates = [text]
        # 「UTF-8 字节被当 GBK 解」→ 编回 GBK 再按 UTF-8 解一次就复原了 ✓
        try:
            repaired = text.encode('gbk', 'ignore').decode('utf-8', 'ignore')
            if repaired and repaired != text:
                candidates.append(repaired)
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        for candidate in candidates:
            score = candidate.count('\ufffd') * 5 + sum(
                candidate.count(char) for char in MOJIBAKE_CHARS)
            if best is None or score < best[0]:
                best = (score, candidate)
        if best is not None and best[0] == 0:
            break
    if best is None:
        return chunk.decode('utf-8', 'replace')
    return best[1]


def decode_bytes(data: bytes) -> str:
    """把子进程 / 文件字节解码成文字（**按行**，混合编码也能各解各的 ✓）

    Windows 的 `cmd` / `dir` / 老脚本是 **CP936(GBK)**，而设了
    `PYTHONIOENCODING=utf-8` 的 python 输出又是 UTF-8 —— 同一条命令里混着两种，
    整块解码必然坏一半（用户 2026-11-08 实测 ✗）。
    """
    if not data:
        return ''
    raw = data.replace(b'\r\n', b'\n')
    if b'\n' not in raw:
        return _decode_one(raw)
    return '\n'.join(_decode_one(line) for line in raw.split(b'\n'))


def read_text_smart(path: str, limit: int = MAX_READ_BYTES) -> str:
    """读文本文件：自动 UTF-8 / GBK（中文源码常见）→ 前 `limit` 字节 ✓"""
    with open(path, 'rb') as handle:
        return decode_bytes(handle.read(limit))


# ---------------------------------------------------------------- 工具执行
def _inside(root: str, path: str) -> str:
    """把相对路径解析成绝对路径，并确保在 `root` 内（防 `../..` ✗）"""
    base = os.path.abspath(root)
    target = os.path.abspath(os.path.join(base, str(path or '.')))
    if target != base and not target.startswith(base + os.sep):
        raise ValueError(f'路径超出工作区：{path}')
    return target


def run_tool(name: str, args: Dict[str, Any], root: str,
             limits: Optional[Dict[str, Any]] = None,
             desk=None, session: str = '') -> str:
    """执行一个工具，返回给模型的文本结果（出错也返回文本 ✓）

    `limits`（模型对话框 → 高级）可以覆盖：`timeout` 命令超时、
    `output` 工具输出上限、`read` 单文件读取上限 ✓
    """
    limits = limits or {}
    # ★ `desk_*` 工具直接交给工具桥（同进程调 desk 的既有方法 ✓）
    if name.startswith('desk_') and _desk_tools is not None:
        return _desk_tools.call(name, args if isinstance(args, dict) else {},
                                desk, session)
    # ★ 外部 MCP server 的工具（`mcp__<server>__<tool>`）✓
    if name.startswith('mcp__'):
        try:
            from . import mcp_client
            return mcp_client.call_tool(
                name, args if isinstance(args, dict) else {})
        except Exception as error:                            # noqa: BLE001
            return f'外部 MCP 调用失败：{type(error).__name__}: {error}'
    try:
        timeout = float(limits.get('timeout') or COMMAND_TIMEOUT)
    except (TypeError, ValueError):
        timeout = COMMAND_TIMEOUT
    try:
        output_limit = int(limits.get('output') or MAX_TOOL_OUTPUT)
    except (TypeError, ValueError):
        output_limit = MAX_TOOL_OUTPUT
    try:
        read_limit = int(limits.get('read') or MAX_READ_BYTES)
    except (TypeError, ValueError):
        read_limit = MAX_READ_BYTES
    try:
        if name == 'list_dir':
            folder = _inside(root, args.get('path') or '.')
            rows = []
            for entry in sorted(os.listdir(folder))[:200]:
                full = os.path.join(folder, entry)
                rows.append(f'{entry}/' if os.path.isdir(full) else entry)
            return '\n'.join(rows) or '（空目录）'
        if name == 'read_file':
            path = _inside(root, args.get('path') or '')
            return read_text_smart(path, read_limit)
        if name == 'grep':
            pattern = str(args.get('pattern') or '')
            if not pattern:
                return '（pattern 为空）'
            regex = re.compile(pattern)
            folder = _inside(root, args.get('path') or '.')
            rows: List[str] = []
            for base, dirs, files in os.walk(folder):
                # ★ 跳过缓存 / 依赖目录（`.pyc` 读出来全是乱码 ✗）
                dirs[:] = [item for item in dirs
                           if item not in SKIP_DIRS
                           and not item.startswith('.')]
                for entry in files:
                    full = os.path.join(base, entry)
                    try:
                        with open(full, 'rb') as handle:
                            raw = handle.read(read_limit)
                    except OSError:
                        continue
                    if b'\x00' in raw[:2048]:        # 二进制文件 → 跳过 ✓
                        continue
                    text = decode_bytes(raw)
                    for number, line in enumerate(text.splitlines(), 1):
                        if regex.search(line):
                            rows.append(
                                f'{os.path.relpath(full, root)}:'
                                f'{number}: {line.strip()[:160]}')
                            if len(rows) >= 80:
                                return '\n'.join(rows)
            return '\n'.join(rows) or '（没有匹配）'
        if name == 'write_file':
            path = _inside(root, args.get('path') or '')
            content = str(args.get('content') or '')
            if len(content.encode('utf-8')) > MAX_FILE_BYTES:
                return '文件太大（>200KB），拒绝写入'
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(content)
            return f'已写入 {os.path.relpath(path, root)}（{len(content)} 字）'
        if name == 'run_command':
            command = str(args.get('command') or '')
            limit = float(args.get('timeout') or timeout)
            limit = max(1.0, min(timeout, limit))
            env = dict(os.environ)
            env.setdefault('PYTHONIOENCODING', 'utf-8')
            result = subprocess.run(
                command, shell=True, cwd=os.path.abspath(root),
                capture_output=True, timeout=limit,
                stdin=subprocess.DEVNULL, env=env)
            out = decode_bytes(result.stdout or b'') \
                + decode_bytes(result.stderr or b'')
            return (out or f'（无输出，退出码 {result.returncode}）')[
                :output_limit]
        return f'未知工具：{name}'
    except subprocess.TimeoutExpired:
        return '命令超时（>25 秒）'
    except Exception as error:                                   # noqa: BLE001
        return f'工具执行失败：{type(error).__name__}: {error}'


# ---------------------------------------------------------------- 模型调用
def _post_stream(url: str, payload: Dict[str, Any], key: str,
                 on_delta, timeout: float = 180.0,
                 on_thinking=None) -> Dict[str, Any]:
    """POST `/chat/completions`（`stream: true`），逐块回调 `on_delta` ✓"""
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = f'Bearer {key}'
    request = urllib.request.Request(url, data=body, method='POST',
                                     headers=headers)
    content: List[str] = []
    thinking: List[str] = []
    tool_calls: Dict[int, Dict[str, Any]] = {}
    finish = ''
    usage: Dict[str, Any] = {}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw in response:
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                chunk = line[5:].strip()
                if chunk == '[DONE]':
                    break
                try:
                    data = json.loads(chunk)
                except ValueError:
                    continue
                # ★ 有些服务把 usage 放在**最后一块**（`include_usage` ✓）
                if isinstance(data.get('usage'), dict):
                    usage = data['usage']
                choices = data.get('choices') or []
                if not choices:
                    continue
                choice = choices[0] or {}
                delta = choice.get('delta') or {}
                piece = delta.get('content') or ''
                if piece:
                    content.append(piece)
                    on_delta(piece)
                # ★ 思考过程：DeepSeek `reasoning_content` / OpenRouter `reasoning`
                #   / 其它兼容层的 `thinking`（可能是字符串或 `{content}` ✓）
                thought = (delta.get('reasoning_content')
                           or delta.get('reasoning') or delta.get('thinking')
                           or '')
                if isinstance(thought, dict):
                    thought = (thought.get('content') or thought.get('text')
                               or '')
                if thought:
                    thinking.append(str(thought))
                    if on_thinking:
                        on_thinking(str(thought))
                for call in delta.get('tool_calls') or []:
                    index = int(call.get('index') or 0)
                    slot = tool_calls.setdefault(index, {
                        'id': '', 'name': '', 'arguments': ''})
                    if call.get('id'):
                        slot['id'] = str(call['id'])
                    function = call.get('function') or {}
                    if function.get('name'):
                        slot['name'] = str(function['name'])
                    if function.get('arguments'):
                        slot['arguments'] += str(function['arguments'])
                if choice.get('finish_reason'):
                    finish = str(choice['finish_reason'])
    except urllib.error.HTTPError as error:
        detail = ''
        try:
            detail = error.read().decode('utf-8', 'replace')[:300]
        except Exception:                                        # noqa: BLE001
            detail = ''
        return {'ok': False, 'error': f'HTTP {error.code}：{detail or error.reason}'}
    except urllib.error.URLError as error:
        return {'ok': False, 'error': f'连不上接口：{error.reason}'}
    except Exception as error:                                   # noqa: BLE001
        return {'ok': False, 'error': f'请求失败：{error!r}'}
    return {'ok': True, 'content': ''.join(content), 'finish': finish,
            'thinking': ''.join(thinking), 'usage': usage,
            'tool_calls': [tool_calls[key] for key in sorted(tool_calls)]}


def ping(config: Dict[str, Any], timeout: float = 20.0) -> Dict[str, Any]:
    """「测试连接」：最小请求（1 token），把错误原样带回来 ✓

    只验证 **地址 + Key + 模型名** 能不能用，不产生真实对话 ✓
    """
    import time as _time

    base = str(config.get('base') or DEFAULT_BASE).rstrip('/')
    key = str(config.get('key') or '')
    if not key and not re.search(r'(127\.0\.0\.1|localhost)', base):
        return {'ok': False, 'base': base, 'model': config.get('model'),
                'error': '还没填 API Key'}
    started = _time.time()
    reply = _post_stream(
        base + '/chat/completions',
        {'model': config.get('model') or DEFAULT_MODEL,
         'messages': [{'role': 'user', 'content': 'ping'}],
         'stream': True, 'max_tokens': 1, 'temperature': 0},
        key, lambda _piece: None, timeout)
    elapsed = int((_time.time() - started) * 1000)
    if not reply.get('ok'):
        return {'ok': False, 'base': base, 'model': config.get('model'),
                'error': str(reply.get('error') or '连接失败'), 'ms': elapsed}
    return {'ok': True, 'base': base, 'model': config.get('model'),
            'ms': elapsed, 'tokens': (reply.get('usage') or {}).get(
                'total_tokens') or 0}


def chat_once(config: Dict[str, Any], messages: List[Dict[str, Any]],
              on_delta=None, tools: Optional[List[Dict[str, Any]]] = None,
              timeout: float = 180.0,
              max_tokens: Optional[int] = None,
              temperature: float = 0.2,
              on_thinking=None) -> Dict[str, Any]:
    """单次调用（流式）；`tools` 非空时带函数定义 ✓"""
    if not config.get('key') and 'localhost' not in config.get('base', '') \
            and '127.0.0.1' not in config.get('base', ''):
        return {'ok': False,
                'error': '还没配置 API Key：设置 → AI 助手 → API Key'
                         '（或环境变量 MINIBT_AI_KEY）'}
    payload: Dict[str, Any] = {
        'model': config.get('model') or DEFAULT_MODEL,
        'messages': messages,
        'stream': True,
        'temperature': float(temperature),
        # 让服务在最后一块回 usage（拿不到就本地粗估 ✓）
        'stream_options': {'include_usage': True},
    }
    if max_tokens:
        payload['max_tokens'] = int(max_tokens)
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = 'auto'
    url = str(config.get('base') or DEFAULT_BASE).rstrip(
        '/') + '/chat/completions'
    reply = _post_stream(url, payload, str(config.get('key') or ''),
                         on_delta or (lambda _piece: None), timeout,
                         on_thinking=on_thinking)
    if not reply.get('ok'):
        error = str(reply.get('error') or '')
        # 老 / 精简版服务可能不认 `stream_options` → 去掉再试一次 ✓
        if 'stream_options' in error or 'HTTP 400' in error:
            payload.pop('stream_options', None)
            reply = _post_stream(url, payload, str(config.get('key') or ''),
                                 on_delta or (lambda _piece: None), timeout,
                                 on_thinking=on_thinking)
    return reply


class AgentRun:
    """一次「发送」的完整流程（后台线程跑，支持中断 ✓）"""

    def __init__(self, desk, session: Dict[str, Any], config: Dict[str, Any],
                 text: str, reuse_last_user: bool = False,
                 refs: Optional[List[str]] = None,
                 attachments: Optional[List[Dict[str, Any]]] = None,
                 event_type: str = 'ai_event') -> None:
        self.desk = desk
        self.session = session
        self.config = config
        self.text = text
        self.cancelled = False
        self.reuse_last_user = bool(reuse_last_user)
        #: 补丁类型（PI 页用 `pi_event`，内置 AI 页用 `ai_event` ✓）
        self.event_type = str(event_type or 'ai_event')
        #: 工具限制（模型对话框「高级」→ `models.json.limits`）✓
        self.limits = {
            'timeout': config.get('timeout') or COMMAND_TIMEOUT,
            'output': config.get('maxOutput') or MAX_TOOL_OUTPUT,
            'read': config.get('maxRead') or MAX_READ_BYTES,
        }
        self.refs = list(refs or [])
        # ★ 附件（图片 / 文本）：界面显示 + 请求时转 content parts ✓
        self.attachments = sanitize_attachments(attachments or [])
        self.session_id = str(session.get('id') or '')
        self.root = str(session.get('cwd') or os.getcwd())
        # ★ 会话级选项（模型 / 强度 / 权限 / 压缩 / 技能）✓
        self.options = dict(session.get('options') or {})
        # ★ 执行中用户又发了消息 → 追加到**这一轮**（不重启 ✓）
        self.pending: List[str] = []
        self._pending_lock = threading.Lock()
        #: 这一轮是否已经彻底结束（结束后再插话就要排队 ✓）
        self.finished = False

    def append_user(self, text: str) -> bool:
        """执行中追加一句用户消息（下一轮工具调用后就会带上 ✓）"""
        value = str(text or '').strip()
        if not value or getattr(self, 'finished', False):
            return False
        with self._pending_lock:
            self.pending.append(value)
        return True

    def _drain_pending(self, messages: List[Dict[str, Any]]) -> None:
        """把排队中的用户消息并入上下文（进循环前 / 每轮工具后 ✓）"""
        with self._pending_lock:
            rows, self.pending = self.pending, []
        for text in rows:
            messages.append({'role': 'user', 'content': text})
            self.push({'event': 'user', 'text': text})
            self.save(messages)

    # ------------------------------------------------------------ 补丁
    def push(self, payload: Dict[str, Any]) -> None:
        try:
            self.desk.push({'type': self.event_type,
                            'id': self.session_id, **payload})
        except Exception:                                        # noqa: BLE001
            pass

    # ------------------------------------------------------------ 主流程
    def run(self) -> None:
        try:
            self._run()
        except Exception as error:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            self.push({'event': 'error',
                       'error': f'{type(error).__name__}: {error}'})
        finally:
            self.finished = True
            # ★ 这一轮彻底结束：注销 + 放行「执行中排队」的那条 ✓
            try:
                unregister(self.session_id)
            except Exception:                                 # noqa: BLE001
                pass
            flush = getattr(self.desk, 'flush_pi_queue', None)
            if callable(flush):
                try:
                    flush(self.session_id)
                except Exception:                             # noqa: BLE001
                    pass

    def _run(self) -> None:
        messages = list(self.session.get('messages') or [])
        if self.reuse_last_user:
            # 「重新生成」：上一条 user 消息已经在里面了，不重复追加 ✓
            self.push({'event': 'restart'})
        else:
            content = self.text
            if self.refs:
                extra = read_refs(self.root, self.refs)
                if extra:
                    content = content + chr(10) + chr(10) + extra
            note = describe_attachments(self.attachments)
            if note:
                content = (content + chr(10) + chr(10) + note).strip()
            user_message: Dict[str, Any] = {'role': 'user',
                                            'content': content}
            if self.attachments:
                user_message['attachments'] = self.attachments
            messages.append(user_message)
            self.save(messages)
            self.push({'event': 'user', 'text': content,
                       'attachments': [
                           {key: item.get(key) for key in
                            ('name', 'mime', 'kind', 'size')}
                           for item in self.attachments]})
        messages = self.prepare_context(messages)

        messages = self.with_system(messages)
        tools = self.filtered_tools()
        effort = EFFORT_LEVELS.get(str(self.options.get('effort') or 'medium'),
                                   EFFORT_LEVELS['medium'])
        for turn in range(int(self.config.get('turns') or MAX_TURNS)):
            # ★ 用户在执行中插话 → 这里带上（不用 stop+重启 ✓）
            self._drain_pending(messages)
            if self.cancelled:
                self.push({'event': 'done', 'cancelled': True})
                return
            started = time.monotonic()
            reply = chat_once(self.config, api_messages(messages),
                              on_delta=lambda piece:
                              self.push({'event': 'delta', 'text': piece}),
                              on_thinking=lambda piece:
                              self.push({'event': 'thinking', 'text': piece}),
                              tools=tools,
                              max_tokens=int(effort['max_tokens']),
                              temperature=float(effort['temperature']))
            if not reply.get('ok'):
                self.push({'event': 'error',
                           'error': reply.get('error') or '请求失败'})
                return
            round_usage = self.track_usage(reply.get('usage'), messages)
            content = str(reply.get('content') or '')
            thought = str(reply.get('thinking') or '')
            calls = reply.get('tool_calls') or []
            assistant: Dict[str, Any] = {
                'role': 'assistant', 'content': content,
                # ★ 这几项只给界面看（api_messages() 会剥掉 ✓）
                'thinking': thought,
                'usage': round_usage,
                'model': str(self.config.get('model') or ''),
                'seconds': round(time.monotonic() - started, 1),
            }
            if calls:
                assistant['tool_calls'] = [
                    {'id': call.get('id') or f'call{index}',
                     'type': 'function',
                     'function': {'name': call.get('name') or '',
                                  'arguments': call.get('arguments') or '{}'}}
                    for index, call in enumerate(calls)]
            messages.append(assistant)
            self.save(messages)
            if content:
                self.push({'event': 'assistant', 'text': content})
            if not calls:
                note = ''
                if str(reply.get('finish') or '') == 'length':
                    note = '（回答被 max_tokens 截断了 —— 可以把「强度」调高，'
                    '或回「继续」接着写）'
                elif not content.strip():
                    note = '（模型这次没有返回文字：可以直接回「继续」，'
                    '或换个更明确的说法）'
                if note:
                    self.push({'event': 'assistant', 'text': note})
                self.push({'event': 'done', 'cancelled': self.cancelled,
                           'note': note})
                return
            for call in calls:
                if self.cancelled:
                    self.push({'event': 'done', 'cancelled': True,
                               'note': '已停止'})
                    return
                name = str(call.get('name') or '')
                started = time.monotonic()
                try:
                    args = json.loads(call.get('arguments') or '{}')
                except ValueError:
                    args = {}
                self.push({'event': 'tool', 'name': name, 'args': args})
                result = run_tool(name, args if isinstance(args, dict) else {},
                                  self.root, self.limits, desk=self.desk,
                                  session=self.session_id)
                messages.append({
                    'role': 'tool',
                    'tool_call_id': call.get('id') or '',
                    'name': name,
                    # 参数 / 耗时也存下来：重开会话时工具卡才画得出来 ✓
                    'args': json.dumps(args, ensure_ascii=False)[:4000],
                    'elapsed': round(time.monotonic() - started, 2),
                    'content': result[:MAX_TOOL_OUTPUT],
                })
                self.save(messages)
                self.push({'event': 'tool_result', 'name': name,
                           'text': result[:int(self.limits['output'])],
                           'elapsed': round(time.monotonic() - started, 2)})
                self._drain_pending(messages)
        limit = int(self.config.get('turns') or MAX_TURNS)
        note = (f'（已经连续调了 {limit} 轮工具，先停在这里 —— '
                '回「继续」我就接着做；也可以让我一步到位）')
        self.push({'event': 'assistant', 'text': note})
        self.push({'event': 'done', 'cancelled': self.cancelled,
                   'note': note, 'limit': limit})

    def with_system(self, messages: List[Dict[str, Any]]) \
            -> List[Dict[str, Any]]:
        """插入 system 提示（工作区 / 技能 / 强度说明 ✓）"""
        effort = EFFORT_LEVELS.get(str(self.options.get('effort') or 'medium'),
                                   EFFORT_LEVELS['medium'])
        lines = [
            '你是 PI 助手，运行在 minibt desk（Python 量化交易终端）里，'
            '帮用户读写项目文件、跑命令、改策略与指标。',
            f'当前工作区：{self.root}',
            '工具只能操作这个工作区；改文件前先读一遍，改完给出验证方法。',
            '可以连续调用多个工具（最多 12 轮），每一步都简短说明在做什么。',
            effort['hint'],
            # ★ 工具选择规则（v1.3.7-45）：实测能把「加指标 + 回放」从 48 轮降到 1~3 轮
            '【工具选择规则 · 很重要】',
            '1. 不确定指标 key 时**先调 desk_find_indicator{query}**，'
            '不要猜（例：`pandas_ta.macd` 的真实 key 是 `pta_macd`；'
            '`macd` 有多个版本，必须从候选里挑一个）。',
            '2. `desk_indicator_picker` 只是**打开选择器让用户自己挑**，'
            '不会添加指标；模型要加指标一律用 `desk_add_indicator`。',
            '3. 本地图表（CSV 数据）的所有工具都要带 `local:true`：'
            '`desk_add_indicator{key, local:true}`、`desk_replay{local:true}`、'
            "`desk_set_layout{local:true, symbols:['数据集A','数据集B']}`；"
            '不需要传 symbol（自动用当前格的数据集）。',
            '4. 一件任务需要 2 步以上（查指标 → 加 → 回放 / 切布局 → 加指标）时，'
            '**优先用 `desk_sequence{steps:[{tool,args}…]}` 一次调完**（≤6 步），'
            '不要一轮只做一步。下单 / 实盘 / 撤单不能放进 sequence。',
            '5. 不确定当前状态先 `desk_status`（带 hints / local_pages），'
            '别反复试错；工具回 `next_hint` / `candidates` 时照它做。',
            '6. 例：用户说「给本地图表 test 加 pandas_ta 的 macd 并回放」→ 一次：'
            '`desk_sequence{steps:[{tool:"desk_add_indicator",'
            'args:{key:"pta_macd", local:true}},'
            '{tool:"desk_replay", args:{local:true}}]}'
            '`（不确定 key 就先加一步 desk_find_indicator）。',
            '7. **涉及账户 / 下单**：先 `desk_account{action:"summary"}` 看登录'
            '与资金；`ready:false` 说明交易没连上 → 先 `desk_login_futures`，'
            '**不要**硬下单。`desk_order` 回 `need_login` / `ok:false` 时必须'
            '如实告诉用户「委托没有提交」，绝不能说成已下单。',
            '8. 账户查询统一用 `desk_account`：`summary` / `positions` / '
            '`orders`（全部委托）/ `unfilled`（真实未成交）/ `trades`（成交）/ '
            '`pending` / `audit`（委托审计）。审计里的 `PENDING` 只是'
            '「已提交给柜台」，**不是成交**，也不是"排队等重连生效"。',
            '9. **分析行情要数字，不要凭截图猜**：`desk_market{action:"klines"}`'
            ' 拿 OHLCV + 涨跌幅 / 高低 / MA；`desk_market{action:"indicator", key, '
            'params}` 拿指标数值（金叉 / 背离按两列自己比）；'
            '`desk_market{action:"summary"}` 一次给报价 + K 线统计 + 图上指标；'
            '`desk_market{action:"quote", symbols}` 看多合约最新价。'
            '本地 CSV 加 `local:true`(+`name`)。',
            '11. **分析一段行情优先一条命令**：'
            '`desk_market{action:"analysis"}` —— 一次返回 支撑阻力（levels）+ '
            'ATR/RSI/趋势（stats）+ K 线形态（patterns）+ 紧凑文本（text），'
            '**不要**连调三次。要下钻再单独取数：`{action:"levels"}` 支撑阻力'
            '（前高前低 / 斐波那契 / 成交量分布 POC）、`{action:"stats"}` ATR·波动率·'
            'RSI·趋势斜率、`{action:"patterns"}` K 线形态、`{action:"depth"}` 五档'
            '买卖压力、`{action:"digest"}` 紧凑文本（长对话省 token）；'
            '多合约一起挑用 `desk_scan{symbols, key, op:"cross_up", value}`；'
            '回测结果 / 策略信号用 `desk_strategy_data{action:"summary"|"trades"|'
            '"equity"|"signals"}`。**不要凭截图猜数字**。',
            '10. 「全部K线 / 只看最近 300 根」是**视图缩放**，'
            '用 `desk_bars{action:"all"}` / `desk_bars{action:"last", count:300}`；'
            '**不要去改设置里的 `chart_data_length`**（那是加载长度，改了会影响'
            '所有图表，也不一定立刻生效）。',
        ]
        skills = str(self.options.get('skillsPrompt') or '').strip()
        if skills:
            lines.append('可用的技能（按需遵循）：\n' + skills)
        keep = [item for item in messages
                if str(item.get('role')) != 'system']
        return [{'role': 'system', 'content': '\n'.join(lines)}] + keep

    def external_names(self) -> List[str]:
        """外部 MCP 工具名（每次都查缓存，挂新 server 不用重启 ✓）"""
        try:
            from . import mcp_client
            return mcp_client.names()
        except Exception:                                     # noqa: BLE001
            return []

    def filtered_tools(self) -> Optional[List[Dict[str, Any]]]:
        """按「权限」过滤工具（只读 / 默认 / 完全 ✓）"""
        if not self.config.get('tools'):
            return None
        permission = str(self.options.get('permission') or 'default')
        allowed = set(TOOL_GROUPS.get(permission, TOOL_GROUPS['default']))
        candidates = list(TOOLS)
        # ★ 外部 MCP 工具：只读档不给（它们可能写数据 / 花钱 ✓）
        if permission != 'readonly':
            extra = external_tools()
            allowed.update(
                str((tool.get('function') or {}).get('name'))
                for tool in extra)
            candidates += extra
        rows = [tool for tool in candidates
                if str((tool.get('function') or {}).get('name')) in allowed]
        return rows or None

    def maybe_compress(self, messages: List[Dict[str, Any]]) \
            -> List[Dict[str, Any]]:
        """「压缩」开关：超过 60% 窗口就先让模型总结旧对话（失败退回裁剪 ✓）"""
        if not self.options.get('compress'):
            return messages
        window = int(self.config.get('window') or DEFAULT_WINDOW)
        if messages_tokens(messages) <= window * COMPRESS_AT:
            return messages
        # 只保留最后 6 条，之前的让模型压缩成一段摘要
        head = messages[:-6]
        tail = messages[-6:]
        if len(head) <= 1:
            return messages
        try:
            summary = chat_once(self.config, [
                {'role': 'system',
                 'content': '把下面这段对话压缩成 200 字以内的中文摘要，'
                            '保留结论、已改的文件、未完成的事项。'},
                {'role': 'user', 'content': '\n'.join(
                    f"{item.get('role')}: {str(item.get('content') or '')[:2000]}"
                    for item in head)},
            ], None, None, timeout=90, max_tokens=600, temperature=0.1)
            text = str(summary.get('content') or '').strip()
        except Exception:                                        # noqa: BLE001
            text = ''
        if not text:
            return trim_messages(messages, self.config)
        self.push({'event': 'compressed', 'chars': len(text)})
        return [{'role': 'assistant',
                 'content': '（更早的对话已压缩）\n' + text}] + tail

    def prepare_context(self, messages: List[Dict[str, Any]]) \
            -> List[Dict[str, Any]]:
        """上下文太长 → 先告警、再裁剪（用户能看见 ✓）"""
        window = int(self.config.get('window') or DEFAULT_WINDOW)
        tokens = messages_tokens(messages)
        percent = 100.0 * tokens / max(1, window)
        if percent >= CONTEXT_WARN * 100:
            self.push({'event': 'context_warn', 'percent': round(percent, 1),
                       'context': tokens, 'window': window})
        if percent >= CONTEXT_TRIM * 100:
            kept = trim_messages(messages, self.config)
            dropped = len(messages) - len(kept)
            if dropped > 0:
                self.push({'event': 'trimmed', 'dropped': dropped,
                           'context': messages_tokens(kept), 'window': window})
                self.save(kept)
                return kept
        return self.maybe_compress(messages)

    def track_usage(self, usage: Any,
                    messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """累计 token / 花费（服务没回 usage 就本地粗估 ✓）→ 返回**单轮**用量"""
        round_usage = usage_of(usage, messages, self.config)
        prompt = int(round_usage['prompt'])
        completion = int(round_usage['completion'])
        total = int(round_usage['total'])
        cached = int(round_usage['cached'])
        cost = float(round_usage['cost'])
        current = self.session.get('usage') or {}
        current = {
            'prompt': int(current.get('prompt') or 0) + prompt,
            'completion': int(current.get('completion') or 0) + completion,
            'cached': int(current.get('cached') or 0) + cached,
            'total': int(current.get('total') or 0) + total,
            'cost': float(current.get('cost') or 0.0) + cost,
            'calls': int(current.get('calls') or 0) + 1,
            'last_prompt': prompt,
            'last_completion': completion,
        }
        self.session['usage'] = current
        window = int(self.config.get('window') or DEFAULT_WINDOW)
        context = messages_tokens(messages)
        self.push({'event': 'usage', 'usage': current,
                   'round': round_usage,
                   'context': context, 'window': window,
                   'percent': round(100.0 * context / max(1, window), 1)})
        return round_usage

    def save(self, messages: List[Dict[str, Any]]) -> None:
        self.session['messages'] = messages
        if not str(self.session.get('title') or '').strip() \
                or self.session.get('title') == '新会话':
            head = ' '.join(str(self.text or '').split())
            self.session['title'] = (head[:40] or '新会话')
        save_session(self.session)


def start_run(desk, session: Dict[str, Any], config: Dict[str, Any],
              text: str, reuse_last_user: bool = False,
              refs: Optional[List[str]] = None,
              attachments: Optional[List[Dict[str, Any]]] = None,
              event_type: str = 'ai_event') -> AgentRun:
    """后台线程跑一次对话（返回句柄，供 `ai_stop` 取消 ✓）"""
    run = AgentRun(desk, session, config, text,
                   reuse_last_user=reuse_last_user, refs=refs,
                   attachments=attachments, event_type=event_type)
    threading.Thread(target=run.run, daemon=True).start()
    return run


def truncate_for_regenerate(session: Dict[str, Any]) -> Dict[str, Any]:
    """把会话截到「最后一条 user 消息」为止（重新生成回答用 ✓）"""
    messages = list(session.get('messages') or [])
    cut = None
    for index in range(len(messages) - 1, -1, -1):
        if str(messages[index].get('role')) == 'user':
            cut = index
            break
    if cut is None:
        return session
    session['messages'] = messages[:cut + 1]
    return session


#: 正在跑的会话（`session id → AgentRun`）
RUNS: Dict[str, AgentRun] = {}
_LOCK = threading.Lock()


def register(run: AgentRun) -> None:
    with _LOCK:
        RUNS[run.session_id] = run


def cancel(session_id: str) -> bool:
    with _LOCK:
        run = RUNS.get(str(session_id))
    if run is None:
        return False
    run.cancelled = True
    return True


def unregister(session_id: str) -> None:
    with _LOCK:
        RUNS.pop(str(session_id), None)

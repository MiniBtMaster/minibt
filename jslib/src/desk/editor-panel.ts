/**
 * EditorPanel —— 「代码」页签（资源管理器 + CodeMirror ✓）
 *
 * 结构（`tradingview/vscode资源管理器.png`）：
 *
 *   ┌ 工具栏：打开目录 / 新建▾ / 保存 / 语法检查 / 格式化 / 加到图表 / 删除 /
 *   │        刷新 / 刷新指标策略  … 打开的标签页                    ┐
 *   ├─────────────┬─────────────────────────────────────────────────┤
 *   │ 资源管理器   │ CodeMirror（Python 高亮，右键菜单 ✓）            │
 *   │ ▾ my_root    │                                                 │
 *   │   ▸ sub      │                                                 │
 *   │    a.py      │                                                 │
 *   └─────────────┴─────────────────────────────────────────────────┘
 *
 * 文件树是**真的文件系统**（`explorer_list`），不是「个人指标 / 策略」两栏；
 * 根目录可以用「打开目录」换，并存在 `settings.explorer_root` ✓
 */
import { CodeEditor } from './code-editor';
import { showMenuBelow, type MenuItem } from './menu';
import {
    ICON_COPY, ICON_ERASER, ICON_PENCIL, ICON_REFRESH, ICON_TRASH,
} from './icons';

export interface ExplorerItem {
    name: string;
    path: string;
    dir: boolean;
    py?: boolean;
    /** 文本类文件（md / txt / json…）：也能在编辑器里打开 ✓ */
    text?: boolean;
    size?: number;
    mtime?: number;
    editable?: boolean;
}

export interface ExplorerData {
    ok: boolean;
    root: string;
    path: string;
    parent?: string;
    items: ExplorerItem[];
    error?: string;
}

export interface EditorCheckResult {
    ok: boolean;
    line?: number;
    col?: number;
    error?: string;
    defines?: Array<{ kind: string; name: string }>;
}

export interface EditorPanelOptions {
    theme: 'light' | 'dark';
    onCommand: (cmd: string, payload?: unknown) => void;
    onToast?: (level: string, text: string, actions?: unknown[],
               detail?: string, placement?: 'bottom' | 'top') => void;
    /** 本地图表：加到图表走 `local_add_indicator`（不带实时合约 ✓） */
    local?: boolean;
    /** 本地图表的 CSV 名（`local` 时用 ✓） */
    symbol?: () => string;
    /** 本地图表当前格号（多布局；`local` 时用 ✓） */
    cell?: () => number;
    /** 是否显示「策略实盘 / 停止实盘」（**实时图表**才有；本地图表隐藏 ✓） */
    allowLive?: boolean;
    /** 策略回测 / 参数优化入口（只在本地图表提供 ✓） */
    onBacktest?: (path: string) => void;
    onOptimize?: (path: string) => void;
    /** LSP 服务地址（后端起好后 app 传进来；undefined = 还没起来 ✓） */
    lsp?: () => { url: string; root: string } | undefined;
    /** 初始值：保存时自动格式化（设置 → 编辑器 ✓） */
    formatOnSave?: boolean;
}

/** 极简 Markdown → HTML（标题 / 粗斜体 / 行内码 / 代码块 / 列表 / 链接 / 分隔线 ✓） */
function renderMarkdown(source: string): string {
    const lines = String(source || '').replace(/\r\n?/g, '\n').split('\n');
    const out: string[] = [];
    let inCode = false;
    let listType = '';
    let inTable = false;
    let skipLines = 0;
    let cursor = 0;
    const inline = (text: string) => esc(text)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
        .replace(/(^|[^*])\*([^*]+)\*/g, '$1<i>$2</i>')
        .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g,
                 '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
    const closeList = () => {
        if (listType) {
            out.push(listType === 'ol' ? '</ol>' : '</ul>');
            listType = '';
        }
    };
    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index];
        cursor = index;
        if (skipLines > 0) {           // 表格已整块输出 → 跳过后续行 ✓
            skipLines -= 1;
            continue;
        }
        if (line.trim().startsWith('```')) {
            if (inCode) {
                out.push('</code></pre>');
                inCode = false;
            } else {
                closeList();
                out.push('<pre><code>');
                inCode = true;
            }
            continue;
        }
        if (inCode) {
            out.push(`${esc(line)}\n`);
            continue;
        }
        const heading = /^(#{1,6})\s+(.*)$/.exec(line);
        if (heading) {
            closeList();
            const level = heading[1].length;
            out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
            continue;
        }
        if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
            closeList();
            out.push('<hr/>');
            continue;
        }
        const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);
        const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
        if (ordered || bullet) {
            const want = ordered ? 'ol' : 'ul';
            if (listType !== want) {
                closeList();
                out.push(want === 'ol' ? '<ol>' : '<ul>');
                listType = want;
            }
            const text = (ordered || bullet || ['', ''])[1];
            out.push(`<li>${inline(text)}</li>`);
            continue;
        }
        if (!line.trim()) {
            closeList();
            out.push('');
            continue;
        }
        // ★ 表格（GFM）：`| a | b |` + `|---|---|` → `<table>`（用户实测
        //   md 预览里表格被当成普通段落 ✗）
        if (/^\s*\|.*\|\s*$/.test(line) && !inTable) {
            const rows: string[] = [];
            let index = lines.indexOf(line, cursor);
            const start = index < 0 ? 0 : index;
            for (let k = start; k < lines.length; k += 1) {
                if (!/^\s*\|.*\|\s*$/.test(lines[k])) break;
                rows.push(lines[k]);
            }
            const parsed = rows.map((row) => row.trim()
                .replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim()));
            const isDivider = (cells: string[]) => cells.every(
                (cell) => /^:?-{2,}:?$/.test(cell));
            if (parsed.length >= 2 && isDivider(parsed[1])) {
                closeList();
                const head = parsed[0].map((cell) => `<th>${inline(cell)}</th>`);
                const body = parsed.slice(2)
                    .filter((cells) => !isDivider(cells))
                    .map((cells) => '<tr>'
                        + cells.map((cell) => `<td>${inline(cell)}</td>`).join('')
                        + '</tr>');
                out.push('<table><thead><tr>' + head.join('') + '</tr></thead>'
                    + '<tbody>' + body.join('') + '</tbody></table>');
                skipLines = rows.length - 1;
                continue;
            }
        }
        out.push(`<p>${inline(line)}</p>`);
    }
    closeList();
    if (inCode) out.push('</code></pre>');
    return out.join('\n');
}

function esc(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch] || ch));
}

const STYLE_ID = 'desk-editor-style';

const CSS = `
.desk-editor { flex: 1 1 auto; display: flex; min-height: 0; height: 100%; }
.desk-editor-side { flex: 0 0 220px; display: flex; flex-direction: column;
    min-height: 0; border-right: 1px solid var(--desk-border); }
.desk-editor-sidehead { flex: 0 0 auto; display: flex; align-items: center;
    gap: 4px; padding: 4px 6px; font-size: 10.5px; letter-spacing: .4px;
    color: var(--desk-muted); border-bottom: 1px solid var(--desk-border); }
.desk-editor-sidehead .grow { flex: 1 1 auto; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
.desk-editor-tree { flex: 1 1 auto; overflow: auto; padding: 2px 0 8px; }
.desk-editor-node { display: flex; align-items: center; gap: 4px;
    padding: 3px 6px; font-size: 12px; cursor: pointer; user-select: none;
    white-space: nowrap; }
.desk-editor-node:hover { background: var(--desk-hover); }
.desk-editor-node.on { background: var(--desk-active);
    color: var(--desk-accent); }
.desk-editor-node .twist { width: 12px; flex: 0 0 auto; opacity: .7;
    font-size: 10px; }
.desk-editor-node .name { flex: 1 1 auto; overflow: hidden;
    text-overflow: ellipsis; }
.desk-editor-node .dirty { color: var(--desk-up); }
.desk-editor-node .ico { flex: 0 0 auto; opacity: .8; }
.desk-editor-main { flex: 1 1 auto; display: flex; flex-direction: column;
    min-width: 0; min-height: 0; }
.desk-editor-toolbar { flex: 0 0 auto; display: flex; align-items: center;
    gap: 4px; padding: 4px 8px; border-bottom: 1px solid var(--desk-border);
    background: var(--desk-panel); overflow-x: auto; }
.desk-editor-tabs { display: flex; align-items: center; gap: 2px;
    overflow-x: auto; flex: 1 1 auto;
    /* ★ 文件多了不显示滚动条，但**鼠标滚轮**能横向翻（用户要求 ✓） */
    scrollbar-width: none; -ms-overflow-style: none; }
.desk-editor-tabs::-webkit-scrollbar { height: 0; width: 0; }
.desk-editor-tab { display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;
    /* 未选中：灰底、无描边 ✓ */
    background: var(--desk-hover); color: var(--desk-muted);
    border: 1px solid transparent; white-space: nowrap; }
/* 选中：**主题色描边**（和未保存时「保存」按钮同款 ✓） */
.desk-editor-tab.on {
    background: var(--desk-active); color: var(--desk-accent);
    border-color: var(--desk-accent);
}
.desk-editor-tab .x { opacity: .6; }
.desk-editor-tab .x:hover { opacity: 1; }
.desk-editor-host { flex: 1 1 auto; min-height: 0; overflow: hidden;
    display: flex; }
.desk-editor-host > div { flex: 1 1 auto; min-height: 0; min-width: 0;
    display: flex; }
.desk-editor-host .cm-editor { height: 100%; flex: 1 1 auto; min-height: 0; }
/* 代码长了要能滚动（以前 overflow:hidden 把后面的代码剪掉了 ✗） */
.desk-editor-host .cm-scroller { overflow: auto; }

/* ------------------------------------------------------------------ 悬停提示
   对齐 VS Code：限定宽度 / 高度，**内容可滚动**（以前文档一长就超出
   底部面板被裁掉、还滚不动 ✗），等宽字体 + 更紧凑的标题。 */
.desk-editor-host .cm-tooltip {
    max-width: min(680px, 62vw);
    padding: 0;
    border: 1px solid var(--desk-border);
    border-radius: 6px;
    background: var(--desk-panel);
    box-shadow: 0 10px 28px rgba(0, 0, 0, .30);
    overflow: hidden;
    pointer-events: auto;
    z-index: 40;
}
.desk-editor-host .cm-tooltip-hover {
    max-height: min(420px, 52vh);
    overflow-y: auto;                 /* ★ 可以滚轮翻看完整文档 ✓ */
    overscroll-behavior: contain;
}
.desk-editor-host .cm-tooltip-hover::-webkit-scrollbar { width: 8px; }
.desk-editor-host .cm-tooltip-hover::-webkit-scrollbar-thumb {
    background: var(--desk-border); border-radius: 4px;
}
.desk-editor-host .cm-tooltip .documentation {
    padding: 8px 11px;
    max-width: 100%;
    color: var(--desk-text);
    font-family: Consolas, "Cascadia Mono", Menlo, monospace;
    font-size: 11.5px;
    line-height: 1.6;
    word-break: break-word;
}
.desk-editor-host .cm-tooltip .documentation p { margin: 4px 0; }
.desk-editor-host .cm-tooltip .documentation h1,
.desk-editor-host .cm-tooltip .documentation h2,
.desk-editor-host .cm-tooltip .documentation h3,
.desk-editor-host .cm-tooltip .documentation h4 {
    margin: 8px 0 4px; font-size: 12px; font-weight: 700;
}
.desk-editor-host .cm-tooltip .documentation ul,
.desk-editor-host .cm-tooltip .documentation ol {
    margin: 4px 0 4px 18px; padding: 0;
}
.desk-editor-host .cm-tooltip .documentation li { margin: 1px 0; }
.desk-editor-host .cm-tooltip .documentation pre {
    margin: 6px 0; padding: 7px 9px; border-radius: 5px;
    background: var(--desk-bg); border: 1px solid var(--desk-border);
    overflow-x: auto; font-size: 11px; line-height: 1.5;
}
.desk-editor-host .cm-tooltip .documentation code {
    padding: 0 3px; border-radius: 3px; background: var(--desk-hover);
    font-family: inherit; font-size: 11px;
}
.desk-editor-host .cm-tooltip .documentation pre code {
    background: transparent; padding: 0;
}
.desk-editor-host .cm-tooltip .documentation a { color: var(--desk-accent); }
.desk-editor-host .cm-tooltip .documentation hr {
    border: 0; border-top: 1px solid var(--desk-border); margin: 8px 0;
}
.desk-editor-host .cm-tooltip .documentation table {
    border-collapse: collapse; font-size: 11px;
}
.desk-editor-host .cm-tooltip .documentation th,
.desk-editor-host .cm-tooltip .documentation td {
    border: 1px solid var(--desk-border); padding: 2px 6px;
}
.desk-editor-status { flex: 0 0 auto; padding: 2px 8px; font-size: 11px;
    color: var(--desk-muted); border-top: 1px solid var(--desk-border);
    display: flex; gap: 12px; align-items: center; }
.desk-editor-status .err { color: var(--desk-up); }
.desk-editor-status .ok { color: var(--desk-down); }
.desk-editor-empty { color: var(--desk-muted); font-size: 11.5px;
    padding: 10px 12px; }
.desk-editor-btn { height: 22px; padding: 0 8px; border-radius: 4px;
    border: 1px solid var(--desk-border); background: transparent;
    color: var(--desk-text); font-size: 11.5px; cursor: pointer;
    display: inline-flex; align-items: center; gap: 3px; white-space: nowrap; }
.desk-editor-btn:hover { background: var(--desk-hover); }
.desk-editor-btn.on { border-color: var(--desk-accent); color: var(--desk-accent); }
.desk-editor-btn:disabled { opacity: .4; cursor: default; }
`;

interface OpenTab {
    path: string;
    name: string;
    kind: 'indicator' | 'strategy' | 'file';
    text: string;
    saved: string;
    editor: CodeEditor;
    button: HTMLButtonElement;
}

/** 找到 `params = dict(` 的**配对右括号**（支持嵌套 dict / tuple / 字符串）

以前用 `/params\s*=\s*dict\s*\([^)]*\)/`，遇到
`params = dict(fast=(5, 20), nested={'a': (1, 2)})` 会在第一个 `)` 截断，
把文件写坏 ✗。这里做括号配对 + 字符串/注释跳过。
*/
function replaceParamsDict(text: string, replacement: string): string | null {
    const match = /params\s*=\s*dict\s*\(/m.exec(text);
    if (!match) return null;
    let index = match.index + match[0].length;
    let depth = 1;
    let quote = '';
    let escaped = false;
    for (; index < text.length; index += 1) {
        const ch = text[index];
        if (quote) {
            if (escaped) { escaped = false; continue; }
            if (ch === '\\') { escaped = true; continue; }
            if (ch === quote) quote = '';
            continue;
        }
        if (ch === "'" || ch === '"') { quote = ch; continue; }
        if (ch === '#') {
            while (index < text.length && text[index] !== '\n') index += 1;
            continue;
        }
        if (ch === '(') depth += 1;
        else if (ch === ')') {
            depth -= 1;
            if (depth === 0) {
                return text.slice(0, match.index) + replacement
                    + text.slice(index + 1);
            }
        }
    }
    return null;
}

export class EditorPanel {
    readonly element: HTMLDivElement;
    private readonly sideHead: HTMLDivElement;
    private readonly tree: HTMLDivElement;
    private readonly tabs: HTMLDivElement;
    private readonly host: HTMLDivElement;
    private readonly status: HTMLDivElement;
    private readonly saveButton: HTMLButtonElement;
    private readonly checkButton: HTMLButtonElement;
    private readonly formatButton: HTMLButtonElement;
    private readonly addButton: HTMLButtonElement;
    private readonly backtestButton: HTMLButtonElement;
    private readonly optimizeButton: HTMLButtonElement;
    private readonly refreshPersonalButton: HTMLButtonElement;
    private readonly options: EditorPanelOptions;
    private readonly open = new Map<string, OpenTab>();
    /** `path → 子项`（展开过的目录缓存 ✓） */
    private readonly children = new Map<string, ExplorerItem[]>();
    private readonly expanded = new Set<string>();
    /** 大纲（文档符号）容器 ✓ */
    private readonly outline: HTMLDivElement;
    private readonly outlineHead: HTMLDivElement;
    /** Markdown 预览（只有 .md 才显示 ✓） */
    private previewPane: HTMLDivElement | null = null;
    private previewButton: HTMLButtonElement | null = null;
    private previewOn = false;
    /** 保存时自动格式化（设置里可开关 ✓） */
    private formatOnSave = false;
    /** 工作区符号搜索（跨文件 ✓） */
    private symbolButton: HTMLButtonElement | null = null;
    private symbolBox: HTMLDivElement | null = null;
    private symbolTimer: number | undefined;
    private previewTimer: number | undefined;
    /** 和磁盘版本对比（`@codemirror/merge` ✓） */
    private diffButton: HTMLButtonElement | null = null;
    private diffPane: HTMLDivElement | null = null;
    private diffOn = false;
    /** 等待后端体检的「回测 / 参数优化」请求（id → 动作 ✓） */
    private readonly pendingStrategy = new Map<string,
        { path: string; mode: 'backtest' | 'optimize' }>();
    private liveButton: HTMLButtonElement | null = null;
    private stopLiveButton: HTMLButtonElement | null = null;
    private root = '';
    private activePath = '';
    private activeDir = '';
    private mounted = false;
    /** 「刷新指标策略」是否可用（当前目录 = 我的脚本 / 我的策略 ✓） */
    private personalKind: 'indicator' | 'strategy' | '' = '';

    constructor(options: EditorPanelOptions) {
        this.options = options;
        this.formatOnSave = !!options.formatOnSave;
        this._ensureStyle();
        this.element = document.createElement('div');
        this.element.className = 'desk-editor';
        this.element.style.position = 'relative';

        // ---- 左侧资源管理器 ---------------------------------------------
        const side = document.createElement('div');
        side.className = 'desk-editor-side';
        this.sideHead = document.createElement('div');
        this.sideHead.className = 'desk-editor-sidehead';
        this.tree = document.createElement('div');
        this.tree.className = 'desk-editor-tree';
        // ★ 大纲（文档符号）：只有 .py 才有（jedi 的 documentSymbol ✓）
        this.outlineHead = document.createElement('div');
        this.outlineHead.className = 'desk-editor-sidehead desk-editor-outline-head';
        this.outlineHead.textContent = '大纲';
        this.outline = document.createElement('div');
        this.outline.className = 'desk-editor-outline';
        // 大纲点击 → 跳到对应行 ✓
        this.symbolBox?.addEventListener('click', (event) => {
            const item = (event.target as HTMLElement).closest<HTMLElement>(
                '[data-symbol-path]');
            if (!item) return;
            const target = String(item.dataset.symbolPath || '');
            const line = Number(item.dataset.symbolLine || 0);
            if (this.symbolBox) this.symbolBox.style.display = 'none';
            this.options.onCommand('editor_open', { path: target });
            // 等文件打开 + 编辑器挂载后再跳行 ✓
            window.setTimeout(() => {
                const tab = this.open.get(target);
                const handle = tab?.editor.handle as unknown as {
                    jumpToLine?: (value: number) => void;
                } | null;
                handle?.jumpToLine?.(line);
            }, 900);
        });
        this.outline.addEventListener('click', (event) => {
            const item = (event.target as HTMLElement).closest<HTMLElement>(
                '[data-outline-line]');
            if (!item) return;
            const current = this.open.get(this.activePath);
            const handle = current?.editor.handle as unknown as {
                jumpToLine?: (line: number) => void;
            } | null;
            handle?.jumpToLine?.(Number(item.dataset.outlineLine || 0));
        });
        side.append(this.sideHead, this.tree, this.outlineHead, this.outline);

        // ---- 右侧编辑区 -------------------------------------------------
        const main = document.createElement('div');
        main.className = 'desk-editor-main';
        const toolbar = document.createElement('div');
        toolbar.className = 'desk-editor-toolbar';
        // ① 「系统目录 ▾」放最左边：系统个人指标 / 系统个人策略（用户要求 ✓）
        const folderButton = this._button('系统目录 ▾', (button) => {
            showMenuBelow(button, [
                // ★ 第一项：整个 personal 根目录（indicators + strategies 都在里面 ✓）
                { label: '系统指标和策略（personal）',
                  run: () => this.options.onCommand(
                      'explorer_system_dir', { kind: 'all' }) },
                { label: '系统个人指标（personal/indicators）',
                  run: () => this.options.onCommand(
                      'explorer_system_dir', { kind: 'indicator' }) },
                { label: '系统个人策略（personal/strategies）',
                  run: () => this.options.onCommand(
                      'explorer_system_dir', { kind: 'strategy' }) },
                { label: '', separator: true },
                { label: '其它目录…', run: () => this.options.onCommand(
                    'explorer_pick', {}) },
            ]);
        });
        const newButton = this._button('新建 ▾', (button) => {
            showMenuBelow(button, [
                { label: '新建文件…', run: () => this._newEntry('new_file') },
                { label: '新建文件夹…', run: () => this._newEntry('new_folder') },
                { label: '指标模板（BtIndicator）', separator: true,
                  run: () => this._newPersonal('indicator') },
                { label: '策略模板（Strategy）',
                  run: () => this._newPersonal('strategy') },
            ]);
        });
        this.saveButton = this._button('保存', () => this._save());
        this.saveButton.innerHTML = `${ICON_PENCIL}<span>保存</span>`;
        this.checkButton = this._button('语法检查', () => this._check());
        this.formatButton = this._button('格式化', () => this._format());
        this.addButton = this._button('加到图表', () => this._addToChart());
        this.backtestButton = this._button('策略回测', () => this._strategyAction('backtest'));
        this.optimizeButton = this._button('参数优化', () => this._strategyAction('optimize'));
        this.backtestButton.title = '用当前策略文件跑回测（独立策略 Tab）';
        this.optimizeButton.title = '用当前策略文件跑参数优化（独立策略 Tab）';
        if (!this.options.onBacktest && !this.options.onOptimize) {
            this.backtestButton.style.display = 'none';
            this.optimizeButton.style.display = 'none';
        }
        // ★ 「策略实盘 / 模拟盘」：把当前策略文件**常驻运行**
        //   （`Bt(live=True)` + 快期模拟账号 → 真下单 ✓）
        //   「加到图表」只是图上回放（跑完就停），要连续交易点这里 ✓
        this.liveButton = this._button('策略实盘', () => {
            const path = this.activePath;
            if (!path) {
                this._toastTop('warning', '先打开一个策略文件');
                return;
            }
            // ★ 策略实盘会**真下单**（模拟号也会）；启动前必须人工确认 ✓
            const ok = window.confirm(
                '策略实盘会把当前文件常驻运行，并按账户页当前选择'
                + '（快期模拟 / 实盘）真实下单。\n\n确认启动？');
            if (!ok) return;
            this.options.onCommand('strategy_live_start',
                                   { file: path, confirm: true });
        });
        this.liveButton.title = '把当前策略常驻运行（天勤模拟号 / 实盘会真的下单）';
        this.liveButton.classList.add('desk-editor-live');
        this.stopLiveButton = this._button('停止实盘', () => {
            this.options.onCommand('strategy_live_stop', {});
        });
        this.stopLiveButton.title = '停止正在运行的策略实盘';
        // ★ 本地图表是离线 CSV → 策略实盘 / 停止都隐藏；
        //   实时图表 → 两个按钮都显示（停止在未运行时禁用）✓
        const allowLive = this.options.allowLive !== false;
        this.liveButton.style.display = allowLive ? '' : 'none';
        this.stopLiveButton.style.display = allowLive ? '' : 'none';
        this.stopLiveButton.disabled = true;
        const removeButton = this._button('', () => this._removeFile());
        removeButton.innerHTML = ICON_TRASH;
        removeButton.title = '删除当前文件';
        const refreshButton = this._button('', () => this._refreshAll());
        refreshButton.innerHTML = ICON_REFRESH;
        refreshButton.title = '刷新资源管理器';
        // 「刷新指标策略」按用户要求删掉：
        // 个人指标 / 策略在打开「更多指标和策略」时才按目录扫描 ✓
        this.refreshPersonalButton = this._button('', () => undefined);
        this.refreshPersonalButton.style.display = 'none';
        const shotButton = this._button('', () => this._copyAll());
        shotButton.innerHTML = ICON_COPY;          // 复制图标（以前是相机 ✗）
        shotButton.title = '复制全部代码到剪贴板';
        // 「帮助」放**最右边**（和 MiniQT 编辑器的帮助按钮一致 ✓）
        const helpButton = this._button('帮助', () => {
            this.options.onCommand('editor_help', {});
        });
        helpButton.title = '帮助（环境配置指引）';
        helpButton.classList.add('desk-editor-help');
        this.tabs = document.createElement('div');
        this.tabs.className = 'desk-editor-tabs';
        // ★ 鼠标滚轮 → **横向翻页**（竖向滚轮也认；文件多了不用拖滚动条 ✓）
        this.tabs.addEventListener('wheel', (event) => {
            const host = this.tabs as HTMLDivElement;
            if (host.scrollWidth <= host.clientWidth) return;
            const delta = event.deltaY || event.deltaX;
            if (!delta) return;
            event.preventDefault();
            host.scrollLeft += delta;
        }, { passive: false });
        toolbar.append(folderButton, newButton, this.saveButton,
                       this.checkButton, this.formatButton, this.addButton,
                       this.backtestButton, this.optimizeButton,
                       this.liveButton, this.stopLiveButton,
                       removeButton, refreshButton, shotButton, this.tabs,
                       helpButton);

        this.symbolButton = this._button('符号', () => this._toggleSymbols());
        this.symbolButton.title = '工作区符号搜索（跨文件 class / def，Ctrl+T）';
        this.symbolButton.style.display = 'none';
        toolbar.appendChild(this.symbolButton);
        this.symbolBox = document.createElement('div');
        this.symbolBox.className = 'desk-editor-symbols';
        this.symbolBox.style.display = 'none';
        this.diffButton = this._button('对比', () => this._toggleDiff());
        this.diffButton.title = '和磁盘上的版本对比（未保存的改动）';
        this.diffButton.style.display = 'none';
        toolbar.appendChild(this.diffButton);
        this.diffPane = document.createElement('div');
        this.diffPane.className = 'desk-editor-diff';
        this.diffPane.style.display = 'none';
        this.previewButton = this._button('预览', () => {
            this.previewOn = !this.previewOn;
            this._syncPreview();
        });
        this.previewButton.title = 'Markdown 预览（Ctrl+Shift+V）';
        this.previewButton.style.display = 'none';
        toolbar.appendChild(this.previewButton);
        this.previewPane = document.createElement('div');
        this.previewPane.className = 'desk-editor-preview';
        this.previewPane.style.display = 'none';
        this.host = document.createElement('div');
        this.host.className = 'desk-editor-host';
        this.status = document.createElement('div');
        this.status.className = 'desk-editor-status';
        this._writeStatus('选择左侧文件开始编辑（Ctrl+S 保存）');
        const body = document.createElement('div');
        body.className = 'desk-editor-body';
        body.append(this.host);
        if (this.previewPane) body.appendChild(this.previewPane);
        if (this.diffPane) body.appendChild(this.diffPane);
        main.append(toolbar, body, this.status);
        this.element.append(side, main);

        // 编辑器区域的右键菜单（添加到图表 / 格式化 / 语法检测 / 剪切 / 复制…）
        this.host.addEventListener('contextmenu', (event) => {
            if (!this.activePath) return;
            event.preventDefault();
            this._editorMenu(event.clientX, event.clientY);
        });
        this._renderEmpty('正在读取目录…');
        // ★ 资源管理器**空白处**右键：新建文件 / 新建文件夹（用户要求 ✓）
        this.tree.addEventListener('contextmenu', (event) => {
            if ((event.target as HTMLElement).closest('.desk-editor-node')) {
                return;                    // 点在文件 / 文件夹上 → 用那一行的菜单
            }
            event.preventDefault();
            const base = this.activeDir || this.root;
            showMenuBelow(this._anchor(event.clientX, event.clientY), [
                { label: '新建文件…', run: () => this._newEntryAt('new_file', base) },
                { label: '新建文件夹…',
                  run: () => this._newEntryAt('new_folder', base) },
                { label: '', separator: true },
                { label: '刷新', run: () => this._refreshAll() },
            ]);
        });
        void ICON_ERASER;
    }

    // ------------------------------------------------------------ 生命周期
    show(): void {
        this.element.style.display = 'flex';
        if (!this.mounted) {
            this.mounted = true;
            this.options.onCommand('explorer_list', {});
            // ★ 恢复**上次打开的文件**（资源管理器根目录后端已按
            //   `settings.explorer_root` 恢复 ✓）——只在第一次显示时做，
            //   文件不在了后端会静默忽略 ✓
            this.options.onCommand('editor_restore', {});
        }
        this._activeEditor()?.focus();
    }

    hide(): void {
        this.element.style.display = 'none';
    }

    setTheme(theme: 'light' | 'dark'): void {
        this.options.theme = theme;
        for (const tab of this.open.values()) tab.editor.setTheme(theme);
    }

    // ------------------------------------------------------------ 后端补丁
    /** `{type:'explorer'}` → 目录内容 ✓ */
    setExplorer(data: ExplorerData): void {
        if (!data || !data.ok) {
            this._renderEmpty(data?.error || '读取目录失败');
            return;
        }
        this.root = data.root || this.root;
        const path = data.path || this.root;
        this.children.set(path, data.items || []);
        if (path !== this.root) this.expanded.add(path);
        if (!this.activeDir) this.activeDir = path;
        // 后端有时只推**子目录**（比如新建文件后推父目录）→ 根目录列表还没拿到
        // 就补一次请求，否则树是空的 ✗
        if (!this.children.has(this.root)) {
            this.options.onCommand('explorer_list', { path: this.root });
        }
        this._renderTree();
        // 根目录一变就查一次：是不是「我的脚本 / 我的策略」目录 ✓
        if (path === this.root) this._syncPersonal(this.root);
        this.sideHead.title = this.personalKind
            ? '当前目录是「我的脚本 / 我的策略」' : '';
    }

    /** `{type:'editor_file'}` → 打开 / 切换标签 ✓ */
    setFile(file: { path?: string; name?: string; kind?: string;
                    text?: string; new?: boolean }): void {
        const path = String(file.path || '');
        if (!path) return;
        if (this.open.has(path)) {
            this._activate(path);
            return;
        }
        const name = String(file.name || path.split(/[\\/]/).pop() || '');
        const text = String(file.text || '');
        const kind = file.kind === 'strategy'
            || /class\s+\w+\s*\([^)]*Strategy[^)]*\)/.test(text)
            ? 'strategy'
            : (file.kind === 'indicator' ? 'indicator' : 'file');
        const editor = new CodeEditor({
            parent: document.createElement('div'),
            value: text,
            theme: this.options.theme,
            // ★ 绝对路径 + LSP 地址：补全 / 悬停 / 跳转 / 语法浪线都靠它 ✓
            path,
            lsp: this.options.lsp?.(),
            onLspStatus: (statusText, level) => this._setLspStatus(
                statusText, level),
            // 跨文件 F12 / Ctrl+点击：打开目标文件再跳行 ✓
            onOpenLocation: (targetPath, line) => this._openAt(targetPath,
                                                               line),
            onCursor: (line, column) => this._setCursor(line, column),
            onChange: (value) => this._onChange(path, value),
            onSave: () => this._save(),
        });
        const button = document.createElement('button');
        button.className = 'desk-editor-tab';
        const label = document.createElement('span');
        label.textContent = name;
        const close = document.createElement('span');
        close.className = 'x';
        close.textContent = '×';
        close.addEventListener('click', (event) => {
            event.stopPropagation();
            this._closeTab(path);
        });
        button.append(label, close);
        button.addEventListener('click', () => this._activate(path));
        this.tabs.appendChild(button);
        this.open.set(path, { path, name, kind, text, saved: text, editor,
            button });
        this.activeDir = path.replace(/[\\/][^\\/]*$/, '');
        this._activate(path);
    }

    markSaved(path: string, text?: string): void {
        const tab = this.open.get(String(path || ''));
        if (!tab) return;
        if (text !== undefined) tab.text = text;
        tab.saved = tab.text;
        this._renderTabs();
    }

    setCheck(path: string, result: EditorCheckResult): void {
        const tab = this.open.get(String(path || ''));
        if (!tab) return;
        this._writeStatus('');
        if (result?.ok) {
            const ok = document.createElement('span');
            ok.className = 'ok';
            ok.textContent = '语法 OK';
            this.status.append(ok);
            const names = (result.defines || [])
                .map((item) => `${item.name}（${item.kind}）`).join('、');
            if (names) {
                const about = document.createElement('span');
                about.textContent = `定义：${names}`;
                this.status.appendChild(about);
            }
        } else {
            const bad = document.createElement('span');
            bad.className = 'err';
            bad.textContent = `第 ${result?.line || 0} 行：`
                + `${result?.error || '语法错误'}`;
            this.status.appendChild(bad);
        }
    }

    /** `{type:'editor_formatted'}` → 换掉编辑器内容 ✓ */
    setFormatted(path: string, text: string, tool: string): void {
        const tab = this.open.get(String(path || ''));
        if (!tab) return;
        // Ctrl+S / 保存按钮：后端会把同一份 text 回推一次。
        // 内容没变就不要 setValue —— 整篇 replace 会让编辑器跳回顶部 ✗。
        if (tab.text !== text) {
            tab.editor.setValue(text);
            tab.text = text;
        }
        if (tool === 'save') tab.saved = text;
        this._renderTabs();
        this._writeStatus(tool === 'save' ? '已保存' : `已格式化（${tool}）`);
    }

    remove(path: string): void {
        this._closeTab(String(path || ''), true);
    }

    /** 目录是不是「我的脚本 / 我的策略」（只在状态栏提示，不再有按钮 ✓） */
    setPersonalKind(kind: 'indicator' | 'strategy' | ''): void {
        this.personalKind = kind;
        if (kind) {
            this._writeStatus('当前目录是「'
                + (kind === 'indicator' ? '我的脚本' : '我的策略')
                + '」—— 保存后打开「更多指标和策略」即可看到');
        }
    }

    // ------------------------------------------------------------ 文件树
    private _renderEmpty(text: string): void {
        this.tree.textContent = '';
        const empty = document.createElement('div');
        empty.className = 'desk-editor-empty';
        empty.textContent = text;
        this.tree.appendChild(empty);
    }

    private _renderTree(): void {
        this.sideHead.textContent = '';
        const title = document.createElement('span');
        title.className = 'grow';
        title.textContent = this.root ? this.root.split(/[\\/]/).pop() || 'ROOT'
            : '资源管理器';
        title.title = this.root;
        const openBtn = document.createElement('button');
        openBtn.className = 'desk-editor-btn';
        openBtn.textContent = '打开';
        openBtn.title = '选择文件夹作为根目录';
        openBtn.addEventListener('click', () => {
            // ★ 一律弹**系统**文件夹框（后端 `choose_directory`：
            //   Qt 原生 / tkinter 兜底），用户不用手输路径 ✓
            this.options.onCommand('explorer_pick', {});
        });
        const newBtn = document.createElement('button');
        newBtn.className = 'desk-editor-btn';
        newBtn.textContent = '＋';
        newBtn.title = '新建文件 / 文件夹';
        newBtn.addEventListener('click', () => showMenuBelow(newBtn, [
            { label: '新建文件…', run: () => this._newEntry('new_file') },
            { label: '新建文件夹…', run: () => this._newEntry('new_folder') },
        ]));
        const refreshBtn = document.createElement('button');
        refreshBtn.className = 'desk-editor-btn';
        refreshBtn.textContent = '⟳';
        refreshBtn.title = '刷新';
        refreshBtn.addEventListener('click', () => this._refreshAll());
        // 「个人指标策略管理」：查看 / 删除已导入的目录（默认目录不显示 ✓）
        const manageBtn = document.createElement('button');
        manageBtn.className = 'desk-editor-btn';
        manageBtn.textContent = '⚙';
        manageBtn.title = '个人指标策略管理（查看 / 删除已导入的目录）';
        manageBtn.addEventListener('click', () => this._refreshPersonal());
        this.sideHead.append(title, openBtn, newBtn, refreshBtn, manageBtn);
        this.sideHead.title = this.personalKind
            ? '当前目录是「我的脚本 / 我的策略」' : '';

        this.tree.textContent = '';
        if (!this.root) {
            this._renderEmpty('点「打开目录」选择文件夹');
            return;
        }
        const items = this.children.get(this.root) || [];
        if (!items.length) {
            this._renderEmpty('（空目录 —— 点「＋」新建文件）');
        }
        for (const item of items) this._renderNode(item, 0);
    }

    private _renderNode(item: ExplorerItem, depth: number): void {
        const row = document.createElement('div');
        row.className = 'desk-editor-node'
            + (item.path === this.activePath ? ' on' : '');
        row.style.paddingLeft = `${6 + depth * 12}px`;
        const twist = document.createElement('span');
        twist.className = 'twist';
        if (item.dir) {
            twist.textContent = this.expanded.has(item.path) ? '▾' : '▸';
        }
        const ico = document.createElement('span');
        ico.className = 'ico';
        ico.textContent = item.dir ? '📁' : (item.py ? '🐍'
            : (item.text ? '📝' : '📄'));
        const name = document.createElement('span');
        name.className = 'name';
        name.textContent = item.name;
        name.title = item.path;
        row.append(twist, ico, name);
        const tab = this.open.get(item.path);
        if (tab && tab.text !== tab.saved) {
            const dirty = document.createElement('span');
            dirty.className = 'dirty';
            dirty.textContent = '●';
            row.appendChild(dirty);
        }
        row.addEventListener('click', () => {
            this.activeDir = item.dir ? item.path : item.path.replace(
                /[\\/][^\\/]*$/, '');
            if (item.dir) {
                this._toggleDir(item.path);
                this._syncPersonal(item.path);
            } else if (item.py || item.text) {
                this.options.onCommand('editor_open', { path: item.path });
                this._syncPersonal(this.activeDir);
            } else {
                this._writeStatus('只支持编辑文本类文件（.py / .md / .txt …）');
            }
            this._renderTree();
        });
        row.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            event.stopPropagation();
            this._nodeMenu(item, event.clientX, event.clientY);
        });
        this.tree.appendChild(row);
        if (item.dir && this.expanded.has(item.path)) {
            for (const child of this.children.get(item.path) || []) {
                this._renderNode(child, depth + 1);
            }
        }
    }

    private _toggleDir(path: string): void {
        if (this.expanded.has(path)) {
            this.expanded.delete(path);
            return;
        }
        this.expanded.add(path);
        this.options.onCommand('explorer_list', { path });
    }

    /** 目录对上「我的脚本 / 我的策略」→ 「刷新指标策略」可用 ✓ */
    private _syncPersonal(path: string): void {
        this.options.onCommand('explorer_check_personal', { path });
    }

    private _refreshAll(): void {
        this.children.clear();
        this.expanded.clear();
        this.options.onCommand('explorer_list', {});
    }

    /** 打开「个人指标策略管理」（后端推 `personal_menu` → 弹管理对话框 ✓） */
    private _refreshPersonal(): void {
        this.options.onCommand('personal_menu', {});
    }

    // ------------------------------------------------------------ 右键菜单
    private _nodeMenu(item: ExplorerItem, x: number, y: number): void {
        const items: MenuItem[] = [];
        if (!item.dir && item.py) {
            items.push({
                label: '打开', run: () => this.options.onCommand(
                    'editor_open', { path: item.path }),
            });
            items.push({
                label: '加到图表', run: () => {
                    // ★ 先打开文件（UX），但加图表必须用**右键这一项**的
                    //   path；`_addToChart()` 读 activePath 时 editor_open
                    //   还是异步的，会加成上一个文件 ✗
                    this.options.onCommand('editor_open',
                                           { path: item.path });
                    this._addToChart(item.path);
                },
            });
            items.push({ label: '', separator: true });
        }
        items.push({ label: '新建文件…',
                     run: () => this._newEntry('new_file', item) });
        items.push({ label: '新建文件夹…',
                     run: () => this._newEntry('new_folder', item) });
        items.push({ label: '', separator: true });
        items.push({
            label: '复制地址', run: () => this._copyPath(item.path),
        });
        items.push({ label: '', separator: true });
        items.push({
            label: '剪切', run: () => this.options.onCommand(
                'explorer_op', { action: 'cut', path: item.path }),
        });
        items.push({
            label: '复制', run: () => this.options.onCommand(
                'explorer_op', { action: 'copy', path: item.path }),
        });
        items.push({
            label: '粘贴', run: () => this.options.onCommand(
                'explorer_op',
                { action: 'paste', path: item.dir ? item.path : this.activeDir }),
        });
        items.push({ label: '', separator: true });
        items.push({
            label: '重命名…', run: () => {
                const name = window.prompt('新名字', item.name);
                if (!name) return;
                this.options.onCommand('explorer_op', {
                    action: 'rename', path: item.path, name,
                });
            },
        });
        items.push({
            label: '删除', run: () => {
                if (!window.confirm(`删除 ${item.name}？`)) return;
                this.options.onCommand('explorer_op', {
                    action: 'delete', path: item.path,
                });
            },
        });
        showMenuBelow(this._anchor(x, y), items);
    }

    private _editorMenu(x: number, y: number): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        const items: MenuItem[] = [
            { label: '添加到图表', run: () => this._addToChart() },
            { label: '格式化', run: () => this._format() },
            { label: '语法检测', run: () => this._check() },
            { label: '', separator: true },
            { label: '剪切', run: () => this._clipboard('cut') },
            { label: '复制', run: () => this._clipboard('copy') },
            { label: '粘贴', run: () => this._clipboard('paste') },
            { label: '全选', run: () => tab.editor.selectAll() },
            { label: '', separator: true },
            { label: '保存（Ctrl+S）', run: () => this._save() },
            { label: '复制全部代码', run: () => this._copyAll() },
        ];
        showMenuBelow(this._anchor(x, y), items);
    }

    /** 菜单需要一个锚点元素（`showMenuBelow` 是按元素定位的 ✓） */
    private _anchor(x: number, y: number): HTMLElement {
        const anchor = document.createElement('span');
        anchor.style.cssText = `position:fixed;left:${x}px;top:${y}px;`
            + 'width:0;height:0;';
        document.body.appendChild(anchor);
        window.setTimeout(() => anchor.remove(), 0);
        return anchor;
    }

    // ------------------------------------------------------------ 动作
    private _activeEditor(): CodeEditor | null {
        return this.open.get(this.activePath)?.editor || null;
    }

    private _renderTabs(): void {
        for (const [path, tab] of this.open) {
            tab.button.classList.toggle('on', path === this.activePath);
            const label = tab.button.firstElementChild as HTMLElement | null;
            if (label) {
                label.textContent = tab.text === tab.saved
                    ? tab.name : `${tab.name} ●`;
            }
        }
        if (this.root) this._renderTree();
        this._syncButtons();
    }

    /** 「符号」按钮：只在 Python 文件里出现（LSP 才有这个能力 ✓） */
    private _syncSymbolsButton(): void {
        const tab = this.open.get(this.activePath);
        const isPy = !!tab && /\.(py|pyi)$/i.test(tab.path || '');
        if (this.symbolButton) {
            this.symbolButton.style.display = isPy ? '' : 'none';
        }
        if (!isPy && this.symbolBox) this.symbolBox.style.display = 'none';
    }

    /** 打开 / 关闭符号搜索框 ✓ */
    private _toggleSymbols(): void {
        const box = this.symbolBox;
        if (!box) return;
        const show = box.style.display === 'none';
        box.style.display = show ? 'block' : 'none';
        if (!show) return;
        box.innerHTML = '<input class="desk-editor-symbol-input" '
            + 'placeholder="搜索 class / def（跨文件）…" />'
            + '<div class="desk-editor-symbol-list"></div>';
        const input = box.querySelector('input') as HTMLInputElement;
        input.addEventListener('input', () => {
            if (this.symbolTimer !== undefined) {
                window.clearTimeout(this.symbolTimer);
            }
            this.symbolTimer = window.setTimeout(
                () => this._searchSymbols(input.value), 250);
        });
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') box.style.display = 'none';
        });
        input.focus();
        this._searchSymbols('');
    }

    /** 跑一次工作区符号搜索并渲染结果 ✓ */
    private _searchSymbols(query: string): void {
        const box = this.symbolBox;
        const tab = this.open.get(this.activePath);
        const handle = tab?.editor.handle as unknown as {
            searchSymbols?: (q: string) => Promise<Array<{
                name: string; kind: number; path: string; line: number }>>;
        } | null;
        const list = box?.querySelector('.desk-editor-symbol-list') as
            HTMLElement | null;
        if (!list || !handle?.searchSymbols) return;
        handle.searchSymbols(query).then((items) => {
            if (!items || !items.length) {
                list.innerHTML = '<div class="desk-editor-symbol-empty">'
                    + '没有匹配的符号</div>';
                return;
            }
            list.innerHTML = items.slice(0, 60).map((item) => {
                const fileName = item.path.split(/[\/]/).pop() || '';
                return `<button class="desk-editor-symbol-item"
                    data-symbol-path="${esc(item.path)}"
                    data-symbol-line="${item.line}"
                    title="${esc(item.path)}:${item.line + 1}"
                ><b>${item.kind === 5 ? 'C' : 'ƒ'}</b>
                <span>${esc(item.name)}</span>
                <em>${esc(fileName)}:${item.line + 1}</em></button>`;
            }).join('');
        }).catch(() => {
            list.innerHTML = '<div class="desk-editor-symbol-empty">搜索失败</div>';
        });
    }

    /** 打开 / 关闭「和磁盘版本对比」（在编辑器下方铺一块 MergeView ✓） */
    private _toggleDiff(): void {
        const tab = this.open.get(this.activePath);
        if (!tab || !this.diffPane) return;
        this.diffOn = !this.diffOn;
        if (!this.diffOn) {
            this.diffPane.style.display = 'none';
            this.diffPane.innerHTML = '';
            return;
        }
        this.diffPane.style.display = '';
        import('@codemirror/merge').then(({ MergeView }) => {
            this.diffPane!.innerHTML = '';
            const host = document.createElement('div');
            host.className = 'desk-editor-diff-host';
            this.diffPane!.appendChild(host);
            new MergeView({
                a: { doc: tab.saved || '', extensions: [] },
                b: { doc: tab.text || '', extensions: [] },
                parent: host,
                highlightChanges: true,
                gutter: true,
                collapseUnchanged: { margin: 3, minSize: 4 },
            });
            this._writeStatus('左：磁盘版本　右：当前编辑（只读对比 ✓）');
        }).catch(() => {
            this.diffPane!.innerHTML = '<div class="desk-editor-empty">'
                + '对比视图不可用</div>';
        });
    }

    /** 打开另一个文件并跳到某一行（F12 / 符号搜索 / Ctrl+点击 ✓） */
    private _openAt(path: string, line: number): void {
        const target = String(path || '');
        if (!target) return;
        if (!this.open.has(target)) {
            this.options.onCommand('editor_open', { path: target });
        }
        window.setTimeout(() => {
            this._activate(target);
            window.setTimeout(() => {
                (this.open.get(target)?.editor.handle as unknown as {
                    jumpToLine?: (value: number) => void;
                } | null)?.jumpToLine?.(line);
            }, 250);
        }, this.open.has(target) ? 0 : 900);
    }

    /** 状态栏：行 / 列 ✓ */
    private _setCursor(line: number, column: number): void {
        const node = this.element.querySelector('[data-cursor]') as HTMLElement
            | null;
        if (!node) return;
        node.textContent = `行 ${line}，列 ${column}`;
    }

    /** 是否 Markdown 文件（决定「预览」按钮显不显示 ✓） */
    private _isMarkdown(path: string): boolean {
        return /\.(md|markdown)$/i.test(String(path || ''));
    }

    /** 预览开关 / 内容同步（只有 .md 用 ✓） */
    private _syncPreview(): void {
        const tab = this.open.get(this.activePath);
        const isMarkdown = !!tab && this._isMarkdown(tab.path);
        if (this.previewButton) {
            this.previewButton.style.display = isMarkdown ? '' : 'none';
            this.previewButton.classList.toggle('on', isMarkdown
                && this.previewOn);
        }
        if (!this.previewPane) return;
        if (!isMarkdown || !this.previewOn) {
            this.previewOn = isMarkdown && this.previewOn;
            this.previewPane.style.display = 'none';
            return;
        }
        this.previewPane.style.display = '';
        this.previewPane.innerHTML = renderMarkdown(
            tab ? tab.editor.value : '');
    }

    /** 刷新左侧「大纲」（jedi 的 documentSymbol ✓） */
    private _refreshOutline(): void {
        const tab = this.open.get(this.activePath);
        if (!this.outline) return;
        if (!tab) {
            this.outline.innerHTML = '';
            return;
        }
        const handle = tab.editor.handle as unknown as {
            outline?: () => Promise<Array<{ name: string; kind: number;
                                            line: number; depth: number }>>;
        } | null;
        if (!handle?.outline) {
            this.outline.innerHTML = '';
            return;
        }
        handle.outline().then((items) => {
            if (!items || !items.length) {
                this.outline.innerHTML = '<div class="desk-editor-outline-empty">'
                    + '（无符号 / 非 Python 文件）</div>';
                return;
            }
            const icon = (kind: number) => (kind === 5 ? 'C'
                : (kind === 12 ? 'ƒ' : 'm'));
            this.outline.innerHTML = items.map((item) =>
                `<button class="desk-editor-outline-item" data-outline-line="${item.line}"
                    data-outline-depth="${item.depth || 0}"
                    title="${esc(item.name)}（第 ${item.line + 1} 行）"
                ><i>${icon(item.kind)}</i>${esc(item.name)}</button>`).join('');
        }).catch(() => {
            this.outline.innerHTML = '';
        });
    }

    private _activate(path: string): void {
        const tab = this.open.get(path);
        if (!tab) return;
        this.activePath = path;
        this.host.textContent = '';
        this.host.appendChild(tab.editor.options.parent);
        void tab.editor.mount().then(() => {
            if (this.activePath === path) tab.editor.focus();
        });
        this._writeStatus(tab.kind === 'strategy'
            ? '策略可回测 / 参数优化（数据源由策略里的 get_kline 决定）'
            : 'Ctrl+S 保存后可在「指标 → 个人」里加到图表');
        // LSP 连上后再拉大纲（刚 mount 时 client 还没 ready，等一拍 ✓）
        window.setTimeout(() => this._refreshOutline(), 1200);
        this._syncPreview();
        this._syncSymbolsButton();
        if (this.diffOn) {                 // 换文件时关掉对比 ✓
            this.diffOn = false;
            if (this.diffPane) {
                this.diffPane.style.display = 'none';
                this.diffPane.innerHTML = '';
            }
        }
        if (this.diffButton) {
            this.diffButton.style.display = tab.text !== tab.saved
                ? '' : 'none';
        }
        this._syncStrategyButtons();
        this._renderTabs();
    }

    private _closeTab(path: string, force = false): void {
        const tab = this.open.get(path);
        if (!tab) return;
        if (!force && tab.text !== tab.saved
            && !window.confirm(`${tab.name} 还没保存，确定关闭？`)) {
            return;
        }
        tab.editor.destroy();
        tab.button.remove();
        this.open.delete(path);
        if (this.activePath === path) {
            this.activePath = '';
            this.host.textContent = '';
            const next = [...this.open.keys()].pop();
            if (next) this._activate(next);
            else this._writeStatus('选择左侧文件开始编辑（Ctrl+S 保存）');
        }
        this._renderTabs();
    }

    private _onChange(path: string, value: string): void {
        if (this._isMarkdown(path) && this.previewOn) {
            if (this.previewTimer !== undefined) {
                window.clearTimeout(this.previewTimer);
            }
            this.previewTimer = window.setTimeout(() => {
                if (this.previewPane) {
                    this.previewPane.innerHTML = renderMarkdown(value);
                }
            }, 200);
        }
        const tab = this.open.get(path);
        if (!tab || tab.text === value) return;
        tab.text = value;
        this._renderTabs();
    }

    private _syncButtons(): void {
        const tab = this.open.get(this.activePath);
        this.saveButton.disabled = !tab;
        this.saveButton.classList.toggle('on',
            !!tab && tab.text !== tab.saved);
        this.checkButton.disabled = !tab;
        this.formatButton.disabled = !tab;
        // 指标 / 策略都能加到图表（策略优先，后端判断 ✓）——只要有打开的文件
        this.addButton.disabled = !tab;
    }

    /** 设置 → 编辑器「保存时自动格式化」✓ */
    setFormatOnSave(enabled: boolean): void {
        this.formatOnSave = !!enabled;
    }

    private _save(): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        this.options.onCommand('editor_save', {
            path: tab.path, text: tab.text, format: this.formatOnSave,
        });
    }

    private _check(): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        this.options.onCommand('editor_check', { path: tab.path, text: tab.text });
    }

    private _format(): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        this.options.onCommand('editor_format', {
            path: tab.path, text: tab.text,
        });
    }

    /**
     * 当前文件是不是 Strategy；决定「策略回测 / 参数优化」是否可用 ✓
     *
     * ⚠ 判据不能只看 `tab.kind`：文件**打开时**还不是策略（刚新建 / 刚写完类
     * 还没保存）时 kind 会是 `file`，之后永远灰着（用户实测：关掉回测页后
     * 两个按钮还是不可用 ✗）。这里再按**当前源码**兜底判一次 ✓
     */
    private _syncStrategyButtons(): void {
        const tab = this.open.get(this.activePath);
        const source = String(tab?.text ?? '');
        const looksStrategy = tab?.kind === 'strategy'
            || /class\s+\w+\s*\([^)]*Strategy[^)]*\)/.test(source);
        void looksStrategy;
        if (looksStrategy && tab && tab.kind !== 'strategy') {
            tab.kind = 'strategy';           // 兜底修正，下次直接用 ✓
        }
        // ★ 用户要求：**不限制**（不因为「已有一个回测页 / 文件不是策略」而灰掉）
        //   没有处理函数才禁用（那种情况点了也没用）
        const enabled = !!(this.options.onBacktest || this.options.onOptimize);
        this.backtestButton.disabled = !enabled;
        this.optimizeButton.disabled = !enabled;
    }

    /** 策略实盘状态（后端 `strategy_live` 补丁 → 按钮变「运行中 PID」✓） */
    setStrategyLive(patch: Record<string, any>): void {
        const running = !!patch.running;
        const pid = Number(patch.pid) || 0;
        if (this.liveButton) {
            this.liveButton.textContent = running
                ? (pid ? `运行中 ${pid}` : '运行中') : '策略实盘';
            this.liveButton.title = running
                ? `策略正在后台运行（PID ${pid || '?'}）：天勤模拟/实盘会真的下单`
                : '把当前策略常驻运行（天勤模拟号 / 实盘会真的下单）';
            this.liveButton.classList.toggle('on', running);
        }
        if (this.stopLiveButton) {
            // 实时图表始终显示「停止实盘」，未运行时禁用；
            // 本地图表（allowLive=false）始终隐藏 ✓
            const allowLive = this.options.allowLive !== false;
            this.stopLiveButton.style.display = allowLive ? '' : 'none';
            this.stopLiveButton.disabled = !running;
            this.stopLiveButton.title = running
                ? '停止正在运行的策略实盘（子进程会被结束 ✓）'
                : '当前没有运行中的策略实盘';
        }
        // 状态栏徽标（像 VS Code 底部）
        const badge = this.status.querySelector('[data-live]') as
            HTMLElement | null;
        if (badge) {
            badge.className = 'desk-editor-live-badge '
                + (running ? 'on' : 'off');
            badge.textContent = running
                ? `● 实盘 运行中${pid ? ` · PID ${pid}` : ''}`
                : '● 实盘 未运行';
            badge.title = running
                ? `策略实盘在后台运行（PID ${pid || '?'}）—— 点「停止实盘」结束`
                : '策略实盘未运行（点工具栏「策略实盘」启动）';
        }
        if (patch.error) this._toastTop('error', String(patch.error));
    }

    /** 外部（关掉回测 / 优化页签后）刷新两个按钮的可用状态 ✓ */
    refreshStrategyButtons(): void {
        this._syncStrategyButtons();
    }

    /**
     * 回测 / 参数优化：**先体检**（语法 → Strategy 子类 → `op_config`）✓
     *
     * 以前直接开策略 Tab，没语法没策略也能开一个空白页 ✗
     * 现在把检查交给后端（只读源码、不执行），不通过就在**顶部中间**弹提示。
     */
    private _strategyAction(mode: 'backtest' | 'optimize'): void {
        const tab = this.open.get(this.activePath);
        if (!tab) {
            this._toastTop('warning', '先打开一个 Strategy 文件');
            return;
        }
        if (tab.text !== tab.saved) this._save();
        const id = String(Date.now());
        this.pendingStrategy.set(id, { path: tab.path, mode });
        this.options.onCommand('strategy_check',
                               { id, path: tab.path, mode });
    }

    /** 后端体检结果：通过 → 开策略 Tab；否则顶部中间提示 ✓ */
    setStrategyCheck(patch: Record<string, any>): void {
        const id = String(patch.id || '');
        const pending = this.pendingStrategy.get(id);
        this.pendingStrategy.delete(id);
        const ok = !!patch.ok;
        if (!ok) {
            this._toastTop('warning', String(patch.reason || '检查没有通过'));
            return;
        }
        const path = String(patch.path || pending?.path || '');
        const mode = (patch.mode === 'optimize' ? 'optimize' : 'backtest') as
            'backtest' | 'optimize';
        const strategies = (patch.strategies || []) as string[];
        if (mode === 'backtest') this.options.onBacktest?.(path);
        else this.options.onOptimize?.(path);
        if (strategies.length > 1) {
            this._toastTop('info',
                `文件里有 ${strategies.length} 个策略：${strategies.join(' / ')}`);
        }
    }

    /**
     * 写状态栏文字：**保留右侧的 LSP 徽标**（`textContent = ''` 会连徽标一起清掉 ✗）
     */
    private _writeStatus(text: string): void {
        // ★ 状态栏文字 + 右侧「行/列 · 换行 · 编码」+ LSP 徽标：三个都在 ✓
        const badge = this.status.querySelector('[data-lsp]') as HTMLElement
            | null;
        const meta = this.status.querySelector('[data-meta]') as HTMLElement
            | null;
        this.status.textContent = text;
        if (meta) this.status.appendChild(meta);
        if (badge) this.status.appendChild(badge);
        else this._ensureLspBadge();
        if (!meta) {
            // 顺序：文字 → 元信息 → 徽标（元信息靠 `margin-left:auto` 贴右 ✓）
            const info = this.status.querySelector('[data-meta]');
            if (info && badge) this.status.insertBefore(info, badge);
        }
    }

    private _ensureLspBadge(): void {
        if (this.status.querySelector('[data-meta]')) {
            /* 元信息已就位 ✓ */
        } else {
            const meta = document.createElement('span');
            meta.className = 'desk-editor-meta';
            meta.dataset.meta = '1';
            const cursor = document.createElement('span');
            cursor.dataset.cursor = '1';
            cursor.textContent = '行 1，列 1';
            meta.append(cursor, document.createTextNode(
                '    LF    UTF-8    空格: 4'));
            this.status.appendChild(meta);
        }
        if (!this.status.querySelector('[data-live]')) {
            // ★ 状态栏「策略实盘」徽标（● 运行中 PID / 未运行 ✓）
            const live = document.createElement('span');
            live.className = 'desk-editor-live-badge off';
            live.dataset.live = '1';
            live.textContent = '● 实盘 未运行';
            live.title = '策略实盘状态（点工具栏「策略实盘」启动）';
            this.status.appendChild(live);
        }
        if (this.status.querySelector('[data-lsp]')) return;
        const badge = document.createElement('span');
        badge.className = 'desk-editor-lsp';
        badge.dataset.lsp = '1';
        badge.dataset.level = 'off';
        badge.textContent = 'LSP 未启用';
        badge.title = 'LSP（jedi）：补全 / 悬停 / 跳转定义 / 语法浪线';
        this.status.appendChild(badge);
    }

    /** LSP 状态（状态栏右侧的小徽标 ✓） */
    private _setLspStatus(text: string, level?: 'ok' | 'error' | 'off'): void {
        const badge = this.element.querySelector('[data-lsp]') as HTMLElement
            | null;
        if (!badge) return;
        badge.textContent = text;
        badge.dataset.level = level || 'off';
        badge.title = text;
    }

    /** 顶部中间的提示（体检不通过 / 多个策略 等 ✓） */
    private _toastTop(level: string, text: string): void {
        this.options.onToast?.(level, text, [], undefined, 'top');
    }

    /** 把参数写回当前文件的编辑器缓冲区（不自动保存 ✓） */
    applyParams(path: string, params: Record<string, unknown>): void {
        const tab = this.open.get(path);
        if (!tab || !params || !Object.keys(params).length) return;
        const entries = Object.entries(params).map(([key, value]) =>
            `${key}=${typeof value === 'string' ? JSON.stringify(value) : value}`
        ).join(', ');
        const replacement = `params = dict(${entries})`;
        let text = tab.text;
        const replaced = replaceParamsDict(text, replacement);
        if (replaced !== null) {
            text = replaced;
        } else {
            const classLine = /^class\s+\w+\s*\([^)]*\)\s*:\s*$/m;
            if (classLine.test(text)) {
                text = text.replace(classLine, (line) => `${line}
    ${replacement}`);
            } else {
                text += `
${replacement}
`;
            }
        }
        tab.text = text;
        tab.editor.setValue(text);
        this._activate(path);
        this.options.onToast?.('info', '最优参数已写回编辑器缓冲区（未保存）');
    }

    /** 复制文件 / 文件夹的**绝对路径**（走后端系统剪贴板，`file://` 也能用 ✓） */
    private _copyPath(path: string): void {
        const text = String(path || '');
        if (!text) return;
        // ★ 先让**后端**写系统剪贴板：`file://` 页面里 navigator.clipboard
        //   需要安全上下文，实测直接 reject → 以前「复制地址点不动」✗
        this.options.onCommand('clipboard_set', { text });
        this.options.onToast?.('success', `已复制地址：${text}`);
    }

    private _addToChart(pathOverride?: string): void {
        const path = String(pathOverride
            || this.open.get(this.activePath)?.path
            || this.activePath || '');
        if (!path) {
            this.options.onToast?.('warning', '先打开一个指标文件');
            return;
        }
        // 后端按**文件路径**算 `pi:<分类>/<名字>`（类 / 函数都认 ✓）
        this.options.onCommand('editor_add_indicator', {
            path,
            local: !!this.options.local,
            symbol: this.options.symbol ? this.options.symbol() : '',
            cell: this.options.cell ? this.options.cell() : 0,
        });
    }

    private _newEntry(action: 'new_file' | 'new_folder',
                      item?: ExplorerItem): void {
        const base = item
            ? (item.dir ? item.path : this.activeDir)
            : (this.activeDir || this.root);
        const name = window.prompt(
            action === 'new_file' ? '新文件名（如 demo.py）' : '新文件夹名', '');
        if (!name) return;
        this.options.onCommand('explorer_op', { action, path: base, name });
    }

    /** 在**指定目录**新建文件 / 文件夹（空白处右键用 ✓） */
    private _newEntryAt(action: 'new_file' | 'new_folder',
                        base: string): void {
        const name = window.prompt(
            action === 'new_file' ? '新文件名（如 demo.py）' : '新文件夹名', '');
        if (!name) return;
        this.options.onCommand('explorer_op', { action, path: base, name });
    }

    private _newPersonal(kind: 'indicator' | 'strategy'): void {
        const name = window.prompt(kind === 'strategy'
            ? '策略文件名（不用写 .py）' : '指标文件名（不用写 .py）', '');
        if (!name) return;
        this.options.onCommand('editor_new', { kind, name });
    }

    private _removeFile(): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        if (!window.confirm(`删除 ${tab.name}？`)) return;
        this.options.onCommand('editor_delete', { path: tab.path });
    }

    private _copyAll(): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        void navigator.clipboard?.writeText(tab.text);
        this._writeStatus('已复制全部代码到剪贴板');
    }

    /** 编辑器右键的剪切 / 复制 / 粘贴（走系统剪贴板 ✓） */
    private _clipboard(mode: 'cut' | 'copy' | 'paste'): void {
        const tab = this.open.get(this.activePath);
        if (!tab) return;
        const editor = tab.editor;
        if (mode === 'paste') {
            void navigator.clipboard?.readText().then((text) => {
                if (text) editor.insert(text);
            }).catch(() => {
                this.options.onToast?.('warning',
                    '剪贴板不可用（浏览器权限）');
            });
            return;
        }
        const selected = editor.getSelection();
        if (!selected) {
            this.options.onToast?.('info', '先选中一段代码');
            return;
        }
        void navigator.clipboard?.writeText(selected);
        if (mode === 'cut') editor.insert('');
        this._writeStatus(mode === 'cut' ? '已剪切' : '已复制');
    }

    private _button(label: string,
                    run: (button: HTMLButtonElement) => void): HTMLButtonElement {
        const button = document.createElement('button');
        button.className = 'desk-editor-btn';
        button.textContent = label;
        button.addEventListener('click', () => run(button));
        return button;
    }

    private _ensureStyle(): void {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = CSS;
        document.head.appendChild(style);
    }
}

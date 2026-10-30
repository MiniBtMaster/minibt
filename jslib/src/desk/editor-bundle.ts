/**
 * 编辑器懒加载包（IIFE → 全局 `DeskCodeEditor`）✓
 *
 * `desk.js` 是 IIFE，Rollup 不能在 IIFE 里做代码分割（动态 import 会被原样
 * 保留 → 浏览器 404 ✗）。所以编辑器单独打一个 IIFE：平时不加载，
 * 第一次点「代码」页签时由 `code-editor.ts` 插 `<script src="./desk-editor.js">`。
 *
 * 本文件只做「把 CodeMirror 组装成一个 EditorView」，与 UI 无关 ✓
 */
import { EditorState, EditorSelection, type Extension } from '@codemirror/state';
import {
    EditorView, keymap, lineNumbers, highlightActiveLine,
    highlightActiveLineGutter, drawSelection, dropCursor,
    rectangularSelection, crosshairCursor, highlightSpecialChars, placeholder,
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab,
    toggleComment } from '@codemirror/commands';
import {
    bracketMatching, indentOnInput, syntaxHighlighting,
    HighlightStyle, foldGutter, foldKeymap, foldService, indentUnit,
} from '@codemirror/language';
import { tags } from '@lezer/highlight';
import { python as pythonLang, pythonLanguage }
    from '@codemirror/lang-python';
import { markdown as markdownLang } from '@codemirror/lang-markdown';
import { json as jsonLang } from '@codemirror/lang-json';
import { search, searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import {
    autocompletion, completionKeymap, type Completion,
    type CompletionContext, type CompletionResult,
} from '@codemirror/autocomplete';
import { lintGutter } from '@codemirror/lint';
import {
    LanguageServerClient, WebSocketTransport, languageServerWithTransport,
} from 'codemirror-languageserver';

export interface MountSpec {
    parent: HTMLElement;
    value?: string;
    theme?: 'light' | 'dark';
    onChange?: (value: string) => void;
    onSave?: () => void;
    /** 文件的**绝对路径**（LSP 的 documentUri / 跳转都要它 ✓） */
    path?: string;
    /** LSP：`{url: 'ws://127.0.0.1:PORT', root: '/abs/path'}` ✓ */
    lsp?: { url: string; root: string };
    /** LSP 状态回调（连接成功 / 报错，编辑器状态栏显示 ✓） */
    onLspStatus?: (text: string, level?: 'ok' | 'error' | 'off') => void;
    /** 跳转到**别的文件**（跨文件 F12 / Ctrl+点击 ✓） */
    onOpenLocation?: (path: string, line: number) => void;
    /** 光标 / 状态变化（状态栏：行号 列号 ✓） */
    onCursor?: (line: number, column: number) => void;
}

export interface EditorHandle {
    getValue(): string;
    setValue(text: string): void;
    focus(): void;
    destroy(): void;
    /** 当前选中文本（右键「剪切 / 复制」用 ✓） */
    getSelection(): string;
    /** 用新文本替换选区（没有选区就插在光标处 ✓） */
    insert(text: string): void;
    /** 全选 ✓ */
    selectAll(): void;
    /** 文档符号（大纲）：`[{name, kind, line, depth}]` ✓ */
    outline(): Promise<Array<{ name: string; kind: number; line: number;
                               depth: number }>>;
    /** 格式化（LSP：ruff / black / yapf）✓ */
    format(): void;
    /** 工作区符号搜索（跨文件 class / def ✓） */
    searchSymbols(query: string): Promise<Array<{
        name: string; kind: number; path: string; line: number }>>;
    /** 跳到某一行（大纲点击 / 跳转定义后 ✓） */
    jumpToLine(line: number): void;
}

/**
 * VS Code 深色（One Dark Pro 风格）的语法配色 ✓
 *
 * 用户明确要求：**函数名黄色**（`#DCDCAA`）、**常量 / True False None 蓝色**
 * （`#569CD6`）。默认的 highlightStyle 把函数画成紫色、常量也是紫色，
 * 和 VS Code 差得远 ✗
 */
const VSCODE_DARK = HighlightStyle.define([
    { tag: tags.comment, color: '#6A9955', fontStyle: 'italic' },
    { tag: [tags.keyword, tags.controlKeyword, tags.moduleKeyword],
      color: '#C586C0' },
    { tag: [tags.bool, tags.null, tags.atom], color: '#569CD6' },
    { tag: tags.number, color: '#B5CEA8' },
    { tag: [tags.string, tags.special(tags.string)], color: '#CE9178' },
    { tag: tags.regexp, color: '#D16969' },
    { tag: tags.function(tags.variableName), color: '#DCDCAA' },
    { tag: tags.function(tags.propertyName), color: '#DCDCAA' },
    { tag: tags.className, color: '#4EC9B0' },
    { tag: tags.typeName, color: '#4EC9B0' },
    { tag: tags.definition(tags.variableName), color: '#9CDCFE' },
    { tag: tags.variableName, color: '#9CDCFE' },
    { tag: tags.propertyName, color: '#9CDCFE' },
    { tag: [tags.operator, tags.punctuation], color: '#D4D4D4' },
    { tag: tags.self, color: '#569CD6', fontStyle: 'italic' },
    { tag: tags.invalid, color: '#F44747' },
]);

/** 浅色主题（VS Code Light+）✓ */
const VSCODE_LIGHT = HighlightStyle.define([
    { tag: tags.comment, color: '#008000', fontStyle: 'italic' },
    { tag: [tags.keyword, tags.controlKeyword, tags.moduleKeyword],
      color: '#AF00DB' },
    { tag: [tags.bool, tags.null, tags.atom], color: '#0000FF' },
    { tag: tags.number, color: '#098658' },
    { tag: [tags.string, tags.special(tags.string)], color: '#A31515' },
    { tag: tags.function(tags.variableName), color: '#795E26' },
    { tag: tags.function(tags.propertyName), color: '#795E26' },
    { tag: tags.className, color: '#267F99' },
    { tag: tags.typeName, color: '#267F99' },
    { tag: tags.definition(tags.variableName), color: '#001080' },
    { tag: tags.variableName, color: '#001080' },
    { tag: tags.propertyName, color: '#001080' },
    { tag: [tags.operator, tags.punctuation], color: '#333333' },
    { tag: tags.invalid, color: '#CD3131' },
]);

/**
 * 代码补全（P63）：Python 关键词 + numpy / pandas / minibt 的常用 API ✓
 *
 * * 普通位置 → 关键词 + minibt 顶层名字 + 常用片段（`class` 模板等）
 * * `np.` / `numpy.` → numpy 常用函数
 * * `pd.` / `pandas.` → pandas 常用 API
 * * `minibt.` / `bt.` → minibt 顶层
 * * `self.kline.` / `self.` → OHLCV 字段 + 策略/指标常用成员
 */
const PY_KEYWORDS = ('and as assert async await break class continue def del '
    + 'elif else except False finally for from global if import in is lambda '
    + 'None nonlocal not or pass raise return True try while with yield '
    + 'self print len range enumerate zip list dict set tuple isinstance '
    + 'float int str bool min max sum abs round sorted map filter open')
    .split(' ');

const NUMPY_API = ('array arange linspace zeros ones empty full eye mean std '
    + 'var median percentile sum prod cumsum cumprod diff shift roll where '
    + 'maximum minimum abs sqrt log log10 exp sin cos tan sign floor ceil '
    + 'round clip power isnan isfinite nan inf concatenate stack vstack hstack '
    + 'reshape ravel transpose argmax argmin argsort unique repeat tile')
    .split(' ');

const PANDAS_API = ('DataFrame Series concat merge to_datetime date_range '
    + 'isna notna isnull notnull rolling ewm shift pct_change fillna ffill '
    + 'bfill dropna drop duplicates groupby resample apply map agg to_numpy '
    + 'to_dict sort_values sort_index reset_index set_index iloc loc at iat '
    + 'columns index values head tail copy astype rename assign clip nlargest '
    + 'nsmallest rank corr cov describe')
    .split(' ');

const MINIBT_API = ('KLine BtIndicator Strategy Bt LocalDatas StockApi '
    + 'PlotInfo LineStyle SignalStyle BandStyle SpanStyle TableStyle '
    + 'CandleStyle WaterMark VPStyle BtStop tq_auth tq_account '
    + 'kline_random get_kline indicator_step indicator '
    + 'lines params overlap isplot ismain iscandles next buy sell close '
    + 'position get_kline plotinfo linestyle signalstyle bandstyle '
    + 'spanstyle tablestyle candlestyle legend order size stop_step')
    .split(' ');

const KLINE_FIELDS = ('open high low close volume amount open_interest '
    + 'datetime duration symbol position')
    .split(' ');

function words(list: string[]): Completion[] {
    return list.map((label) => ({ label, type: 'keyword' }));
}

function apiWords(list: string[]): Completion[] {
    return list.map((label) => ({ label, type: 'function' }));
}

/** 依据光标前的 `xxx.` 选补全表 ✓ */
function pythonCompletions(context: CompletionContext):
    CompletionResult | null {
    const word = context.matchBefore(/[\w.]*/);
    if (!word) return null;
    if (word.from === word.to && !context.explicit) return null;
    const text = word.text;
    // 光标前 24 个字符用来判断 `np.` / `pd.` / `self.kline.` 这类前缀 ✓
    const before = context.state.sliceDoc(
        Math.max(0, word.from - 24), word.from);
    const match = /([A-Za-z_][\w]*)\.\w*$/.exec(`${before}${text}`);
    const owner = match ? match[1] : '';
    let options: Completion[];
    if (!owner) {
        options = [...words(PY_KEYWORDS), ...apiWords(MINIBT_API)];
    } else if (owner === 'np' || owner === 'numpy') {
        options = apiWords(NUMPY_API);
    } else if (owner === 'pd' || owner === 'pandas') {
        options = apiWords(PANDAS_API);
    } else if (owner === 'minibt' || owner === 'bt') {
        options = apiWords(MINIBT_API);
    } else if (owner === 'kline' || owner === 'self') {
        options = [...apiWords(KLINE_FIELDS), ...apiWords(MINIBT_API)];
    } else {
        options = words(PY_KEYWORDS);
    }
    // 只替换**最后一个点之后**的那段（`np.ar` → 补 `arange` 不吞掉 `np.` ✓）
    const dot = text.lastIndexOf('.');
    return {
        from: word.from + (dot >= 0 ? dot + 1 : 0),
        options,
        validFor: /^[\w]*$/,
    };
}

/**
 * 按后缀挑语言：`.py`/`.pyi` → Python，`.md` → Markdown，`.json` → JSON，
 * 其它（txt / yaml / toml / csv / log / sh…）→ 纯文本（行号 / 查找 / 折叠照常）✓
 */
function languageOf(path?: string): Extension {
    const name = String(path || '').toLowerCase();
    if (name.endsWith('.md') || name.endsWith('.markdown')) {
        return markdownLang() as unknown as Extension;
    }
    if (name.endsWith('.json')) return jsonLang() as unknown as Extension;
    if (!name || name.endsWith('.py') || name.endsWith('.pyi')) {
        return pythonLang() as unknown as Extension;
    }
    return [] as unknown as Extension;      // 纯文本：不装任何语言包 ✓
}

/** 后缀 → LSP 的 `languageId`（目前只有 Python 有服务端 ✓） */
function languageIdOf(path?: string): string {
    const name = String(path || '').toLowerCase();
    if (!name || name.endsWith('.py') || name.endsWith('.pyi')) return 'python';
    if (name.endsWith('.md')) return 'markdown';
    if (name.endsWith('.json')) return 'json';
    return 'plaintext';
}

/** Windows 路径分隔符（写成常量，避免源码里出现难转义的反斜杠 ✓） */
const BACKSLASH = String.fromCharCode(92);

/** 绝对路径 → `file:///C:/...`（LSP 的 uri 格式 ✓） */
function fileUri(path: string): string {
    const text = String(path || '').split(BACKSLASH).join('/');
    if (!text) return 'file:///';
    return text.startsWith('/') ? `file://${text}` : `file:///${text}`;
}

/**
 * LSP 扩展：连到 desk 后端自带的 jedi 服务（`minibt/desk/lsp.py`）✓
 *
 * 提供：补全（带文档）/ 悬停 / 跳转定义 / 引用 / 签名 / **语法诊断浪线**。
 * 连不上就静默降级（只保留本地语法高亮），不影响编辑 ✓
 */
/**
 * 调 LSP 的 JSON-RPC（`LanguageServerClient.request` 是 protected，
 * 这里包一层，超时 5s 避免卡住 UI ✓）
 */
async function lspRequest(client: LanguageServerClient, method: string,
                          params: Record<string, unknown>): Promise<unknown> {
    const call = (client as unknown as {
        request: (m: string, p: Record<string, unknown>,
                  timeout?: number) => Promise<unknown>;
    }).request.bind(client);
    return call(method, params, 5000);
}

/**
 * 建 LSP 客户端（只有 Python 文件才有；其它文件返回 null 静默降级 ✓）
 */
function createClient(spec: MountSpec): LanguageServerClient | null {
    if (languageIdOf(spec.path) !== 'python') return null;
    const info = spec.lsp;
    if (!info?.url) return null;
    try {
        return new LanguageServerClient({
            rootUri: fileUri(info.root || ''),
            workspaceFolders: info.root ? [{
                uri: fileUri(info.root), name: 'personal',
            }] : null,
            documentUri: fileUri(spec.path || ''),
            languageId: 'python',
            transport: new WebSocketTransport(info.url),
            onCapabilities: () => spec.onLspStatus?.(
                'LSP 已连接（jedi：补全 / 悬停 / 跳转 / 语法检查）', 'ok'),
            onError: (error) => spec.onLspStatus?.(
                `LSP 出错：${String(error)}`, 'error'),
            onClose: () => spec.onLspStatus?.('LSP 已断开', 'off'),
        });
    } catch (error) {
        spec.onLspStatus?.(`LSP 连接失败：${String(error)}`, 'error');
        return null;
    }
}

/** 把 client 变成 CodeMirror 扩展（补全 / 悬停 / 跳转 / 诊断 / F2 重命名 ✓） */
function lspExtensions(spec: MountSpec,
                       client: LanguageServerClient | null): Extension[] {
    if (languageIdOf(spec.path) !== 'python') {
        spec.onLspStatus?.('无语言服务（仅语法高亮）', 'off');
        return [];
    }
    if (!client) {
        spec.onLspStatus?.('LSP 未启用', 'off');
        return [];
    }
    try {
        // ⚠ 必须用 `languageServerWithTransport`：`languageServer` 会**另建**
        //   一个 client（忽略传入的），那个 client 没挂到 view 上 →
        //   永远不发 `didOpen`，诊断 / 补全全哑 ✗
        return languageServerWithTransport({
            client,
            rootUri: fileUri(spec.lsp?.root || ''),
            workspaceFolders: spec.lsp?.root ? [{
                uri: fileUri(spec.lsp.root), name: 'personal',
            }] : null,
            documentUri: fileUri(spec.path || ''),
            languageId: 'python',
            // markdown 文档（jedi docstring）按 HTML 渲染，和 VS Code 一致 ✓
            allowHTMLContent: true,
        } as never) as Extension[];
    } catch (error) {
        spec.onLspStatus?.(`LSP 挂载失败：${String(error)}`, 'error');
        return [];
    }
}

export function mount(spec: MountSpec): EditorHandle {
    const dark = (spec.theme || 'dark') !== 'light';
    // 语言服务客户端（只有 Python 才有）；大纲 / 折叠 / 格式化都靠它 ✓
    const client = createClient(spec);
    const documentUri = fileUri(spec.path || '');
    /** 跳到某一行（大纲 / 跳转定义 / 符号搜索都用 ✓） */
    const jumpTo = (line: number) => {
        const target = view.state.doc.line(
            Math.max(1, Math.min(view.state.doc.lines, Number(line) + 1)));
        view.dispatch({
            selection: { anchor: target.from },
            effects: EditorView.scrollIntoView(target.from,
                                               { y: 'center' }),
        });
        view.focus();
    };

    /** 格式化：走后端 LSP（ruff / black / yapf）+ 应用到编辑器 ✓ */
    const formatDocumentText = () => {
        if (!client) {
            spec.onLspStatus?.('该文件不支持格式化（不是 Python）', 'off');
            return;
        }
        import('codemirror-languageserver').then((mod) => {
            try {
                (mod as unknown as {
                    formatDocument?: (view: EditorView) => unknown;
                }).formatDocument?.(view);
                spec.onLspStatus?.('已格式化（ruff / black）', 'ok');
            } catch {
                spec.onLspStatus?.('格式化失败', 'error');
            }
        }).catch(() => undefined);
    };
    const foldRanges = new Map<number, number>();      // 行 → 结束行
    const foldProvider = (state: EditorState, lineStart: number,
                          lineEnd: number) => {
        const line = state.doc.lineAt(lineStart).number - 1;
        const end = foldRanges.get(line);
        if (end === undefined) return null;
        const target = state.doc.line(Math.min(end + 1, state.doc.lines));
        return { from: lineEnd, to: target.to };
    };
    const view = new EditorView({
        parent: spec.parent,
        state: EditorState.create({
            doc: spec.value || '',
            extensions: [
                lineNumbers(),
                highlightActiveLineGutter(),
                highlightSpecialChars(),
                history(),
                foldGutter(),
                // ★ VS Code 风格多光标：Alt+点击加光标 / Alt+Shift+点击
                //   从当前光标行到点击行批量加光标（见下面的 mousedown）✓
                EditorState.allowMultipleSelections.of(true),
                EditorView.clickAddsSelectionRange.of(
                    (event) => event.altKey && event.button === 0),
                drawSelection(),
                dropCursor(),
                // Python 习惯：Enter / Tab 缩进 4 个空格（默认是 2 ✗）
                EditorState.tabSize.of(4),
                indentUnit.of('    '),
                indentOnInput(),
                bracketMatching(),
                rectangularSelection(),
                crosshairCursor(),
                highlightActiveLine(),
                highlightSelectionMatches(),
                // ★ 搜索/替换面板放在编辑器**顶部**（工具栏下面），
                //   默认在底部会被状态栏挡住（用户实测 ✗）
                search({ top: true }),
                syntaxHighlighting(dark ? VSCODE_DARK : VSCODE_LIGHT,
                                  { fallback: true }),
                // 代码补全（Python 关键词 / numpy / pandas / minibt ✓）
                pythonLanguage.data.of({ autocomplete: pythonCompletions }),
                autocompletion({
                    activateOnTyping: true,
                    maxRenderedOptions: 40,
                    defaultKeymap: true,
                }),
                languageOf(spec.path),
                // 语法诊断的左侧标记（浪线由 LSP 的 setDiagnostics 画 ✓）
                lintGutter(),
                foldService.of(foldProvider),
                // Ctrl / Cmd + 点击：跳转定义（跨文件由面板打开 ✓）
                EditorView.domEventHandlers({
                    mousedown: (event) => {
                        // ★ Alt+Shift+左击：从当前主光标所在行到点击行，
                        //   每行在**点击列**放一个光标（VS Code 式多行光标）。
                        //   Alt+单击由 CodeMirror 的 clickAddsSelectionRange
                        //   + 矩形选择处理，只加一个光标；Alt+拖拽仍是矩形选择 ✓
                        if (event.altKey && event.shiftKey
                            && event.button === 0) {
                            const pos = view.posAtCoords({
                                x: event.clientX, y: event.clientY,
                            });
                            if (pos == null) return false;
                            const anchor = view.state.selection.main.head;
                            const anchorLine = view.state.doc.lineAt(anchor);
                            const targetLine = view.state.doc.lineAt(pos);
                            const column = pos - targetLine.from;
                            // 从主光标行朝点击行逐行加，最后加的是点击行 →
                            // 主光标 / 状态栏停在左击位置（向上框选也一致 ✓）
                            const step = targetLine.number >= anchorLine.number
                                ? 1 : -1;
                            let selection = view.state.selection;
                            for (let lineNo = anchorLine.number; ;
                                 lineNo += step) {
                                const line = view.state.doc.line(lineNo);
                                // 短行钳到行尾，避免光标跑到下一行 ✓
                                const at = Math.min(line.from + column,
                                                    line.to);
                                selection = selection.addRange(
                                    EditorSelection.cursor(at));
                                if (lineNo === targetLine.number) break;
                            }
                            view.dispatch({ selection,
                                            scrollIntoView: true });
                            view.focus();
                            return true;
                        }
                        if (!(event.ctrlKey || event.metaKey)) return false;
                        if (!client) return false;
                        event.preventDefault();
                        gotoDefinition();
                        return true;
                    },
                }),
                // 光标移动 → 状态栏（行 / 列 ✓）
                EditorView.updateListener.of((update) => {
                    if (!update.selectionSet && !update.docChanged) return;
                    const head = update.state.selection.main.head;
                    const line = update.state.doc.lineAt(head);
                    spec.onCursor?.(line.number, head - line.from + 1);
                }),
                ...lspExtensions(spec, client),
                placeholder('# 在这里写 Python…（Ctrl+S 保存）'),
                keymap.of([
                    {
                        key: 'Mod-s',
                        preventDefault: true,
                        run: () => {
                            spec.onSave?.();
                            return true;
                        },
                    },
                    {
                        key: 'F12',
                        preventDefault: true,
                        run: () => {
                            gotoDefinition();
                            return true;
                        },
                    },
                    {
                        // Shift+Alt+F：格式化（和「格式化」按钮同一个函数 ✓）
                        key: 'Shift-Alt-f',
                        preventDefault: true,
                        run: () => {
                            formatDocumentText();
                            return true;
                        },
                    },
                    // ★ VS Code 同款注释快捷键（用户要求 ✓）：
                    //   `Ctrl+K Ctrl+C` 注释选中行 / `Ctrl+/` 切换注释
                    { key: 'Mod-k Mod-c', run: toggleComment,
                      preventDefault: true },
                    { key: 'Mod-/', run: toggleComment,
                      preventDefault: true },
                    { key: 'Ctrl-/', run: toggleComment,
                      preventDefault: true },
                    { key: 'Ctrl-K Ctrl-C', run: toggleComment,
                      preventDefault: true },
                    indentWithTab,
                    ...completionKeymap,
                    ...defaultKeymap,
                    ...historyKeymap,
                    ...foldKeymap,
                    ...searchKeymap,
                ]),
                EditorView.theme({
                    '&': {
                        height: '100%',
                        fontSize: '12.5px',
                        backgroundColor: dark ? '#14181e' : '#ffffff',
                        color: dark ? '#d8d9db' : '#1f2329',
                    },
                    '.cm-scroller': {
                        fontFamily:
                            'Consolas, "JetBrains Mono", Menlo, monospace',
                        lineHeight: '1.5',
                    },
                    '.cm-gutters': {
                        backgroundColor: dark ? '#14181e' : '#f6f7f9',
                        color: dark ? '#5c6470' : '#98a0ab',
                        border: 'none',
                    },
                    // ★ 选中文本：`drawSelection()` 画的是
                    //   `.cm-selectionBackground` 图层，默认几乎透明 →
                    //   选中的字看着像没选中（用户实测 ✗）。这里给足对比度，
                    //   焦点内 / 失焦两种状态都设一遍 ✓
                    '.cm-selectionBackground, &.cm-focused .cm-selectionBackground':
                        {
                            backgroundColor: dark
                                ? 'rgba(58, 120, 200, .45)'
                                : 'rgba(58, 120, 200, .26)',
                        },
                    '&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground':
                        {
                            backgroundColor: dark
                                ? 'rgba(64, 132, 220, .55)'
                                : 'rgba(58, 120, 200, .30)',
                        },
                    // 原生选区（输入框 / 未用 drawSelection 的场景）✓
                    '& ::selection': {
                        backgroundColor: dark
                            ? 'rgba(64, 132, 220, .55)'
                            : 'rgba(58, 120, 200, .30)',
                        color: 'inherit',
                    },
                    // 同词高亮（选中一个词时高亮其它出现处）稍微淡一点 ✓
                    '.cm-selectionMatch': {
                        backgroundColor: dark
                            ? 'rgba(255, 213, 79, .18)'
                            : 'rgba(255, 193, 7, .22)',
                    },
                    '.cm-activeLine': {
                        backgroundColor: dark ? '#1b2027' : '#f3f5f8',
                    },
                    '.cm-activeLineGutter': {
                        backgroundColor: dark ? '#1b2027' : '#eef1f5',
                    },
                    '.cm-content': {
                        caretColor: dark ? '#d8d9db' : '#1f2329',
                    },
                    '.cm-diagnostic-error': {
                        borderLeft: '3px solid #ef5350',
                        paddingLeft: '4px',
                    },
                }, { dark }),
                EditorView.lineWrapping,
                EditorView.updateListener.of((update) => {
                    if (!update.docChanged) return;
                    spec.onChange?.(update.state.doc.toString());
                }),
            ],
        }),
    });
    /** 跳到定义：同文件直接跳；别的文件交给面板打开 ✓ */
    const gotoDefinition = () => {
        if (!client) return;
        const head = view.state.selection.main.head;
        const line = view.state.doc.lineAt(head);
        const character = head - line.from;
        lspRequest(client, 'textDocument/definition', {
            textDocument: { uri: documentUri },
            position: { line: line.number - 1, character },
        }).then((result) => {
            const list = (Array.isArray(result) ? result : [result])
                .filter(Boolean) as Array<Record<string, any>>;
            const first = list[0];
            if (!first) return;
            const uri = String(first.uri || '');
            const start = ((first.range || {}).start || {}).line;
            const target = typeof start === 'number' ? start : 0;
            if (!uri || uri === documentUri) {
                jumpTo(target);
                return;
            }
            const path = uri.replace(/^file:\/\//, '')
                .replace(/^\/([A-Za-z]:)/, '$1');
            spec.onOpenLocation?.(path, target);
        }).catch(() => undefined);
    };

    // 文档变了就刷新折叠范围（防抖 500ms ✓）
    let foldTimer: number | undefined;
    const refreshFolds = () => {
        if (!client) return;
        if (foldTimer !== undefined) window.clearTimeout(foldTimer);
        foldTimer = window.setTimeout(() => {
            lspRequest(client, 'textDocument/foldingRange',
                       { textDocument: { uri: documentUri } })
                .then((ranges: unknown) => {
                    foldRanges.clear();
                    for (const item of (ranges || []) as Array<
                        { startLine: number; endLine: number }>) {
                        const start = Number(item.startLine);
                        const end = Number(item.endLine);
                        if (Number.isFinite(start) && Number.isFinite(end)
                            && end > start) {
                            foldRanges.set(start, end);
                        }
                    }
                    view.dispatch({});
                })
                .catch(() => undefined);
        }, 500);
    };
    window.setTimeout(refreshFolds, 800);

    return {
        getValue: () => view.state.doc.toString(),
        getSelection: () => {
            const range = view.state.selection.main;
            return view.state.sliceDoc(range.from, range.to);
        },
        insert: (text: string) => {
            const range = view.state.selection.main;
            view.dispatch({
                changes: { from: range.from, to: range.to, insert: text },
                selection: { anchor: range.from + text.length },
            });
            view.focus();
        },
        selectAll: () => {
            view.dispatch({
                selection: { anchor: 0, head: view.state.doc.length },
            });
            view.focus();
        },
        outline: async () => {
            if (!client) return [];
            try {
                const symbols = await lspRequest(
                    client, 'textDocument/documentSymbol',
                    { textDocument: { uri: documentUri } }) as Array<Record<
                    string, any>>;
                const flatten = (items: Array<Record<string, any>>,
                                 depth: number): Array<{
                                     name: string; kind: number;
                                     line: number; depth: number;
                                 }> => {
                    const out: Array<{ name: string; kind: number;
                                       line: number; depth: number }> = [];
                    for (const item of items || []) {
                        const start = ((item.range || {}).start || {}).line;
                        if (typeof start !== 'number') continue;
                        out.push({
                            name: String(item.name || ''),
                            kind: Number(item.kind) || 0,
                            depth: Number(item.depth ?? depth) || 0,
                            line: start,
                        });
                        if (Array.isArray(item.children)) {
                            out.push(...flatten(item.children, depth + 1));
                        }
                    }
                    return out;
                };
                return flatten(symbols, 0);
            } catch {
                return [];
            }
        },
        format: () => formatDocumentText(),
        searchSymbols: async (query: string) => {
            if (!client) return [];
            try {
                const items = await lspRequest(client, 'workspace/symbol',
                                               { query }) as Array<Record<
                    string, any>>;
                return (items || []).map((item) => {
                    const uri = String(((item.location || {}).uri) || '');
                    const start = (((item.location || {}).range || {})
                        .start || {}).line;
                    return {
                        name: String(item.name || ''),
                        kind: Number(item.kind) || 0,
                        path: uri.replace(/^file:\/\//, ''),
                        line: typeof start === 'number' ? start : 0,
                    };
                });
            } catch {
                return [];
            }
        },
        jumpToLine: (line: number) => jumpTo(line),
        setValue: (text: string) => {
            // 保存 / 格式化后替换全文时保留当前滚动位置和大致光标位置；
            // 否则 CodeMirror 的整篇 replace 会把视口拉回第 1 行（用户实测 ✗）。
            const selection = view.state.selection.main;
            const scrollTop = view.scrollDOM.scrollTop;
            const anchor = Math.min(selection.anchor, text.length);
            const head = Math.min(selection.head, text.length);
            view.dispatch({
                changes: { from: 0, to: view.state.doc.length, insert: text },
                selection: { anchor, head },
            });
            view.scrollDOM.scrollTop = scrollTop;
        },
        focus: () => view.focus(),
        destroy: () => {
            try {
                view.destroy();
            } catch {
                /* ignore */
            }
        },
    };
}

/** 给 `code-editor.ts` 用的全局入口 ✓ */
(window as unknown as { DeskCodeEditor?: unknown }).DeskCodeEditor = {
    ready: true, mount,
};

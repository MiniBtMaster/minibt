/**
 * CodeEditor —— CodeMirror 6 的薄封装（**懒加载** ✓）
 *
 * `desk.js` 是 IIFE，没法在内部做代码分割 → 编辑器单独打成 `desk-editor.js`
 * （也是 IIFE，全局 `DeskCodeEditor`）。这里只做：
 *
 * 1. 第一次 `mount()` 时插 `<script src="./desk-editor.js?...">` 并等它 ready；
 * 2. 把 `mount / setValue / focus / destroy` 转发过去。
 *
 * 结果：首屏 `desk.js` 体积不变，没点开「代码」页签就**永远不下载**编辑器 ✓
 */

export interface CodeEditorOptions {
    parent: HTMLElement;
    value?: string;
    theme?: 'light' | 'dark';
    onChange?: (value: string) => void;
    onSave?: () => void;
    /** 文件绝对路径（LSP 的 documentUri ✓） */
    path?: string;
    /** LSP 服务地址（后端 `minibt/desk/lsp.py` 起在 127.0.0.1 随机端口）✓ */
    lsp?: { url: string; root: string };
    /** LSP 状态（编辑器状态栏显示 ✓） */
    onLspStatus?: (text: string, level?: 'ok' | 'error' | 'off') => void;
    /** 跨文件跳转（F12 / Ctrl+点击 命中别的文件 ✓） */
    onOpenLocation?: (path: string, line: number) => void;
    /** 光标位置（状态栏 行/列 ✓） */
    onCursor?: (line: number, column: number) => void;
}

interface EditorHandle {
    getValue(): string;
    setValue(text: string): void;
    focus(): void;
    destroy(): void;
    getSelection(): string;
    insert(text: string): void;
    selectAll(): void;
}

interface EditorBundle {
    ready?: boolean;
    mount: (spec: CodeEditorOptions) => EditorHandle;
}

declare global {
    interface Window {
        DeskCodeEditor?: EditorBundle;
        __deskEditorLoading?: Promise<EditorBundle>;
    }
}

/** 动态插 `<script>` 加载 `desk-editor.js`（只加载一次 ✓） */
function loadBundle(): Promise<EditorBundle> {
    if (window.DeskCodeEditor?.mount) {
        return Promise.resolve(window.DeskCodeEditor);
    }
    if (window.__deskEditorLoading) return window.__deskEditorLoading;
    const promise = new Promise<EditorBundle>((resolve, reject) => {
        const script = document.createElement('script');
        script.src = `./desk-editor.js?v=${Date.now().toString(36)}`;
        script.async = true;
        script.onload = () => {
            const bundle = window.DeskCodeEditor;
            if (bundle?.mount) resolve(bundle);
            else reject(new Error('desk-editor.js 加载了但没有挂上全局对象'));
        };
        script.onerror = () => reject(new Error('desk-editor.js 加载失败'));
        document.head.appendChild(script);
    });
    window.__deskEditorLoading = promise;
    return promise;
}

export class CodeEditor {
    /** 底层句柄（大纲 / 跳行 / 格式化要用 ✓，未 mount 时为 null） */
    public handle: EditorHandle | null = null;
    private loading: Promise<void> | null = null;
    private buffer: string;
    readonly options: CodeEditorOptions;

    constructor(options: CodeEditorOptions) {
        this.options = options;
        this.buffer = options.value || '';
    }

    /** 第一次调用才真正下载 / 初始化 CodeMirror ✓ */
    async mount(): Promise<void> {
        if (this.handle) return;
        if (this.loading) return this.loading;
        this.loading = (async () => {
            const bundle = await loadBundle();
            this.handle = bundle.mount({
                ...this.options,
                value: this.buffer,
            });
            this.buffer = '';
        })();
        return this.loading;
    }

    get value(): string {
        return this.handle ? this.handle.getValue() : this.buffer;
    }

    setValue(text: string): void {
        this.buffer = text;
        this.handle?.setValue(text);
    }

    focus(): void {
        this.handle?.focus();
    }

    /** 选中文本（右键剪切 / 复制 ✓） */
    getSelection(): string {
        return this.handle?.getSelection() || '';
    }

    /** 替换选区 / 插入（粘贴 ✓） */
    insert(text: string): void {
        this.handle?.insert(text);
    }

    selectAll(): void {
        this.handle?.selectAll();
    }

    /** 主题变了：内容保留，重建一个（CodeMirror 主题是编译进 extensions 的） */
    setTheme(theme: 'light' | 'dark'): void {
        if (this.options.theme === theme) return;
        const text = this.value;
        this.destroy();
        this.options.theme = theme;
        this.buffer = text;
        void this.mount();
    }

    destroy(): void {
        try {
            this.handle?.destroy();
        } catch {
            /* ignore */
        }
        this.handle = null;
        this.loading = null;
    }
}

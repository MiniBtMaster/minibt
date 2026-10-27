/**
 * LogPage —— 独立的「运行日志」页（顶栏 tab，从 `＋ 新建 ▾` 打开 ✓）
 *
 * 以前日志只能从看盘窗口 / 本地图表的底部面板看（要先打开图、再切「运行日志」），
 * 排查问题很不方便（用户要求 ✓）。现在：
 *
 * * **所有** `log` 补丁同时进这里（也照旧进底部面板，两处都能看 ✓）
 * * 打开页面时把**之前已经产生的日志**一起带过来（`app.ts` 里有个环形缓冲 ✓）
 * * 支持过滤 / 复制 / 清空 / 自动滚到底，级别用颜色区分
 */
import type { DeskTheme } from './theme';

export interface LogItem {
    text: string;
    level: string;
    ts?: string;
}

/** 最多保留多少条（和后端 / 底部面板一致 ✓） */
export const LOG_LIMIT = 800;

const STYLE_ID = 'desk-logpage-style';

const CSS = `
.desk-logpage {
    display: flex; flex-direction: column; height: 100%; width: 100%;
    background: var(--desk-bg); color: var(--desk-text);
    font-family: 'Cascadia Code', Consolas, 'Courier New', monospace;
    font-size: 12px;
}
.desk-logpage-bar {
    flex: 0 0 auto; display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; border-bottom: 1px solid var(--desk-border);
    background: var(--desk-panel);
    font-family: 'Segoe UI', Inter, Arial, sans-serif;
}
.desk-logpage-bar input {
    flex: 1 1 auto; height: 24px; padding: 0 8px; min-width: 0;
    border: 1px solid var(--desk-border); border-radius: 5px;
    background: var(--desk-bg); color: var(--desk-text); font-size: 12px;
}
.desk-logpage-bar input:focus { outline: none; border-color: var(--desk-accent); }
.desk-logpage-bar button {
    height: 24px; padding: 0 10px; border-radius: 5px; cursor: pointer;
    border: 1px solid var(--desk-border); background: var(--desk-bg);
    color: var(--desk-text); font-size: 12px;
}
.desk-logpage-bar button:hover { background: var(--desk-hover); }
.desk-logpage-bar .count { color: var(--desk-muted); font-size: 11.5px; }
.desk-logpage-list {
    flex: 1 1 auto; overflow: auto; padding: 4px 10px 10px;
    white-space: pre-wrap; word-break: break-word; line-height: 1.55;
}
.desk-logpage-line { padding: 1px 0; }
.desk-logpage-line .ts { color: var(--desk-muted); }
.desk-logpage-line.warning { color: #e0a030; }
.desk-logpage-line.error { color: var(--desk-up); }
.desk-logpage-line.success { color: var(--desk-down); }
.desk-logpage-empty { color: var(--desk-muted); padding: 16px 4px; }
`;

function ensureStyle(): void {
    if (document.getElementById(STYLE_ID)) return;
    const node = document.createElement('style');
    node.id = STYLE_ID;
    node.textContent = CSS;
    document.head.appendChild(node);
}

export class LogPage {
    public readonly element: HTMLDivElement;

    private readonly input: HTMLInputElement;
    private readonly list: HTMLDivElement;
    private readonly count: HTMLSpanElement;
    private items: LogItem[] = [];
    private theme: DeskTheme = 'dark';

    constructor(options: { theme: DeskTheme; items?: LogItem[] }) {
        ensureStyle();
        this.theme = options.theme === 'light' ? 'light' : 'dark';

        this.element = document.createElement('div');
        this.element.className = 'desk-logpage';
        this.element.classList.toggle('theme-light', this.theme === 'light');

        const bar = document.createElement('div');
        bar.className = 'desk-logpage-bar';
        this.input = document.createElement('input');
        this.input.placeholder = '过滤日志（关键字 / 级别：warning、error…）';
        this.input.title = '输入关键字过滤；清空恢复全部';
        this.input.addEventListener('input', () => this._applyFilter());
        this.count = document.createElement('span');
        this.count.className = 'count';
        const copy = document.createElement('button');
        copy.textContent = '复制';
        copy.title = '复制当前列表（过滤后的）到剪贴板';
        copy.addEventListener('click', () => this._copy());
        const clear = document.createElement('button');
        clear.textContent = '清空';
        clear.title = '清空本页日志（底部面板的日志不受影响）';
        clear.addEventListener('click', () => this.clear());
        bar.append(this.input, this.count, copy, clear);

        this.list = document.createElement('div');
        this.list.className = 'desk-logpage-list';

        this.element.append(bar, this.list);
        if (options.items && options.items.length) this.setItems(options.items);
        else this._render();
    }

    // ------------------------------------------------------------- 数据
    setItems(items: LogItem[]): void {
        this.items = (items || []).slice(-LOG_LIMIT);
        this._render();
    }

    append(text: string, level = 'info', ts = ''): void {
        if (!text) return;
        this.items.push({ text, level: level || 'info', ts });
        if (this.items.length > LOG_LIMIT) {
            this.items.splice(0, this.items.length - LOG_LIMIT);
        }
        const line = this._line(this.items[this.items.length - 1]);
        line.dataset.raw = `${ts ? `[${ts}] ` : ''}${text}`.toLowerCase();
        this.list.appendChild(line);
        while (this.list.childElementCount > LOG_LIMIT) {
            this.list.firstElementChild?.remove();
        }
        this._applyFilterTo(line);
        this._syncCount();
        const nearBottom = this.list.scrollHeight - this.list.scrollTop
            - this.list.clientHeight < 80;
        if (nearBottom) this.list.scrollTop = this.list.scrollHeight;
    }

    clear(): void {
        this.items = [];
        this._render();
    }

    show(): void { this.element.style.display = 'flex'; }

    hide(): void { this.element.style.display = 'none'; }

    setTheme(theme: DeskTheme): void {
        this.theme = theme === 'light' ? 'light' : 'dark';
        this.element.classList.toggle('theme-light', this.theme === 'light');
    }

    // ------------------------------------------------------------- 内部
    private _line(item: LogItem): HTMLDivElement {
        const line = document.createElement('div');
        line.className = `desk-logpage-line ${item.level || 'info'}`;
        const ts = document.createElement('span');
        ts.className = 'ts';
        ts.textContent = item.ts ? `[${item.ts}] ` : '';
        const text = document.createElement('span');
        text.textContent = item.text;
        line.append(ts, text);
        return line;
    }

    private _render(): void {
        this.list.textContent = '';
        if (!this.items.length) {
            const empty = document.createElement('div');
            empty.className = 'desk-logpage-empty';
            empty.textContent = '（还没有日志）';
            this.list.appendChild(empty);
            this._syncCount();
            return;
        }
        const frag = document.createDocumentFragment();
        for (const item of this.items) {
            const line = this._line(item);
            line.dataset.raw = `${item.ts ? `[${item.ts}] ` : ''}${item.text}`
                .toLowerCase();
            frag.appendChild(line);
        }
        this.list.appendChild(frag);
        this._applyFilter();
        this.list.scrollTop = this.list.scrollHeight;
        this._syncCount();
    }

    private _applyFilter(): void {
        this.list.querySelectorAll<HTMLElement>('.desk-logpage-line')
            .forEach((line) => this._applyFilterTo(line));
        this._syncCount();
    }

    private _applyFilterTo(line: HTMLElement): void {
        const needle = this.input.value.trim().toLowerCase();
        line.style.display = !needle
            || (line.dataset.raw || line.textContent || '').toLowerCase()
                .includes(needle) ? '' : 'none';
    }

    private _syncCount(): void {
        const visible = Array.from(
            this.list.querySelectorAll<HTMLElement>('.desk-logpage-line'))
            .filter((line) => line.style.display !== 'none').length;
        this.count.textContent = `共 ${this.items.length} 条`
            + (visible !== this.items.length ? ` · 显示 ${visible}` : '');
    }

    private _copy(): void {
        const lines = Array.from(
            this.list.querySelectorAll<HTMLElement>('.desk-logpage-line'))
            .filter((line) => line.style.display !== 'none')
            .map((line) => line.textContent || '');
        const text = lines.join('\n');
        const nav = navigator as unknown as { clipboard?: { writeText?: Function } };
        if (nav.clipboard?.writeText) {
            void nav.clipboard.writeText(text);
            return;
        }
        const area = document.createElement('textarea');
        area.value = text;
        document.body.appendChild(area);
        area.select();
        try { document.execCommand('copy'); } catch { /* ignore */ }
        area.remove();
    }
}

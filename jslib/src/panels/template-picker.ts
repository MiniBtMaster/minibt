/**
 * TemplatePicker — 「指标模板」对话框（复刻 miniqt 的模板列表）。
 *
 *   ┌ 指标模板                                  ✕ ┐
 *   │ [搜索]                                      │
 *   │ 个人     │ pta_adx           1 个指标       │
 *   │  我的模板 │ pandas_adx        1 个指标       │
 *   │ 内置     │                                 │
 *   │  技术指标 │                                 │
 *   │  财务指标 │                                 │
 *   │ 🗑                                            │
 *   └────────────────────────────────────────────┘
 *
 * 事件（``;;;`` 分隔）：``apply;;;<key>`` / ``delete;;;<key>`` /
 * ``save``（保存当前图为模板）。
 */
import { emitCallback, ensureStyle } from './emit';

export interface TemplateItem {
    key: string;
    name: string;
    count?: number;
    items?: Array<Record<string, unknown>>;
}

export interface TemplatePickerOptions {
    groups?: Array<{ key: string; label: string; sections: Array<{ key: string; label: string }> }>;
    templates?: TemplateItem[];
    theme?: 'light' | 'dark';
    callbackName?: string | null;
}

const STYLE_ID = 'pylightcharts-templatepicker-style';

/**
 * 模板参数摘要：`MA(length=20) · MACD(fast=12, slow=26)` ✓
 *
 * 有 `paramMeta` 时把**参数区间**也带上（`length=20[1~200/1]`），
 * 直接作为参数优化入口的参考 ✓
 */
export function summarizeParams(items: Array<Record<string, unknown>>): string {
    const parts: string[] = [];
    for (const item of items) {
        const params = (item.params || {}) as Record<string, unknown>;
        const meta = (item.paramMeta || {}) as Record<string, Record<string, unknown>>;
        const names = Object.keys(params);
        if (!names.length) continue;
        parts.push(`${String(item.key || '')}(${names
            .map((name) => {
                const range = meta[name];
                const suffix = range && range.min !== undefined
                    ? `[${range.min}~${range.max}/${range.step ?? 1}]` : '';
                return `${name}=${String(params[name])}${suffix}`;
            }).join(', ')})`);
    }
    return parts.slice(0, 3).join(' · ');
}

function esc(value: unknown): string {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

const CSS = `
.pylc-tp-mask{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:11800;
  display:flex;align-items:center;justify-content:center}
.pylc-tp{width:780px;height:560px;max-height:86vh;display:flex;flex-direction:column;
  border-radius:10px;overflow:hidden;background:var(--tp-bg);color:var(--tp-text);
  border:1px solid var(--tp-border);box-shadow:0 20px 60px rgba(0,0,0,.45)}
.pylc-tp-head{display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px;font-size:15px;font-weight:600}
.pylc-tp-close{border:none;background:transparent;color:var(--tp-text);
  cursor:pointer;font-size:17px}
.pylc-tp-search-wrap{padding:0 16px 10px}
.pylc-tp-search{width:100%;height:30px;padding:0 10px;border-radius:6px;outline:none;
  border:1px solid var(--tp-border);background:var(--tp-input);color:var(--tp-text);
  font-size:12.5px}
.pylc-tp-body{flex:1;min-height:0;display:flex;border-top:1px solid var(--tp-border)}
.pylc-tp-tree{flex:0 0 190px;overflow:auto;padding:8px 0;
  border-right:1px solid var(--tp-border)}
.pylc-tp-group{padding:6px 14px 2px;color:var(--tp-accent);font-size:12px}
.pylc-tp-section{padding:5px 14px;cursor:pointer;font-size:12.5px;white-space:nowrap}
.pylc-tp-section:hover{background:var(--tp-hover)}
.pylc-tp-section.on{background:var(--tp-active);font-weight:600}
.pylc-tp-list{flex:1;min-width:0;overflow:auto;position:relative}
.pylc-tp-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;
  padding:9px 16px;cursor:pointer;border-bottom:1px solid var(--tp-border);font-size:12.5px}
.pylc-tp-row:hover{background:var(--tp-hover)}
.pylc-tp-row.on{background:var(--tp-active)}
.pylc-tp-count{color:var(--tp-muted);font-size:11.5px;white-space:nowrap}
.pylc-tp-params{color:var(--tp-muted);font-size:11px;margin-top:2px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:420px}
.pylc-tp-gear{border:none;background:transparent;color:var(--tp-muted);
  cursor:pointer;font-size:12px;margin-left:6px}
.pylc-tp-gear:hover{color:var(--tp-text)}
.pylc-tp-empty{padding:18px 16px;color:var(--tp-muted);font-size:12.5px}
.pylc-tp-foot{display:flex;align-items:center;gap:8px;padding:10px 16px;
  border-top:1px solid var(--tp-border)}
.pylc-tp-del{border:1px solid var(--tp-border);background:transparent;
  color:var(--tp-text);border-radius:6px;height:28px;min-width:34px;cursor:pointer}
.pylc-tp-del:disabled{opacity:.4;cursor:not-allowed}
.pylc-tp-spacer{flex:1}
.pylc-tp-btn{height:28px;padding:0 14px;border-radius:6px;cursor:pointer;
  border:1px solid var(--tp-border);background:transparent;color:var(--tp-text);
  font-size:12.5px}
.pylc-tp-btn.primary{background:var(--tp-accent);border-color:var(--tp-accent);
  color:#fff}
`;

const PALS = {
    dark: {
        bg: '#161a20', text: '#d8d9db', muted: '#8b93a1', border: '#262c36',
        input: '#0f1115', hover: '#1e242d', active: '#263041', accent: '#4c8dff',
    },
    light: {
        bg: '#ffffff', text: '#1f2329', muted: '#6b7280', border: '#e3e6ea',
        input: '#f6f7f9', hover: '#eef1f5', active: '#e6efff', accent: '#1a73e8',
    },
};

export class TemplatePicker {
    public readonly element: HTMLDivElement;
    public callbackName: string | null = null;
    public onApplyCallback: ((item: TemplateItem) => void) | null = null;
    public onDeleteCallback: ((key: string) => void) | null = null;
    public onSaveCallback: ((name: string) => void) | null = null;
    /** ✎ 编辑模板里各指标参数（参数区间 ✓） */
    public onEditCallback: ((row: TemplateItem) => void) | null = null;

    private readonly tree: HTMLDivElement;
    private readonly list: HTMLDivElement;
    private readonly search: HTMLInputElement;
    private readonly deleteButton: HTMLButtonElement;
    private templates: TemplateItem[] = [];
    private groups: TemplatePickerOptions['groups'] = [];
    private section = 'my_templates';
    private selected: string | null = null;

    constructor(options: TemplatePickerOptions = {}) {
        ensureStyle(STYLE_ID, CSS);
        this.callbackName = options.callbackName || null;
        this.groups = options.groups || [
            { key: 'personal', label: '个人',
              sections: [{ key: 'my_templates', label: '我的模板' }] },
            { key: 'builtin', label: '内置',
              sections: [{ key: 'tech', label: '技术指标' },
                         { key: 'finance', label: '财务指标' }] },
        ];
        this.templates = options.templates || [];

        this.element = document.createElement('div');
        this.element.className = 'pylc-tp-mask';
        this.element.style.display = 'none';

        const box = document.createElement('div');
        box.className = 'pylc-tp';

        const head = document.createElement('div');
        head.className = 'pylc-tp-head';
        head.innerHTML = '<span>指标模板</span>';
        const close = document.createElement('button');
        close.className = 'pylc-tp-close';
        close.textContent = '✕';
        close.title = '关闭';
        close.addEventListener('click', () => this.close());
        head.appendChild(close);

        const searchWrap = document.createElement('div');
        searchWrap.className = 'pylc-tp-search-wrap';
        this.search = document.createElement('input');
        this.search.className = 'pylc-tp-search';
        this.search.placeholder = '搜索';
        this.search.title = '按模板名搜索';
        this.search.addEventListener('input', () => this._render());
        searchWrap.appendChild(this.search);

        this.tree = document.createElement('div');
        this.tree.className = 'pylc-tp-tree';
        this.list = document.createElement('div');
        this.list.className = 'pylc-tp-list';
        const body = document.createElement('div');
        body.className = 'pylc-tp-body';
        body.append(this.tree, this.list);

        const foot = document.createElement('div');
        foot.className = 'pylc-tp-foot';
        this.deleteButton = document.createElement('button');
        this.deleteButton.className = 'pylc-tp-del';
        this.deleteButton.textContent = '🗑';
        this.deleteButton.title = '删除选中的模板';
        this.deleteButton.disabled = true;
        this.deleteButton.addEventListener('click', () => {
            if (!this.selected) return;
            emitCallback(this.callbackName, `delete;;;${this.selected}`);
            this.onDeleteCallback?.(this.selected);
            this.templates = this.templates.filter(
                (item) => item.key !== this.selected);
            this.selected = null;
            this._render();
        });
        const spacer = document.createElement('span');
        spacer.className = 'pylc-tp-spacer';
        const save = document.createElement('button');
        save.className = 'pylc-tp-btn';
        save.textContent = '保存当前指标为模板';
        save.title = '把当前图表上的指标保存成一个模板';
        save.addEventListener('click', () => {
            const name = window.prompt('模板名称', this._defaultName());
            if (!name) return;
            emitCallback(this.callbackName, `save;;;${name}`);
            this.onSaveCallback?.(name);
        });
        const cancel = document.createElement('button');
        cancel.className = 'pylc-tp-btn';
        cancel.textContent = '关闭';
        cancel.addEventListener('click', () => this.close());
        foot.append(this.deleteButton, spacer, save, cancel);

        box.append(head, searchWrap, body, foot);
        this.element.appendChild(box);
        this.element.addEventListener('mousedown', (event) => {
            if (event.target === this.element) this.close();
        });
        document.body.appendChild(this.element);

        this.setTheme(options.theme === 'light' ? 'light' : 'dark');
        this._renderTree();
        this._render();
    }

    // ------------------------------------------------------------- 数据
    setTemplates(templates: TemplateItem[]): void {
        this.templates = templates || [];
        this._render();
    }

    setTheme(theme: 'light' | 'dark'): void {
        const pal = PALS[theme === 'light' ? 'light' : 'dark'];
        for (const [key, value] of Object.entries(pal)) {
            this.element.style.setProperty(`--tp-${key}`, value);
        }
    }

    open(): void {
        this.element.style.display = '';
        this.search.value = '';
        this._render();
        this.search.focus();
    }

    close(): void {
        this.element.style.display = 'none';
    }

    get visible(): boolean {
        return this.element.style.display !== 'none';
    }

    // ------------------------------------------------------------- 内部
    private _defaultName(): string {
        const now = new Date();
        const pad = (value: number) => String(value).padStart(2, '0');
        return `模板 ${pad(now.getMonth() + 1)}-${pad(now.getDate())} `
            + `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    }

    private _renderTree(): void {
        this.tree.textContent = '';
        for (const group of this.groups || []) {
            const title = document.createElement('div');
            title.className = 'pylc-tp-group';
            title.textContent = group.label;
            this.tree.appendChild(title);
            for (const section of group.sections) {
                const row = document.createElement('div');
                row.className = 'pylc-tp-section'
                    + (section.key === this.section ? ' on' : '');
                row.textContent = section.label;
                row.addEventListener('click', () => {
                    this.section = section.key;
                    this._renderTree();
                    this._render();
                });
                this.tree.appendChild(row);
            }
        }
    }

    private _render(): void {
        const needle = this.search.value.trim().toLowerCase();
        this.list.textContent = '';
        this.deleteButton.disabled = !this.selected;
        if (this.section !== 'my_templates') {
            const empty = document.createElement('div');
            empty.className = 'pylc-tp-empty';
            empty.textContent = '（内置模板暂未提供）';
            this.list.appendChild(empty);
            return;
        }
        const rows = this.templates.filter((item) => !needle
            || item.name.toLowerCase().includes(needle));
        if (!rows.length) {
            const empty = document.createElement('div');
            empty.className = 'pylc-tp-empty';
            empty.textContent = '（还没有模板：先加指标，再点下方「保存当前指标为模板」）';
            this.list.appendChild(empty);
            return;
        }
        for (const item of rows) {
            const row = document.createElement('div');
            row.className = 'pylc-tp-row'
                + (this.selected === item.key ? ' on' : '');
            const params = summarizeParams(item.items || []);
            const left = document.createElement('span');
            left.innerHTML = `<span>${esc(item.name)}</span>`
                + (params
                    ? `<div class="pylc-tp-params" title="${esc(params)}">`
                      + `${esc(params)}</div>` : '');
            const right = document.createElement('span');
            right.className = 'pylc-tp-count';
            right.textContent = `${item.count ?? 0} 个指标`;
            if (params) {
                const gear = document.createElement('button');
                gear.className = 'pylc-tp-gear';
                gear.textContent = '✎';
                gear.title = '编辑这个模板的指标参数';
                gear.addEventListener('click', (event) => {
                    event.stopPropagation();
                    this.onEditCallback?.(item);
                });
                right.appendChild(gear);
            }
            row.append(left, right);
            row.title = '点击应用这个模板（替换当前图上的指标）';
            row.addEventListener('click', () => {
                this.selected = item.key;
                this._render();
                emitCallback(this.callbackName, `apply;;;${item.key}`);
                this.onApplyCallback?.(item);
                this.close();
            });
            this.list.appendChild(row);
        }
    }
}

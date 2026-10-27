/**
 * FilterBar — the chip bar for the Screener: active conditions as removable
 * chips, an optional inline "add condition" form, and a clear button.
 *
 * On every change it reports the **full filter list** to Python (base64 JSON, so
 * no separator in the data can break the bridge message).
 */

import { emitCallback, ensureStyle } from './emit';

export interface FilterChip {
    column: string;
    op: string;
    value: string | number;
}

export interface FilterBarTheme {
    background?: string;
    text?: string;
    muted?: string;
    border?: string;
    chip?: string;
    hover?: string;
    accent?: string;
    negative?: string;
}

export interface FilterBarOptions {
    filters?: FilterChip[];
    columns?: string[];
    operators?: string[];
    editable?: boolean;
    clearLabel?: string;
    addLabel?: string;
    theme?: FilterBarTheme;
    onChange?: (filters: FilterChip[]) => void;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    border: string;
    chip: string;
    hover: string;
    accent: string;
    negative: string;
}

const OPERATORS = ['>', '>=', '<', '<=', '==', '!=', 'contains', 'in'];

const STYLE_ID = 'pylightcharts-filterbar-style';
const CSS = `
.pylc-filterbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:6px 8px;
  background:var(--fb-bg);border-bottom:1px solid var(--fb-border);color:var(--fb-text);
  font-size:12px;flex:0 0 auto;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif}
.pylc-fb-chip{display:inline-flex;align-items:center;gap:6px;background:var(--fb-chip);
  border:1px solid var(--fb-border);border-radius:12px;padding:2px 8px;white-space:nowrap}
.pylc-fb-chip .x{cursor:pointer;color:var(--fb-muted);font-weight:700;line-height:1}
.pylc-fb-chip .x:hover{color:var(--fb-negative)}
.pylc-fb-add{display:inline-flex;align-items:center;gap:4px}
.pylc-fb-add select,.pylc-fb-add input{background:var(--fb-bg);color:var(--fb-text);
  border:1px solid var(--fb-border);border-radius:4px;padding:2px 5px;font-size:12px;outline:none}
.pylc-fb-add input{width:80px}
.pylc-fb-btn{background:transparent;border:1px solid var(--fb-border);border-radius:4px;
  color:var(--fb-text);padding:2px 8px;cursor:pointer;font-size:12px;font-family:inherit}
.pylc-fb-btn:hover{background:var(--fb-hover)}
.pylc-fb-empty{color:var(--fb-muted)}
.pylc-stack>.pylc-filterbar{flex:0 0 auto}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

function encodeFilters(filters: FilterChip[]): string {
    const json = JSON.stringify(filters);
    const bytes = new TextEncoder().encode(json);
    let binary = '';
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    return btoa(binary);
}

export class FilterBar {
    public callbackName: string | null = null;
    public readonly element: HTMLDivElement;

    private _filters: FilterChip[] = [];
    private _columns: string[] = [];
    private _operators: string[];
    private _editable: boolean;
    private _clearLabel: string;
    private _addLabel: string;
    private _theme: ResolvedTheme;
    private _onChange?: (filters: FilterChip[]) => void;

    constructor(options: FilterBarOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._columns = options.columns ?? [];
        this._operators = options.operators ?? OPERATORS.slice();
        this._editable = options.editable ?? false;
        this._clearLabel = options.clearLabel ?? '清除';
        this._addLabel = options.addLabel ?? '添加';
        this._theme = this._resolveTheme(options.theme ?? {});
        this._onChange = options.onChange;

        this.element = document.createElement('div');
        this.element.className = 'pylc-filterbar';
        this._applyThemeVars();
        (parent ?? defaultContainer()).appendChild(this.element);
        this.setFilters(options.filters ?? []);
    }

    setFilters(filters: FilterChip[]): void {
        this._filters = (filters ?? []).map((filter) => ({
            column: String(filter.column),
            op: String(filter.op),
            value: filter.value,
        }));
        this._render();
    }

    getFilters(): FilterChip[] {
        return this._filters.map((filter) => ({ ...filter }));
    }

    setColumns(columns: string[]): void {
        this._columns = columns ?? [];
        this._render();
    }

    setOptions(options: Partial<FilterBarOptions>): void {
        if (options.columns) this._columns = options.columns;
        if (options.operators) this._operators = options.operators;
        if (options.editable !== undefined) this._editable = options.editable;
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        this._render();
    }

    destroy(): void {
        this.element.remove();
    }

    // --------------------------------------------------------------- internal
    private _resolveTheme(theme: FilterBarTheme): ResolvedTheme {
        return {
            background: theme.background ?? '#1e222d',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            chip: theme.chip ?? '#2a2e39',
            hover: theme.hover ?? '#363a45',
            accent: theme.accent ?? '#2962ff',
            negative: theme.negative ?? '#ef5350',
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--fb-bg', this._theme.background);
        style.setProperty('--fb-text', this._theme.text);
        style.setProperty('--fb-muted', this._theme.muted);
        style.setProperty('--fb-border', this._theme.border);
        style.setProperty('--fb-chip', this._theme.chip);
        style.setProperty('--fb-hover', this._theme.hover);
        style.setProperty('--fb-accent', this._theme.accent);
        style.setProperty('--fb-negative', this._theme.negative);
    }

    private _render(): void {
        this.element.textContent = '';
        if (this._filters.length === 0) {
            const empty = document.createElement('span');
            empty.className = 'pylc-fb-empty';
            empty.textContent = '无条件';
            this.element.appendChild(empty);
        }
        this._filters.forEach((filter, index) => {
            const chip = document.createElement('span');
            chip.className = 'pylc-fb-chip';
            const text = document.createElement('span');
            text.textContent = `${filter.column} ${filter.op} ${filter.value}`;
            chip.appendChild(text);
            const close = document.createElement('span');
            close.className = 'x';
            close.textContent = '×';
            close.addEventListener('click', () => {
                this._filters.splice(index, 1);
                this._render();
                this._emit();
            });
            chip.appendChild(close);
            this.element.appendChild(chip);
        });

        if (this._editable) {
            this.element.appendChild(this._makeAdder());
        }
        if (this._filters.length > 0) {
            const clear = document.createElement('button');
            clear.className = 'pylc-fb-btn';
            clear.textContent = this._clearLabel;
            clear.addEventListener('click', () => {
                this._filters = [];
                this._render();
                this._emit();
            });
            this.element.appendChild(clear);
        }
    }

    private _makeAdder(): HTMLDivElement {
        const adder = document.createElement('div');
        adder.className = 'pylc-fb-add';
        adder.addEventListener('click', (event) => event.stopPropagation());

        const column = document.createElement('select');
        for (const name of (this._columns.length ? this._columns : ['column'])) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            column.appendChild(option);
        }
        const op = document.createElement('select');
        for (const name of this._operators) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            op.appendChild(option);
        }
        const value = document.createElement('input');
        value.type = 'text';
        value.placeholder = '值';
        const add = document.createElement('button');
        add.className = 'pylc-fb-btn';
        add.textContent = this._addLabel;
        const commit = (): void => {
            const raw = value.value.trim();
            if (raw === '') {
                return;
            }
            const number = Number(raw);
            this._filters.push({
                column: column.value,
                op: op.value,
                value: Number.isFinite(number) && raw !== '' ? number : raw,
            });
            this._render();
            this._emit();
        };
        add.addEventListener('click', commit);
        value.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                commit();
            }
        });

        adder.appendChild(column);
        adder.appendChild(op);
        adder.appendChild(value);
        adder.appendChild(add);
        return adder;
    }

    private _emit(): void {
        if (this.callbackName) {
            emitCallback(this.callbackName, encodeFilters(this._filters));
            return;
        }
        if (this._onChange) {
            this._onChange(this.getFilters());
        }
    }
}

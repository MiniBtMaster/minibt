/**
 * DataGrid — a themed, sortable, filterable, virtualised data table.
 *
 * It is the shared primitive behind the TradingView-style market widgets
 * (Market Data, Watchlist, Screener, ...). Compared to `Lib.Table` it adds:
 *
 *   - declarative columns (`{key, title, type, colorBy, ...}`);
 *   - click-to-sort headers and a search box;
 *   - **virtual scrolling** - only the visible rows exist in the DOM, so a
 *     watchlist of 5000 instruments stays smooth;
 *   - per-cell formatters (number / percent / change / 万·亿) and sign colours;
 *   - an inline `Sparkline` cell type;
 *   - row click / double-click callbacks routed through the Python bridge.
 *
 * Python drives it through the generic bridge:
 *
 *   grid = new Lib.DataGrid({...});        // window.<id> = ...
 *   Lib.invoke('window.<id>', 'setRows', [rows]);
 *   grid.callbackName = 'window.<id>';     // row callbacks -> python handlers
 */

import { Sparkline } from './sparkline';
import type { SparklineOptions } from './sparkline';

export type DataGridAlign = 'left' | 'center' | 'right';
export type DataGridColumnType =
    'text' | 'number' | 'percent' | 'change' | 'spark' | 'action';

/** 行内动作按钮（`type: 'action'`）✓ */
export interface DataGridAction {
    /** 按钮文字（按行算，`★` / `☆` ✓） */
    text: (row: RowData) => string;
    /** tooltip（可选） */
    title?: (row: RowData) => string;
    /** 附加 class（`on` = 已收藏 ✓） */
    className?: (row: RowData) => string;
    /** 点击（已阻止冒泡，不会触发行点击 ✓） */
    run: (row: RowData) => void;
}
export type DataGridColorBy = 'sign' | 'none';
export type DataGridColorScheme = 'cn' | 'tv';

export interface DataGridColumn {
    key: string;
    title?: string;
    /** flex grow weight (default 1) */
    width?: number;
    align?: DataGridAlign;
    type?: DataGridColumnType;
    decimals?: number;
    /**
     * **按行**取小数位（每个合约 `price_tick` 不同 → 3 位 / 2 位 / 0 位 ✓）。
     * 返回 `undefined` 时退回 `decimals`。
     */
    decimalsOf?: (row: RowData) => number | undefined;
    /** show up to `decimals` places but strip trailing zeros (e.g. prices) */
    trim?: boolean;
    colorBy?: DataGridColorBy;
    visible?: boolean;
    sortable?: boolean;
    prefix?: string;
    suffix?: string;
    /** render large numbers as 万 / 亿 (Chinese futures convention) */
    compact?: boolean;
    /** map a cell value to an explicit colour (e.g. importance: 高/中/低) */
    colors?: Record<string, string>;
    /** options forwarded to the inline Sparkline for `type: 'spark'` */
    spark?: SparklineOptions;
    /** 这一列在 CSV 里用别的小数位（`decimals` 列本身就用 0 ✓） */
    csvDecimals?: number;
    /** `type: 'action'` 的行内按钮（收藏 ★ / 删除 … ✓） */
    action?: DataGridAction;
}

export interface DataGridTheme {
    background?: string;
    headerBackground?: string;
    headerText?: string;
    text?: string;
    muted?: string;
    border?: string;
    rowHover?: string;
    striped?: string;
    gridLine?: string;
    scrollbar?: string;
    accent?: string;
    positive?: string;
    negative?: string;
}

export interface DataGridOptions {
    /**
     * 宿主接管导出（Qt 里落盘到 `~/.minibt/exports/` ✓）。
     *
     * 返回 `true` = 已处理（不再走浏览器下载）；没设 / 返回假 → 走 Blob 下载
     * （静态 `minibt-charts` 导出目录里没有后端时 ✓）
     */
    onExport?: (filename: string, text: string) => boolean | void;
    /**
     * CSV **专用列**（默认用当前可见列）；报价页会多带一列 `decimals`，
     * 方便把导出的表直接拿去二次计算 ✓
     */
    exportColumns?: DataGridColumn[];
    columns?: DataGridColumn[];
    /** field that uniquely identifies a row (default `'symbol'`) */
    rowKey?: string;
    rowHeight?: number;
    headerHeight?: number;
    /** cell font size (px); the row height should be set to match (default 12) */
    fontSize?: number;
    searchable?: boolean;
    /** `'cn'` = red up / green down (default), `'tv'` = green up / red down */
    colorScheme?: DataGridColorScheme;
    theme?: DataGridTheme;
    striped?: boolean;
    emptyText?: string;
    onRowClick?: (key: string, row: RowData) => void;
    onRowDoubleClick?: (key: string, row: RowData) => void;
}

export type RowData = Record<string, unknown>;

interface ResolvedTheme {
    background: string;
    headerBackground: string;
    headerText: string;
    text: string;
    muted: string;
    border: string;
    rowHover: string;
    striped: string;
    gridLine: string;
    scrollbar: string;
    accent: string;
    positive: string;
    negative: string;
}

const STYLE_ID = 'pylightcharts-datagrid-style';

const CSS = `
.pylc-dg{display:flex;flex-direction:column;height:100%;width:100%;background:var(--dg-bg);
  color:var(--dg-text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",
  Roboto,Arial,sans-serif;font-size:12px;font-variant-numeric:tabular-nums;overflow:hidden}
.pylc-dg-toolbar{display:flex;align-items:center;gap:8px;padding:6px 8px;
  border-bottom:1px solid var(--dg-border);flex:0 0 auto}
.pylc-dg-search{flex:1;min-width:0;background:var(--dg-header);border:1px solid var(--dg-border);
  color:var(--dg-text);border-radius:4px;padding:4px 8px;font-size:12px;outline:none}
.pylc-dg-search:focus{border-color:var(--dg-accent)}
.pylc-dg-count{color:var(--dg-muted);font-size:11px;white-space:nowrap}
.pylc-dg-export{height:22px;padding:0 9px;border-radius:4px;cursor:pointer;
  border:1px solid var(--dg-border);background:var(--dg-header);color:var(--dg-text);
  font-size:11.5px}
.pylc-dg-export:hover{border-color:var(--dg-accent);color:var(--dg-accent)}
.pylc-dg-body{position:relative;flex:1;min-height:0;overflow-y:auto;overflow-x:hidden}
.pylc-dg-head{position:sticky;top:0;z-index:2;display:flex;background:var(--dg-header);
  border-bottom:1px solid var(--dg-border)}
.pylc-dg-th{padding:0 8px;height:var(--dg-header-h);display:flex;align-items:center;gap:4px;
  color:var(--dg-header-text);font-weight:600;font-size:11.5px;letter-spacing:.02em;cursor:pointer;
  user-select:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pylc-dg-th:hover{color:var(--dg-text)}
.pylc-dg-th-arrow{font-size:9px;opacity:.35}
.pylc-dg-th.sorted{color:var(--dg-text)}
.pylc-dg-th.sorted .pylc-dg-th-arrow{opacity:1;color:var(--dg-accent)}
.pylc-dg-content{position:relative;width:100%}
.pylc-dg-row{position:absolute;left:0;right:0;top:0;display:flex;align-items:center;
  border-bottom:1px solid var(--dg-grid);cursor:default}
.pylc-dg-row.striped{background:var(--dg-striped)}
.pylc-dg-row:hover{background:var(--dg-hover)}
.pylc-dg-cell{padding:0 8px;height:100%;display:flex;align-items:center;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pylc-dg-cell>.pylc-sparkline{display:block}
.pylc-dg-spark{justify-content:center}
/* 行内动作按钮（★ 收藏 / 删除 …）✓ */
.pylc-dg-action-cell{justify-content:center}
.pylc-dg-action{
    border:0;background:transparent;cursor:pointer;padding:0 2px;
    font-size:13px;line-height:1;color:var(--dg-muted);
}
.pylc-dg-action:hover{color:#f5b301;transform:scale(1.15)}
.pylc-dg-action.on{color:#f5b301}
.pylc-dg-empty{padding:24px;text-align:center;color:var(--dg-muted)}
.pylc-dg-body::-webkit-scrollbar{width:10px;height:10px}
.pylc-dg-body::-webkit-scrollbar-thumb{background:var(--dg-scrollbar);border-radius:5px}
.pylc-dg-body::-webkit-scrollbar-track{background:transparent}
/* composite panels (MarketData = Tabs + DataGrid): the grid flexes under the bar */
.pylc-stack{display:flex;flex-direction:column;height:100%;width:100%;min-height:0}
.pylc-stack>.pylc-tabs{flex:0 0 auto}
.pylc-stack>.pylc-dg{height:auto;flex:1 1 auto;min-height:0}
`;

function ensureStyle(): void {
    if (document.getElementById(STYLE_ID)) {
        return;
    }
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
}

function defaultAlign(column: DataGridColumn): DataGridAlign {
    if (column.align) {
        return column.align;
    }
    if (column.type === 'number' || column.type === 'percent' || column.type === 'change') {
        return 'right';
    }
    return 'left';
}

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class DataGrid {
    /** set by the Python wrapper; row events are reported under this name */
    public callbackName: string | null = null;
    public readonly element: HTMLDivElement;

    private _options: DataGridOptions;
    private _columns: DataGridColumn[] = [];
    private _rows = new Map<string, RowData>();
    private _view: RowData[] = [];
    private _rowKey: string;
    private _rowHeight: number;
    private _headerHeight: number;
    private _scheme: DataGridColorScheme;
    private _theme: ResolvedTheme;
    private _striped: boolean;
    private _emptyText: string;

    private _sortKey: string | null = null;
    private _sortDir = 1;
    private _filter = '';

    private _body!: HTMLDivElement;
    private _head!: HTMLDivElement;
    private _content!: HTMLDivElement;
    private _empty!: HTMLDivElement;
    private _countEl: HTMLSpanElement | null = null;
    private _exportButton: HTMLButtonElement | null = null;
    private _exportHook: ((filename: string, text: string) => boolean | void)
        | null = null;
    private _rendered = new Map<number, HTMLDivElement>();
    private _sparks = new WeakMap<HTMLDivElement, Map<string, Sparkline>>();

    constructor(options: DataGridOptions = {}, parent?: HTMLElement | null) {
        ensureStyle();
        this._options = options;
        this._rowKey = options.rowKey ?? 'symbol';
        this._rowHeight = options.rowHeight ?? 26;
        this._headerHeight = options.headerHeight ?? 28;
        this._scheme = options.colorScheme ?? 'cn';
        this._striped = options.striped ?? true;
        this._emptyText = options.emptyText ?? '暂无数据';
        this._theme = this._resolveTheme(options.theme ?? {});
        this._exportHook = options.onExport ?? null;

        this.element = document.createElement('div');
        this.element.className = 'pylc-dg';
        if (options.fontSize) {
            this.element.style.fontSize = `${options.fontSize}px`;
        }
        this._applyThemeVars();

        if (options.searchable !== false) {
            this._buildToolbar();
        }
        this._body = document.createElement('div');
        this._body.className = 'pylc-dg-body';
        this._head = document.createElement('div');
        this._head.className = 'pylc-dg-head';
        this._content = document.createElement('div');
        this._content.className = 'pylc-dg-content';
        this._empty = document.createElement('div');
        this._empty.className = 'pylc-dg-empty';
        this._empty.textContent = this._emptyText;
        this._empty.style.display = 'none';

        this._body.appendChild(this._head);
        this._body.appendChild(this._content);
        this._body.appendChild(this._empty);
        this.element.appendChild(this._body);

        this._body.addEventListener('scroll', () => this._renderWindow());

        const target = parent ?? defaultContainer();
        target.appendChild(this.element);

        if (options.columns) {
            this.setColumns(options.columns);
        }
    }

    // ---------------------------------------------------------------- public
    setColumns(columns: DataGridColumn[]): void {
        this._columns = columns.filter((column) => column.visible !== false);
        this._buildHead();
        this._rebuild();
    }

    setRows(rows: RowData[]): void {
        this._rows.clear();
        rows.forEach((row, index) => this._rows.set(this._keyOf(row, index), row));
        this._rebuild();
    }

    appendRows(rows: RowData[]): void {
        rows.forEach((row, index) => this._rows.set(this._keyOf(row, this._rows.size + index), row));
        this._rebuild();
    }

    updateRow(row: RowData): void {
        const key = this._keyOf(row, this._rows.size);
        if (this._rows.has(key)) {
            this._rows.set(key, row);
            this._rebuild();
        }
    }

    updateRows(rows: RowData[]): void {
        for (const row of rows) {
            this._rows.set(this._keyOf(row, this._rows.size), row);
        }
        this._rebuild();
    }

    deleteRow(key: string): void {
        if (this._rows.delete(key)) {
            this._rebuild();
        }
    }

    setCell(key: string, column: string, value: unknown): void {
        const row = this._rows.get(key);
        if (!row) {
            return;
        }
        row[column] = value;
        this._rebuild();
    }

    clear(): void {
        this._rows.clear();
        this._rebuild();
    }

    setFilter(text: string): void {
        this._filter = text.trim().toLowerCase();
        this._rebuild();
    }

    sort(column: string | null, direction: 1 | -1 = 1): void {
        this._sortKey = column;
        this._sortDir = direction;
        this._rebuild();
    }

    setOptions(options: Partial<DataGridOptions>): void {
        if (options.colorScheme && options.colorScheme !== this._scheme) {
            this._scheme = options.colorScheme;
            this._theme = this._resolveTheme(options.theme ?? this._options.theme ?? {});
            this._applyThemeVars();
        } else if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        if (options.striped !== undefined) this._striped = options.striped;
        if (options.emptyText !== undefined) {
            this._emptyText = options.emptyText;
            this._empty.textContent = options.emptyText;
        }
        this._rebuild();
    }

    reSize(width: number | null, height: number | null): void {
        if (width !== null) {
            this.element.style.width = typeof width === 'number' && width <= 1 ? `${width * 100}%` : `${width}px`;
        }
        if (height !== null) {
            this.element.style.height = typeof height === 'number' && height <= 1 ? `${height * 100}%` : `${height}px`;
        }
        this._renderWindow();
    }

    getElement(): HTMLDivElement {
        return this.element;
    }

    rowCount(): number {
        return this._rows.size;
    }

    viewCount(): number {
        return this._view.length;
    }

    scrollToTop(): void {
        this._body.scrollTop = 0;
    }

    destroy(): void {
        this.element.remove();
    }

    // --------------------------------------------------------------- internal
    private _resolveTheme(theme: DataGridTheme): ResolvedTheme {
        const cn = this._scheme === 'cn';
        return {
            background: theme.background ?? '#131722',
            headerBackground: theme.headerBackground ?? '#1e222d',
            headerText: theme.headerText ?? '#9aa0aa',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            rowHover: theme.rowHover ?? '#1e222d',
            striped: theme.striped ?? 'rgba(255,255,255,0.02)',
            gridLine: theme.gridLine ?? 'rgba(255,255,255,0.04)',
            scrollbar: theme.scrollbar ?? '#3a3f4b',
            accent: theme.accent ?? '#2962ff',
            positive: theme.positive ?? (cn ? '#ef5350' : '#26a69a'),
            negative: theme.negative ?? (cn ? '#26a69a' : '#ef5350'),
        };
    }

    private _applyThemeVars(): void {
        const theme = this._theme;
        const style = this.element.style;
        style.setProperty('--dg-bg', theme.background);
        style.setProperty('--dg-header', theme.headerBackground);
        style.setProperty('--dg-header-text', theme.headerText);
        style.setProperty('--dg-text', theme.text);
        style.setProperty('--dg-muted', theme.muted);
        style.setProperty('--dg-border', theme.border);
        style.setProperty('--dg-hover', theme.rowHover);
        style.setProperty('--dg-striped', theme.striped);
        style.setProperty('--dg-grid', theme.gridLine);
        style.setProperty('--dg-accent', theme.accent);
        style.setProperty('--dg-scrollbar', theme.scrollbar);
        style.setProperty('--dg-header-h', `${this._headerHeight}px`);
    }

    private _buildToolbar(): void {
        const toolbar = document.createElement('div');
        toolbar.className = 'pylc-dg-toolbar';
        const input = document.createElement('input');
        input.className = 'pylc-dg-search';
        input.type = 'text';
        input.placeholder = '搜索 / Filter…';
        input.addEventListener('input', () => this.setFilter(input.value));
        input.addEventListener('click', (event) => event.stopPropagation());
        const exportButton = document.createElement('button');
        exportButton.className = 'pylc-dg-export';
        exportButton.textContent = '导出';
        exportButton.title = '把当前（筛选/排序后）列表导出成 CSV'
            + '（小数位跟合约走 ✓）';
        exportButton.addEventListener('click', () => this.exportCsv());
        this._exportButton = exportButton;

        this._countEl = document.createElement('span');
        this._countEl.className = 'pylc-dg-count';
        toolbar.appendChild(input);
        toolbar.appendChild(this._countEl);
        toolbar.appendChild(exportButton);
        this.element.appendChild(toolbar);
    }

    private _buildHead(): void {
        this._head.textContent = '';
        for (const column of this._columns) {
            const th = document.createElement('div');
            th.className = 'pylc-dg-th';
            th.style.flexGrow = String(column.width ?? 1);
            th.style.flexBasis = '0';
            th.style.flexShrink = '1';
            th.style.minWidth = '0';
            th.style.justifyContent = defaultAlign(column) === 'right' ? 'flex-end' : defaultAlign(column) === 'center' ? 'center' : 'flex-start';
            const label = document.createElement('span');
            label.textContent = column.title ?? column.key;
            label.style.overflow = 'hidden';
            label.style.textOverflow = 'ellipsis';
            const arrow = document.createElement('span');
            arrow.className = 'pylc-dg-th-arrow';
            arrow.textContent = '↕';
            th.appendChild(label);
            th.appendChild(arrow);
            if (column.sortable !== false) {
                th.addEventListener('click', () => this._toggleSort(column.key));
            } else {
                th.style.cursor = 'default';
            }
            this._head.appendChild(th);
        }
    }

    private _toggleSort(key: string): void {
        if (this._sortKey === key) {
            this._sortDir = -this._sortDir;
        } else {
            this._sortKey = key;
            this._sortDir = 1;
        }
        this._rebuild();
    }

    private _updateSortIndicators(): void {
        const cells = this._head.children;
        for (let i = 0; i < cells.length; i++) {
            const th = cells[i] as HTMLDivElement;
            const arrow = th.lastElementChild as HTMLSpanElement | null;
            const sorted = this._columns[i].key === this._sortKey;
            th.classList.toggle('sorted', sorted);
            if (arrow) {
                arrow.textContent = sorted ? (this._sortDir > 0 ? '▲' : '▼') : '↕';
            }
        }
    }

    private _keyOf(row: RowData, index: number): string {
        const key = row[this._rowKey];
        if (key === null || key === undefined || key === '') {
            return `__row_${index}`;
        }
        return String(key);
    }

    private _matches(row: RowData): boolean {
        if (!this._filter) {
            return true;
        }
        for (const column of this._columns) {
            const value = row[column.key];
            if (value !== null && value !== undefined && String(value).toLowerCase().includes(this._filter)) {
                return true;
            }
        }
        return false;
    }

    private _compare(a: RowData, b: RowData): number {
        const key = this._sortKey;
        if (!key) {
            return 0;
        }
        const av = a[key];
        const bv = b[key];
        let result: number;
        if (typeof av === 'number' && typeof bv === 'number') {
            result = av - bv;
        } else {
            result = String(av ?? '').localeCompare(String(bv ?? ''), 'zh-Hans-CN');
        }
        return result * this._sortDir;
    }

    private _rebuild(): void {
        let view = Array.from(this._rows.values());
        if (this._filter) {
            view = view.filter((row) => this._matches(row));
        }
        if (this._sortKey) {
            view = view.slice().sort((a, b) => this._compare(a, b));
        }
        this._view = view;

        this._content.textContent = '';
        this._rendered.clear();
        this._content.style.height = `${view.length * this._rowHeight}px`;
        this._empty.style.display = view.length === 0 ? 'block' : 'none';
        if (this._countEl) {
            this._countEl.textContent = view.length === this._rows.size
                ? `${view.length} 行`
                : `${view.length} / ${this._rows.size} 行`;
        }
        this._updateSortIndicators();
        this._renderWindow();
    }

    private _renderWindow(): void {
        const bodyHeight = this._body.clientHeight;
        const scrollTop = this._body.scrollTop;
        const first = Math.max(0, Math.floor(scrollTop / this._rowHeight) - 2);
        const last = Math.min(this._view.length, Math.ceil((scrollTop + bodyHeight) / this._rowHeight) + 2);

        for (const [index, element] of this._rendered) {
            if (index < first || index >= last) {
                element.remove();
                this._rendered.delete(index);
            }
        }
        for (let index = first; index < last; index++) {
            let element = this._rendered.get(index);
            if (!element) {
                element = this._makeRow();
                this._content.appendChild(element);
                this._rendered.set(index, element);
            }
            element.style.transform = `translateY(${index * this._rowHeight}px)`;
            this._fillRow(element, this._view[index], index);
        }
    }

    private _makeRow(): HTMLDivElement {
        const row = document.createElement('div');
        row.className = 'pylc-dg-row';
        row.style.height = `${this._rowHeight}px`;
        const sparks = new Map<string, Sparkline>();
        for (const column of this._columns) {
            const cell = document.createElement('div');
            cell.className = 'pylc-dg-cell';
            const align = defaultAlign(column);
            cell.style.flexGrow = String(column.width ?? 1);
            cell.style.flexBasis = '0';
            cell.style.flexShrink = '1';
            cell.style.minWidth = '0';
            cell.style.justifyContent = align === 'right' ? 'flex-end' : align === 'center' ? 'center' : 'flex-start';
            if (column.type === 'action') {
                cell.classList.add('pylc-dg-action-cell');
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'pylc-dg-action';
                cell.appendChild(button);
            }
            if (column.type === 'spark') {
                cell.classList.add('pylc-dg-spark');
                const spark = new Sparkline({
                    width: 72,
                    height: this._rowHeight - 8,
                    upColor: this._theme.positive,
                    downColor: this._theme.negative,
                    ...(column.spark ?? {}),
                });
                cell.appendChild(spark.element);
                sparks.set(column.key, spark);
            }
            row.appendChild(cell);
        }
        this._sparks.set(row, sparks);
        row.addEventListener('click', () => this._emit('rowclick', row.dataset.key ?? ''));
        row.addEventListener('dblclick', () => this._emit('rowdblclick', row.dataset.key ?? ''));
        return row;
    }

    private _fillRow(element: HTMLDivElement, row: RowData, index: number): void {
        element.dataset.key = this._keyOf(row, index);
        element.classList.toggle('striped', this._striped && index % 2 === 1);
        const sparks = this._sparks.get(element);
        const cells = element.children;
        for (let i = 0; i < this._columns.length; i++) {
            const column = this._columns[i];
            const cell = cells[i] as HTMLDivElement;
            const value = row[column.key];
            if (column.type === 'action') {
                const button = cell.firstElementChild as HTMLButtonElement
                    | null;
                const spec = column.action;
                if (button && spec) {
                    button.textContent = spec.text(row);
                    button.title = spec.title ? spec.title(row) : '';
                    button.className = 'pylc-dg-action'
                        + (spec.className ? ` ${spec.className(row)}` : '');
                    button.onclick = (event) => {
                        event.stopPropagation();
                        spec.run(row);
                    };
                }
                continue;
            }
            if (column.type === 'spark') {
                const spark = sparks?.get(column.key);
                if (spark) {
                    spark.setData(Array.isArray(value) ? (value as number[]) : []);
                }
                continue;
            }
            cell.textContent = this._format(value, column, row);
            const mapped = column.colors ? column.colors[String(value)] : undefined;
            if (mapped) {
                cell.style.color = mapped;
            } else if (column.colorBy === 'sign' || column.type === 'change'
                       || column.type === 'percent') {
                cell.style.color = column.colorBy === 'none' ? this._theme.text : this._color(value);
            } else {
                cell.style.color = this._theme.text;
            }
        }
    }

    /**
     * 导出**当前视图**（筛选 + 排序后）为 CSV —— 数值按列 `decimalsOf(row)`
     * 格式化，所以每个合约都是自己的小数位（`rb` 0 位、`au` 2 位…）✓
     *
     * 返回导出的行数（0 = 没数据，调用方可提示）。
     */
    exportCsv(filename?: string): number {
        const rows = this._view;
        if (!rows.length) return 0;
        const columns = (this._options.exportColumns && this._options
            .exportColumns.length) ? this._options.exportColumns : this._columns;
        // CSV 里的数字不带千分位（Excel 会把 "3,600" 当文本 ✗）
        const cell = (row: RowData, column: DataGridColumn): string => {
            const value = row[column.key];
            if (column.type === 'spark' || column.type === 'action') return '';
            if (typeof value === 'number' && Number.isFinite(value)) {
                const target = column.csvDecimals === undefined
                    ? column : { ...column, decimals: column.csvDecimals,
                                 decimalsOf: undefined };
                return this._format(value, target, row).replace(/,/g, '');
            }
            return value === null || value === undefined ? '' : String(value);
        };
        const escape = (text: string): string => {
            const needs = text.includes('"') || text.includes(',')
                || text.includes('\n');
            return needs ? `"${text.replace(/"/g, '""')}"` : text;
        };
        const lines = [columns
            .map((column) => escape(column.title ?? column.key)).join(',')];
        for (const row of rows) {
            lines.push(columns
                .map((column) => escape(cell(row, column))).join(','));
        }
        const stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19);
        const name = filename || `grid_${stamp}.csv`;
        const text = lines.join('\n');
        // ★ 有宿主钩子（desk/Qt）→ 交给后端写 `~/.minibt/exports/` ✓
        if (this._exportHook && this._exportHook(name, text)) {
            return rows.length;
        }
        const blob = new Blob(['\ufeff' + text],
            { type: 'text/csv;charset=utf-8' });
        const link = document.createElement('a');
        link.download = name;
        link.href = URL.createObjectURL(blob);
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        return rows.length;
    }

    /** 当前视图的行（导出 / 计数用 ✓） */
    get viewRows(): RowData[] {
        return this._view;
    }

    /** 设置导出钩子（`desk` 用：落盘到 `~/.minibt/exports/` ✓） */
    setExportHandler(handler: ((filename: string, text: string) =>
        boolean | void) | null): void {
        this._exportHook = handler;
    }

    /** 工具栏「导出」按钮（宿主可以藏起来 ✓） */
    setExportVisible(visible: boolean): void {
        if (this._exportButton) {
            this._exportButton.style.display = visible ? '' : 'none';
        }
    }

    private _format(value: unknown, column: DataGridColumn,
                    row?: RowData): string {
        if (value === null || value === undefined || value === '') {
            return '—';
        }
        if (typeof value !== 'number') {
            return `${column.prefix ?? ''}${String(value)}${column.suffix ?? ''}`;
        }
        // ★ 每行小数位（合约 price_tick 决定）优先 ✓
        const perRow = row && column.decimalsOf
            ? column.decimalsOf(row) : undefined;
        const decimals = (typeof perRow === 'number' && Number.isFinite(perRow))
            ? perRow
            : (column.decimals ?? (column.type === 'percent' ? 2 : 0));
        let text: string;
        if (column.compact) {
            text = this._compact(value, decimals);
        } else if (column.trim) {
            // 去掉小数末尾的 0：3112 -> "3,112"，102.572 -> "102.572" ✓
            text = value.toLocaleString('en-US', {
                minimumFractionDigits: 0,
                maximumFractionDigits: decimals,
            });
        } else {
            text = value.toLocaleString('en-US', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals,
            });
        }
        const signed = column.type === 'percent' || column.type === 'change';
        if (signed && value > 0) {
            text = `+${text}`;
        }
        if (column.type === 'percent') {
            text += '%';
        }
        return `${column.prefix ?? ''}${text}${column.suffix ?? ''}`;
    }

    private _compact(value: number, decimals: number): string {
        const abs = Math.abs(value);
        if (abs >= 1e8) {
            return `${(value / 1e8).toFixed(decimals)}亿`;
        }
        if (abs >= 1e4) {
            return `${(value / 1e4).toFixed(decimals)}万`;
        }
        return value.toFixed(decimals);
    }

    private _color(value: unknown): string {
        if (typeof value !== 'number' || value === 0) {
            return this._theme.text;
        }
        return value > 0 ? this._theme.positive : this._theme.negative;
    }

    private _emit(kind: 'rowclick' | 'rowdblclick', key: string): void {
        const row = this._rows.get(key) ?? {};
        if (this.callbackName) {
            const host = window as unknown as { callbackFunction?: (message: string) => void };
            if (typeof host.callbackFunction === 'function') {
                host.callbackFunction(`${this.callbackName}_~_${key};;;${kind}`);
                return;
            }
        }
        if (kind === 'rowclick' && this._options.onRowClick) {
            this._options.onRowClick(key, row);
        } else if (kind === 'rowdblclick' && this._options.onRowDoubleClick) {
            this._options.onRowDoubleClick(key, row);
        }
    }
}

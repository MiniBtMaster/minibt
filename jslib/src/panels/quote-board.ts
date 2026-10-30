/**
 * QuoteBoard — 行情报价（类型 / 交易所分类 + 报价表 + 滚动条）。
 *
 * miniqt「行情报价」页的公共组件版：把 `DataGrid` 与 `Ticker` 拼起来，并加上
 *
 *   - **类型 chips**（期货 / 主连 / 指数 / 期权 / 股票 …）
 *   - **交易所 chips**（中金所 / 上期所 / … / 港股 / 美股）+ 顶部搜索框
 *   - **加载中 / 暂无数据** 两种空表文案（不会「永远在加载」✓）
 *   - 行点击 / 双击 / 右键、筛选变化、刷新 —— 都通过 `callbackName` 回 Python
 *
 * 事件载荷（与 `pylightcharts.util.parse_event_message` 对齐）：
 *
 *     '<symbol>;;;click'      单击（可选：合约概览气泡）
 *     '<symbol>;;;dblclick'   双击（通常用来开图）
 *     '<symbol>;;;context'    右键（周期菜单）
 *     'filter;;;<type>;;;<exchange>;;;<text>'
 *     'refresh'
 */
import { DataGrid, type DataGridColumn, type DataGridOptions, type RowData } from './data-grid';
import { emitCallback, ensureStyle } from './emit';
import { Ticker, type TickerItem, type TickerOptions } from './ticker';

export interface QuoteBoardChip {
    key: string;
    label: string;
}

export interface QuoteBoardOptions extends DataGridOptions {
    types?: QuoteBoardChip[];
    exchanges?: QuoteBoardChip[];
    type?: string;
    exchange?: string;
    /** 顶部搜索框（默认 true，本地过滤 ✓） */
    showSearch?: boolean;
    /** 底部滚动条（默认 false；传 items 或 true 才显示） */
    showTicker?: boolean;
    ticker?: TickerItem[];
    tickerOptions?: TickerOptions;
    /** 加载中 / 空表文案 */
    loadingText?: string;
    emptyText?: string;
    callbackName?: string | null;
}

const STYLE_ID = 'pylightcharts-quoteboard-style';

const CSS = `
.pylc-qb{display:flex;flex-direction:column;height:100%;width:100%;min-height:0;
  background:var(--dg-bg);color:var(--dg-text);font-size:12px}
.pylc-qb-top{flex:0 0 auto;display:flex;align-items:center;gap:6px;padding:6px 8px;
  border-bottom:1px solid var(--dg-border)}
.pylc-qb-search{flex:1;min-width:0;height:24px;padding:0 8px;border-radius:4px;
  border:1px solid var(--dg-border);background:var(--dg-header);color:var(--dg-text);
  outline:none;font-size:12px}
.pylc-qb-search:focus{border-color:var(--dg-accent)}
.pylc-qb-count{color:var(--dg-muted);font-size:11px;white-space:nowrap}
.pylc-qb-refresh{height:24px;padding:0 10px;border-radius:4px;cursor:pointer;
  border:1px solid var(--dg-border);background:transparent;color:var(--dg-text);
  font-size:11.5px}
.pylc-qb-refresh:hover{background:var(--dg-striped)}
.pylc-qb-chips{flex:0 0 auto;display:flex;align-items:center;gap:6px;padding:4px 8px;
  overflow-x:auto;scrollbar-width:none}
.pylc-qb-chips::-webkit-scrollbar{height:0}
.pylc-qb-chip{flex:0 0 auto;height:24px;padding:0 12px;border-radius:12px;
  border:1px solid var(--dg-border);background:transparent;color:var(--dg-muted);
  font-size:12px;cursor:pointer;white-space:nowrap}
.pylc-qb-chip:hover{color:var(--dg-text);background:var(--dg-striped)}
.pylc-qb-chip.on{background:var(--dg-accent);border-color:var(--dg-accent);color:#fff}
.pylc-qb-grid{position:relative;flex:1 1 auto;min-height:0}
.pylc-qb-ticker{flex:0 0 auto;height:31px;border-top:1px solid var(--dg-border)}
`;

export class QuoteBoard {
    public readonly element: HTMLDivElement;
    /** 事件回调名（Python 侧 `_bind_callback` 会设置 ✓） */
    public callbackName: string | null = null;

    private readonly typesRow: HTMLDivElement;
    private readonly chipsRow: HTMLDivElement;
    private readonly gridHost: HTMLDivElement;
    private readonly tickerHost: HTMLDivElement;
    private readonly search: HTMLInputElement;
    private readonly count: HTMLSpanElement;

    private grid: DataGrid;
    private ticker: Ticker | null = null;
    private type = '';
    private exchange = '';
    private text = '';
    private loading = false;
    private loadingText: string;
    private emptyText: string;
    private searchTimer: number | undefined;
    private pointer = { x: 0, y: 0 };

    constructor(private readonly options: QuoteBoardOptions = {},
                parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this.type = options.type || '';
        this.exchange = options.exchange || '';
        this.loadingText = options.loadingText || '正在加载合约…';
        this.emptyText = options.emptyText || '暂无数据';
        this.callbackName = options.callbackName || null;

        this.element = document.createElement('div');
        this.element.className = 'pylc-qb';

        // ---- 顶部：搜索 + 行数 + 刷新 --------------------------------
        const top = document.createElement('div');
        top.className = 'pylc-qb-top';
        this.search = document.createElement('input');
        this.search.className = 'pylc-qb-search';
        this.search.placeholder = options.showSearch === false ? '' : '商品代码、名称';
        if (options.showSearch === false) this.search.style.display = 'none';
        this.search.addEventListener('input', () => this._scheduleSearch());
        this.count = document.createElement('span');
        this.count.className = 'pylc-qb-count';
        this.count.textContent = '—';
        const refresh = document.createElement('button');
        refresh.className = 'pylc-qb-refresh';
        refresh.textContent = '刷新';
        refresh.title = '重新拉取当前类型/交易所的合约';
        refresh.addEventListener('click', () => {
            this.setLoading(true, '刷新中…');
            emitCallback(this.callbackName, 'refresh');
        });
        top.append(this.search, this.count, refresh);

        // ---- chips ----------------------------------------------------
        this.typesRow = document.createElement('div');
        this.typesRow.className = 'pylc-qb-chips';
        this.chipsRow = document.createElement('div');
        this.chipsRow.className = 'pylc-qb-chips';

        // ---- 表格 -----------------------------------------------------
        this.gridHost = document.createElement('div');
        this.gridHost.className = 'pylc-qb-grid';
        this.grid = new DataGrid({
            ...options,
            searchable: false,
            onRowDoubleClick: (key: string) => {
                emitCallback(this.callbackName, `${key};;;dblclick`);
                options.onRowDoubleClick?.(key, {});
            },
        }, this.gridHost);

        this.tickerHost = document.createElement('div');
        this.tickerHost.className = 'pylc-qb-ticker';
        this.tickerHost.style.display = 'none';

        this.element.append(top, this.typesRow, this.chipsRow, this.gridHost,
                            this.tickerHost);
        (parent ?? document.getElementById('container') ?? document.body)
            .appendChild(this.element);

        this.setTypes(options.types || [], this.type);
        this.setExchanges(options.exchanges || [], this.exchange);
        if (options.ticker || options.showTicker) {
            this._ensureTicker(options.tickerOptions || {});
            if (options.ticker) this.setTicker(options.ticker);
        }
        this._syncEmpty();
        this._wireRowEvents();
    }

    // ------------------------------------------------------------- chips
    setTypes(items: QuoteBoardChip[], current?: string): void {
        this.type = current ?? this.type;
        this._renderChips(this.typesRow, items, this.type, 'type');
    }

    setExchanges(items: QuoteBoardChip[], current?: string): void {
        this.exchange = current ?? this.exchange;
        this._renderChips(this.chipsRow, items, this.exchange, 'exchange');
    }

    private _renderChips(row: HTMLDivElement, items: QuoteBoardChip[],
                         current: string, field: 'type' | 'exchange'): void {
        row.textContent = '';
        row.style.display = items.length ? '' : 'none';
        for (const item of items) {
            const chip = document.createElement('button');
            chip.className = 'pylc-qb-chip';
            chip.dataset.key = item.key;
            chip.textContent = item.label;
            chip.title = field === 'type' ? `切换到「${item.label}」`
                : `只显示「${item.label}」的合约`;
            if (item.key === current) chip.classList.add('on');
            chip.addEventListener('click', () => {
                if (field === 'type') this.type = item.key;
                else this.exchange = item.key;
                row.querySelectorAll('.pylc-qb-chip.on')
                    .forEach((node) => node.classList.remove('on'));
                chip.classList.add('on');
                this.setLoading(true);
                this._emitFilter();
            });
            row.appendChild(chip);
        }
    }

    private _emitFilter(): void {
        emitCallback(this.callbackName,
            ['filter', this.type, this.exchange, this.text].join(';;;'));
    }

    // ------------------------------------------------------------- data
    setRows(rows: RowData[]): void {
        this.loading = false;
        this.grid.setRows(rows);
        this.setCount(`${rows.length} 行`);
        this._syncEmpty();
    }

    appendRows(rows: RowData[]): void {
        this.grid.appendRows(rows);
        this.loading = false;
        this._syncEmpty();
    }

    updateRows(rows: RowData[]): void {
        this.grid.updateRows(rows);
    }

    setColumnVisibility(key: string, visible: boolean): void {
        const columns = ((this.options.columns || []) as DataGridColumn[])
            .map((column) => (column.key === key ? { ...column, visible } : column));
        this.grid.setColumns(columns as never);
    }

    setCount(text: string): void {
        this.count.textContent = text || '—';
    }

    setLoading(loading: boolean, text?: string): void {
        this.loading = !!loading;
        if (text) this.loadingText = text;
        this._syncEmpty();
        if (loading) this.setCount('加载中…');
    }

    setTicker(items: TickerItem[]): void {
        this._ensureTicker({});
        this.ticker?.setData(items);
    }

    private _ensureTicker(options: TickerOptions): void {
        if (this.ticker) return;
        this.tickerHost.style.display = '';
        this.ticker = new Ticker({ ...this.options.tickerOptions, ...options,
                                   onItemClick: (symbol) => emitCallback(
                                       this.callbackName, `${symbol};;;dblclick`) },
                                 this.tickerHost);
    }

    private _syncEmpty(): void {
        const text = this.loading
            ? `（${this.loadingText}）`
            : `（${this.emptyText}）`;
        (this.grid as unknown as { setOptions?: Function })
            .setOptions?.({ emptyText: text });
    }

    // ------------------------------------------------------------- events
    private _wireRowEvents(): void {
        this.gridHost.addEventListener('mousedown', (event) => {
            this.pointer = { x: event.clientX, y: event.clientY };
        });
        this.grid.element.addEventListener('click', (event) => {
            const key = (event.target as HTMLElement | null)
                ?.closest('.pylc-dg-row')?.getAttribute('data-key');
            if (!key) return;
            // 单击也上报（预览气泡用；坐标一起给，Python 可原样下发 ✓）
            emitCallback(this.callbackName,
                `${key};;;click;;;${Math.round(this.pointer.x)};;;` +
                `${Math.round(this.pointer.y)}`);
        });
        this.grid.element.addEventListener('contextmenu', (event) => {
            const key = (event.target as HTMLElement | null)
                ?.closest('.pylc-dg-row')?.getAttribute('data-key');
            if (!key) return;
            event.preventDefault();
            emitCallback(this.callbackName, `${key};;;context`);
        });
    }

    private _scheduleSearch(): void {
        if (this.searchTimer !== undefined) window.clearTimeout(this.searchTimer);
        this.searchTimer = window.setTimeout(() => {
            this.text = this.search.value.trim();
            this.grid.setFilter(this.text);
            this._emitFilter();
        }, 120);
    }

    /** 可见行（`updateRows` 增量只用这些 ✓） */
    visibleKeys(): string[] {
        const keys: string[] = [];
        this.grid.element.querySelectorAll<HTMLElement>('.pylc-dg-row')
            .forEach((node) => {
                const key = node.getAttribute('data-key');
                if (key) keys.push(key);
            });
        return keys;
    }

    destroy(): void {
        this.grid.destroy();
        this.ticker?.destroy();
        this.element.remove();
    }
}

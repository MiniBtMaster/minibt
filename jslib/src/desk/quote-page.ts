/**
 * QuotePage — the initial page of the desk (mirrors miniqt 行情报价).
 *
 * Layout (top → bottom), exactly like the screenshot:
 *
 *   1. search row       商品代码、名称  +  「N 行」
 *   2. type chips       期货 / 主连 / 指数 / 期权 / 股票 / 主力
 *   3. exchange chips   中金所 / 上期所 / … (rebuilt per type)
 *   4. data grid        Lib.DataGrid (virtualised, sortable, sparkline cells)
 *   5. ticker tape      Lib.TickerTape (click → open chart)
 *
 * P0 ships the structure + empty grid; P1 fills rows from the backend.
 */
import { DataGrid, type DataGridColumn, type RowData } from '../panels/data-grid';
import { showExportHistory, type ExportRow } from './export-history';
import { gridPalette, tickerPalette, type DeskTheme } from './theme';
import { Ticker } from '../panels/ticker';

export interface ChipItem {
    /** machine key sent to the backend (`FUT`, `SHFE`, …) */
    key: string;
    /** display text (`期货`, `上期所`, …) */
    label: string;
}

export interface QuotePageOptions {
    /** called when the user clicks a row (preview bubble) */
    onRowClick?: (key: string, row: RowData, at: { x: number; y: number }) => void;
    /** called on double click → open a chart tab */
    onRowDoubleClick?: (key: string, row: RowData) => void;
    /** called on right click → period menu */
    onRowContext?: (key: string, row: RowData, event: MouseEvent) => void;
    /** called when the type/exchange/search filter changes */
    onFilterChange?: (filter: QuoteFilter) => void;
    /** called when the visible row set changes (incremental updates) */
    onVisibleChange?: (keys: string[]) => void;
    /** 「刷新」按钮 → 后端 reload_contracts（绕过缓存 ✓） */
    onRefresh?: () => void;
    /** 「导出」按钮没数据时的提示 ✓ */
    onExportEmpty?: () => void;
    /** CSV 导出交给宿主（Qt 里落盘到 `~/.minibt/exports/` ✓） */
    onExportCsv?: (filename: string, text: string) => boolean | void;
    /** 「导出历史」按钮 → 让后端推 `exports` 补丁 ✓ */
    onExportHistory?: () => void;
    /** 打开某个导出文件 / 它的文件夹 ✓ */
    onOpenExport?: (path: string, folder?: boolean) => void;
    /** 删除一条导出记录 / 清空历史 ✓ */
    onExportRemove?: (path: string) => void;
    onExportClear?: () => void;
    /** 搜索框 → **全市场**搜索（本地没命中时用 ✓） */
    onGlobalSearch?: (text: string) => void;
    /** 播放条开关（只显示有报价的合约 ✓） */
    onTickerSetting?: (key: string, value: unknown) => void;
    /** 开关变了 → 让后端重推一次播放条 ✓ */
    onTickerRefresh?: () => void;
    /** 点「其他市场」条目 → 打开该合约的看盘页 ✓ */
    onOpenSymbol?: (symbol: string, name?: string) => void;
    /** ★ 收藏（末列的星标；只影响「收藏」这一类 ✓） */
    favorites?: string[];
    /** 返回**最新**收藏列表（前端据此重画 ★/☆ ✓） */
    onToggleFavorite?: (symbol: string) => string[] | void;
}

export interface QuoteFilter {
    type: string;
    exchange: string;
    text: string;
}

/**
 * 价格列的小数位：跟**合约**的 `decimals`（后端由 `price_tick` 推）走 ✓
 *
 * 没拿到（首屏用缓存清单时）才退回 3 位 —— 之前是**全部硬编码 3 位**，
 * 螺纹 / 铁矿这种 `price_tick = 1` 的品种会显示 `3600.000` ✗
 */
function rowDecimals(fallback = 3) {
    return (row: RowData): number | undefined => {
        const value = Number((row as unknown as { decimals?: number }).decimals);
        return Number.isFinite(value) ? value : fallback;
    };
}

/** CSV 最后多带的一列：「小数位」（该合约的 `decimals` ✓） */
export const CSV_DECIMALS_COLUMN: DataGridColumn = {
    key: 'decimals', title: '小数位', type: 'number', decimals: 0,
};

/** 最右一列：★ 收藏（点击切换，只针对「收藏」分组 ✓） */
export const FAVORITE_COLUMN: DataGridColumn = {
    key: 'favorite', title: '自选', width: 0.55, align: 'center',
    type: 'action',
    action: {
        text: () => '☆',           // 真实状态由 `setFavorites` 覆盖 ✓
        title: (row) => `收藏 ${String(row.symbol ?? '')}`,
        run: () => undefined,
    },
};

/** Column set copied 1:1 from miniqt (`_COLUMNS`, market_quote_preview.py:99). */
export const QUOTE_COLUMNS: DataGridColumn[] = [
    { key: 'symbol', title: '代码', width: 1.7, type: 'text' },
    { key: 'name', title: '名称', width: 1.3, type: 'text' },
    { key: 'last', title: '最新价', type: 'number', decimals: 3, trim: true,
      decimalsOf: rowDecimals() },
    { key: 'bid_price1', title: '买一价', type: 'number', decimals: 3,
      trim: true, decimalsOf: rowDecimals() },
    { key: 'bid_volume1', title: '买一量', type: 'number', decimals: 0 },
    { key: 'ask_price1', title: '卖一价', type: 'number', decimals: 3,
      trim: true, decimalsOf: rowDecimals() },
    { key: 'ask_volume1', title: '卖一量', type: 'number', decimals: 0 },
    { key: 'upper_limit', title: '涨停价', type: 'number', decimals: 3,
      trim: true, decimalsOf: rowDecimals() },
    { key: 'lower_limit', title: '跌停价', type: 'number', decimals: 3,
      trim: true, decimalsOf: rowDecimals() },
    { key: 'chg', title: '涨跌', type: 'change', decimals: 3,
      decimalsOf: rowDecimals(), colorBy: 'sign' },
    { key: 'chg_pct', title: '涨跌幅', type: 'percent', decimals: 2,
      colorBy: 'sign' },
    { key: 'volume', title: '成交量', type: 'number', decimals: 0,
      compact: true },
    { key: 'open', title: '今开盘', type: 'number', decimals: 3, trim: true,
      decimalsOf: rowDecimals() },
    { key: 'high', title: '最高价', type: 'number', decimals: 3, trim: true,
      decimalsOf: rowDecimals() },
    { key: 'low', title: '最低价', type: 'number', decimals: 3, trim: true,
      decimalsOf: rowDecimals() },
    { key: 'pre_close', title: '昨收盘', type: 'number', decimals: 3,
      trim: true, decimalsOf: rowDecimals() },
    { key: 'pre_settlement', title: '昨结算', type: 'number', decimals: 3,
      trim: true, decimalsOf: rowDecimals() },
    { key: 'quote_time', title: '行情更新时间', width: 1.5, type: 'text' },
    { key: 'price_tick', title: '最小价位', type: 'number', decimals: 3,
      trim: true },
    { key: 'spark', title: '走势', width: 1.4, type: 'spark' },
    FAVORITE_COLUMN,
];

/** Option contracts insert 行权价 / 到期日 after 名称 (miniqt `_OPTION_COLUMNS`). */
export const OPTION_COLUMNS: DataGridColumn[] = [
    ...QUOTE_COLUMNS.slice(0, 2),
    { key: 'strike', title: '行权价', width: 1.0, type: 'number', decimals: 3, trim: true },
    { key: 'expiry', title: '到期日', width: 1.1, type: 'text' },
    ...QUOTE_COLUMNS.slice(2),
];

export class QuotePage {
    /** 顶栏「全局搜索」→ 打开报价页并聚焦搜索框 ✓ */
    focusSearch(): void {
        this.search.focus();
        this.search.select();
    }

    public readonly element: HTMLDivElement;

    private readonly search: HTMLInputElement;
    private readonly count: HTMLSpanElement;
    private readonly typeRow: HTMLDivElement;
    private readonly exchangeRow: HTMLDivElement;
    private readonly gridHost: HTMLDivElement;
    private readonly tickerHost: HTMLDivElement;

    private grid: DataGrid;
    private ticker: Ticker;
    private columns: DataGridColumn[] = QUOTE_COLUMNS;
    private filter: QuoteFilter = { type: '', exchange: '', text: '' };
    private rowsByKey = new Map<string, RowData>();
    private searchTimer: number | undefined;
    private visibleTimer: number | undefined;
    /** last pointer position inside the grid (px, viewport) — used to anchor
     *  the preview bubble and the context menu ✓ */
    private pointer: { x: number; y: number } = { x: 0, y: 0 };
    /** 收藏的合约（★ / ☆ 两种状态 ✓） */
    private favorites = new Set<string>();
    /** 是否正在加载合约（决定空表文案 ✓） */
    private loading = false;
    /** 最近导出的文件（后端 `exports` 补丁 ✓） */
    private exports: ExportRow[] = [];
    /** 点了「导出历史」但列表还没到 → 到了再弹菜单 ✓ */
    private pendingHistory = false;
    private historyButton: HTMLButtonElement | null = null;
    /** 「其他市场」候选（本地过滤不到时出现 ✓） */
    private globalHost: HTMLDivElement | null = null;
    private globalTimer: number | undefined;
    private lastQuery = '';
    /** 播放条：只显示有报价的合约（settings.ticker_only_quoted ✓） */
    private tickerOnlyQuoted = false;
    private tickerButton: HTMLButtonElement | null = null;
    private loadingText = '正在加载合约…';
    private optionMode = false;

    constructor(private readonly options: QuotePageOptions = {}) {
        this.element = document.createElement('div');
        this.element.className = 'desk-quote-page';

        // ---- 1. search row -------------------------------------------------
        const searchRow = document.createElement('div');
        searchRow.className = 'desk-quote-search-row';
        this.search = document.createElement('input');
        this.search.className = 'desk-input';
        this.search.placeholder = '商品代码、名称';
        this.search.title = '按代码 / 名称过滤当前列表（本地过滤）';
        this.search.addEventListener('input', () => this._scheduleSearch());
        this.count = document.createElement('span');
        this.count.className = 'desk-muted desk-rows-count';
        this.count.textContent = '暂无数据';
        const refresh = document.createElement('button');
        refresh.className = 'desk-tool';
        refresh.textContent = '刷新';
        refresh.title = '绕过缓存重新拉当前类型/交易所的合约';
        refresh.addEventListener('click', () => {
            this.setLoading(true, '刷新合约中…');
            this.options.onRefresh?.();
        });
        // 导出 CSV（当前筛选/排序后的列表；小数位跟合约走 ✓）
        const exportButton = document.createElement('button');
        exportButton.className = 'desk-tool';
        exportButton.textContent = '导出';
        exportButton.title = '把当前列表导出成 CSV'
            + '（价格按合约小数位：rb → 3600、au → 456.32 ✓）';
        exportButton.addEventListener('click', () => {
            const count = this.grid.exportCsv(
                `quotes_${new Date().toISOString().slice(0, 19)
                    .replace(/[:T]/g, '-')}.csv`);
            if (!count) this.options.onExportEmpty?.();
        });
        // 导出历史（最近 20 条，点一下用系统程序打开 ✓）
        const historyButton = document.createElement('button');
        historyButton.className = 'desk-tool';
        historyButton.textContent = '导出历史';
        historyButton.title = '最近导出的文件（~/.minibt/exports/，点一下打开）';
        historyButton.addEventListener('click', () => this.openExportHistory());
        this.historyButton = historyButton;
        // 播放条开关：只显示有报价的合约（存 settings ✓）
        const tickerButton = document.createElement('button');
        tickerButton.className = 'desk-tool';
        tickerButton.textContent = '播放条';
        tickerButton.title = 'Ticker-Tape：只显示**有报价**的合约（开关存偏好 ✓）';
        tickerButton.addEventListener('click', () => {
            this.tickerOnlyQuoted = !this.tickerOnlyQuoted;
            this._syncTickerButton();
            this.options.onTickerSetting?.('ticker_only_quoted',
                                           this.tickerOnlyQuoted);
            this.options.onTickerRefresh?.();
        });
        this.tickerButton = tickerButton;
        const optionButton = document.createElement('button');
        optionButton.className = 'desk-tool';
        optionButton.textContent = '期权列';
        optionButton.title = '切换「行权价 / 到期日」列（期权合约）';
        optionButton.addEventListener('click', () => {
            this.setOptionMode(!this.optionMode);
            optionButton.classList.toggle('on', this.optionMode);
        });
        searchRow.append(this.search, this.count, refresh, exportButton,
                         historyButton, tickerButton, optionButton);
        // 「其他市场」候选列表（绝对定位在搜索框下面 ✓）
        this.globalHost = document.createElement('div');
        this.globalHost.className = 'desk-quote-global';
        this.globalHost.style.display = 'none';
        this.element.appendChild(this.globalHost);

        // ---- 2/3. chip rows ------------------------------------------------
        this.typeRow = document.createElement('div');
        this.typeRow.className = 'desk-chip-row';
        this.exchangeRow = document.createElement('div');
        this.exchangeRow.className = 'desk-chip-row';

        // ---- 4. grid -------------------------------------------------------
        this.gridHost = document.createElement('div');
        this.gridHost.className = 'desk-quote-grid-host';
        this.grid = new DataGrid({
            columns: this.columns,
            // CSV 里多带一列「小数位」（方便二次计算 ✓）
            exportColumns: [...QUOTE_COLUMNS, CSV_DECIMALS_COLUMN],
            onExport: (filename, text) => this.options.onExportCsv?.(
                filename, text),
            rowKey: 'symbol',
            searchable: false,            // page-level search (like miniqt)
            colorScheme: 'cn',
            striped: true,
            emptyText: '（正在加载合约…）',   // setLoading 会改掉 ✓
            onRowClick: (key, row) => this.options.onRowClick?.(
                key, row, { ...this.pointer }),
            onRowDoubleClick: (key, row) => this.options.onRowDoubleClick?.(key, row),
        }, this.gridHost);
        this.grid.element.addEventListener('mousedown', (event) => {
            this.pointer = { x: event.clientX, y: event.clientY };
        });
        this.grid.element.addEventListener('contextmenu', (event) => {
            this.pointer = { x: event.clientX, y: event.clientY };
            const target = (event.target as HTMLElement | null)?.closest('.pylc-dg-row');
            const key = target?.getAttribute('data-key') || '';
            if (!key) return;
            event.preventDefault();
            const row = this.rowsByKey.get(key) || { symbol: key };
            this.options.onRowContext?.(key, row, event);
        });
        this.grid.element.addEventListener('scroll', () => this._scheduleVisible(), true);

        // ---- 5. ticker -----------------------------------------------------
        this.tickerHost = document.createElement('div');
        this.tickerHost.className = 'desk-quote-ticker-host';
        this.ticker = new Ticker({
            speed: 60, showName: true, colorScheme: 'cn', decimals: 2,
            onItemClick: (symbol) => this.options.onRowDoubleClick?.(symbol, {}),
        }, this.tickerHost);

        this.element.append(searchRow, this.typeRow, this.exchangeRow,
                            this.gridHost, this.tickerHost);
        // ★ 收藏列：进页面先按当前收藏集合装一遍 ✓
        this.favorites = new Set((this.options.favorites || [])
            .map((item) => String(item)));
        this._applyFavoriteColumn();
    }

    // ------------------------------------------------------------- chips
    setTypes(items: ChipItem[], current = ''): this {
        this._renderChips(this.typeRow, items, current || items[0]?.key || '', 'type');
        return this;
    }

    setExchanges(items: ChipItem[], current = ''): this {
        this._renderChips(this.exchangeRow, items, current || items[0]?.key || '',
                          'exchange');
        return this;
    }

    private _renderChips(row: HTMLDivElement, items: ChipItem[], current: string,
                         field: 'type' | 'exchange'): void {
        row.textContent = '';
        items.forEach((item) => {
            const chip = document.createElement('button');
            chip.className = 'desk-chip';
            chip.dataset.key = item.key;
            chip.textContent = item.label;
            chip.title = field === 'type' ? `切换到「${item.label}」`
                : `只显示「${item.label}」的合约`;
            if (item.key === current) chip.classList.add('on');
            chip.addEventListener('click', () => {
                row.querySelectorAll('.desk-chip.on').forEach((node) => {
                    node.classList.remove('on');
                });
                chip.classList.add('on');
                this.filter = { ...this.filter, [field]: item.key };
                this.options.onFilterChange?.({ ...this.filter });
            });
            row.appendChild(chip);
        });
    }

    setFilter(filter: Partial<QuoteFilter>): this {
        this.filter = { ...this.filter, ...filter };
        this.options.onFilterChange?.({ ...this.filter });
        return this;
    }

    // ------------------------------------------------------------- data
    /** Option contracts swap the column set (行权价 / 到期日). */
    setOptionMode(on: boolean): this {
        const next = on ? OPTION_COLUMNS : QUOTE_COLUMNS;
        this.optionMode = !!on;
        if (next === this.columns) return this;
        this.columns = next;
        this.grid.setColumns(next.map((column) => ({ ...column })));
        // ★ 换列后重新把「★ 收藏」动作装到末列，避免点击变 no-op ✗
        this._applyFavoriteColumn();
        return this;
    }

    /** 跟随主题：表格 + **底部播放条**都要变色（以前只改表格 ✗） */
    applyTheme(theme: DeskTheme): void {
        this.grid.setOptions?.({
            colorScheme: 'cn',
            theme: gridPalette(theme),
        } as never);
        this.ticker.setOptions?.({
            colorScheme: 'cn',
            theme: tickerPalette(theme),
        } as never);
    }

    /** 收藏集合（首页 ★ 与这里同一份 localStorage ✓） */
    setFavorites(symbols: string[]): void {
        this.favorites = new Set((symbols || []).map((item) => String(item)));
        this._applyFavoriteColumn();
    }

    /** 把「★ / ☆ + 点击切换」装进末列（每次收藏变化 / 换列都重装 ✓） */
    private _applyFavoriteColumn(): void {
        const favorites = this.favorites;
        const toggle = this.options.onToggleFavorite;
        const column: DataGridColumn = {
            ...FAVORITE_COLUMN,
            action: {
                text: (row) => (favorites.has(String(row.symbol ?? ''))
                    ? '★' : '☆'),
                title: (row) => (favorites.has(String(row.symbol ?? ''))
                    ? '取消收藏' : '加入收藏'),
                className: (row) => (favorites.has(String(row.symbol ?? ''))
                    ? 'on' : ''),
                run: (row) => {
                    const symbol = String(row.symbol ?? '');
                    if (!symbol) return;
                    const next = toggle?.(symbol);
                    if (Array.isArray(next)) this.setFavorites(next);
                },
            },
        };
        const columns = this.columns.map((item) => (
            item.key === FAVORITE_COLUMN.key ? column : item));
        this.columns = columns;
        this.grid.setColumns(columns.map((item) => ({ ...item })));
    }

    /** 加载中（空表显示「正在加载 X 合约…」✓） */
    /** 播放条开关状态（`settings` 补丁 → 这里同步按钮 ✓） */
    setSettings(settings: Record<string, unknown>): void {
        const value = settings?.ticker_only_quoted;
        this.tickerOnlyQuoted = value === true || value === 1
            || value === 'true';
        this._syncTickerButton();
    }

    private _syncTickerButton(): void {
        const button = this.tickerButton;
        if (!button) return;
        button.classList.toggle('on', this.tickerOnlyQuoted);
        button.title = this.tickerOnlyQuoted
            ? '播放条：只显示有报价的合约（点一下改回全部）'
            : '播放条：显示全部合约（点一下只显示有报价的）';
    }

    /** 导出历史（后端 `exports` 补丁 → 弹共用菜单 ✓） */
    setExports(items: ExportRow[]): void {
        this.exports = Array.isArray(items) ? items : [];
        if (!this.pendingHistory) return;
        this.pendingHistory = false;
        showExportHistory(this.historyButton, this.exports, {
            onOpen: (path, folder) => this.options.onOpenExport?.(path, folder),
            onDelete: (path) => this.options.onExportRemove?.(path),
            onClear: () => this.options.onExportClear?.(),
        });
    }

    /** 外部（看盘页也有一份）直接弹历史菜单 ✓ */
    openExportHistory(): void {
        this.pendingHistory = true;
        this.options.onExportHistory?.();
        // ★ 等后端真实 `exports` 补丁再弹；不要马上用旧缓存，
        //   否则首次打开会显示“还没有导出过”（后端结果随后被忽略 ✗）
    }

    setLoading(loading: boolean, text = '正在加载合约…'): this {
        this.loading = !!loading;
        this.loadingText = text || '正在加载合约…';
        this._syncEmptyText();
        return this;
    }

    /** 空表文案：加载中 / 真的没有（不会再「永远在加载」✓） */
    private _syncEmptyText(): void {
        const grid = this.grid as unknown as { setOptions?: Function };
        const text = this.loading ? `（${this.loadingText}）`
            : '（暂无合约：换个类型 / 交易所，或点「刷新」重试）';
        grid.setOptions?.({ emptyText: text });
    }

    setRows(rows: RowData[]): this {
        this.loading = false;
        this.rowsByKey = new Map(rows.map((row) => [String(row.symbol ?? ''), row]));
        this.grid.setRows(rows);
        this._updateCount(rows.length);
        this._syncEmptyText();
        this._scheduleVisible();
        return this;
    }

    appendRows(rows: RowData[]): this {
        for (const row of rows) this.rowsByKey.set(String(row.symbol ?? ''), row);
        this.grid.appendRows?.(rows);
        this._updateCount(this.rowsByKey.size);
        return this;
    }

    updateRows(rows: RowData[]): this {
        // 只更新**当前列表里已有的合约**（拼写差异 / 别的交易所的旧补丁直接丢掉 ✓）
        const merged: RowData[] = [];
        for (const row of rows) {
            const key = String(row.symbol ?? '');
            const known = this.rowsByKey.get(key);
            if (!known) continue;             // ← 防「主力里混进大商所」✗
            const next = { ...known, ...row };
            // 报价行没有 spark（`null`）→ 保留上一次算好的走势 ✓
            if (next.spark == null && known.spark != null) {
                next.spark = known.spark;
            }
            // 名称缺了（报价行常常没有 name）→ 保留清单里的中文名 ✓
            if (!String(next.name ?? '').trim()) next.name = known.name;
            this.rowsByKey.set(key, next);
            merged.push(next);
        }
        if (merged.length) this.grid.updateRows(merged);
        return this;
    }

    setTicker(items: Array<Record<string, unknown>>): this {
        this.ticker.setData(items as never);
        return this;
    }

    /** Filter locally as the user types (over the loaded rows, like miniqt). */
    private _scheduleSearch(): void {
        if (this.searchTimer !== undefined) window.clearTimeout(this.searchTimer);
        this.searchTimer = window.setTimeout(() => {
            this.filter = { ...this.filter, text: this.search.value.trim() };
            this.grid.setFilter(this.filter.text);
            this.options.onFilterChange?.({ ...this.filter });
            this._maybeGlobalSearch(this.filter.text);
        }, 120);
    }

    /**
     * 本地没命中 → 问后端**全市场**索引 ✓
     *
     * miniqt 的报价页搜索是「当前列表过滤」，但用户经常想搜别的市场
     * （比如期货页里搜 `00700`）—— 这里在本地 0 行时补一条「其他市场」列表，
     * 点一下就能开着盘页 ✓
     */
    private _maybeGlobalSearch(text: string): void {
        const query = String(text || '').trim();
        if (this.globalTimer !== undefined) {
            window.clearTimeout(this.globalTimer);
        }
        this.lastQuery = query;
        if (query.length < 2) {
            this.setGlobalResults([]);
            return;
        }
        this.globalTimer = window.setTimeout(() => {
            if (this.lastQuery !== query) return;
            this.options.onGlobalSearch?.(query);
        }, 260);
    }

    /** 后端 `symbol_search` 结果 → 「其他市场」列表（最多 8 条 ✓） */
    setGlobalResults(items: Array<Record<string, unknown>>): void {
        const host = this.globalHost;
        if (!host) return;
        const text = String(this.filter.text || '').trim().toLowerCase();
        const rows = (items || []).filter((item) => {
            const key = String(item.symbol || '');
            // 本地已有的不重复列（本地过滤时已经能看到 ✓）
            if (this.rowsByKey.has(key)) return false;
            const name = String(item.name || '').toLowerCase();
            return !text || key.toLowerCase().includes(text)
                || name.includes(text);
        }).slice(0, 8);
        host.textContent = '';
        if (!rows.length) {
            host.style.display = 'none';
            return;
        }
        const head = document.createElement('div');
        head.className = 'desk-quote-global-head';
        head.textContent = '其他市场（点一下打开看盘）';
        host.appendChild(head);
        for (const item of rows) {
            const row = document.createElement('button');
            row.className = 'desk-quote-global-row';
            const symbol = String(item.symbol || '');
            const name = String(item.name || '');
            row.innerHTML = `<span class="sym">${symbol}</span>`
                + (name ? `<span class="nm">${name}</span>` : '')
                + `<span class="mk">${String(item.exchange || item.market || '')}`
                + ` ${String(item.type_label || item.type || '')}</span>`;
            row.title = `打开 ${symbol} ${name} 的看盘窗口`;
            row.addEventListener('click', () => {
                this.setGlobalResults([]);
                this.options.onOpenSymbol?.(symbol, name);
            });
            host.appendChild(row);
        }
        host.style.display = '';
    }

    private _scheduleVisible(): void {
        if (this.visibleTimer !== undefined) return;
        this.visibleTimer = window.setTimeout(() => {
            this.visibleTimer = undefined;
            const keys: string[] = [];
            this.grid.element.querySelectorAll<HTMLElement>('.pylc-dg-row').forEach((node) => {
                const key = node.getAttribute('data-key');
                if (key) keys.push(key);
            });
            // ★ **空列表也要上报**：虚拟列表临时为空（滚到底 / 切市场）时
            //   不上报的话，后端会一直以为那批股票还在可见范围里
            //   → 富途订阅只增不减（用户实测 ✗）
            this.options.onVisibleChange?.(keys);
        }, 60);
    }

    private _updateCount(shown: number): void {
        // 本地已经有结果 → 收起「其他市场」（它只在 0 行时有意义 ✓）
        if (shown > 0 && this.globalHost) this.globalHost.style.display = 'none';
        this.count.textContent = shown ? `${shown} 行` : '暂无数据';
        const gridCount = this.grid.element.querySelector('.pylc-dg-count');
        if (gridCount) gridCount.textContent = shown ? `${shown} 行` : '';
    }

    show(): void { this.element.style.display = ''; }

    hide(): void { this.element.style.display = 'none'; }
}

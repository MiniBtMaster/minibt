/**
 * QuotePanel — the right-side 「二级报价」 of a chart tab (miniqt `quote_panel.py`).
 *
 *   ┌ SHFE.ag2612        5档 ▾ ┐
 *   │ 卖5 13852.00      19     │
 *   │ …                        │
 *   │ 卖1 13836.00       5     │
 *   │ 买1 13836.00       1     │
 *   │ …                        │
 *   │ 买5 13830.00       19    │
 *   ├──────────────────────────┤
 *   │ 最新 / 涨跌 / 涨跌幅 …    │
 *   ├──────────────────────────┤
 *   │ 时间   价格   手数  方向  │
 *   └──────────────────────────┘
 *
 * P2 = 只读（下单按钮 P4 才启用）。
 */
export interface BookLevel {
    price: number | null;
    volume: number | null;
}

export interface BookInfo {
    last?: number | null;
    chg?: number | null;
    chg_pct?: number | null;
    pre_settlement?: number | null;
    settlement?: number | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    volume?: number | null;
    open_interest?: number | null;
    amount?: number | null;
}

export interface BookTick {
    time: string;
    price: number | null;
    volume: number | null;
    direction?: string;
}

export interface BookData {
    symbol: string;
    levels?: number;
    asks?: BookLevel[];
    bids?: BookLevel[];
    info?: BookInfo;
    ticks?: BookTick[];
    /** 1 = 股票（只有买卖一），5 = 期货 ✓ */
    depth?: number;
    trading?: boolean;
}

const INFO_FIELDS: Array<[keyof BookInfo, string]> = [
    ['last', '最新'], ['chg', '涨跌'], ['chg_pct', '涨跌幅'],
    ['pre_settlement', '昨结'], ['settlement', '结算'],
    ['open', '今开'], ['high', '最高'], ['low', '最低'],
    ['volume', '成交量'], ['open_interest', '持仓量'],
    ['amount', '额'],
];

function compact(value: unknown): string {
    const number = Number(value);
    if (value === null || value === undefined || !Number.isFinite(number)) {
        return '--';
    }
    const abs = Math.abs(number);
    if (abs >= 1e8) return `${(number / 1e8).toFixed(2)}亿`;
    if (abs >= 1e4) return `${(number / 1e4).toFixed(2)}万`;
    return number.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function num(value: unknown, digits = 3): string {
    const number = Number(value);
    if (value === null || value === undefined || !Number.isFinite(number)) {
        return '--';
    }
    return number.toLocaleString('en-US', {
        minimumFractionDigits: 0, maximumFractionDigits: digits,
    });
}

/** 分笔方向 → 蜡烛图涨/跌色（买 = 上涨色，卖 = 下跌色 ✓） */
function tickClass(direction: unknown): 'buy' | 'sell' | '' {
    const text = String(direction || '').trim().toUpperCase();
    if (!text) return '';
    if (text.includes('买') || text === 'BUY' || text === 'B'
        || text === 'LONG') return 'buy';
    if (text.includes('卖') || text === 'SELL' || text === 'S'
        || text === 'SHORT') return 'sell';
    return '';
}

export interface OrderRequest {
    side: 'buy' | 'sell' | 'close';
    volume: number;
    price: number | null;
}

export class QuotePanel {
    /** 档位点击 →（`ask` 买入 / `bid` 卖出）✓ */
    public onLevelClick: ((side: 'ask' | 'bid', price: number) => void) | null
        = null;

    public readonly element: HTMLDivElement;

    private readonly title: HTMLSpanElement;
    private readonly levels: HTMLDivElement;
    private readonly info: HTMLDivElement;
    private readonly tickBody: HTMLTableSectionElement;
    private collapsed = false;
    private depth = 5;
    private trading = false;
    private real = false;
    private lastPriceValue: number | null = null;
    /** 价格小数位（`book.decimals`，由合约 price_tick 推 ✓） */
    private decimals = 3;

    constructor() {
        this.element = document.createElement('div');
        this.element.className = 'desk-book';

        const head = document.createElement('div');
        head.className = 'desk-book-head';
        this.title = document.createElement('span');
        this.title.className = 'desk-book-title';
        this.title.textContent = '二级报价';
        const collapse = document.createElement('button');
        collapse.className = 'desk-book-toggle';
        collapse.textContent = '▾';
        collapse.title = '收起 / 展开 5 档买卖';
        collapse.addEventListener('click', () => {
            this.collapsed = !this.collapsed;
            this.element.classList.toggle('collapsed', this.collapsed);
            collapse.textContent = this.collapsed ? '▸' : '▾';
        });
        head.append(this.title, collapse);

        this.levels = document.createElement('div');
        this.levels.className = 'desk-book-levels';

        this.info = document.createElement('div');
        this.info.className = 'desk-book-info';

        const tickWrap = document.createElement('div');
        tickWrap.className = 'desk-book-ticks';
        const table = document.createElement('table');
        const thead = document.createElement('thead');
        thead.innerHTML = '<tr><th>时间</th><th>价格</th><th>手数</th>'
            + '<th>方向</th></tr>';
        this.tickBody = document.createElement('tbody');
        table.append(thead, this.tickBody);
        tickWrap.appendChild(table);

        this.element.append(head, this.levels, this.info, tickWrap);
    }

    /** 最新价（预警输入框默认值 ✓） */
    get lastPrice(): number | null {
        return this.lastPriceValue;
    }

    /** 点档位 → 把价格填进**统一交易面板**的价格框（host 负责 ✓） */
    onPricePick: ((price: number) => void) | null = null;

    /** 当前合约（标题用 ✓） */
    setSymbol(symbol: string): void {
        if (!symbol) return;
        this.title.textContent = symbol;
    }

    /** 交易开关 / 是否实盘（统一交易面板据此做二次确认 ✓） */
    setTrading(enabled: boolean, real = false): void {
        this.trading = !!enabled;
        this.real = !!real;
    }

    /** 是否实盘账户（交易面板的确认框用 ✓） */
    get isReal(): boolean {
        return this.real;
    }

    /** 是否能交易（未连接交易接口 → 面板按钮禁用 ✓） */
    get canTrade(): boolean {
        return this.trading;
    }

    setBook(data: BookData): void {
        this.depth = Number(data.depth || (data.levels === 1 ? 1 : 5));
        if (data.symbol) this.setSymbol(data.symbol);
        const decimals = Number((data as unknown as { decimals?: number })
            .decimals);
        if (Number.isFinite(decimals) && decimals >= 0) {
            this.decimals = Math.min(6, Math.round(decimals));
        }
        this._renderLevels(data.asks || [], data.bids || []);
        this._renderInfo(data.info || {});
        this._renderTicks(data.ticks || []);
        this.setTrading(!!data.trading, !!(data as never as {
            real?: boolean }).real);
        if (data.info?.last !== undefined && data.info?.last !== null) {
            this.lastPriceValue = Number(data.info.last);
        }
    }

    // ------------------------------------------------------------ render
    private _renderLevels(asks: BookLevel[], bids: BookLevel[]): void {
        this.levels.textContent = '';
        const depth = this.depth;
        // 卖 N … 卖1（价格自上而下递减）
        for (let index = depth - 1; index >= 0; index -= 1) {
            const level = asks[index];
            if (!level && depth > 1) continue;
            this.levels.appendChild(
                this._levelRow(`卖${index + 1}`, level, 'ask'));
        }
        for (let index = 0; index < depth; index += 1) {
            const level = bids[index];
            if (!level && depth > 1) continue;
            this.levels.appendChild(
                this._levelRow(`买${index + 1}`, level, 'bid'));
        }
    }

    private _levelRow(label: string, level: BookLevel | undefined,
                      side: 'ask' | 'bid'): HTMLDivElement {
        const row = document.createElement('div');
        row.className = `desk-book-level ${side}`;
        row.innerHTML = `<span class="k">${label}</span>`
            + `<b class="p">${num(level?.price, this.decimals)}</b>`
            + `<span class="v">${num(level?.volume, 0)}</span>`;
        const price = Number(level?.price);
        if (Number.isFinite(price) && price > 0) {
            row.style.cursor = 'pointer';
            row.title = `点一下：把 ${price} 填到下单价格框`
                + `（${side === 'ask' ? '卖出价 → 买入' : '买入价 → 卖出'}）`;
            row.addEventListener('click', () => {
                // ★ 点 10 档 → 价格填进**统一交易面板**（用户要求 ✓）
                this.onPricePick?.(price);
                this.onLevelClick?.(side, price);
            });
        }
        return row;
    }

    private _renderInfo(info: BookInfo): void {
        this.info.textContent = '';
        for (const [key, label] of INFO_FIELDS) {
            const value = info[key];
            if (value === null || value === undefined) continue;
            const cell = document.createElement('div');
            cell.className = 'desk-book-info-cell';
            const digits = key === 'chg_pct' ? 2 : 3;
            const text = key === 'amount' ? compact(value)
                : (key === 'volume' || key === 'open_interest'
                    ? compact(value) : num(value, digits));
            const cls = (key === 'chg' || key === 'chg_pct')
                ? (Number(value) > 0 ? 'up' : (Number(value) < 0 ? 'down' : ''))
                : '';
            cell.innerHTML = `<span class="desk-muted">${label}</span>`
                + `<b class="${cls}" title="${num(value, digits)}">`
                + `${text}</b>`;
            this.info.appendChild(cell);
        }
    }

    private _renderTicks(ticks: BookTick[]): void {
        this.tickBody.textContent = '';
        for (const tick of ticks.slice(0, 14)) {
            const row = document.createElement('tr');
            const cls = tickClass(tick.direction);
            if (cls) row.className = cls;         // 整行跟蜡烛涨/跌色 ✓
            row.innerHTML = `<td>${tick.time || ''}</td>`
                + `<td>${num(tick.price, this.decimals)}</td>`
                + `<td>${num(tick.volume, 0)}</td>`
                + `<td>${tick.direction || ''}</td>`;
            this.tickBody.appendChild(row);
        }
    }
}

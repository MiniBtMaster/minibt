/**
 * SymbolPreview — the bubble that pops up on a **left click** in the quote page
 * (miniqt 的「合约概览」气泡：名称/代码 + 最新价 + 涨跌 + 开高低收 + 走势 + 打开图表).
 *
 * Auto-closes after `AUTO_CLOSE_MS`; a second click on the same row refreshes it.
 */
import { Sparkline } from '../panels/sparkline';

export const AUTO_CLOSE_MS = 8000;

export interface PreviewData {
    symbol: string;
    name?: string;
    exchange?: string;
    last?: number | null;
    chg?: number | null;
    chg_pct?: number | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    pre_close?: number | null;
    volume?: number | null;
    /** 合约小数位（后端由 `price_tick` 推，和报价页同一套 ✓） */
    decimals?: number | null;
    spark?: number[];
}

function text(value: unknown, digits = 3): string {
    if (value === null || value === undefined || value === '') return '—';
    const number = Number(value);
    // ★ NaN（天勤盘前占位行情以前会直接送过来）不能显示成字面量「NaN」✗
    if (!Number.isFinite(number)) return '—';
    return number.toLocaleString('en-US', {
        minimumFractionDigits: 0, maximumFractionDigits: digits,
    });
}

function compact(value: unknown): string {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    if (Math.abs(number) >= 1e8) return `${(number / 1e8).toFixed(2)}亿`;
    if (Math.abs(number) >= 1e4) return `${(number / 1e4).toFixed(2)}万`;
    return text(number, 0);
}

function signed(value: unknown, digits = 3): string {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    const body = number.toFixed(digits);
    return number > 0 ? `+${body}` : body;
}

export class SymbolPreview {
    public readonly element: HTMLDivElement;

    private readonly title: HTMLDivElement;
    private readonly price: HTMLDivElement;
    private readonly grid: HTMLDivElement;
    private readonly sparkHost: HTMLDivElement;
    private readonly spark: Sparkline;
    private timer: number | undefined;

    constructor(private readonly onOpen?: (symbol: string) => void) {
        this.element = document.createElement('div');
        this.element.className = 'desk-preview';
        this.element.style.display = 'none';

        const header = document.createElement('div');
        header.className = 'desk-preview-head';
        this.title = document.createElement('div');
        this.title.className = 'desk-preview-title';
        this.price = document.createElement('div');
        this.price.className = 'desk-preview-price';
        const close = document.createElement('button');
        close.className = 'desk-preview-close';
        close.textContent = '×';
        close.title = '关闭（Esc）';
        close.addEventListener('click', (event) => {
            event.stopPropagation();
            this.hide();
        });
        header.append(this.title, this.price, close);

        this.grid = document.createElement('div');
        this.grid.className = 'desk-preview-grid';

        this.sparkHost = document.createElement('div');
        this.sparkHost.className = 'desk-preview-spark';
        this.spark = new Sparkline({
            width: '100%', height: 40, baseline: 'first',
        }, this.sparkHost);

        const actions = document.createElement('div');
        actions.className = 'desk-preview-actions';
        const button = document.createElement('button');
        button.className = 'desk-tool on';
        button.textContent = '打开图表';
        button.addEventListener('click', () => {
            const symbol = this.element.dataset.symbol || '';
            this.hide();
            if (symbol) this.onOpen?.(symbol);
        });
        const countdown = document.createElement('span');
        countdown.className = 'desk-muted desk-preview-count';
        actions.append(button, countdown);
        this.countdown = countdown;

        this.element.append(header, this.grid, this.sparkHost, actions);

        // Esc / 点空白处关闭（不用等 8 秒倒计时 ✓）
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && this.visible) this.hide();
        });
        document.addEventListener('pointerdown', (event) => {
            if (!this.visible) return;
            if (this.element.contains(event.target as Node)) return;
            this.hide();
        });
    }

    private countdown: HTMLSpanElement;

    show(data: PreviewData, x: number, y: number): void {
        this.element.dataset.symbol = data.symbol;
        // ★ 先显示再 update：Sparkline 的 canvas 宽度是 100%，隐藏时
        //   clientWidth=0 → 按 80px 画完再被 CSS 放大 → 价格线模糊 ✗
        this.element.style.display = '';
        this.update(data);
        // 布局完成后再按真实宽度重画一次（devicePixelRatio 已在 Sparkline 里处理 ✓）
        window.requestAnimationFrame(() => {
            if (!this.visible) return;
            this.spark.reSize('100%', 40);
        });
        const box = this.element.getBoundingClientRect();
        const left = Math.max(8, Math.min(x + 14, window.innerWidth - box.width - 8));
        const top = Math.max(8, Math.min(y + 14, window.innerHeight - box.height - 8));
        this.element.style.left = `${left}px`;
        this.element.style.top = `${top}px`;

        if (this.timer !== undefined) window.clearInterval(this.timer);
        let left8 = Math.round(AUTO_CLOSE_MS / 1000);
        this.countdown.textContent = `${left8}s 后关闭`;
        this.timer = window.setInterval(() => {
            left8 -= 1;
            this.countdown.textContent = `${Math.max(0, left8)}s 后关闭`;
            if (left8 <= 0) this.hide();
        }, 1000);
    }

    update(data: Partial<PreviewData>): void {
        if (data.symbol) this.element.dataset.symbol = data.symbol;
        const symbol = this.element.dataset.symbol || '';
        const name = data.name || '';
        this.title.textContent = name ? `${name}  ${symbol}` : symbol;
        // ★ 小数位跟合约走（`rb` tick=1 → 0 位；`au` → 2 位 ✓）
        const decimals = this._decimals(data);

        const chg = Number(data.chg ?? NaN);
        const cls = Number.isFinite(chg) && chg !== 0
            ? (chg > 0 ? 'up' : 'down') : '';
        const pct = Number(data.chg_pct ?? NaN);
        this.price.textContent = `${text(data.last, decimals)}`
            + `  ${signed(data.chg, decimals)}`
            + (Number.isFinite(pct) ? `  ${signed(pct, 2)}%` : '');
        this.price.className = `desk-preview-price ${cls}`;

        const cells: Array<[string, string]> = [
            ['今开', text(data.open, decimals)],
            ['最高', text(data.high, decimals)],
            ['最低', text(data.low, decimals)],
            ['昨收', text(data.pre_close, decimals)],
            ['成交量', compact(data.volume)],
        ];
        this.grid.textContent = '';
        for (const [key, value] of cells) {
            const cell = document.createElement('div');
            cell.className = 'desk-preview-cell';
            cell.innerHTML = `<span class="desk-muted">${key}</span><b>${value}</b>`;
            this.grid.appendChild(cell);
        }

        const spark = (data.spark || []).filter((value) => Number.isFinite(value));
        this.sparkHost.style.display = spark.length > 1 ? '' : 'none';
        if (spark.length > 1) this.spark.setData(spark);
    }

    /** 记下最近一次的小数位（部分推送只带价格，不带 decimals ✓） */
    private lastDecimals = 3;

    private _decimals(data: Partial<PreviewData>): number {
        const value = Number(data.decimals);
        if (Number.isFinite(value) && value >= 0) {
            this.lastDecimals = Math.min(6, Math.round(value));
        }
        return this.lastDecimals;
    }

    hide(): void {
        this.element.style.display = 'none';
        if (this.timer !== undefined) {
            window.clearInterval(this.timer);
            this.timer = undefined;
        }
    }

    get visible(): boolean {
        return this.element.style.display !== 'none';
    }
}

/**
 * OrderTicket — the TradingView buy / spread / sell ticket at the chart's top-left.
 *
 * A thin shell: it only renders three cells（买入 / 点差 / 卖出）and exposes
 * `setData({sell, buy, spread})` for the host to push live values. Clicking the
 * two sides fires `onSideClick('sell' | 'buy')` back to Python.
 */

import { ensureStyle } from './emit';

export interface OrderTicketTheme {
    background?: string;
    text?: string;
    muted?: string;
    border?: string;
    /** 卖出（红）*/
    sell?: string;
    /** 买入（蓝）*/
    buy?: string;
    spread?: string;
    hover?: string;
}

export interface OrderTicketOptions {
    sell?: number | null;
    buy?: number | null;
    spread?: number | null;
    decimals?: number;
    /** 字号（px）；整个卡片都跟着缩放 ✓ */
    fontSize?: number;
    theme?: OrderTicketTheme;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    border: string;
    sell: string;
    buy: string;
    spread: string;
    hover: string;
}

const STYLE_ID = 'pylightcharts-orderticket-style';
const CSS = `
.pylc-ot{display:inline-flex;align-items:center;gap:8px;padding:4px 6px;box-sizing:border-box;
  font:13px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif;
  color:var(--ot-text)}
.pylc-ot-side{display:flex;flex-direction:column;align-items:center;justify-content:center;
  min-width:4.6em;padding:3px 9px;border:1px solid var(--ot-border);border-radius:6px;
  cursor:pointer;background:transparent;user-select:none;transition:background .12s}
.pylc-ot-side:hover{background:var(--ot-hover)}
.pylc-ot-price{font-size:1.2em;font-weight:600}
.pylc-ot-label{font-size:1em}
.pylc-ot-sell{border-color:var(--ot-sell);color:var(--ot-sell)}
.pylc-ot-buy{border-color:var(--ot-buy);color:var(--ot-buy)}
.pylc-ot-spread{min-width:3em;text-align:center;color:var(--ot-muted);font-size:1em}
.pylc-stack>.pylc-ot{align-self:flex-start}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class OrderTicket {
    public callbackName: string | null = null;
    public readonly element: HTMLDivElement;

    private _decimals: number;
    private _theme: ResolvedTheme;
    private _sellPrice: HTMLDivElement;
    private _buyPrice: HTMLDivElement;
    private _spread: HTMLDivElement;

    constructor(options: OrderTicketOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._decimals = options.decimals ?? 2;
        this._theme = this._resolveTheme(options.theme ?? {});
        this.element = document.createElement('div');
        this.element.className = 'pylc-ot';
        this.element.style.fontSize = `${options.fontSize ?? 13}px`;
        this._applyThemeVars();
        // 左边 = 买入、右边 = 卖出（国内习惯：买入在左、卖出在右 ✓）。
        // 点击顺序仍是 buy / sell，Python 侧不用做左右互换。
        this._buyPrice = this._makeSide('buy', '买入');
        this._spread = document.createElement('div');
        this._spread.className = 'pylc-ot-spread';
        this._spread.textContent = '—';
        this.element.appendChild(this._spread);
        this._sellPrice = this._makeSide('sell', '卖出');
        (parent ?? defaultContainer()).appendChild(this.element);
        if (options.sell !== undefined || options.buy !== undefined) {
            this.setData(options);
        }
    }

    /** Push the current sell / buy (bid / ask) prices and spread. */
    setData(data: {
        sell?: number | null;
        buy?: number | null;
        spread?: number | null;
    }): void {
        const sell = data.sell ?? null;
        const buy = data.buy ?? null;
        let spread = data.spread ?? null;
        if (spread === null && sell !== null && buy !== null) {
            spread = Math.abs(buy - sell);
        }
        this._sellPrice.textContent = sell === null ? '—' : this._format(sell);
        this._buyPrice.textContent = buy === null ? '—' : this._format(buy);
        this._spread.textContent = spread === null ? '—' : this._format(spread);
    }

    setOptions(options: Partial<OrderTicketOptions>): void {
        if (options.decimals !== undefined) {
            this._decimals = options.decimals;
        }
        if (options.fontSize !== undefined) {
            this.element.style.fontSize = `${options.fontSize}px`;
        }
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        if (options.sell !== undefined || options.buy !== undefined
            || options.spread !== undefined) {
            this.setData(options);
        }
    }

    destroy(): void {
        this.element.remove();
    }

    private _makeSide(side: 'sell' | 'buy', label: string): HTMLDivElement {
        const node = document.createElement('div');
        node.className = `pylc-ot-side pylc-ot-${side}`;
        const price = document.createElement('div');
        price.className = 'pylc-ot-price';
        price.textContent = '—';
        const text = document.createElement('div');
        text.className = 'pylc-ot-label';
        text.textContent = label;
        node.appendChild(price);
        node.appendChild(text);
        node.addEventListener('click', () => this._emitSide(side));
        this.element.appendChild(node);
        return price;
    }

    private _emitSide(side: 'sell' | 'buy'): void {
        if (!this.callbackName) {
            return;
        }
        const host = window as unknown as {
            callbackFunction?: (message: string) => void;
        };
        if (typeof host.callbackFunction === 'function') {
            host.callbackFunction(`${this.callbackName}_~_${side}`);
        }
    }

    private _resolveTheme(theme: OrderTicketTheme): ResolvedTheme {
        return {
            background: theme.background ?? 'transparent',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            sell: theme.sell ?? '#ef5350',
            buy: theme.buy ?? '#2962ff',
            spread: theme.spread ?? '#787b86',
            hover: theme.hover ?? 'rgba(255,255,255,0.06)',
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--ot-bg', this._theme.background);
        style.setProperty('--ot-text', this._theme.text);
        style.setProperty('--ot-muted', this._theme.muted);
        style.setProperty('--ot-border', this._theme.border);
        style.setProperty('--ot-sell', this._theme.sell);
        style.setProperty('--ot-buy', this._theme.buy);
        style.setProperty('--ot-hover', this._theme.hover);
    }

    private _format(value: number): string {
        return Number(value).toFixed(this._decimals);
    }
}

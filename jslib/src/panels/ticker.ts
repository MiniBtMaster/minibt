/**
 * Ticker — a quote strip. One implementation covers the whole TradingView
 * ticker family by `layout`:
 *
 *   - `'scroll'` — the moving marquee (Ticker Tape);
 *   - `'wrap'`   — a static wrap/grid of quote chips (Ticker Tag, Single Ticker,
 *                  Tickers).
 *
 * Items are `{symbol, name?, last?, chg?, chg_pct?}`; the change is coloured by
 * sign (`colorScheme: 'cn'` red-up / `'tv'` green-up). Clicking an item reports
 * its symbol to Python.
 */

import { emitCallback, ensureStyle } from './emit';

export type TickerColorScheme = 'cn' | 'tv';
export type TickerLayout = 'scroll' | 'wrap';

export interface TickerItem {
    /** 合约小数位（`last` 显示用 ✓） */
    decimals?: number | null;
    symbol: string;
    name?: string;
    last?: number;
    chg?: number;
    chg_pct?: number;
}

export interface TickerTheme {
    background?: string;
    text?: string;
    muted?: string;
    border?: string;
    hover?: string;
    positive?: string;
    negative?: string;
}

export interface TickerOptions {
    items?: TickerItem[];
    layout?: TickerLayout;
    /** marquee speed in pixels per second (default 60) */
    speed?: number;
    colorScheme?: TickerColorScheme;
    separator?: string;
    decimals?: number;
    compact?: boolean;
    showName?: boolean;
    theme?: TickerTheme;
    onItemClick?: (symbol: string) => void;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    border: string;
    hover: string;
    positive: string;
    negative: string;
}

const STYLE_ID = 'pylightcharts-ticker-style';
const CSS = `
.pylc-ticker{background:var(--tk-bg);color:var(--tk-text);overflow:hidden;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif;
  font-size:12px;font-variant-numeric:tabular-nums}
.pylc-ticker.scroll{position:relative;border-bottom:1px solid var(--tk-border);
  border-top:1px solid var(--tk-border)}
.pylc-ticker.wrap{display:flex;flex-wrap:wrap;gap:6px;padding:8px}
.pylc-ticker-track{display:inline-flex;white-space:nowrap;will-change:transform;
  animation:pylc-ticker-scroll var(--tk-duration,40s) linear infinite}
.pylc-ticker.scroll:hover .pylc-ticker-track{animation-play-state:paused}
@keyframes pylc-ticker-scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.pylc-ticker-item{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;
  cursor:pointer;white-space:nowrap;border-right:1px solid var(--tk-border)}
.pylc-ticker.wrap .pylc-ticker-item{border:1px solid var(--tk-border);border-radius:5px;
  padding:4px 10px;background:var(--tk-bg)}
.pylc-ticker-item:hover{background:var(--tk-hover)}
.pylc-ticker-sym{font-weight:600;color:var(--tk-text)}
.pylc-ticker-name{color:var(--tk-muted)}
.pylc-ticker-last{font-weight:600}
.pylc-ticker-chg{font-weight:600}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class Ticker {
    public callbackName: string | null = null;
    public readonly element: HTMLDivElement;

    private _items: TickerItem[] = [];
    private _layout: TickerLayout;
    private _speed: number;
    private _scheme: TickerColorScheme;
    private _separator: string;
    private _decimals: number;
    private _compact: boolean;
    private _showName: boolean;
    private _theme: ResolvedTheme;
    private _onItemClick?: (symbol: string) => void;
    private _track: HTMLDivElement | null = null;

    constructor(options: TickerOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._layout = options.layout ?? 'scroll';
        this._speed = options.speed ?? 60;
        this._scheme = options.colorScheme ?? 'cn';
        this._separator = options.separator ?? '';
        this._decimals = options.decimals ?? 2;
        this._compact = options.compact ?? false;
        this._showName = options.showName ?? false;
        this._theme = this._resolveTheme(options.theme ?? {});
        this._onItemClick = options.onItemClick;

        this.element = document.createElement('div');
        this.element.className = `pylc-ticker ${this._layout}`;
        this._applyThemeVars();
        (parent ?? defaultContainer()).appendChild(this.element);
        if (options.items) {
            this.setItems(options.items);
        }
    }

    setItems(items: TickerItem[]): void {
        this._items = items ?? [];
        this._render();
    }

    updateItem(item: TickerItem): void {
        const index = this._items.findIndex((entry) => entry.symbol === item.symbol);
        if (index < 0) {
            this._items.push(item);
        } else {
            this._items[index] = item;
        }
        this._render();
    }

    /** Update values **in place** (keeps the marquee animation running).
     *
     * ``setItems`` rebuilds the DOM, which restarts the CSS scroll animation
     * from the beginning ✗; use this for periodic price refreshes. Falls back to
     * ``setItems`` when the symbol list/order changed (e.g. switching pages).
     */
    setData(items: TickerItem[]): void {
        const next = items ?? [];
        if (!this._sameOrder(next)) {
            this.setItems(next);
            return;
        }
        this._items = next;
        const nodes = this.element.querySelectorAll<HTMLElement>('.pylc-ticker-item');
        const count = next.length;
        if (count === 0) {
            return;
        }
        for (let i = 0; i < nodes.length; i++) {
            this._updateNode(nodes[i], next[i % count]);
        }
    }

    private _sameOrder(items: TickerItem[]): boolean {
        if (items.length !== this._items.length) {
            return false;
        }
        for (let i = 0; i < items.length; i++) {
            if (items[i].symbol !== this._items[i].symbol) {
                return false;
            }
        }
        return true;
    }

    private _updateNode(node: HTMLElement, item: TickerItem): void {
        const symbol = node.querySelector<HTMLElement>('.pylc-ticker-sym');
        if (symbol) {
            symbol.textContent = item.name && this._showName ? item.name : item.symbol;
        }
        this._updateCell(
            node, 'pylc-ticker-last',
            item.last === undefined || item.last === null
                ? null : this._format(item.last, item.decimals),
        );
        const hasPct = item.chg_pct !== undefined && item.chg_pct !== null;
        this._updateCell(
            node, 'pylc-ticker-chg',
            hasPct ? `${item.chg_pct! >= 0 ? '+' : ''}${item.chg_pct!.toFixed(2)}%` : null,
            hasPct ? this._color(item.chg_pct!) : undefined,
        );
    }

    private _updateCell(node: HTMLElement, className: string, text: string | null,
                        color?: string): void {
        let span = node.querySelector<HTMLElement>('.' + className);
        if (text === null) {
            if (span) {
                span.remove();
            }
            return;
        }
        if (!span) {
            span = document.createElement('span');
            span.className = className;
            node.appendChild(span);
        }
        span.textContent = text;
        if (color) {
            span.style.color = color;
        }
    }

    setOptions(options: Partial<TickerOptions>): void {
        if (options.layout && options.layout !== this._layout) {
            this._layout = options.layout;
            this.element.className = `pylc-ticker ${this._layout}`;
        }
        if (options.speed !== undefined) this._speed = options.speed;
        if (options.colorScheme && options.colorScheme !== this._scheme) {
            this._scheme = options.colorScheme;
            this._theme = this._resolveTheme(options.theme ?? {});
            this._applyThemeVars();
        } else if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        if (options.separator !== undefined) this._separator = options.separator;
        if (options.decimals !== undefined) this._decimals = options.decimals;
        if (options.compact !== undefined) this._compact = options.compact;
        if (options.showName !== undefined) this._showName = options.showName;
        this._render();
    }

    destroy(): void {
        this.element.remove();
    }

    private _resolveTheme(theme: TickerTheme): ResolvedTheme {
        const cn = this._scheme === 'cn';
        return {
            background: theme.background ?? '#131722',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            hover: theme.hover ?? 'rgba(255,255,255,0.05)',
            positive: theme.positive ?? (cn ? '#ef5350' : '#26a69a'),
            negative: theme.negative ?? (cn ? '#26a69a' : '#ef5350'),
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--tk-bg', this._theme.background);
        style.setProperty('--tk-text', this._theme.text);
        style.setProperty('--tk-muted', this._theme.muted);
        style.setProperty('--tk-border', this._theme.border);
        style.setProperty('--tk-hover', this._theme.hover);
    }

    private _render(): void {
        this.element.textContent = '';
        this._track = null;
        if (this._layout === 'scroll') {
            this._track = document.createElement('div');
            this._track.className = 'pylc-ticker-track';
            this.element.appendChild(this._track);
            this._fill(this._track, false);
            this._fill(this._track, true);       // duplicate for the seamless loop
            this._scheduleDuration();
        } else {
            this._fill(this.element, false);
        }
    }

    private _fill(host: HTMLElement, duplicate: boolean): void {
        for (const item of this._items) {
            host.appendChild(this._makeItem(item, duplicate));
        }
    }

    private _makeItem(item: TickerItem, duplicate: boolean): HTMLSpanElement {
        const node = document.createElement('span');
        node.className = 'pylc-ticker-item';
        if (!duplicate) {
            node.addEventListener('click', () => this._select(item.symbol));
        } else {
            node.style.pointerEvents = 'none';
        }
        const symbol = document.createElement('span');
        symbol.className = 'pylc-ticker-sym';
        symbol.textContent = item.name && this._showName ? item.name : item.symbol;
        node.appendChild(symbol);

        if (item.last !== undefined && item.last !== null) {
            const last = document.createElement('span');
            last.className = 'pylc-ticker-last';
            last.textContent = this._format(item.last, item.decimals);
            node.appendChild(last);
        }
        if (item.chg_pct !== undefined && item.chg_pct !== null) {
            const change = document.createElement('span');
            change.className = 'pylc-ticker-chg';
            change.style.color = this._color(item.chg_pct);
            change.textContent = `${item.chg_pct >= 0 ? '+' : ''}${item.chg_pct.toFixed(2)}%`;
            node.appendChild(change);
        }
        if (this._separator) {
            const sep = document.createElement('span');
            sep.className = 'pylc-ticker-name';
            sep.textContent = this._separator;
            node.appendChild(sep);
        }
        return node;
    }

    private _scheduleDuration(): void {
        if (!this._track) {
            return;
        }
        const track = this._track;
        const apply = (): void => {
            const half = track.scrollWidth / 2;
            const duration = half > 0 ? Math.max(5, half / this._speed) : 40;
            this.element.style.setProperty('--tk-duration', `${duration}s`);
        };
        if (typeof requestAnimationFrame === 'function') {
            requestAnimationFrame(apply);
        } else {
            setTimeout(apply, 0);
        }
    }

    /** `digits`（可选）= 该合约的小数位，缺省用面板默认 ✓ */
    private _format(value: number, digits?: number | null): string {
        const places = (typeof digits === 'number' && Number.isFinite(digits))
            ? Math.max(0, Math.min(6, Math.round(digits))) : this._decimals;
        if (this._compact) {
            const abs = Math.abs(value);
            if (abs >= 1e8) return `${(value / 1e8).toFixed(places)}亿`;
            if (abs >= 1e4) return `${(value / 1e4).toFixed(places)}万`;
        }
        return value.toLocaleString('en-US', {
            minimumFractionDigits: places,
            maximumFractionDigits: places,
        });
    }

    private _color(value: number): string {
        if (value === 0) {
            return this._theme.text;
        }
        return value > 0 ? this._theme.positive : this._theme.negative;
    }

    private _select(symbol: string): void {
        if (this.callbackName) {
            emitCallback(this.callbackName, symbol);
            return;
        }
        if (this._onItemClick) {
            this._onItemClick(symbol);
        }
    }
}

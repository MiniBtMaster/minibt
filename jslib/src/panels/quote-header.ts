/**
 * QuoteHeader — a symbol quote header (Symbol Info / Symbol Overview).
 *
 * Shows the name, code, last price and change, plus a row of OHLC / volume /
 * open-interest fields and an optional inline {@link Sparkline}.
 */

import { ensureStyle } from './emit';
import { Sparkline } from './sparkline';

export type QuoteColorScheme = 'cn' | 'tv';

export interface QuoteHeaderData {
    symbol?: string;
    name?: string;
    exchange?: string;
    last?: number;
    chg?: number;
    chg_pct?: number;
    open?: number;
    high?: number;
    low?: number;
    pre_close?: number;
    volume?: number;
    open_interest?: number;
    spark?: number[];
}

export interface QuoteHeaderTheme {
    background?: string;
    text?: string;
    muted?: string;
    border?: string;
    positive?: string;
    negative?: string;
}

export interface QuoteHeaderOptions extends QuoteHeaderData {
    decimals?: number;
    compact?: boolean;
    colorScheme?: QuoteColorScheme;
    /** field order; default open/high/low/pre_close/volume/open_interest */
    fields?: string[];
    showSpark?: boolean;
    sparkWidth?: number;
    sparkHeight?: number;
    theme?: QuoteHeaderTheme;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    border: string;
    positive: string;
    negative: string;
}

const LABELS: Record<string, string> = {
    open: '开',
    high: '高',
    low: '低',
    pre_close: '昨收',
    volume: '量',
    open_interest: '持仓',
    chg: '涨跌',
    chg_pct: '涨跌幅',
};

const DEFAULT_FIELDS = ['open', 'high', 'low', 'pre_close', 'volume', 'open_interest'];

const STYLE_ID = 'pylightcharts-quote-style';
const CSS = `
.pylc-quote{display:flex;align-items:flex-start;gap:16px;padding:10px 14px;
  background:var(--q-bg);color:var(--q-text);border-bottom:1px solid var(--q-border);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif;
  font-variant-numeric:tabular-nums;flex:0 0 auto}
.pylc-quote-main{display:flex;flex-direction:column;gap:3px;min-width:0}
.pylc-quote-row{display:flex;align-items:baseline;gap:10px;white-space:nowrap}
.pylc-quote-name{font-size:15px;font-weight:700;color:var(--q-text)}
.pylc-quote-code{font-size:11.5px;color:var(--q-muted)}
.pylc-quote-last{font-size:17px;font-weight:700}
.pylc-quote-chg{font-size:12.5px;font-weight:600}
.pylc-quote-fields{display:flex;flex-wrap:wrap;gap:12px}
.pylc-quote-field{font-size:11.5px;color:var(--q-muted)}
.pylc-quote-field b{font-weight:600;color:var(--q-text);margin-left:3px}
.pylc-quote-spark{margin-left:auto;flex:0 0 auto}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class QuoteHeader {
    public readonly element: HTMLDivElement;

    private _data: QuoteHeaderData;
    private _decimals: number;
    private _compact: boolean;
    private _scheme: QuoteColorScheme;
    private _fields: string[];
    private _showSpark: boolean;
    private _sparkWidth: number;
    private _sparkHeight: number;
    private _theme: ResolvedTheme;
    private _main!: HTMLDivElement;
    private _spark: Sparkline | null = null;
    private _sparkHost: HTMLDivElement | null = null;

    constructor(options: QuoteHeaderOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._decimals = options.decimals ?? 0;
        this._compact = options.compact ?? false;
        this._scheme = options.colorScheme ?? 'cn';
        this._fields = options.fields ?? DEFAULT_FIELDS.slice();
        this._showSpark = options.showSpark ?? false;
        this._sparkWidth = options.sparkWidth ?? 160;
        this._sparkHeight = options.sparkHeight ?? 42;
        this._theme = this._resolveTheme(options.theme ?? {});
        this._data = options;

        this.element = document.createElement('div');
        this.element.className = 'pylc-quote';
        this._applyThemeVars();
        this._main = document.createElement('div');
        this._main.className = 'pylc-quote-main';
        this.element.appendChild(this._main);
        (parent ?? defaultContainer()).appendChild(this.element);
        this._render();
    }

    setData(data: QuoteHeaderData): void {
        this._data = { ...this._data, ...data };
        this._render();
    }

    setOptions(options: Partial<QuoteHeaderOptions>): void {
        if (options.decimals !== undefined) this._decimals = options.decimals;
        if (options.compact !== undefined) this._compact = options.compact;
        if (options.fields) this._fields = options.fields;
        if (options.showSpark !== undefined) this._showSpark = options.showSpark;
        if (options.colorScheme && options.colorScheme !== this._scheme) {
            this._scheme = options.colorScheme;
        }
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
        } else {
            this._theme = this._resolveTheme({
                positive: this._theme.positive,
                negative: this._theme.negative,
            });
        }
        this._applyThemeVars();
        this._render();
    }

    destroy(): void {
        this.element.remove();
    }

    private _resolveTheme(theme: QuoteHeaderTheme): ResolvedTheme {
        const cn = this._scheme === 'cn';
        return {
            background: theme.background ?? 'transparent',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            positive: theme.positive ?? (cn ? '#ef5350' : '#26a69a'),
            negative: theme.negative ?? (cn ? '#26a69a' : '#ef5350'),
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--q-bg', this._theme.background);
        style.setProperty('--q-text', this._theme.text);
        style.setProperty('--q-muted', this._theme.muted);
        style.setProperty('--q-border', this._theme.border);
    }

    private _render(): void {
        const data = this._data;
        this._main.textContent = '';

        const title = document.createElement('div');
        title.className = 'pylc-quote-row';
        const name = document.createElement('span');
        name.className = 'pylc-quote-name';
        name.textContent = data.name ?? data.symbol ?? '';
        title.appendChild(name);
        if (data.symbol || data.exchange) {
            const code = document.createElement('span');
            code.className = 'pylc-quote-code';
            code.textContent = [data.symbol, data.exchange].filter(Boolean).join(' · ');
            title.appendChild(code);
        }
        this._main.appendChild(title);

        const price = document.createElement('div');
        price.className = 'pylc-quote-row';
        const last = document.createElement('span');
        last.className = 'pylc-quote-last';
        last.style.color = this._changeColor();
        last.textContent = this._format(data.last);
        price.appendChild(last);
        if (data.chg_pct !== undefined || data.chg !== undefined) {
            const change = document.createElement('span');
            change.className = 'pylc-quote-chg';
            change.style.color = this._changeColor();
            const pct = data.chg_pct !== undefined
                ? `${data.chg_pct >= 0 ? '+' : ''}${data.chg_pct.toFixed(2)}%` : '';
            const abs = data.chg !== undefined
                ? `${data.chg >= 0 ? '+' : ''}${this._format(data.chg)}` : '';
            change.textContent = [abs, pct].filter(Boolean).join('  ');
            price.appendChild(change);
        }
        this._main.appendChild(price);

        const fields = document.createElement('div');
        fields.className = 'pylc-quote-row pylc-quote-fields';
        for (const key of this._fields) {
            const value = (data as Record<string, unknown>)[key];
            if (value === undefined || value === null) {
                continue;
            }
            const field = document.createElement('span');
            field.className = 'pylc-quote-field';
            field.textContent = LABELS[key] ?? key;
            const bold = document.createElement('b');
            bold.textContent = key === 'volume' || key === 'open_interest'
                ? this._formatCompact(value as number) : this._format(value as number);
            field.appendChild(bold);
            fields.appendChild(field);
        }
        this._main.appendChild(fields);

        this._renderSpark();
    }

    private _renderSpark(): void {
        if (!this._showSpark || !Array.isArray(this._data.spark)) {
            if (this._sparkHost) {
                this._sparkHost.remove();
                this._sparkHost = null;
                this._spark = null;
            }
            return;
        }
        if (!this._sparkHost) {
            this._sparkHost = document.createElement('div');
            this._sparkHost.className = 'pylc-quote-spark';
            this.element.appendChild(this._sparkHost);
            this._spark = new Sparkline({
                width: this._sparkWidth,
                height: this._sparkHeight,
                upColor: this._theme.positive,
                downColor: this._theme.negative,
            }, this._sparkHost);
        }
        this._spark?.setData(this._data.spark);
    }

    private _changeColor(): string {
        const value = this._data.chg_pct ?? this._data.chg ?? 0;
        if (value === 0) {
            return this._theme.text;
        }
        return value > 0 ? this._theme.positive : this._theme.negative;
    }

    private _format(value: number | undefined): string {
        if (value === undefined || value === null || Number.isNaN(value)) {
            return '—';
        }
        return value.toLocaleString('en-US', {
            minimumFractionDigits: this._decimals,
            maximumFractionDigits: this._decimals,
        });
    }

    private _formatCompact(value: number): string {
        if (this._compact) {
            const abs = Math.abs(value);
            if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
            if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万`;
        }
        return this._format(value);
    }
}

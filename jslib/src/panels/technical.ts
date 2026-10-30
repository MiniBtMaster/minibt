/**
 * TechnicalAnalysis — the TradingView "Technical Analysis" widget: a buy/sell
 * gauge, a summary (counts), and two compact tables (oscillators / moving
 * averages).
 *
 * The library does not compute the signals — Python supplies them (see
 * `pylightcharts.panels.technical.ta_summary`). Data shape:
 *
 *   {
 *     score: 0.32,                     // -1 .. +1
 *     label: 'BUY',                    // optional; derived from score otherwise
 *     counts: {buy: 10, neutral: 4, sell: 3},
 *     oscillators:     [{name: 'RSI(14)', value: 56.3, signal: 'buy'}, ...],
 *     moving_averages: [{name: 'MA10',   value: 190.2, signal: 'buy'}, ...],
 *   }
 */

import { ensureStyle } from './emit';

export type TaSignal = 'buy' | 'neutral' | 'sell';

export interface TaRow {
    name: string;
    value?: number | string;
    signal: TaSignal | string;
}

export interface TaData {
    score?: number;
    label?: string;
    counts?: { buy?: number; neutral?: number; sell?: number };
    oscillators?: TaRow[];
    moving_averages?: TaRow[];
}

export interface TaTheme {
    background?: string;
    text?: string;
    muted?: string;
    border?: string;
    buyColor?: string;
    sellColor?: string;
    neutralColor?: string;
}

export interface TaOptions extends TaData {
    decimals?: number;
    theme?: TaTheme;
}

interface ResolvedTheme {
    background: string;
    text: string;
    muted: string;
    border: string;
    buy: string;
    sell: string;
    neutral: string;
}

const STYLE_ID = 'pylightcharts-ta-style';
const CSS = `
.pylc-ta{display:flex;flex-direction:column;height:100%;width:100%;background:var(--ta-bg);
  color:var(--ta-text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif}
.pylc-ta-top{display:flex;align-items:center;gap:12px;padding:8px 12px;flex:0 0 auto}
.pylc-ta-gauge{flex:0 0 auto}
.pylc-ta-summary{display:flex;flex-direction:column;gap:5px;min-width:0}
.pylc-ta-label{font-size:18px;font-weight:700;letter-spacing:.02em}
.pylc-ta-counts{display:flex;gap:10px;font-size:11px;color:var(--ta-muted)}
.pylc-ta-counts b{font-weight:700}
.pylc-ta-tables{display:flex;flex:1 1 auto;min-height:0;border-top:1px solid var(--ta-border)}
.pylc-ta-col{flex:1 1 0;min-width:0;display:flex;flex-direction:column;min-height:0}
.pylc-ta-col+.pylc-ta-col{border-left:1px solid var(--ta-border)}
.pylc-ta-col h4{margin:0;padding:5px 10px;font-size:11px;font-weight:600;color:var(--ta-muted);
  border-bottom:1px solid var(--ta-border);flex:0 0 auto}
.pylc-ta-rows{overflow:auto;flex:1 1 auto;min-height:0;padding:2px 10px 6px}
.pylc-ta-row{display:flex;align-items:center;justify-content:space-between;gap:8px;
  font-size:11px;padding:2px 0;white-space:nowrap}
.pylc-ta-row .v{color:var(--ta-muted);font-variant-numeric:tabular-nums}
.pylc-ta-row .s{font-weight:600;min-width:34px;text-align:right}
.pylc-stack>.pylc-ta{height:auto;flex:1 1 auto;min-height:0}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

const CX = 80;
const CY = 78;
const R_OUT = 66;
const R_IN = 46;
const ZONES: TaSignal[] = ['sell', 'sell', 'neutral', 'buy', 'buy'];

function polar(angleDeg: number, radius: number): [number, number] {
    const rad = (angleDeg * Math.PI) / 180;
    return [CX + radius * Math.cos(rad), CY - radius * Math.sin(rad)];
}

function arcPath(a0: number, a1: number, rOut: number, rIn: number): string {
    const [x0, y0] = polar(a0, rOut);
    const [x1, y1] = polar(a1, rOut);
    const [x2, y2] = polar(a1, rIn);
    const [x3, y3] = polar(a0, rIn);
    const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
    return `M ${x0} ${y0} A ${rOut} ${rOut} 0 ${large} 1 ${x1} ${y1} ` +
           `L ${x2} ${y2} A ${rIn} ${rIn} 0 ${large} 0 ${x3} ${y3} Z`;
}

function labelFor(score: number): string {
    if (score >= 0.5) return 'STRONG BUY';
    if (score >= 0.15) return 'BUY';
    if (score > -0.15) return 'NEUTRAL';
    if (score > -0.5) return 'SELL';
    return 'STRONG SELL';
}

function signalFor(score: number): TaSignal {
    if (score >= 0.15) return 'buy';
    if (score <= -0.15) return 'sell';
    return 'neutral';
}

export class TechnicalAnalysis {
    public readonly element: HTMLDivElement;

    private _data: TaData = {};
    private _decimals: number;
    private _theme: ResolvedTheme;

    constructor(options: TaOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._decimals = options.decimals ?? 2;
        this._theme = this._resolveTheme(options.theme ?? {});
        this.element = document.createElement('div');
        this.element.className = 'pylc-ta';
        this._applyThemeVars();
        (parent ?? defaultContainer()).appendChild(this.element);
        this._data = options;
        this._render();
    }

    setData(data: TaData): void {
        this._data = { ...this._data, ...data };
        this._render();
    }

    setOptions(options: Partial<TaOptions>): void {
        if (options.decimals !== undefined) this._decimals = options.decimals;
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        this.setData(options);
    }

    destroy(): void {
        this.element.remove();
    }

    // --------------------------------------------------------------- internal
    private _resolveTheme(theme: TaTheme): ResolvedTheme {
        return {
            background: theme.background ?? '#131722',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            border: theme.border ?? '#2a2e39',
            buy: theme.buyColor ?? '#26a69a',
            sell: theme.sellColor ?? '#ef5350',
            neutral: theme.neutralColor ?? '#787b86',
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--ta-bg', this._theme.background);
        style.setProperty('--ta-text', this._theme.text);
        style.setProperty('--ta-muted', this._theme.muted);
        style.setProperty('--ta-border', this._theme.border);
    }

    private _signalColor(signal: string): string {
        const value = String(signal).toLowerCase();
        if (value === 'buy') return this._theme.buy;
        if (value === 'sell') return this._theme.sell;
        return this._theme.neutral;
    }

    private _render(): void {
        this.element.textContent = '';
        const score = Math.max(-1, Math.min(1, Number(this._data.score ?? 0) || 0));
        const label = this._data.label ?? labelFor(score);

        const top = document.createElement('div');
        top.className = 'pylc-ta-top';
        top.appendChild(this._makeGauge(score));
        top.appendChild(this._makeSummary(label, score, this._data.counts));
        this.element.appendChild(top);

        const tables = document.createElement('div');
        tables.className = 'pylc-ta-tables';
        tables.appendChild(this._makeTable('振荡器 Oscillators', this._data.oscillators ?? []));
        tables.appendChild(this._makeTable('移动平均 Moving Averages',
                                           this._data.moving_averages ?? []));
        this.element.appendChild(tables);
    }

    private _makeGauge(score: number): SVGSVGElement {
        const ns = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('class', 'pylc-ta-gauge');
        svg.setAttribute('width', '168');
        svg.setAttribute('height', '96');
        svg.setAttribute('viewBox', '0 0 168 96');

        for (let i = 0; i < 5; i++) {
            const a0 = 180 - i * 36;
            const a1 = 180 - (i + 1) * 36;
            const path = document.createElementNS(ns, 'path');
            path.setAttribute('d', arcPath(a0, a1, R_OUT, R_IN));
            path.setAttribute('fill', this._signalColor(ZONES[i]));
            path.setAttribute('opacity', i === 2 ? '0.55' : '0.9');
            svg.appendChild(path);
        }

        const angle = 90 - score * 90;
        const [nx, ny] = polar(angle, R_IN - 4);
        const needle = document.createElementNS(ns, 'line');
        needle.setAttribute('x1', String(CX));
        needle.setAttribute('y1', String(CY));
        needle.setAttribute('x2', String(nx));
        needle.setAttribute('y2', String(ny));
        needle.setAttribute('stroke', this._theme.text);
        needle.setAttribute('stroke-width', '3');
        needle.setAttribute('stroke-linecap', 'round');
        svg.appendChild(needle);

        const hub = document.createElementNS(ns, 'circle');
        hub.setAttribute('cx', String(CX));
        hub.setAttribute('cy', String(CY));
        hub.setAttribute('r', '5');
        hub.setAttribute('fill', this._theme.text);
        svg.appendChild(hub);
        return svg;
    }

    private _makeSummary(label: string, score: number, counts?: TaData['counts']): HTMLDivElement {
        const box = document.createElement('div');
        box.className = 'pylc-ta-summary';
        const title = document.createElement('div');
        title.className = 'pylc-ta-label';
        title.style.color = this._signalColor(signalFor(score));
        title.textContent = label;
        box.appendChild(title);

        if (counts) {
            const row = document.createElement('div');
            row.className = 'pylc-ta-counts';
            const entries: Array<[string, string, number]> = [
                ['sell', this._theme.sell, counts.sell ?? 0],
                ['neutral', this._theme.neutral, counts.neutral ?? 0],
                ['buy', this._theme.buy, counts.buy ?? 0],
            ];
            for (const [name, color, value] of entries) {
                const item = document.createElement('span');
                item.innerHTML = `${name} <b style="color:${color}">${value}</b>`;
                row.appendChild(item);
            }
            box.appendChild(row);
        }
        return box;
    }

    private _makeTable(title: string, rows: TaRow[]): HTMLDivElement {
        const col = document.createElement('div');
        col.className = 'pylc-ta-col';
        const head = document.createElement('h4');
        head.textContent = title;
        col.appendChild(head);
        const body = document.createElement('div');
        body.className = 'pylc-ta-rows';
        for (const row of rows) {
            const node = document.createElement('div');
            node.className = 'pylc-ta-row';
            const name = document.createElement('span');
            name.textContent = row.name;
            const value = document.createElement('span');
            value.className = 'v';
            value.textContent = typeof row.value === 'number'
                ? row.value.toFixed(this._decimals) : String(row.value ?? '—');
            const signal = document.createElement('span');
            signal.className = 's';
            signal.style.color = this._signalColor(row.signal);
            signal.textContent = String(row.signal);
            node.appendChild(name);
            node.appendChild(value);
            node.appendChild(signal);
            body.appendChild(node);
        }
        col.appendChild(body);
        return col;
    }
}

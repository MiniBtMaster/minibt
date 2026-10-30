/**
 * SeasonalChart — a canvas bar chart for seasonality (average performance per
 * period). Positive bars go up and are coloured by the scheme's positive colour,
 * negative bars go down, and the zero line sits in the middle so the periods are
 * directly comparable.
 *
 * Python aggregates the numbers (see `pylightcharts.panels.seasonal`); this only
 * draws them.
 */

import { ensureStyle } from './emit';

export type SeasonalColorScheme = 'cn' | 'tv';

export interface SeasonalTheme {
    background?: string;
    grid?: string;
    text?: string;
    muted?: string;
    positive?: string;
    negative?: string;
    zero?: string;
}

export interface SeasonalOptions {
    /** either numbers or `{label, value}` points */
    values?: Array<number | { label?: string; value: number }>;
    labels?: string[];
    colorScheme?: SeasonalColorScheme;
    showValues?: boolean;
    showZeroLine?: boolean;
    /** value decimals for the bar labels (default 2) */
    decimals?: number;
    /** treat values as percentages (adds `%`); default true */
    percent?: boolean;
    padding?: number;
    theme?: SeasonalTheme;
}

interface ResolvedTheme {
    background: string;
    grid: string;
    text: string;
    muted: string;
    positive: string;
    negative: string;
    zero: string;
}

interface Bar {
    label: string;
    value: number;
}

const STYLE_ID = 'pylightcharts-seasonal-style';
const CSS = `
.pylc-seasonal{position:relative;width:100%;height:100%;overflow:hidden;background:var(--sc-bg)}
.pylc-seasonal canvas{display:block;width:100%;height:100%}
.pylc-stack>.pylc-seasonal{height:auto;flex:1 1 auto;min-height:0}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

export class SeasonalChart {
    public readonly element: HTMLDivElement;

    private readonly _canvas: HTMLCanvasElement;
    private readonly _ctx: CanvasRenderingContext2D;
    private _bars: Bar[] = [];
    private _scheme: SeasonalColorScheme;
    private _showValues: boolean;
    private _showZeroLine: boolean;
    private _decimals: number;
    private _percent: boolean;
    private _padding: number;
    private _theme: ResolvedTheme;
    private _drawWidth = 1;
    private _drawHeight = 1;

    constructor(options: SeasonalOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._scheme = options.colorScheme ?? 'cn';
        this._showValues = options.showValues ?? true;
        this._showZeroLine = options.showZeroLine ?? true;
        this._decimals = options.decimals ?? 2;
        this._percent = options.percent ?? true;
        this._padding = options.padding ?? 1;
        this._theme = this._resolveTheme(options.theme ?? {});

        this.element = document.createElement('div');
        this.element.className = 'pylc-seasonal';
        this._applyThemeVars();
        this._canvas = document.createElement('canvas');
        this.element.appendChild(this._canvas);
        const ctx = this._canvas.getContext('2d');
        if (ctx === null) {
            throw new Error('pylightcharts: 2d canvas context unavailable for SeasonalChart');
        }
        this._ctx = ctx;
        (parent ?? defaultContainer()).appendChild(this.element);

        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(() => this.draw()).observe(this.element);
        }
        if (options.values) {
            this.setData(options.values, options.labels);
        }
    }

    setData(
        values: Array<number | { label?: string; value: number }>,
        labels?: string[],
    ): void {
        this._bars = (values ?? []).map((entry, index) => {
            if (typeof entry === 'number') {
                return { label: labels?.[index] ?? String(index + 1), value: entry };
            }
            return {
                label: entry.label ?? labels?.[index] ?? String(index + 1),
                value: Number(entry.value) || 0,
            };
        });
        this.draw();
    }

    setOptions(options: Partial<SeasonalOptions>): void {
        if (options.colorScheme && options.colorScheme !== this._scheme) {
            this._scheme = options.colorScheme;
        }
        if (options.showValues !== undefined) this._showValues = options.showValues;
        if (options.showZeroLine !== undefined) this._showZeroLine = options.showZeroLine;
        if (options.decimals !== undefined) this._decimals = options.decimals;
        if (options.percent !== undefined) this._percent = options.percent;
        if (options.padding !== undefined) this._padding = options.padding;
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        this.draw();
    }

    reSize(): void {
        this.draw();
    }

    destroy(): void {
        this.element.remove();
    }

    // --------------------------------------------------------------- internal
    private _resolveTheme(theme: SeasonalTheme): ResolvedTheme {
        const cn = this._scheme === 'cn';
        return {
            background: theme.background ?? 'transparent',
            grid: theme.grid ?? 'rgba(120,123,134,0.25)',
            text: theme.text ?? '#d1d4dc',
            muted: theme.muted ?? '#787b86',
            positive: theme.positive ?? (cn ? '#ef5350' : '#26a69a'),
            negative: theme.negative ?? (cn ? '#26a69a' : '#ef5350'),
            zero: theme.zero ?? '#787b86',
        };
    }

    private _applyThemeVars(): void {
        this.element.style.setProperty('--sc-bg', this._theme.background);
    }

    private draw(): void {
        const width = Math.max(1, this.element.clientWidth);
        const height = Math.max(1, this.element.clientHeight);
        const dpr = window.devicePixelRatio || 1;
        const bufferWidth = Math.max(1, Math.round(width * dpr));
        const bufferHeight = Math.max(1, Math.round(height * dpr));
        if (this._canvas.width !== bufferWidth || this._canvas.height !== bufferHeight) {
            this._canvas.width = bufferWidth;
            this._canvas.height = bufferHeight;
            this._ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        this._drawWidth = width;
        this._drawHeight = height;
        this._render();
    }

    private _render(): void {
        const ctx = this._ctx;
        const width = this._drawWidth;
        const height = this._drawHeight;
        ctx.clearRect(0, 0, width, height);
        if (this._bars.length === 0) {
            return;
        }

        const padLeft = 8;
        const padRight = 8;
        const padTop = this._showValues ? 18 : 8;
        const padBottom = 20;
        const plotW = Math.max(1, width - padLeft - padRight);
        const plotH = Math.max(1, height - padTop - padBottom);
        const midY = padTop + plotH / 2;

        let maxAbs = 0;
        for (const bar of this._bars) {
            maxAbs = Math.max(maxAbs, Math.abs(bar.value));
        }
        if (maxAbs === 0) {
            maxAbs = 1;
        }

        if (this._showZeroLine) {
            ctx.strokeStyle = this._theme.zero;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(padLeft, midY + 0.5);
            ctx.lineTo(width - padRight, midY + 0.5);
            ctx.stroke();
        }

        const slot = plotW / this._bars.length;
        const barWidth = Math.max(2, slot * (1 - 0.2 * this._padding) - 4);
        ctx.font = '10px -apple-system, "Microsoft YaHei", Arial, sans-serif';
        ctx.textAlign = 'center';

        for (let i = 0; i < this._bars.length; i++) {
            const bar = this._bars[i];
            const centerX = padLeft + slot * (i + 0.5);
            const barHeight = (Math.abs(bar.value) / maxAbs) * (plotH / 2 - 2);
            const positive = bar.value >= 0;
            ctx.fillStyle = positive ? this._theme.positive : this._theme.negative;
            const top = positive ? midY - barHeight : midY;
            ctx.fillRect(centerX - barWidth / 2, top, barWidth, barHeight);

            ctx.fillStyle = this._theme.muted;
            ctx.fillText(bar.label, centerX, height - 6);

            if (this._showValues) {
                const text = `${positive ? '+' : ''}${bar.value.toFixed(this._decimals)}${this._percent ? '%' : ''}`;
                ctx.fillStyle = positive ? this._theme.positive : this._theme.negative;
                const labelY = positive ? top - 5 : top + barHeight + 11;
                ctx.fillText(text, centerX, labelY);
            }
        }
    }
}

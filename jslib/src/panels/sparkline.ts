/**
 * Sparkline — a tiny canvas line/area chart.
 *
 * Unlike every other series in this package a sparkline is **not** a
 * Lightweight Charts instance: a table with 5000 instruments would need 5000
 * engines, which is far too heavy. A sparkline is a single `<canvas>` that
 * redraws on `setData`, so hundreds of them stay cheap.
 *
 * It is driven from Python through the generic bridge:
 *
 *   spark = new Lib.Sparkline({...});      // window.<id> = ...
 *   Lib.invoke('window.<id>', 'setData', [ [1, 2, 3, ...] ]);
 *
 * The class never appends itself to the page; the Python wrapper (or the
 * DataGrid cell) places `element`.
 */

export type SparklineBaseline = 'first' | 'zero' | 'none';

export interface SparklineOptions {
    /** CSS pixels. A number sets an explicit width, a string is used verbatim. */
    width?: number | string;
    height?: number;
    /** colour used when `baseline` is `'none'` */
    lineColor?: string;
    /** explicit area fill; when omitted the line colour is used at low alpha */
    fillColor?: string;
    /** colour when the last value is **above** the baseline */
    upColor?: string;
    /** colour when the last value is **below** the baseline */
    downColor?: string;
    lineWidth?: number;
    /** `'first'` compares last vs first, `'zero'` vs 0, `'none'` keeps lineColor */
    baseline?: SparklineBaseline;
    padding?: number;
    /** draw a dot on the last point */
    endDot?: boolean;
    /** keep the vertical range pinned to [low, high] instead of the data range */
    min?: number;
    max?: number;
}

export class Sparkline {
    public readonly element: HTMLCanvasElement;

    private readonly _ctx: CanvasRenderingContext2D;
    private _values: number[] = [];
    private _width: number | string;
    private _height: number;
    private _drawWidth = 1;
    private _drawHeight = 1;
    private _lineColor: string;
    private _fillColor: string;
    private _upColor: string;
    private _downColor: string;
    private _lineWidth: number;
    private _baseline: SparklineBaseline;
    private _padding: number;
    private _endDot: boolean;
    private _min: number | null;
    private _max: number | null;

    constructor(options: SparklineOptions = {}, parent?: HTMLElement | null) {
        this.element = document.createElement('canvas');
        this.element.className = 'pylc-sparkline';
        this.element.style.display = 'block';
        const ctx = this.element.getContext('2d');
        if (ctx === null) {
            throw new Error('pylightcharts: 2d canvas context unavailable for Sparkline');
        }
        this._ctx = ctx;

        this._width = typeof options.width === 'number' ? options.width : 80;
        this._height = options.height ?? 24;
        this._lineColor = options.lineColor ?? '#2962ff';
        this._fillColor = options.fillColor ?? '';
        this._upColor = options.upColor ?? '#26a69a';
        this._downColor = options.downColor ?? '#ef5350';
        this._lineWidth = options.lineWidth ?? 1.6;
        this._baseline = options.baseline ?? 'first';
        this._padding = options.padding ?? 2;
        this._endDot = options.endDot ?? false;
        this._min = options.min ?? null;
        this._max = options.max ?? null;

        if (typeof options.width === 'string') {
            this.element.style.width = options.width;
        }
        if (typeof options.height === 'number') {
            this.element.style.height = `${options.height}px`;
        }
        if (parent) {
            parent.appendChild(this.element);
        }
        // a percentage width follows its container: redraw when it resizes
        if (typeof options.width === 'string'
            && typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(() => this.draw()).observe(this.element);
        }
    }

    /** Replace the data and redraw. Non-finite values are dropped. */
    setData(values: number[]): void {
        this._values = (values ?? [])
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value));
        this.draw();
    }

    setOptions(options: SparklineOptions): void {
        if (options.lineColor !== undefined) this._lineColor = options.lineColor;
        if (options.fillColor !== undefined) this._fillColor = options.fillColor;
        if (options.upColor !== undefined) this._upColor = options.upColor;
        if (options.downColor !== undefined) this._downColor = options.downColor;
        if (options.lineWidth !== undefined) this._lineWidth = options.lineWidth;
        if (options.baseline !== undefined) this._baseline = options.baseline;
        if (options.padding !== undefined) this._padding = options.padding;
        if (options.endDot !== undefined) this._endDot = options.endDot;
        if (options.min !== undefined) this._min = options.min;
        if (options.max !== undefined) this._max = options.max;
        this.draw();
    }

    reSize(width: number | string, height: number): void {
        this._width = width;
        this._height = height;
        this.element.style.width = typeof width === 'number' ? `${width}px` : width;
        this.element.style.height = `${height}px`;
        this.draw();
    }

    getElement(): HTMLCanvasElement {
        return this.element;
    }

    /** Current series colour (useful for hosts that colour a sibling label). */
    color(): string {
        return this._seriesColor();
    }

    private _sync(): void {
        const width = typeof this._width === 'number'
            ? this._width
            : Math.max(1, this.element.clientWidth
                || this.element.parentElement?.clientWidth || 80);
        const height = this._height;
        const dpr = window.devicePixelRatio || 1;
        const bufferWidth = Math.max(1, Math.round(width * dpr));
        const bufferHeight = Math.max(1, Math.round(height * dpr));
        if (this.element.width !== bufferWidth
            || this.element.height !== bufferHeight) {
            this.element.width = bufferWidth;
            this.element.height = bufferHeight;
            this._ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        this._drawWidth = width;
        this._drawHeight = height;
    }

    private _seriesColor(): string {
        const values = this._values;
        if (this._baseline === 'none' || values.length === 0) {
            return this._lineColor;
        }
        const last = values[values.length - 1];
        const base = this._baseline === 'zero' ? 0 : values[0];
        return last >= base ? this._upColor : this._downColor;
    }

    private draw(): void {
        this._sync();
        const ctx = this._ctx;
        const width = this._drawWidth;
        const height = this._drawHeight;
        ctx.clearRect(0, 0, width, height);

        const values = this._values;
        if (values.length < 2) {
            return;
        }

        let min = this._min ?? Infinity;
        let max = this._max ?? -Infinity;
        for (const value of values) {
            if (min > value) min = value;
            if (max < value) max = value;
        }
        if (min === max) {
            min -= 1;
            max += 1;
        }

        const pad = this._padding;
        const innerW = Math.max(1, width - pad * 2);
        const innerH = Math.max(1, height - pad * 2);
        const lastIndex = values.length - 1;
        const x = (index: number): number => pad + (index / lastIndex) * innerW;
        const y = (value: number): number =>
            pad + (1 - (value - min) / (max - min)) * innerH;

        const color = this._seriesColor();

        // area fill: explicit colour, or a translucent wash of the line colour
        if (this._fillColor || this._baseline !== 'none') {
            ctx.beginPath();
            ctx.moveTo(x(0), height - pad);
            for (let i = 0; i < values.length; i++) {
                ctx.lineTo(x(i), y(values[i]));
            }
            ctx.lineTo(x(lastIndex), height - pad);
            ctx.closePath();
            if (this._fillColor) {
                ctx.fillStyle = this._fillColor;
            } else {
                ctx.globalAlpha = 0.14;
                ctx.fillStyle = color;
            }
            ctx.fill();
            ctx.globalAlpha = 1;
        }

        ctx.beginPath();
        for (let i = 0; i < values.length; i++) {
            const px = x(i);
            const py = y(values[i]);
            if (i === 0) {
                ctx.moveTo(px, py);
            } else {
                ctx.lineTo(px, py);
            }
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = this._lineWidth;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();

        if (this._endDot) {
            ctx.beginPath();
            ctx.arc(x(lastIndex), y(values[lastIndex]), Math.max(1.2, this._lineWidth), 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        }
    }
}

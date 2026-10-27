import {
    ISeriesApi, MouseEventParams, Point, SeriesType, Time,
} from "lightweight-charts";
import type { Handler } from "./handler";
import { makeTimeFormatter } from "./formatters";
import { unregister } from "./rpc";
import { seriesColor } from "./series-color";

/**
 * Crosshair tooltips - the two from the official
 * [tooltips tutorial](https://tradingview.github.io/lightweight-charts/tutorials/how_to/tooltips):
 *
 * - `tracking`: an opaque box next to the cursor, flipping to the other side
 *   near the right / bottom edge.
 * - `magnifier`: a translucent band pinned to the top edge that only follows
 *   the cursor along the time axis (the tutorial's magnifying glass).
 *
 * The tutorial builds them from an `html` element plus `subscribeCrosshairMove`;
 * this does the same inside the bundle, so no round trip to python is needed on
 * every mouse move. Colours default to the root CSS variables, which is what
 * makes them follow the light / dark themes for free.
 */

export type TooltipMode = 'tracking' | 'magnifier';

export interface TooltipOptions {
    mode?: TooltipMode;
    /** first line; empty (or `showTitle: false`) hides it */
    title?: string;
    /** defaults to the series' own colour */
    titleColor?: string;
    /** colour of the big value (defaults to `textColor`) */
    valueColor?: string;
    /** colour of the field labels (drawn at 70% opacity) */
    labelColor?: string;
    /** extra fields to show; `'auto'` takes every numeric field, e.g. OHLC */
    fields?: string[] | 'auto' | null;
    /** labels for `fields` (defaults to O / H / L / C / V, else the key) */
    fieldLabels?: string[] | null;
    /** tint the value / fields with the series' up & down colours */
    colorByCandle?: boolean;
    /** price decimals; omit to use the series' own price format */
    decimals?: number | null;
    /** time template (`YYYY-MM-DD`, `YYYY-MM-DD HH:mm`, ...) */
    timeFormat?: string;
    /** interpret timestamps as UTC (default true) */
    timeUtc?: boolean;
    width?: number;
    /**
     * tracking: fixed box height (by default the box hugs its content);
     * magnifier: defaults to the pane height
     */
    height?: number;
    /** tracking: gap between the cursor and the box */
    margin?: number;
    padding?: number;
    fontSize?: number;
    bigFontSize?: number;
    fontFamily?: string;
    /** any CSS colour, defaults to `var(--bg-color)` */
    background?: string;
    /** 1 = opaque; the magnifier defaults to 0.25 like the tutorial */
    backgroundOpacity?: number;
    textColor?: string;
    borderColor?: string;
    borderWidth?: number;
    borderRadius?: number;
    shadow?: boolean;
    showTitle?: boolean;
    showValue?: boolean;
    showTime?: boolean;
    /** tracking: flip the box when it would leave the pane */
    flip?: boolean;
    zIndex?: number;
}

/** Where a pane sits inside the chart's own `div`. */
interface PaneBox {
    left: number;
    top: number;
    width: number;
    height: number;
}

/** Single letter labels for the price fields of a bar. */
const FIELD_LETTERS: Record<string, string> = {
    open: 'O', high: 'H', low: 'L', close: 'C', volume: 'V',
};

const DEFAULT_FONT = "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', "
    + "Roboto, Ubuntu, sans-serif";

export class Tooltip {
    private _handler: Handler;
    private _series: ISeriesApi<SeriesType>;
    private _options: TooltipOptions;
    /** false after `hide()`: the crosshair must not bring the box back */
    private _enabled = true;
    private _handle: string | null = null;
    /** last crosshair position, so `applyOptions` can redraw what is on screen */
    private _last: { data: Record<string, unknown>, time: Time, point: Point,
        pane: PaneBox } | null = null;
    public div: HTMLDivElement;
    private _background: HTMLDivElement;
    private _content: HTMLDivElement;
    private _title: HTMLDivElement;
    private _value: HTMLDivElement;
    private _fields: HTMLDivElement;
    private _time: HTMLDivElement;

    constructor(handler: Handler, series: ISeriesApi<SeriesType>,
                options: TooltipOptions = {}) {
        this._handler = handler;
        this._series = series;
        this._options = { ...options };

        this.div = document.createElement('div');
        this.div.classList.add('tooltip');
        this.div.style.position = 'absolute';
        this.div.style.display = 'none';
        this.div.style.boxSizing = 'border-box';
        this.div.style.pointerEvents = 'none';
        this.div.style.overflow = 'hidden';
        this.div.style.whiteSpace = 'nowrap';

        // the translucent magnifier background is its own layer, so the text on
        // top stays fully opaque
        this._background = document.createElement('div');
        this._background.style.position = 'absolute';
        this._background.style.inset = '0';
        this._background.style.borderRadius = 'inherit';
        this.div.appendChild(this._background);

        this._content = document.createElement('div');
        this._content.style.position = 'relative';
        this.div.appendChild(this._content);

        this._title = document.createElement('div');
        this._value = document.createElement('div');
        this._fields = document.createElement('div');
        this._fields.style.display = 'flex';
        this._fields.style.flexWrap = 'wrap';
        this._fields.style.columnGap = '0.6em';
        this._time = document.createElement('div');
        this._content.appendChild(this._title);
        this._content.appendChild(this._value);
        this._content.appendChild(this._fields);
        this._content.appendChild(this._time);

        handler.div.appendChild(this.div);
        handler.addCrosshairListener(this._onCrosshair);
        this.applyOptions(this._options);
    }

    /** Resolved options (the ones given plus the defaults already applied). */
    options(): TooltipOptions {
        return { ...this._options };
    }

    mode(): TooltipMode {
        return this._options.mode === 'magnifier' ? 'magnifier' : 'tracking';
    }

    title(): string {
        return this._options.title ?? '';
    }

    /** Merge new options; a box that is on screen is redrawn immediately. */
    applyOptions(options: TooltipOptions) {
        Object.assign(this._options, options);
        const magnifier = this.mode() === 'magnifier';
        const borderWidth = this._options.borderWidth ?? 1;
        // like the tutorial, the frame is the series' colour (the background
        // and the text stay theme colours, so both themes read well)
        const borderColor = this._options.borderColor
            ?? seriesColor(this._series).solid;
        this.div.style.width = `${this._options.width ?? 96}px`;
        // the magnifier's height comes from the pane and the tracking box hugs
        // its content (a fixed 80px height clipped the time / field lines as
        // soon as a title and the OHLC fields were shown) - both are only
        // overridden when a height is given, see `_place`
        this.div.style.height = this._options.height !== undefined
            ? `${this._options.height}px` : (magnifier ? '100%' : 'auto');
        this.div.style.padding = `${this._options.padding ?? 8}px`;
        this.div.style.fontSize = `${this._options.fontSize ?? 12}px`;
        this.div.style.fontFamily = this._options.fontFamily ?? DEFAULT_FONT;
        this.div.style.textAlign = 'left';
        this.div.style.zIndex = String(this._options.zIndex ?? 1000);
        const border = `${borderWidth}px solid ${borderColor}`;
        this.div.style.border = border;
        // the tutorial's magnifier sits against the top edge, so it has no
        // bottom border - which has to be set explicitly: assigning '' to
        // `borderBottom` *removes* the longhands the `border` shorthand just
        // wrote, leaving the box without its bottom edge
        this.div.style.borderBottom = magnifier ? 'none' : border;
        const radius = this._options.borderRadius;
        this.div.style.borderRadius = radius !== undefined
            ? `${radius}px` : (magnifier ? '4px 4px 0px 0px' : '2px');
        this.div.style.boxShadow = (this._options.shadow ?? magnifier)
            ? '0 2px 5px 0 rgba(117, 134, 150, 0.45)' : 'none';
        this._background.style.background =
            this._options.background ?? 'var(--bg-color)';
        this._background.style.opacity =
            String(this._options.backgroundOpacity ?? (magnifier ? 0.25 : 1));
        const textColor = this._options.textColor ?? 'var(--color)';
        this.div.style.color = textColor;
        // the title defaults to the series' own colour, like the legend row
        this._title.style.color = this._options.titleColor
            ?? seriesColor(this._series).solid;
        this._title.style.display = (this._options.showTitle ?? true)
            && this.title() ? 'block' : 'none';
        this._title.textContent = this.title();
        this._value.style.fontSize = `${this._options.bigFontSize ?? 24}px`;
        this._value.style.margin = '4px 0px';
        this._value.style.display = (this._options.showValue ?? true)
            ? 'block' : 'none';
        this._fields.style.display = this._options.fields ? 'flex' : 'none';
        this._time.style.display = (this._options.showTime ?? true)
            ? 'block' : 'none';
        this._time.style.opacity = '0.8';
        if (this._last) {
            this._fill(this._last.data, this._last.time);
            this._place(this._last.point, this._last.pane);
        }
    }

    setTitle(title: string) {
        this.applyOptions({ title });
    }

    setFields(fields: string[] | 'auto' | null) {
        this.applyOptions({ fields });
    }

    /** Show it again after :meth:`hide` (at the next crosshair move). */
    show() {
        this._enabled = true;
        if (this._last) {
            this.div.style.display = 'block';
            this._fill(this._last.data, this._last.time);
            this._place(this._last.point, this._last.pane);
        }
    }

    /** Stop following the crosshair and hide the box. */
    hide() {
        this._enabled = false;
        this.div.style.display = 'none';
    }

    visible(): boolean {
        return this._enabled && this.div.style.display !== 'none';
    }

    /** Remove the box, stop listening and drop the JS handle. */
    remove() {
        this._handler.removeCrosshairListener(this._onCrosshair);
        this.div.remove();
        if (this._handle) {
            unregister(this._handle);
            this._handle = null;
        }
    }

    /** Called by the handler factory so `remove()` can drop the registry entry. */
    setHandle(handle: string) {
        this._handle = handle;
    }

    toJSON() {
        const { _handler, _series, _last, div, _background, _content, _title,
            _value, _fields, _time, ...serialized } = this;
        return serialized;
    }

    // ---------------------------------------------------------------- render
    private _onCrosshair = (param: MouseEventParams<Time>) => {
        if (!this._enabled) return;
        const point = param.point;
        const data = param.seriesData?.get(this._series) as
            Record<string, unknown> | undefined;
        if (!point || param.time === undefined || !data) {
            this._last = null;
            this.div.style.display = 'none';
            return;
        }
        const pane = this._paneBox(param.paneIndex ?? 0);
        if (point.x < 0 || point.y < 0
            || point.x > pane.width || point.y > pane.height) {
            this._last = null;
            this.div.style.display = 'none';
            return;
        }
        this._last = { data, time: param.time, point, pane };
        this._fill(data, param.time);
        this.div.style.display = 'block';
        this._place(point, pane);
    };

    /**
     * The pane's **drawing area**: the pane widget spans the price scales too, so
     * its own rectangle is not the area `param.point` is measured in - the left
     * scale's width has to be added and `paneSize()` used for the extent.
     */
    private _paneBox(index: number): PaneBox {
        const chart = this._handler.chart;
        const container = this._handler.div.getBoundingClientRect();
        const element = chart.panes()[index]?.getHTMLElement?.();
        const size = chart.paneSize(index);
        const widget = element ? element.getBoundingClientRect() : null;
        return {
            left: (widget ? widget.left - container.left : 0)
                + chart.priceScale('left').width(),
            top: widget ? widget.top - container.top : 0,
            width: size.width,
            height: size.height,
        };
    }

    private _place(point: Point, pane: PaneBox) {
        const width = this._options.width ?? 96;
        const magnifier = this.mode() === 'magnifier';
        let left: number;
        let top: number;
        if (magnifier) {
            // the tutorial's lens: centred on the cursor, clamped to the pane
            left = pane.left + point.x - width / 2;
            left = Math.min(left, pane.left + pane.width - width);
            left = Math.max(left, pane.left);
            top = pane.top;
            if (this._options.height === undefined) {
                this.div.style.height = `${pane.height}px`;
            }
        } else {
            const height = this._options.height
                ?? (this.div.offsetHeight || 80);
            const margin = this._options.margin ?? 15;
            left = pane.left + point.x + margin;
            if (this._options.flip !== false
                && left + width > pane.left + pane.width) {
                left = pane.left + point.x - margin - width;
            }
            top = pane.top + point.y + margin;
            if (this._options.flip !== false
                && top + height > pane.top + pane.height) {
                top = pane.top + point.y - height - margin;
            }
        }
        this.div.style.left = `${Math.round(left)}px`;
        this.div.style.top = `${Math.round(top)}px`;
    }

    /** Format the hovered data point into the box. */
    private _fill(data: Record<string, unknown>, time: Time) {
        const candle = this._candleColor(data);
        const fallback = this._options.textColor ?? 'var(--color)';
        this._value.textContent = this._number(this._mainValue(data));
        this._value.style.color =
            candle ?? this._options.valueColor ?? fallback;
        this._time.textContent = this._formatTime(time);
        this._fillFields(data, candle ?? this._options.valueColor ?? fallback);
    }

    private _fillFields(data: Record<string, unknown>, valueColor: string) {
        const requested = this._options.fields;
        this._fields.textContent = '';
        if (!requested) return;
        const keys = requested === 'auto'
            ? Object.keys(data).filter(key => key !== 'time' && key !== 'color'
                && typeof data[key] === 'number')
            : requested;
        const labels = this._options.fieldLabels ?? [];
        keys.forEach((key, index) => {
            const raw = data[key];
            if (raw === undefined || raw === null) return;
            const entry = document.createElement('span');
            const label = document.createElement('span');
            label.textContent = labels[index] ?? FIELD_LETTERS[key] ?? key;
            label.style.opacity = '0.7';
            label.style.color = this._options.labelColor
                ?? this._options.titleColor ?? this._options.textColor
                ?? 'var(--color)';
            entry.appendChild(label);
            entry.appendChild(document.createTextNode(
                ` ${this._number(raw)}`));
            entry.style.color = valueColor;
            this._fields.appendChild(entry);
        });
    }

    /** The price the big number shows: `close` for bars, `value` otherwise. */
    private _mainValue(data: Record<string, unknown>): number | null {
        for (const key of ['close', 'value', 'price']) {
            const value = data[key];
            if (typeof value === 'number') return value;
        }
        return null;
    }

    private _number(value: unknown): string {
        if (typeof value !== 'number' || !isFinite(value)) {
            return value === undefined || value === null ? '' : String(value);
        }
        const decimals = this._options.decimals;
        if (decimals !== undefined && decimals !== null) {
            return value.toFixed(decimals);
        }
        return this._series.priceFormatter().format(value);
    }

    private _candleColor(data: Record<string, unknown>): string | null {
        if (this._options.colorByCandle === false) return null;
        const open = data.open;
        const close = data.close;
        if (typeof open !== 'number' || typeof close !== 'number') return null;
        const options = this._series.options() as
            { upColor?: string, downColor?: string };
        return close >= open ? options.upColor ?? null : options.downColor ?? null;
    }

    private _formatTime(time: Time): string {
        if (typeof time === 'string') return time;
        const template = this._options.timeFormat
            ?? (typeof time === 'number' ? 'YYYY-MM-DD HH:mm' : 'YYYY-MM-DD');
        return makeTimeFormatter({
            template, utc: this._options.timeUtc !== false,
        })(time);
    }
}

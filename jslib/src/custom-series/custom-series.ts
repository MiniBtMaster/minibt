import {
    Coordinate,
    CustomSeriesHitTestResult,
    CustomSeriesPricePlotValues,
    CustomSeriesWhitespaceData,
    ICustomSeriesPaneRenderer,
    ICustomSeriesPaneView,
    PaneRendererCustomData,
    PriceToCoordinateConverter,
    customSeriesDefaultOptions,
} from 'lightweight-charts';
import { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import { lookupCallback } from '../general/callbacks';

/**
 * A generic, declarative custom series.
 *
 * The hard part of a custom series is `draw()`, which runs synchronously on
 * every frame - python cannot take part in that. So instead we split it:
 *
 *   - "what to draw"  -> a list of shape descriptors stored on each data item,
 *                        produced by python once per data update.
 *   - "how to draw"   -> this file, which maps the descriptors to pixels every
 *                        frame using the bar x coordinate and the price
 *                        converter provided by the library.
 *
 * A data item looks like:
 *
 *   { time, value?, low?, high?, color?, shapes?: Shape[] }
 *
 * Shape coordinates: `price`/`from`/`to` are prices (mapped through the price
 * converter), horizontal positions are offsets in *bar spacing* units from the
 * item's centre (`-0.4` .. `0.4` spans a bar).
 *
 * NOTE: only the bars inside `visibleRange` have a valid `x` - the library
 * computes coordinates for that slice only, so off-screen items keep `NaN` (never
 * shown yet) or a stale value from a previous frame. Renderers must therefore
 * iterate `visibleRange` (see `CustomSeriesPaneView.visibleBars`), otherwise the
 * off-screen shapes pile up along the pane edges while zooming.
 */

export interface Shape {
    type: 'rect' | 'band' | 'line' | 'circle' | 'text' | 'polyline' | 'marker';
    /** vertical anchors (prices) */
    price?: number;
    from?: number;
    to?: number;
    /** horizontal anchors, in bar-spacing units (default -0.4 / 0.4) */
    left?: number;
    right?: number;
    offset?: number;
    /** 标记文字颜色（信号 `B` / `S` ✓） */
    textColor?: string;
    /** 标记文字字号（`SignalStyle.set_label("B", 14)` ✓） */
    textSize?: number;
    /** polyline points: [[xOffset, price], ...] */
    points?: Array<[number, number]>;
    /** style（`borderColor` / `borderWidth` 同时用于下方的标签框 ✓） */
    color?: string;
    fillColor?: string;
    borderColor?: string;
    borderWidth?: number;
    width?: number;
    style?: number;
    radius?: number;
    /** `marker` glyph: a marker name (minibt `Markers`), `size` in pixels */
    marker?: string;
    size?: number;
    text?: string;
    fontSize?: number;
    align?: CanvasTextAlign;
    baseline?: CanvasTextBaseline;
    /** multi-line labels (`\n` inside `text`): line spacing multiplier */
    lineHeight?: number;
    /** pixel offsets (CSS px) on top of the anchor position */
    offsetX?: number;
    offsetY?: number;
    fontFamily?: string;
    fontWeight?: string;
    fontStyle?: string;
    /** label box: background + border (drawn behind the text)
     *
     * `borderColor` / `borderWidth` 与上面「图像样式」共用同一对字段（同一份
     * `ShapeStyle` 里重复声明会报 TS2300 ✗）✓
     */
    backgroundColor?: string;
    backgroundAlpha?: number;
    borderAlpha?: number;
    padding?: number;
}

/**
 * Pixel-space marker glyphs (`marker` shape).
 *
 * `cx`/`cy` is the anchor: for `triangle`/`inverted_triangle`/`arrow_*` it is the
 * glyph's *tip* (so it can be placed right against a bar's high/low); for every
 * other kind it is the centre. `size` is a half-extent in device pixels, so the
 * glyphs stay the same size at every zoom level (unlike `polyline`, whose y is a
 * price).
 */
/**
 * Y offsets for a (possibly multi-line) text label.
 *
 * Newlines in `text` split the label into several lines (same convention as
 * bokeh's
 * `LabelSet` - and the whole block stays anchored at the shape's `y`:
 * `top` grows downwards, `bottom` grows upwards, `middle` (default) keeps the
 * block centred on `y`.
 */
export function textLineOffsets(text: unknown, lineHeight: number,
                                baseline: string): number[] {
    const count = String(text ?? '').split('\n').length;
    const first = baseline === 'top' ? 0
        : baseline === 'bottom' ? -(count - 1) * lineHeight
            : -(count - 1) * lineHeight / 2;
    return Array.from({ length: count }, (_, i) => first + i * lineHeight);
}

function drawMarker(
    ctx: CanvasRenderingContext2D,
    kind: string,
    cx: number,
    cy: number,
    size: number,
    colour: string,
    shape: Shape,
    ratio: number,
): void {
    const r = Math.max(size, 3);
    const stroke = shape.borderColor ?? colour;
    const line = (x1: number, y1: number, x2: number, y2: number): void => {
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
    };
    const poly = (points: Array<[number, number]>): void => {
        ctx.beginPath();
        points.forEach(([x, y], index) => {
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.fill();
        if (shape.borderColor) ctx.stroke();
    };
    ctx.strokeStyle = stroke;
    ctx.fillStyle = colour;
    ctx.lineWidth = Math.max(1, 1.4 * ratio);
    ctx.setLineDash([]);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    switch (kind) {
        case 'dot':
            ctx.beginPath();
            ctx.arc(cx, cy, Math.max(1.5, r * 0.45), 0, TAU);
            ctx.fill();
            break;
        case 'square': {
            const half = r * 0.8;
            ctx.beginPath();
            ctx.rect(cx - half, cy - half, half * 2, half * 2);
            ctx.fill();
            if (shape.borderColor) ctx.stroke();
            break;
        }
        case 'dash':
            ctx.lineWidth = Math.max(2, r * 0.35);
            line(cx - r, cy, cx + r, cy);
            break;
        case 'cross':
            line(cx - r, cy, cx + r, cy);
            line(cx, cy - r, cx, cy + r);
            break;
        case 'asterisk':
            line(cx - r, cy, cx + r, cy);
            line(cx, cy - r, cx, cy + r);
            line(cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7);
            line(cx - r * 0.7, cy + r * 0.7, cx + r * 0.7, cy - r * 0.7);
            break;
        case 'circle':
        case 'circle_cross':
        case 'circle_dot':
        case 'circle_x':
        case 'circle_y': {
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, TAU);
            if (kind === 'circle') {
                ctx.fill();
                if (shape.borderColor) ctx.stroke();
                break;
            }
            ctx.stroke();
            const inner = r * 0.55;
            if (kind === 'circle_cross') {
                line(cx - inner, cy, cx + inner, cy);
                line(cx, cy - inner, cx, cy + inner);
            } else if (kind === 'circle_x') {
                line(cx - inner, cy - inner, cx + inner, cy + inner);
                line(cx - inner, cy + inner, cx + inner, cy - inner);
            } else if (kind === 'circle_y') {
                line(cx - inner, cy - inner, cx, cy);
                line(cx + inner, cy - inner, cx, cy);
                line(cx, cy, cx, cy + inner);
            } else {
                ctx.beginPath();
                ctx.arc(cx, cy, Math.max(1, r * 0.32), 0, TAU);
                ctx.fill();
            }
            break;
        }
        case 'triangle':
        case 'triangle_dot': {
            poly([[cx, cy], [cx + r, cy + r * 1.7], [cx - r, cy + r * 1.7]]);
            if (kind === 'triangle_dot') {
                ctx.beginPath();
                ctx.arc(cx, cy + r * 2.6, Math.max(1.2, r * 0.3), 0, TAU);
                ctx.fill();
            }
            break;
        }
        case 'inverted_triangle':
            poly([[cx, cy], [cx + r, cy - r * 1.7], [cx - r, cy - r * 1.7]]);
            break;
        case 'arrow_up':
        case 'arrow_down': {
            const sign = kind === 'arrow_up' ? 1 : -1;
            poly([[cx, cy], [cx + r * 0.85, cy + sign * r * 1.5],
                [cx - r * 0.85, cy + sign * r * 1.5]]);
            ctx.lineWidth = Math.max(1.5, r * 0.4);
            line(cx, cy + sign * r * 1.2, cx, cy + sign * r * 2.2);
            break;
        }
        default:
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, TAU);
            ctx.fill();
            break;
    }
}

const TAU = Math.PI * 2;

interface CustomDataItem {
    time: unknown;
    value?: number;
    low?: number;
    high?: number;
    color?: string;
    shapes?: Shape[];
}

interface VisibleRange {
    from: number;
    to: number;
}

const DEFAULT_HALF_WIDTH = 0.4;

export class CustomSeriesRenderer implements ICustomSeriesPaneRenderer {
    private readonly _view: CustomSeriesPaneView;

    constructor(view: CustomSeriesPaneView) {
        this._view = view;
    }

    draw(target: CanvasRenderingTarget2D, priceConverter: PriceToCoordinateConverter): void {
        const bars = this._view._bars;
        const spacing = this._view._barSpacing;
        // Only the visible slice has coordinates: `indexesToCoordinates` writes
        // `x` for `[visibleRange.from, visibleRange.to)` and leaves the rest at
        // their initial `NaN` (or a stale value), so drawing all of them smears
        // the off-screen shapes onto the pane edges.
        const range = this._view._visibleRange;
        const from = range ? Math.max(0, range.from) : 0;
        const to = range ? Math.min(bars.length, range.to) : bars.length;

        target.useBitmapCoordinateSpace((scope: BitmapCoordinatesRenderingScope) => {
            if (from >= to) return;
            const ctx = scope.context;
            const h = scope.horizontalPixelRatio;
            const v = scope.verticalPixelRatio;

            const toY = (price: number): number | null => {
                const coordinate = priceConverter(price);
                return coordinate === null || coordinate === undefined ? null : (coordinate as number) * v;
            };

            ctx.save();
            for (let i = from; i < to; i++) {
                const bar = bars[i];
                const shapes = (bar.originalData as CustomDataItem | undefined)?.shapes;
                if (!shapes || !shapes.length) continue;
                const centre = (bar.x as number) * h;
                if (!Number.isFinite(centre)) continue;
                const xAt = (offset: number) => centre + offset * spacing * h;
                for (const shape of shapes) {
                    // ⚠ 单个图形画不出来（例如坐标算成 null → LWC 抛
                    //   `Value is null`）不能连累整条序列：逐图形兜住，
                    //   否则一坏就整段消失（回测盈亏副图实测 ✗）
                    try {
                        this._drawShape(ctx, shape, xAt, h, v, toY);
                    } catch (err) {
                        /* 跳过这一个图形，继续画后面的 ✓ */
                    }
                }
            }
            ctx.restore();
        });
    }

    private _drawShape(
        ctx: CanvasRenderingContext2D,
        shape: Shape,
        xAt: (offset: number) => number,
        h: number,
        v: number,
        toY: (price: number) => number | null,
    ): void {
        const left = shape.left ?? -DEFAULT_HALF_WIDTH;
        const right = shape.right ?? DEFAULT_HALF_WIDTH;
        const x1 = xAt(left);
        const x2 = xAt(right);
        const colour = shape.color ?? shape.fillColor ?? '#2962FF';

        switch (shape.type) {
            case 'rect':
            case 'band': {
                const upper = toY(shape.to ?? shape.from ?? 0);
                const lower = toY(shape.from ?? shape.to ?? 0);
                if (upper === null || lower === null) return;
                const top = Math.min(upper, lower);
                const height = Math.abs(lower - upper);
                const fill = shape.fillColor ?? shape.color;
                if (fill || shape.type === 'band') {
                    ctx.fillStyle = fill ?? 'rgba(41, 98, 255, 0.30)';
                    ctx.fillRect(x1, top, Math.max(x2 - x1, 1), Math.max(height, 1));
                }
                if (shape.borderColor) {
                    ctx.strokeStyle = shape.borderColor;
                    ctx.lineWidth = (shape.borderWidth ?? 1) * h;
                    ctx.setLineDash([]);
                    ctx.strokeRect(x1, top, Math.max(x2 - x1, 1), Math.max(height, 1));
                }
                break;
            }
            case 'line': {
                const y = toY(shape.price ?? 0);
                if (y === null) return;
                ctx.strokeStyle = colour;
                ctx.lineWidth = (shape.width ?? 1) * h;
                setDash(ctx, shape.style ?? 0, h);
                ctx.beginPath();
                ctx.moveTo(x1, y);
                ctx.lineTo(x2, y);
                ctx.stroke();
                break;
            }
            case 'marker': {
                const y = toY(shape.price ?? 0);
                if (y === null) return;
                const kind = shape.marker ?? 'circle';
                const size = (shape.size ?? 10) * h;
                const cx = xAt(0);
                const cy = y + (shape.offset ?? 0) * v;
                drawMarker(ctx, kind, cx, cy, size, colour, shape, h);
                // ★ 信号文字（`SignalStyle.set_label("B")` / 逐点文本 ✓）
                const text = String(shape.text ?? '');
                if (text) {
                    const down = kind.includes('down');
                    // ★ `set_label("B", 14)` 的 14 就是**像素字号**（跟设备像素比）
                    const px = (shape.textSize && shape.textSize > 0)
                        ? Number(shape.textSize) * v
                        : Math.max(12, size * 1.05);
                    const gap = size * 2.0 + px * 0.55;
                    ctx.save();
                    ctx.font = `600 ${Math.max(9, Math.round(px))}px `
                        + `-apple-system, "Segoe UI", Roboto, sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = down ? 'bottom' : 'top';
                    ctx.fillStyle = shape.textColor ?? colour;
                    ctx.fillText(text, cx, down ? cy - gap : cy + gap);
                    ctx.restore();
                }
                break;
            }
            case 'circle': {
                const y = toY(shape.price ?? 0);
                if (y === null) return;
                const radius = (shape.radius ?? 3) * h;
                ctx.beginPath();
                ctx.arc(xAt(shape.offset ?? 0), y, radius, 0, Math.PI * 2);
                if (shape.fillColor ?? shape.color) {
                    ctx.fillStyle = shape.fillColor ?? shape.color as string;
                    ctx.fill();
                }
                if (shape.borderColor) {
                    ctx.strokeStyle = shape.borderColor;
                    ctx.lineWidth = (shape.borderWidth ?? 1) * h;
                    ctx.stroke();
                }
                break;
            }
            case 'text': {
                const anchor = toY(shape.price ?? 0);
                if (anchor === null) return;
                const size = Math.round((shape.fontSize ?? 12) * v);
                const weight = shape.fontWeight && shape.fontWeight !== 'normal'
                    ? shape.fontWeight + ' ' : '';
                const slant = shape.fontStyle && shape.fontStyle !== 'normal'
                    ? shape.fontStyle + ' ' : '';
                ctx.font = `${slant}${weight}${size}px ${shape.fontFamily ?? 'sans-serif'}`;
                ctx.textAlign = shape.align ?? 'center';
                ctx.textBaseline = shape.baseline ?? 'middle';
                // 像素偏移：h / v 是"设备像素/CSS 像素"，乘上去才是真正 1:1
                const x = xAt(shape.offset ?? 0) + (shape.offsetX ?? 0) * h;
                const y = anchor + (shape.offsetY ?? 0) * v;
                const baseline = shape.baseline ?? 'middle';
                const lineHeight = (shape.lineHeight ?? 1.2) * size;
                const lines = String(shape.text ?? '').split('\n');
                const offsets = textLineOffsets(shape.text, lineHeight, baseline);
                // 底色 / 边框：整块文字的外框（含 padding），画在文字**下面**
                if (shape.backgroundColor || shape.borderColor) {
                    const pad = (shape.padding ?? 4) * v;
                    let widest = 0;
                    for (const line of lines) {
                        widest = Math.max(widest, ctx.measureText(line).width);
                    }
                    const left = (shape.align ?? 'center') === 'left' ? x
                        : (shape.align ?? 'center') === 'right' ? x - widest
                            : x - widest / 2;
                    const half = baseline === 'middle' ? size / 2 : 0;
                    const top = (baseline === 'bottom'
                        ? y + offsets[0] - size : y + offsets[0] - half) - pad;
                    const bottom = (baseline === 'top'
                        ? y + offsets[offsets.length - 1] + size
                        : y + offsets[offsets.length - 1] + half) + pad;
                    const alpha = (shape.backgroundAlpha ?? shape.borderAlpha ?? 1);
                    ctx.save();
                    ctx.globalAlpha = alpha;
                    ctx.beginPath();
                    ctx.roundRect(left - pad, top, widest + 2 * pad,
                                  bottom - top, Math.min(pad, size / 2));
                    if (shape.backgroundColor) {
                        ctx.fillStyle = shape.backgroundColor;
                        ctx.fill();
                    }
                    if (shape.borderColor) {
                        ctx.lineWidth = (shape.borderWidth ?? 1) * v;
                        ctx.strokeStyle = shape.borderColor;
                        ctx.stroke();
                    }
                    ctx.restore();
                }
                ctx.fillStyle = colour;
                // 多行文本（bokeh 的 LabelSet 也这么干）：逐行绘制并保持整块锚定
                offsets.forEach((dy, i) => {
                    ctx.fillText(lines[i] ?? '', x, y + dy);
                });
                break;
            }
            case 'polyline': {
                const points = shape.points;
                if (!points || points.length < 2) return;
                ctx.beginPath();
                let started = false;
                for (const [offset, price] of points) {
                    const y = toY(price);
                    if (y === null) return;
                    const x = xAt(offset);
                    if (!started) {
                        ctx.moveTo(x, y);
                        started = true;
                    } else {
                        ctx.lineTo(x, y);
                    }
                }
                if (shape.fillColor) {
                    ctx.fillStyle = shape.fillColor;
                    ctx.fill();
                }
                ctx.strokeStyle = colour;
                ctx.lineWidth = (shape.width ?? 1) * h;
                setDash(ctx, shape.style ?? 0, h);
                ctx.stroke();
                break;
            }
        }
    }
}

function setDash(ctx: CanvasRenderingContext2D, style: number, pixelRatio: number): void {
    const width = ctx.lineWidth || pixelRatio;
    const patterns: Record<number, number[]> = {
        0: [],
        1: [width, width],
        2: [2 * width, 2 * width],
        3: [6 * width, 6 * width],
        4: [width, 4 * width],
    };
    ctx.setLineDash(patterns[style] ?? []);
}

export class CustomSeriesPaneView implements ICustomSeriesPaneView<unknown, any, any> {
    public _bars: ReadonlyArray<{ x: number; originalData?: CustomDataItem }> = [];
    public _barSpacing = 1;
    public _visibleRange: VisibleRange | null = null;
    public _options: Record<string, unknown> = {};

    private readonly _renderer: CustomSeriesRenderer = new CustomSeriesRenderer(this);

    public renderer(): ICustomSeriesPaneRenderer {
        return this._renderer;
    }

    public update(data: PaneRendererCustomData<unknown, any>, seriesOptions: any): void {
        this._bars = data.bars as any;
        this._barSpacing = data.barSpacing;
        this._visibleRange = data.visibleRange;
        this._options = seriesOptions || {};
    }

    /**
     * The bars that currently have a valid `x`, i.e. those inside
     * `visibleRange`. Use this instead of `_bars` from a `rendererDraw`
     * callback: off-screen bars carry a stale or `NaN` coordinate.
     */
    public visibleBars(): ReadonlyArray<{ x: number; originalData?: CustomDataItem }> {
        const range = this._visibleRange;
        if (!range) {
            return this._bars;
        }
        return this._bars.slice(Math.max(0, range.from), Math.min(this._bars.length, range.to));
    }

    public priceValueBuilder(row: CustomDataItem): CustomSeriesPricePlotValues {
        const { low, high, value } = row;
        if (low !== undefined || high !== undefined) {
            const min = low ?? value ?? high as number;
            const max = high ?? value ?? low as number;
            return [min, max, value ?? max];
        }
        if (value !== undefined) {
            return [value, value, value];
        }
        return [];
    }

    public isWhitespace(
        data: CustomDataItem | CustomSeriesWhitespaceData<unknown>,
    ): data is CustomSeriesWhitespaceData<unknown> {
        const item = data as CustomDataItem;
        return item.value === undefined && item.low === undefined && item.high === undefined;
    }

    public defaultOptions(): any {
        return {
            ...customSeriesDefaultOptions,
            priceLineVisible: false,
            lastValueVisible: false,
        };
    }

    public destroy(): void {
        this._bars = [];
        this._visibleRange = null;
    }
}

/** Optional overrides for the declarative custom series (see `PrimitiveSpec` doc). */
export interface CustomSeriesPaneViewSpec {
    /** callback(target, priceConverter, view) — replaces the shape renderer */
    rendererDraw?: string;
    /** callback(x, y, priceConverter, view) -> CustomSeriesHitTestResult | null */
    rendererHitTest?: string;
    /** callback(row, view) -> number[] */
    priceValueBuilder?: string;
    /** callback(data, view) -> boolean */
    isWhitespace?: string;
    /** merged over `defaultOptions()` */
    defaultOptions?: Record<string, unknown>;
    /** callback(view) */
    destroy?: string;
    /** callback(item1, item2, view) -> item */
    conflationReducer?: string;
}

class CallbackCustomSeriesRenderer implements ICustomSeriesPaneRenderer {
    constructor(private readonly _view: SpecCustomSeriesPaneView) { }

    draw(target: CanvasRenderingTarget2D, priceConverter: PriceToCoordinateConverter): void {
        const fn = this._view._spec.rendererDraw ? lookupCallback(this._view._spec.rendererDraw) : undefined;
        if (fn) fn(target, priceConverter, this._view);
    }

    hitTest(x: Coordinate, y: Coordinate, priceConverter: PriceToCoordinateConverter): CustomSeriesHitTestResult | null {
        const fn = this._view._spec.rendererHitTest ? lookupCallback(this._view._spec.rendererHitTest) : undefined;
        return fn ? fn(x, y, priceConverter, this._view) : null;
    }
}

/** A custom series whose pane view is driven by a JSON spec + JS callbacks. */
export class SpecCustomSeriesPaneView extends CustomSeriesPaneView {
    public _spec: CustomSeriesPaneViewSpec;
    private readonly _callbackRenderer = new CallbackCustomSeriesRenderer(this);

    constructor(spec: CustomSeriesPaneViewSpec = {}) {
        super();
        this._spec = spec;
    }

    public renderer(): ICustomSeriesPaneRenderer {
        return this._spec.rendererDraw ? this._callbackRenderer : super.renderer();
    }

    public priceValueBuilder(row: CustomDataItem): CustomSeriesPricePlotValues {
        const fn = this._spec.priceValueBuilder ? lookupCallback(this._spec.priceValueBuilder) : undefined;
        return fn ? fn(row, this) : super.priceValueBuilder(row);
    }

    public isWhitespace(data: CustomDataItem | CustomSeriesWhitespaceData<unknown>): data is CustomSeriesWhitespaceData<unknown> {
        const fn = this._spec.isWhitespace ? lookupCallback(this._spec.isWhitespace) : undefined;
        return fn ? fn(data, this) : super.isWhitespace(data);
    }

    public defaultOptions(): any {
        return { ...super.defaultOptions(), ...(this._spec.defaultOptions || {}) };
    }

    public destroy(): void {
        super.destroy();
        const fn = this._spec.destroy ? lookupCallback(this._spec.destroy) : undefined;
        if (fn) fn(this);
    }

    public conflationReducer(item1: any, item2: any): any {
        const fn = this._spec.conflationReducer ? lookupCallback(this._spec.conflationReducer) : undefined;
        return fn ? fn(item1, item2, this) : item1;
    }
}

import {
    IChartApi,
    ISeriesApi,
    MouseEventHandler,
    MouseEventParams,
    SeriesType,
    Time,
} from 'lightweight-charts';
import { Drawing } from './drawing';
import { Point, timeToLogical, toSeconds, clampLogical } from './data-source';
import { DrawingOptions } from './options';
import { HorizontalLine } from '../horizontal-line/horizontal-line';


/**
 * What the drawing tool needs in order to receive pointer events.
 *
 * The chart itself keeps a *single* slot for click / crosshair subscribers, so the
 * tool registers with the handler (which fans out) instead of the chart. Typed
 * structurally to avoid an import cycle with `handler.ts`.
 */
export interface DrawingEventSource {
    chart: IChartApi;
    addClickListener(listener: MouseEventHandler<Time>): void;
    addCrosshairListener(listener: MouseEventHandler<Time>): void;
}


export class DrawingTool {
    private _series: ISeriesApi<SeriesType>;
    private _finishDrawingCallback: Function | null = null;
    private _changeCallback: Function | null = null;

    private _drawings: Drawing[] = [];
    private _activeDrawing: Drawing | null = null;
    private _isDrawing: boolean = false;
    private _drawingType: (new (...args: any[]) => Drawing) | null = null;
    private _requiredPoints: number = 2;
    private _pointsPlaced: number = 0;
    private _options: Partial<DrawingOptions> | undefined = undefined;

    constructor(source: DrawingEventSource, series: ISeriesApi<SeriesType>,
                finishDrawingCallback: Function | null = null,
                changeCallback: Function | null = null) {
        this._series = series;
        this._finishDrawingCallback = finishDrawingCallback;
        this._changeCallback = changeCallback;

        // go through the source: subscribing on the chart directly would evict the
        // legend and the host application from the chart's single slots
        source.addClickListener(this._clickHandler);
        source.addCrosshairListener(this._moveHandler);
    }

    private _clickHandler = (param: MouseEventParams) => this._onClick(param);
    private _moveHandler = (param: MouseEventParams) => this._onMouseMove(param);

    beginDrawing(DrawingType: new (...args: any[]) => Drawing, options?: Partial<DrawingOptions>) {
        this._drawingType = DrawingType;
        this._isDrawing = true;
        this._requiredPoints = (DrawingType as any).requiredPoints ?? 2;
        this._pointsPlaced = 0;
        this._options = options;
    }

    stopDrawing() {
        this._isDrawing = false;
        this._activeDrawing = null;
        this._pointsPlaced = 0;
    }

    get drawings() {
        return this._drawings;
    }

    addNewDrawing(drawing: Drawing) {
        this._series.attachPrimitive(drawing);
        this._drawings.push(drawing);
    }

    delete(d: Drawing | null) {
        if (d == null) return;
        const idx = this._drawings.indexOf(d);
        if (idx == -1) return;
        this._drawings.splice(idx, 1)
        d.detach();
        // 删除必须落到持久化。右键菜单的 "Delete Drawing" 以前只把图形从画布上
        // 移掉，宿主保存的那份没变，于是重新加载画线工具时它又回来了。
        // 放在这里（而不是各个调用点）是为了让每条删除路径都自动保存：
        // 右键菜单、Ctrl+Z、以后新增的入口都不会漏。
        this._changeCallback?.();
    }

    clearDrawings() {
        for (const d of this._drawings) d.detach();
        this._drawings = [];
    }

    repositionOnTime() {
        // 当前周期的全部 bar 时间（升序，秒）。build 一次给所有点共用。
        const times: number[] = [];
        for (const bar of this._series.data() as { time: Time }[]) {
            const seconds = toSeconds(bar.time);
            if (seconds !== null) times.push(seconds);
        }

        for (const drawing of this.drawings) {
            // 保持 point.time 不变：它才是跨周期的锚，logical 只是当前周期下的缓存。
            let overflow = 0;
            let unanchored = false;
            const prepared = drawing.points.map((point) => {
                if (!point) return point;
                const mapped = point.time ? timeToLogical(times, point.time) : null;
                if (mapped === null) unanchored = true;
                const logical = mapped ?? (Number.isFinite(point.logical) ? point.logical : 0);
                overflow = Math.max(overflow, logical - (times.length - 1));
                return {time: point.time, logical, price: point.price};
            });

            // 没有时间锚的点（旧数据里点在了 bar 空隙上，time 存成了 null）只能沿用保存时
            // 的 bar 序号，而那是在**另一个周期**里量的：1 分钟图的第 300 根，放到 5 分钟图上
            // 已经远在右侧之外，画线就“看不见”了。所以整根左移回到范围内 —— 逐点夹的
            // 话两个点会一起贴到最后一根 bar 上，方框就变成一条线了。
            const shift = unanchored && overflow > 0 ? overflow : 0;
            const newPoints = prepared.map((point) => point && {
                time: point.time,
                logical: clampLogical(point.logical - shift, times.length),
                price: point.price,
            });
            drawing.updatePoints(...newPoints);
        }
    }

    private _onClick(param: MouseEventParams) {
        if (!this._isDrawing) return;

        const point = Drawing._eventToPoint(param, this._series);
        if (!point) return;

        if (this._activeDrawing == null) {
            if (this._drawingType == null) return;
            this._requiredPoints = (this._drawingType as any).requiredPoints ?? 2;
            this._pointsPlaced = 1;
            const seed: Point[] = [];
            for (let i = 0; i < this._requiredPoints; i++) seed.push(point);
            const drawing = new (this._drawingType as any)(...seed, this._options) as Drawing;
            this._activeDrawing = drawing;
            this._series.attachPrimitive(drawing);
            // horizontal lines only need one click
            if (this._requiredPoints <= 1 || this._drawingType === HorizontalLine) {
                this._finishDrawing();
            }
            return;
        }

        this._placePoint(point, this._pointsPlaced);
        this._pointsPlaced += 1;
        if (this._pointsPlaced >= this._requiredPoints) this._finishDrawing();
    }

    /** Move the anchor at `index`, leaving the others untouched. */
    private _placePoint(point: Point, index: number) {
        if (!this._activeDrawing) return;
        const args: (Point | null)[] = [];
        for (let i = 0; i < index; i++) args.push(null);
        args.push(point);
        this._activeDrawing.updatePoints(...args);
    }

    private _finishDrawing() {
        if (!this._activeDrawing) return;
        this._drawings.push(this._activeDrawing);
        this.stopDrawing();
        if (this._finishDrawingCallback) this._finishDrawingCallback();
    }

    private _onMouseMove(param: MouseEventParams) {
        if (!param) return;

        for (const t of this._drawings) t._handleHoverInteraction(param);

        if (!this._isDrawing || !this._activeDrawing) return;

        const point = Drawing._eventToPoint(param, this._series);
        if (!point) return;
        this._placePoint(point, Math.min(this._pointsPlaced, this._requiredPoints - 1));
    }
}
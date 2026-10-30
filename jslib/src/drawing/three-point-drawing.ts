import { MouseEventParams, Coordinate } from 'lightweight-charts';
import { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import { DiffPoint, Point } from './data-source';
import { Drawing, InteractionState } from './drawing';
import { DrawingOptions, defaultOptions } from './options';
import { DrawingPaneView, ViewPoint } from './pane-view';
import { DrawingPaneRenderer } from './pane-renderer';

/**
 * Base class for drawings that need three anchor points (pitchfork, triangle,
 * fibonacci projection, ...). Interaction is generic: drag the body or any of
 * the three handles.
 */
export abstract class ThreePointDrawing extends Drawing {
    public static requiredPoints = 3;
    declare _paneViews: ThreePointDrawingPaneView[];

    protected _hovered: boolean = false;

    constructor(p1: Point, p2: Point, p3: Point, options?: Partial<DrawingOptions>) {
        super(options);
        this.points.push(p1, p2, p3);
        this._options = { ...defaultOptions, ...options };
    }

    get p1(): Point { return this.points[0] as Point; }
    get p2(): Point { return this.points[1] as Point; }
    get p3(): Point { return this.points[2] as Point; }
    get hovered(): boolean { return this._hovered; }

    _moveToState(state: InteractionState) {
        switch (state) {
            case InteractionState.NONE:
                document.body.style.cursor = 'default';
                this._hovered = false;
                this.requestUpdate();
                this._unsubscribe('mousedown', this._handleMouseDownInteraction);
                break;
            case InteractionState.HOVERING:
                document.body.style.cursor = 'pointer';
                this._hovered = true;
                this.requestUpdate();
                this._subscribe('mousedown', this._handleMouseDownInteraction);
                this._unsubscribe('mouseup', this._handleMouseUpInteraction);
                this.chart.applyOptions({ handleScroll: true });
                break;
            case InteractionState.DRAGGINGP1:
            case InteractionState.DRAGGINGP2:
            case InteractionState.DRAGGINGP3:
            case InteractionState.DRAGGING:
                document.body.style.cursor = 'grabbing';
                this._subscribe('mouseup', this._handleMouseUpInteraction);
                this.chart.applyOptions({ handleScroll: false });
                break;
        }
        this._state = state;
    }

    _onDrag(diff: DiffPoint) {
        if (this._state === InteractionState.DRAGGING) {
            for (const point of this.points) this._addDiffToPoint(point, diff.logical, diff.price);
            return;
        }
        const index = this._state === InteractionState.DRAGGINGP1 ? 0
            : this._state === InteractionState.DRAGGINGP2 ? 1 : 2;
        this._addDiffToPoint(this.points[index], diff.logical, diff.price);
    }

    protected _onMouseDown() {
        this._startDragPoint = null;
        const hover = this._latestHoverPoint;
        if (!hover) return;
        const tolerance = 10;
        const views = this._paneViews[0];
        const handles: ViewPoint[] = [views._p1, views._p2, views._p3];
        for (let i = 0; i < handles.length; i++) {
            const { x, y } = handles[i];
            if (x === null || y === null) continue;
            if (Math.abs(hover.x - x) < tolerance && Math.abs(hover.y - y) < tolerance) {
                const states = [InteractionState.DRAGGINGP1, InteractionState.DRAGGINGP2,
                    InteractionState.DRAGGINGP3];
                this._moveToState(states[i]);
                return;
            }
        }
        this._moveToState(InteractionState.DRAGGING);
    }

    protected _mouseIsOverDrawing(param: MouseEventParams, tolerance = 4) {
        if (!param.point) return false;
        const views = this._paneViews[0];
        const handles: ViewPoint[] = [views._p1, views._p2, views._p3];
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        for (const { x, y } of handles) {
            if (x === null || y === null) continue;
            minX = Math.min(minX, x); maxX = Math.max(maxX, x);
            minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        }
        if (minX === Infinity) return false;
        const half = tolerance / 2;
        return param.point.x > minX - half && param.point.x < maxX + half
            && param.point.y > minY - half && param.point.y < maxY + half;
    }
}

export abstract class ThreePointDrawingPaneView extends DrawingPaneView {
    _p1: ViewPoint = { x: null, y: null };
    _p2: ViewPoint = { x: null, y: null };
    _p3: ViewPoint = { x: null, y: null };

    declare _source: ThreePointDrawing;

    constructor(source: ThreePointDrawing) {
        super(source);
        this._source = source;
    }

    update() {
        const series = this._source.series;
        const timeScale = this._source.chart.timeScale();
        const toView = (point: Point | null): ViewPoint => {
            if (!point) return { x: null, y: null };
            return {
                x: timeScale.logicalToCoordinate(point.logical) as unknown as Coordinate,
                y: series.priceToCoordinate(point.price) as unknown as Coordinate,
            };
        };
        this._p1 = toView(this._source.p1);
        this._p2 = toView(this._source.p2);
        this._p3 = toView(this._source.p3);
    }

    abstract renderer(): DrawingPaneRenderer;
}

export abstract class ThreePointDrawingPaneRenderer extends DrawingPaneRenderer {
    _p1: ViewPoint;
    _p2: ViewPoint;
    _p3: ViewPoint;
    protected _hovered: boolean;

    constructor(p1: ViewPoint, p2: ViewPoint, p3: ViewPoint,
                options: DrawingOptions, hovered: boolean) {
        super(options);
        this._p1 = p1;
        this._p2 = p2;
        this._p3 = p3;
        this._hovered = hovered;
    }

    abstract draw(target: CanvasRenderingTarget2D): void;

    _scaled(scope: BitmapCoordinatesRenderingScope) {
        if (this._p1.x === null || this._p1.y === null ||
            this._p2.x === null || this._p2.y === null ||
            this._p3.x === null || this._p3.y === null) return null;
        const h = scope.horizontalPixelRatio;
        const v = scope.verticalPixelRatio;
        return {
            x1: this._p1.x * h, y1: this._p1.y * v,
            x2: this._p2.x * h, y2: this._p2.y * v,
            x3: this._p3.x * h, y3: this._p3.y * v,
        };
    }

    _drawEndCircle(scope: BitmapCoordinatesRenderingScope, x: number, y: number) {
        const radius = 9;
        scope.context.fillStyle = '#000';
        scope.context.beginPath();
        scope.context.arc(x, y, radius, 0, 2 * Math.PI);
        scope.context.stroke();
        scope.context.fill();
    }
}

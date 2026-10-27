import { MouseEventParams } from 'lightweight-charts';
import { DiffPoint, Point } from './data-source';
import { InteractionState } from './drawing';
import { TwoPointDrawing } from './two-point-drawing';

/**
 * A two-point drawing with the standard interactions (hover / drag body /
 * drag either endpoint). TrendLine and Box each re-implement this; new
 * drawing types can just extend this class.
 */
export abstract class SimpleTwoPointDrawing extends TwoPointDrawing {
    constructor(p1: Point, p2: Point, options?: Partial<import('./options').DrawingOptions>) {
        super(p1, p2, options);
    }

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
            case InteractionState.DRAGGING:
                document.body.style.cursor = 'grabbing';
                this._subscribe('mouseup', this._handleMouseUpInteraction);
                this.chart.applyOptions({ handleScroll: false });
                break;
        }
        this._state = state;
    }

    _onDrag(diff: DiffPoint) {
        if (this._state === InteractionState.DRAGGING || this._state === InteractionState.DRAGGINGP1) {
            this._addDiffToPoint(this.p1, diff.logical, diff.price);
        }
        if (this._state === InteractionState.DRAGGING || this._state === InteractionState.DRAGGINGP2) {
            this._addDiffToPoint(this.p2, diff.logical, diff.price);
        }
    }

    protected _onMouseDown() {
        this._startDragPoint = null;
        const hoverPoint = this._latestHoverPoint;
        if (!hoverPoint) return;
        const p1 = this._paneViews[0]._p1;
        const p2 = this._paneViews[0]._p2;
        if (p1.x === null || p2.x === null || p1.y === null || p2.y === null) {
            return this._moveToState(InteractionState.DRAGGING);
        }
        const tolerance = 10;
        if (Math.abs(hoverPoint.x - p1.x) < tolerance && Math.abs(hoverPoint.y - p1.y) < tolerance) {
            this._moveToState(InteractionState.DRAGGINGP1);
        } else if (Math.abs(hoverPoint.x - p2.x) < tolerance && Math.abs(hoverPoint.y - p2.y) < tolerance) {
            this._moveToState(InteractionState.DRAGGINGP2);
        } else {
            this._moveToState(InteractionState.DRAGGING);
        }
    }

    protected _mouseIsOverDrawing(param: MouseEventParams, tolerance = 4) {
        if (!param.point) return false;
        const { x: x1, y: y1 } = this._paneViews[0]._p1;
        const { x: x2, y: y2 } = this._paneViews[0]._p2;
        if (x1 === null || x2 === null || y1 === null || y2 === null) return false;
        const half = tolerance / 2;
        const left = Math.min(x1, x2) - half;
        const right = Math.max(x1, x2) + half;
        const top = Math.min(y1, y2) - half;
        const bottom = Math.max(y1, y2) + half;
        return param.point.x > left && param.point.x < right
            && param.point.y > top && param.point.y < bottom;
    }
}

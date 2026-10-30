import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { ThreePointDrawing } from '../drawing/three-point-drawing';
import { TrianglePaneView } from './pane-view';

export interface TriangleOptions extends DrawingOptions {
    fillEnabled: boolean;
    fillColor: string;
}

/** A filled / outlined triangle through three anchor points. */
export class Triangle extends ThreePointDrawing {
    _type = 'Triangle';
    declare _options: TriangleOptions;

    constructor(p1: Point, p2: Point, p3: Point, options?: Partial<TriangleOptions>) {
        super(p1, p2, p3, options);
        this._options = {
            ...this._options,
            fillEnabled: true,
            fillColor: 'rgba(41, 98, 255, 0.15)',
            ...options,
        } as TriangleOptions;
        this._paneViews = [new TrianglePaneView(this)];
    }
}

import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { SimpleTwoPointDrawing } from '../drawing/simple-two-point';
import { FibonacciPaneView } from './pane-view';

export interface FibonacciOptions extends DrawingOptions {
    /** Retracement ratios (0 = second point, 1 = first point). */
    levels: number[];
    showLabels: boolean;
    fillBackground: boolean;
    backgroundColor: string;
    textColor: string;
    fontSize: number;
}

export const defaultFibonacciLevels: number[] = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

export class FibonacciRetracement extends SimpleTwoPointDrawing {
    _type = 'FibonacciRetracement';
    declare _options: FibonacciOptions;

    constructor(p1: Point, p2: Point, options?: Partial<FibonacciOptions>) {
        super(p1, p2, options);
        this._options = {
            ...this._options,
            levels: defaultFibonacciLevels,
            showLabels: true,
            fillBackground: true,
            backgroundColor: 'rgba(41, 98, 255, 0.08)',
            textColor: '#9598A1',
            fontSize: 11,
            ...options,
        } as FibonacciOptions;
        this._paneViews = [new FibonacciPaneView(this)];
    }
}

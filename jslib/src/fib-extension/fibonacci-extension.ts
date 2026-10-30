import { Point } from '../drawing/data-source';
import { DrawingOptions } from '../drawing/options';
import { ThreePointDrawing } from '../drawing/three-point-drawing';
import { FibonacciExtensionPaneView } from './pane-view';

export interface FibonacciExtensionOptions extends DrawingOptions {
    /** extension ratios applied to the A->B move, projected from C */
    levels: number[];
    showLabels: boolean;
    textColor: string;
    fontSize: number;
    /** how far past the last anchor the lines run, as a fraction of the span */
    extension: number;
}

export const defaultExtensionLevels: number[] = [0, 0.382, 0.618, 1, 1.272, 1.618, 2, 2.618];

/**
 * Fibonacci extension: `p1`/`p2` define the impulse leg, `p3` the retracement
 * point the extension levels are projected from.
 */
export class FibonacciExtension extends ThreePointDrawing {
    _type = 'FibonacciExtension';
    declare _options: FibonacciExtensionOptions;

    constructor(p1: Point, p2: Point, p3: Point, options?: Partial<FibonacciExtensionOptions>) {
        super(p1, p2, p3, options);
        this._options = {
            ...this._options,
            levels: defaultExtensionLevels,
            showLabels: true,
            textColor: '#9598A1',
            fontSize: 11,
            extension: 0.5,
            ...options,
        } as FibonacciExtensionOptions;
        this._paneViews = [new FibonacciExtensionPaneView(this)];
    }
}

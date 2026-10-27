import { FibonacciExtension, defaultExtensionLevels } from './fibonacci-extension';
import { FibonacciExtensionPaneRenderer } from './pane-renderer';
import { ThreePointDrawingPaneView } from '../drawing/three-point-drawing';

export interface ExtensionLevel {
    ratio: number;
    price: number;
    y: number | null;
}

export class FibonacciExtensionPaneView extends ThreePointDrawingPaneView {
    declare _source: FibonacciExtension;
    _levels: ExtensionLevel[] = [];

    constructor(source: FibonacciExtension) {
        super(source);
    }

    update() {
        super.update();
        const series = this._source.series;
        const options = this._source._options;
        const delta = this._source.p2.price - this._source.p1.price;
        const base = this._source.p3.price;
        const levels = options.levels?.length ? options.levels : defaultExtensionLevels;
        this._levels = [...levels].sort((a, b) => a - b).map(ratio => {
            const price = base + delta * ratio;
            const coordinate = series.priceToCoordinate(price);
            return { ratio, price, y: coordinate === null ? null : (coordinate as number) };
        });
    }

    renderer() {
        return new FibonacciExtensionPaneRenderer(
            this._p1,
            this._p2,
            this._p3,
            this._source._options,
            this._source.hovered,
            this._levels,
        );
    }
}

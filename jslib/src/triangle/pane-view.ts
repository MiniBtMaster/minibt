import { Triangle } from './triangle';
import { TrianglePaneRenderer } from './pane-renderer';
import { ThreePointDrawingPaneView } from '../drawing/three-point-drawing';

export class TrianglePaneView extends ThreePointDrawingPaneView {
    declare _source: Triangle;

    constructor(source: Triangle) {
        super(source);
    }

    renderer() {
        return new TrianglePaneRenderer(
            this._p1,
            this._p2,
            this._p3,
            this._source._options,
            this._source.hovered,
        );
    }
}

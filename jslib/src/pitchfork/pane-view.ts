import { AndrewsPitchfork } from './pitchfork';
import { PitchforkPaneRenderer } from './pane-renderer';
import { ThreePointDrawingPaneView } from '../drawing/three-point-drawing';

export class PitchforkPaneView extends ThreePointDrawingPaneView {
    declare _source: AndrewsPitchfork;

    constructor(source: AndrewsPitchfork) {
        super(source);
    }

    renderer() {
        return new PitchforkPaneRenderer(
            this._p1,
            this._p2,
            this._p3,
            this._source._options,
            this._source.hovered,
        );
    }
}

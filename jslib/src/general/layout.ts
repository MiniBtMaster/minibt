import { GlobalParams } from "./global-params";
import { Handler } from "./handler";

declare const window: GlobalParams

/** One divider between two neighbouring charts of a layout. */
interface Divider {
    elem: HTMLDivElement;
    before: Handler;
    after: Handler;
}

interface LayoutState {
    handlers: Handler[];
    kind: string;
    size: number;
    dividers: Divider[];
    detach: () => void;
}

/**
 * Draggable dividers between the charts of a layout.
 *
 * The charts of a `pylightcharts.layout.Layout` are floated siblings sized as
 * fractions of the window, so a separator can simply be floated between them:
 * it takes `size` pixels out of the page and the drag hands those pixels from
 * one chart to the other (see `Layout` in python).
 */
export class LayoutSplitter {
    private static _states = new Map<string, LayoutState>();

    /** (Re)create the dividers of one layout. `size <= 0` removes them. */
    public static set(
        layoutId: string,
        handlers: Handler[],
        kind: string,
        size: number,
        color: string,
        hoverColor: string,
        callbackName?: string,
    ) {
        LayoutSplitter.clear(layoutId);

        LayoutSplitter._fit(handlers, kind, size);

        if (size <= 0 || handlers.length < 2) return;

        const dividers: Divider[] = [];
        for (let i = 0; i + 1 < handlers.length; i++) {
            const before = handlers[i];
            const after = handlers[i + 1];
            const parent = after.wrapper.parentNode;
            if (!parent || before.wrapper.parentNode !== parent) continue;
            const divider = LayoutSplitter._makeDivider(kind, size, color,
                hoverColor, LayoutSplitter._pageHeight());
            parent.insertBefore(divider, after.wrapper);
            LayoutSplitter._bindDrag(divider, before, after, kind,
                handlers, callbackName);
            dividers.push({ elem: divider, before, after });
        }

        // window resizes change the space left for the charts: the fixed
        // divider size has to be subtracted again
        const onResize = () => {
            LayoutSplitter._fit(handlers, kind, size);
            const height = LayoutSplitter._pageHeight();
            for (const divider of dividers) {
                if (kind !== 'vertical') {
                    divider.elem.style.height = `${height}px`;
                }
            }
        };
        window.addEventListener('resize', onResize);
        LayoutSplitter._states.set(layoutId, {
            handlers, kind, size, dividers,
            detach: () => window.removeEventListener('resize', onResize),
        });
    }

    /** Remove the dividers of one layout and give the space back. */
    public static clear(layoutId: string) {
        const state = LayoutSplitter._states.get(layoutId);
        if (!state) return;
        state.detach();
        for (const divider of state.dividers) divider.elem.remove();
        LayoutSplitter._states.delete(layoutId);
        // no re-fit here: the caller applies the new geometry right away, and
        // re-fitting with the *previous* kind would undo a layout switch
    }

    /** Height a chart (or a vertical bar) may use: the window minus its
     *  page-level top bars. */
    private static _pageHeight() {
        return window.innerHeight - Handler.pageHeight();
    }

    /** Size of the charts along the layout axis ('horizontal' -> width). */
    private static _total(kind: string) {
        if (kind === 'vertical') return LayoutSplitter._pageHeight();
        return window.containerDiv.clientWidth;
    }

    /** Give every chart the same share, minus the dividers. */
    private static _fit(handlers: Handler[], kind: string, size: number) {
        if (!handlers.length) return;
        const total = LayoutSplitter._total(kind);
        const usable = total - size * (handlers.length - 1);
        const each = usable / handlers.length;
        for (const handler of handlers) {
            LayoutSplitter._applySize(handler, kind, each, total);
        }
    }

    private static _applySize(handler: Handler, kind: string, px: number,
                              total: number) {
        if (!total) return;
        if (kind === 'vertical') {
            handler.scale.height = px / total;
        } else {
            handler.scale.width = px / total;
        }
        handler.reSize();
    }

    private static _size(handler: Handler, kind: string) {
        const rect = handler.wrapper.getBoundingClientRect();
        return kind === 'vertical' ? rect.height : rect.width;
    }

    private static _makeDivider(kind: string, size: number, color: string,
                                hoverColor: string, pageHeight: number) {
        const divider = document.createElement('div');
        divider.classList.add('layout-divider');
        divider.classList.add(`layout-divider-${kind}`);
        // px, not %: the container's height is auto, so a percentage height
        // would collapse the drag area to 0
        divider.style.cssText = kind === 'vertical'
            ? `float: left; clear: both; width: 100%; height: ${size}px;`
            : `float: left; width: ${size}px; height: ${pageHeight}px;`;
        divider.style.position = 'relative';
        divider.style.zIndex = '100';
        divider.style.cursor = kind === 'vertical'
            ? 'row-resize' : 'col-resize';
        divider.style.backgroundColor = color;
        divider.addEventListener('mouseenter',
            () => divider.style.backgroundColor = hoverColor);
        divider.addEventListener('mouseleave',
            () => divider.style.backgroundColor = color);
        return divider;
    }

    private static _bindDrag(
        divider: HTMLDivElement,
        before: Handler,
        after: Handler,
        kind: string,
        handlers: Handler[],
        callbackName?: string,
    ) {
        const MIN = 40;                       // px, both sides stay usable

        const report = () => {
            if (!callbackName) return;
            const shares = handlers.map((handler) => {
                const value = kind === 'vertical'
                    ? handler.scale.height : handler.scale.width;
                return value.toFixed(6);
            });
            window.callbackFunction(`${callbackName}_~_${shares.join(';;;')}`);
        };

        divider.addEventListener('mousedown', (event: MouseEvent) => {
            event.preventDefault();
            const total = LayoutSplitter._total(kind);
            const start = kind === 'vertical' ? event.clientY : event.clientX;
            const first = LayoutSplitter._size(before, kind);
            const second = LayoutSplitter._size(after, kind);
            const body = document.body;
            const previousSelect = body.style.userSelect;
            body.style.userSelect = 'none';

            const onMove = (move: MouseEvent) => {
                const axis = kind === 'vertical' ? move.clientY : move.clientX;
                const delta = axis - start;
                const room = first + second;
                const limit = room - MIN;
                const left = Math.max(MIN, Math.min(limit, first + delta));
                LayoutSplitter._applySize(before, kind, left, total);
                LayoutSplitter._applySize(after, kind, room - left, total);
            };
            const onUp = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                body.style.userSelect = previousSelect;
                report();
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }
}

/** Called from python (`Layout._apply_dividers`). */
export function setLayoutDividers(
    layoutId: string,
    handlers: Handler[],
    kind: string,
    size: number,
    color: string,
    hoverColor: string,
    callbackName?: string,
) {
    LayoutSplitter.set(layoutId, handlers, kind, size, color, hoverColor,
        callbackName);
}

/**
 * Draggable dividers for a **1D tile** layout (a column of full-width tiles or
 * a row of full-height ones).
 *
 * The absolute tile geometry has no gap, so it cannot be dragged. This helper
 * bakes a `gap` into the tile fractions (the wrappers are still positioned by
 * `Handler._applyTile`) and puts a divider in each gap; dragging rewrites the
 * two neighbouring fractions and re-lays the tiles out.
 */
/** One chart placed in the flow: which handler, and its cell fractions. */
interface TileCell {
    handler: Handler;
    x: number;
    w: number;
}

/** A band of charts that shares the full width (a `_flow_tiles` row). */
interface TileRow {
    y: number;
    h: number;
    cells: TileCell[];
}

interface TileState {
    rows: TileRow[];
    /** row heights (sum = 1) */
    rowSizes: number[];
    /** column widths per row (each row sums to 1) */
    colSizes: number[][];
    /** divider between row `index` and `index + 1` */
    hDividers: { elem: HTMLDivElement; index: number }[];
    /** divider inside `row` between column `col` and `col + 1` */
    vDividers: { elem: HTMLDivElement; row: number; col: number }[];
    gap: number;
    detach: () => void;
}

/**
 * Draggable dividers for a tile layout.
 *
 * The absolute tiles have no gap, so they cannot be dragged. This helper groups
 * the tiles into rows (the same flow `_flow_tiles` builds), bakes a `gap` into
 * the fractions and floats a divider in every gap: one **horizontal** bar
 * between two rows, one **vertical** bar between two columns of a row.
 * Dragging rewrites the two neighbouring fractions and re-lays everything out.
 */
class TilesLayout {
    private static _states = new Map<string, TileState>();

    static clear(layoutId: string) {
        const state = TilesLayout._states.get(layoutId);
        if (!state) return;
        state.detach();
        for (const divider of state.hDividers) divider.elem.remove();
        for (const divider of state.vDividers) divider.elem.remove();
        TilesLayout._states.delete(layoutId);
    }

    static apply(
        layoutId: string,
        handlers: Handler[],
        tiles: number[][],
        gap: number,
        color: string,
        hoverColor: string,
    ) {
        TilesLayout.clear(layoutId);
        const rows = TilesLayout._rows(handlers, tiles);
        if (!rows.length || handlers.length < 2 || gap <= 0) {
            TilesLayout._plain(handlers, tiles);
            return;
        }
        const state: TileState = {
            rows,
            rowSizes: TilesLayout._normalize(rows.map((row) => row.h)),
            colSizes: rows.map((row) => TilesLayout._normalize(
                row.cells.map((cell) => cell.w))),
            hDividers: [],
            vDividers: [],
            gap,
            detach: () => {},
        };
        // Register the dividers **before** `_layout`: it positions them too,
        // and running it while the lists were still empty left every divider
        // without a `top`/`width` (invisible).
        for (let r = 0; r + 1 < rows.length; r++) {
            const divider = TilesLayout._divider(true, gap, color, hoverColor);
            window.containerDiv.appendChild(divider);
            TilesLayout._bindRowDrag(divider, state, r);
            state.hDividers.push({ elem: divider, index: r });
        }
        rows.forEach((row, r) => {
            for (let c = 0; c + 1 < row.cells.length; c++) {
                const divider = TilesLayout._divider(false, gap, color,
                    hoverColor);
                window.containerDiv.appendChild(divider);
                TilesLayout._bindColDrag(divider, state, r, c);
                state.vDividers.push({ elem: divider, row: r, col: c });
            }
        });
        TilesLayout._layout(state);
        const onResize = () => TilesLayout._layout(state);
        window.addEventListener('resize', onResize);
        state.detach = () => window.removeEventListener('resize', onResize);
        TilesLayout._states.set(layoutId, state);
    }

    /** No dividers: just hand the plain tiles to ``Handler._applyTile``. */
    private static _plain(handlers: Handler[], tiles: number[][]) {
        handlers.forEach((handler, index) => {
            const tile = tiles[index] || [0, 0, 1, 1];
            handler.tile = tile;
            handler.scale.width = tile[2];
            handler.scale.height = tile[3];
            handler.reSize();
        });
    }

    /** Group the index-aligned handlers/tiles into rows (same y). */
    private static _rows(handlers: Handler[], tiles: number[][]): TileRow[] {
        const byY = new Map<string, TileRow>();
        handlers.forEach((handler, index) => {
            const [x, y, w, h] = tiles[index] || [0, 0, 1, 1];
            const key = y.toFixed(4);
            let row = byY.get(key);
            if (!row) {
                row = { y, h, cells: [] };
                byY.set(key, row);
            }
            row.h = Math.max(row.h, h);
            row.cells.push({ handler, x, w });
        });
        const rows = [...byY.values()].sort((a, b) => a.y - b.y);
        rows.forEach((row) => row.cells.sort((a, b) => a.x - b.x));
        return rows;
    }

    private static _normalize(values: number[]) {
        const total = values.reduce((a, b) => a + b, 0) || 1;
        return values.map((value) => value / total);
    }

    /** Viewport metrics shared by the layout and the drag handlers. */
    private static _metrics() {
        const area = window.innerHeight - Handler.pageHeight();
        return { area, width: window.innerWidth, top: Handler.pageHeight() };
    }

    /** Bake the gaps into the tile fractions and hand them to `_applyTile`. */
    private static _layout(state: TileState) {
        const { area, width, top } = TilesLayout._metrics();
        const rowGap = area ? state.gap / area : 0;
        const usableH = 1 - rowGap * (state.rows.length - 1);
        const rowTops: number[] = [];
        const rowPixel = state.rowSizes.map((size) => size * usableH * area);
        let y = 0;
        state.rowSizes.forEach((size, index) => {
            rowTops[index] = y;
            y += size * usableH + rowGap;
        });
        state.rows.forEach((row, r) => {
            const colGap = width ? state.gap / width : 0;
            const usableW = 1 - colGap * (row.cells.length - 1);
            let x = 0;
            row.cells.forEach((cell, c) => {
                const w = state.colSizes[r][c] * usableW;
                cell.handler.tile = [x, rowTops[r], w,
                    state.rowSizes[r] * usableH];
                cell.handler.scale.width = w;
                cell.handler.scale.height = state.rowSizes[r] * usableH;
                cell.handler.reSize();
                x += w + colGap;
            });
        });
        state.hDividers.forEach((divider) => {
            const index = divider.index;
            const offset = rowTops[index] + state.rowSizes[index] * usableH;
            divider.elem.style.left = '0px';
            divider.elem.style.width = `${width}px`;
            divider.elem.style.top = `${top + area * offset}px`;
            divider.elem.style.height = `${state.gap}px`;
        });
        state.vDividers.forEach((divider) => {
            const row = state.rows[divider.row];
            const colGap = width ? state.gap / width : 0;
            const usableW = 1 - colGap * (row.cells.length - 1);
            let x = 0;
            for (let c = 0; c <= divider.col; c++) {
                x += state.colSizes[divider.row][c] * usableW;
            }
            x += colGap * divider.col;
            divider.elem.style.left = `${width * x}px`;
            divider.elem.style.top =
                `${top + area * rowTops[divider.row]}px`;
            divider.elem.style.width = `${state.gap}px`;
            divider.elem.style.height = `${rowPixel[divider.row]}px`;
        });
    }

    private static _divider(
        horizontal: boolean, gap: number, color: string, hoverColor: string,
    ) {
        const divider = document.createElement('div');
        divider.classList.add('layout-divider');
        divider.classList.add(horizontal ? 'layout-divider-horizontal'
            : 'layout-divider-vertical');
        divider.style.position = 'absolute';
        divider.style.zIndex = '100';
        divider.style.backgroundColor = color;
        divider.style.cursor = horizontal ? 'row-resize' : 'col-resize';
        if (horizontal) {
            divider.style.height = `${gap}px`;
        } else {
            divider.style.width = `${gap}px`;
        }
        divider.addEventListener('mouseenter',
            () => divider.style.backgroundColor = hoverColor);
        divider.addEventListener('mouseleave',
            () => divider.style.backgroundColor = color);
        return divider;
    }

    /** Drag the boundary between two rows (their heights hand over). */
    private static _bindRowDrag(
        divider: HTMLDivElement, state: TileState, index: number,
    ) {
        const MIN = 40;                       // px, both sides stay usable
        divider.addEventListener('mousedown', (event: MouseEvent) => {
            event.preventDefault();
            const { area } = TilesLayout._metrics();
            const rowGap = area ? state.gap / area : 0;
            const usable = area * (1 - rowGap * (state.rows.length - 1));
            const start = event.clientY;
            const first = state.rowSizes[index] * usable;
            const second = state.rowSizes[index + 1] * usable;
            const room = first + second;
            const body = document.body;
            const previousSelect = body.style.userSelect;
            body.style.userSelect = 'none';
            const onMove = (move: MouseEvent) => {
                const delta = move.clientY - start;
                const left = Math.max(MIN, Math.min(room - MIN, first + delta));
                state.rowSizes[index] = usable ? left / usable : 0;
                state.rowSizes[index + 1] = usable
                    ? (room - left) / usable : 0;
                TilesLayout._layout(state);
            };
            const onUp = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                body.style.userSelect = previousSelect;
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }

    /** Drag the boundary between two columns of one row (widths hand over). */
    private static _bindColDrag(
        divider: HTMLDivElement, state: TileState, row: number, col: number,
    ) {
        const MIN = 40;                       // px, both sides stay usable
        divider.addEventListener('mousedown', (event: MouseEvent) => {
            event.preventDefault();
            const { width } = TilesLayout._metrics();
            const count = state.rows[row].cells.length;
            const colGap = width ? state.gap / width : 0;
            const usable = width * (1 - colGap * (count - 1));
            const start = event.clientX;
            const first = state.colSizes[row][col] * usable;
            const second = state.colSizes[row][col + 1] * usable;
            const room = first + second;
            const body = document.body;
            const previousSelect = body.style.userSelect;
            body.style.userSelect = 'none';
            const onMove = (move: MouseEvent) => {
                const delta = move.clientX - start;
                const left = Math.max(MIN, Math.min(room - MIN, first + delta));
                state.colSizes[row][col] = usable ? left / usable : 0;
                state.colSizes[row][col + 1] = usable
                    ? (room - left) / usable : 0;
                TilesLayout._layout(state);
            };
            const onUp = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                body.style.userSelect = previousSelect;
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }
}

/**
 * Called from python (`Layout.arrange_tiles`): position every chart as a tile.
 *
 * `tiles` is ``[[x, y, w, h], ...]`` (0..1). When ``gap > 0`` and the tiles form
 * a single column / row, draggable dividers are added between them. The geometry
 * lives on the handler (`Handler.tile`) and is applied by `reSize`, so it
 * survives a window resize and cannot be left over on the next layout:
 * `clearLayoutTiles` puts the chart back on the float layout.
 */
export function setLayoutTiles(
    layoutId: string,
    handlers: Handler[],
    tiles: number[][],
    gap: number = 0,
    color: string = '#2a2e39',
    hoverColor: string = '#2962FF',
) {
    LayoutSplitter.clear(layoutId);
    TilesLayout.apply(layoutId, handlers, tiles, gap, color, hoverColor);
}

/** Called from python when a row/column layout replaces a tile layout. */
export function clearLayoutTiles(
    layoutId: string,
    handlers: Handler[],
) {
    TilesLayout.clear(layoutId);
    handlers.forEach((handler) => {
        handler.tile = null;
        handler.reSize();
    });
}

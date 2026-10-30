/**
 * Heatmap — a treemap of tiles sized by one metric and coloured by another
 * (Stock / Crypto / ETF / Forex heatmaps).
 *
 * Layout is the **squarified treemap** (Bruls, Huizing & van Wijk): items are
 * sorted by weight, greedily grouped into rows that keep the worst aspect ratio
 * low, and each row is laid along the shorter side of the remaining rectangle.
 * The result is much closer to square tiles than a naive binary split.
 *
 * Items can be **grouped** (by sector / exchange): the groups are squarified
 * first, each reserves a label strip, and the tiles are squarified inside.
 *
 * Colours interpolate between the theme's negative and positive colours around a
 * neutral, saturating at `±maxShock` percent; a floating tooltip shows the full
 * symbol / name / weight / change, and a small gradient legend shows the scale.
 */

import { emitCallback, ensureStyle } from './emit';

export type HeatColorScheme = 'cn' | 'tv';

export interface HeatItem {
    symbol: string;
    name?: string;
    /** size weight (volume, market cap, ...); defaults to 1 */
    value?: number;
    /** colour metric (percent change); defaults to 0 */
    chg_pct?: number;
}

export interface HeatGroup {
    name: string;
    items: HeatItem[];
}

export interface HeatmapTheme {
    background?: string;
    border?: string;
    text?: string;
    muted?: string;
    positive?: string;
    negative?: string;
    neutral?: string;
    legendBackground?: string;
}

export interface HeatmapOptions {
    items?: HeatItem[];
    groups?: HeatGroup[];
    colorScheme?: HeatColorScheme;
    /** |chg_pct| at which the colour is fully saturated (default 5) */
    maxShock?: number;
    /** gap in pixels between tiles (default 1) */
    padding?: number;
    showLabels?: boolean;
    showGroupLabels?: boolean;
    showLegend?: boolean;
    /** reserve pixels at the top of each group for its label (default 16) */
    groupLabelHeight?: number;
    tooltip?: boolean;
    labelMinWidth?: number;
    labelMinHeight?: number;
    theme?: HeatmapTheme;
    onItemClick?: (symbol: string) => void;
}

interface ResolvedTheme {
    background: string;
    border: string;
    text: string;
    muted: string;
    positive: string;
    negative: string;
    neutral: string;
    legendBackground: string;
}

interface Node {
    symbol: string;
    name?: string;
    value: number;
    chg: number;
}

interface Rect {
    node: Node;
    x: number;
    y: number;
    w: number;
    h: number;
}

interface Child {
    node: Node;
    area: number;
}

const STYLE_ID = 'pylightcharts-heatmap-style';
const CSS = `
.pylc-heatmap{position:relative;width:100%;height:100%;overflow:hidden;
  background:var(--hm-bg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Roboto,Arial,sans-serif}
.pylc-heat-tile{position:absolute;box-sizing:border-box;overflow:hidden;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.55);border:1px solid var(--hm-border);
  transition:filter .1s ease}
.pylc-heat-tile:hover{filter:brightness(1.18)}
.pylc-heat-sym{font-weight:700;line-height:1.1;white-space:nowrap}
.pylc-heat-chg{font-size:.85em;opacity:.95}
.pylc-heat-group{position:absolute;box-sizing:border-box;border:1px solid var(--hm-group-border);
  pointer-events:none}
.pylc-heat-glabel{position:absolute;left:0;top:0;padding:1px 5px;font-size:10px;font-weight:600;
  color:var(--hm-muted);background:var(--hm-bg);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:100%}
.pylc-heat-tip{position:fixed;z-index:9999;pointer-events:none;display:none;
  background:rgba(20,22,28,.96);border:1px solid var(--hm-group-border);border-radius:5px;
  padding:6px 9px;color:#d1d4dc;font:12px/1.5 -apple-system,"Microsoft YaHei",Arial,sans-serif;
  box-shadow:0 6px 18px rgba(0,0,0,.5);white-space:nowrap}
.pylc-heat-tip b{color:#fff}
.pylc-heat-tip .up{color:var(--hm-up)}
.pylc-heat-tip .down{color:var(--hm-down)}
.pylc-heat-legend{position:absolute;left:8px;bottom:6px;z-index:5;display:none;
  align-items:center;gap:6px;pointer-events:none;font-size:10px;color:var(--hm-muted);
  background:var(--hm-legend-bg);padding:2px 6px;border-radius:4px}
.pylc-heat-legend-bar{display:inline-block;width:92px;height:8px;border-radius:2px}
.pylc-stack>.pylc-heatmap{height:auto;flex:1 1 auto;min-height:0}
`;

function defaultContainer(): HTMLElement {
    const host = window as unknown as { containerDiv?: HTMLElement };
    return host.containerDiv ?? document.body;
}

function parseHex(color: string): [number, number, number] | null {
    const match = /^#([0-9a-f]{6})$/i.exec(color.trim());
    if (!match) {
        return null;
    }
    const value = parseInt(match[1], 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
    const ratio = Math.max(0, Math.min(1, t));
    const r = Math.round(a[0] + (b[0] - a[0]) * ratio);
    const g = Math.round(a[1] + (b[1] - a[1]) * ratio);
    const bl = Math.round(a[2] + (b[2] - a[2]) * ratio);
    return `rgb(${r}, ${g}, ${bl})`;
}

export class Heatmap {
    public callbackName: string | null = null;
    public readonly element: HTMLDivElement;

    private _items: HeatItem[] = [];
    private _groups: HeatGroup[] = [];
    private _scheme: HeatColorScheme;
    private _maxShock: number;
    private _padding: number;
    private _showLabels: boolean;
    private _showGroupLabels: boolean;
    private _showLegend: boolean;
    private _groupLabelHeight: number;
    private _tooltip: boolean;
    private _labelMinWidth: number;
    private _labelMinHeight: number;
    private _theme: ResolvedTheme;
    private _onItemClick?: (symbol: string) => void;
    private _tip: HTMLDivElement;
    private _legend: HTMLDivElement;

    constructor(options: HeatmapOptions = {}, parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this._scheme = options.colorScheme ?? 'cn';
        this._maxShock = options.maxShock ?? 5;
        this._padding = options.padding ?? 1;
        this._showLabels = options.showLabels ?? true;
        this._showGroupLabels = options.showGroupLabels ?? true;
        this._showLegend = options.showLegend ?? true;
        this._groupLabelHeight = options.groupLabelHeight ?? 16;
        this._tooltip = options.tooltip ?? true;
        this._labelMinWidth = options.labelMinWidth ?? 26;
        this._labelMinHeight = options.labelMinHeight ?? 20;
        this._theme = this._resolveTheme(options.theme ?? {});
        this._onItemClick = options.onItemClick;

        this.element = document.createElement('div');
        this.element.className = 'pylc-heatmap';
        this._applyThemeVars();
        (parent ?? defaultContainer()).appendChild(this.element);

        this._tip = document.createElement('div');
        this._tip.className = 'pylc-heat-tip';
        this._legend = document.createElement('div');
        this._legend.className = 'pylc-heat-legend';

        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(() => this._render()).observe(this.element);
        }
        if (options.groups) {
            this.setGroups(options.groups);
        } else if (options.items) {
            this.setItems(options.items);
        } else {
            this._render();
        }
    }

    setItems(items: HeatItem[]): void {
        this._items = (items ?? []).filter((item) => item && item.symbol);
        this._groups = [];
        this._render();
    }

    setGroups(groups: HeatGroup[]): void {
        this._groups = (groups ?? [])
            .filter((group) => group && group.name)
            .map((group) => ({
                name: group.name,
                items: (group.items ?? []).filter((item) => item && item.symbol),
            }));
        this._items = [];
        this._render();
    }

    setOptions(options: Partial<HeatmapOptions>): void {
        if (options.colorScheme && options.colorScheme !== this._scheme) {
            this._scheme = options.colorScheme;
        }
        if (options.maxShock !== undefined) this._maxShock = options.maxShock;
        if (options.padding !== undefined) this._padding = options.padding;
        if (options.showLabels !== undefined) this._showLabels = options.showLabels;
        if (options.showGroupLabels !== undefined) this._showGroupLabels = options.showGroupLabels;
        if (options.showLegend !== undefined) this._showLegend = options.showLegend;
        if (options.groupLabelHeight !== undefined) this._groupLabelHeight = options.groupLabelHeight;
        if (options.tooltip !== undefined) this._tooltip = options.tooltip;
        if (options.labelMinWidth !== undefined) this._labelMinWidth = options.labelMinWidth;
        if (options.labelMinHeight !== undefined) this._labelMinHeight = options.labelMinHeight;
        if (options.theme) {
            this._theme = this._resolveTheme(options.theme);
            this._applyThemeVars();
        }
        this._render();
    }

    reSize(): void {
        this._render();
    }

    destroy(): void {
        this.element.remove();
    }

    // --------------------------------------------------------------- internal
    private _resolveTheme(theme: HeatmapTheme): ResolvedTheme {
        const cn = this._scheme === 'cn';
        return {
            background: theme.background ?? '#131722',
            border: theme.border ?? 'rgba(0,0,0,0.35)',
            text: theme.text ?? '#ffffff',
            muted: theme.muted ?? '#787b86',
            positive: theme.positive ?? (cn ? '#ef5350' : '#26a69a'),
            negative: theme.negative ?? (cn ? '#26a69a' : '#ef5350'),
            neutral: theme.neutral ?? '#3a3f4b',
            legendBackground: theme.legendBackground ?? 'rgba(19,23,34,.72)',
        };
    }

    private _applyThemeVars(): void {
        const style = this.element.style;
        style.setProperty('--hm-bg', this._theme.background);
        style.setProperty('--hm-border', this._theme.border);
        style.setProperty('--hm-group-border', 'rgba(128,128,128,0.35)');
        style.setProperty('--hm-legend-bg', this._theme.legendBackground);
        style.setProperty('--hm-muted', this._theme.muted);
        style.setProperty('--hm-up', this._theme.positive);
        style.setProperty('--hm-down', this._theme.negative);
    }

    private _toNode(item: HeatItem): Node {
        return {
            symbol: item.symbol,
            name: item.name,
            value: Math.max(0.0001, Number(item.value ?? 1) || 1),
            chg: Number(item.chg_pct ?? 0) || 0,
        };
    }

    private _heatColor(chg: number): string {
        const neutral = parseHex(this._theme.neutral) ?? [58, 63, 75];
        const target = parseHex(chg >= 0 ? this._theme.positive : this._theme.negative);
        if (target === null) {
            return chg >= 0 ? this._theme.positive : this._theme.negative;
        }
        const raw = this._maxShock > 0 ? Math.min(1, Math.abs(chg) / this._maxShock) : 1;
        // gamma + floor: small moves still read as a solid colour instead of
        // washing out towards the neutral (which looked "transparent" on light)
        const t = Math.min(1, 0.15 + 0.85 * Math.pow(raw, 0.55));
        return mix(neutral, target, t);
    }

    private _render(): void {
        this.element.textContent = '';
        this._renderLegend();
        this.element.appendChild(this._legend);
        this.element.appendChild(this._tip);
        const width = this.element.clientWidth;
        const height = this.element.clientHeight;
        if (width <= 0 || height <= 0) {
            return;
        }
        if (this._groups.length > 0) {
            this._renderGroups(width, height);
        } else if (this._items.length > 0) {
            const rects: Rect[] = [];
            this._layout(this._items.map((item) => this._toNode(item)),
                         0, 0, width, height, rects);
            this._drawTiles(rects);
        }
    }

    private _renderLegend(): void {
        this._legend.textContent = '';
        if (!this._showLegend) {
            this._legend.style.display = 'none';
            return;
        }
        this._legend.style.display = 'flex';
        const lo = document.createElement('span');
        lo.textContent = `-${this._maxShock}%`;
        const bar = document.createElement('span');
        bar.className = 'pylc-heat-legend-bar';
        bar.style.background =
            `linear-gradient(to right, ${this._theme.negative}, ${this._theme.neutral}, ${this._theme.positive})`;
        const hi = document.createElement('span');
        hi.textContent = `+${this._maxShock}%`;
        this._legend.appendChild(lo);
        this._legend.appendChild(bar);
        this._legend.appendChild(hi);
    }

    private _renderGroups(width: number, height: number): void {
        const groups = this._groups
            .map((group) => ({
                name: group.name,
                nodes: group.items.map((item) => this._toNode(item)),
            }))
            .filter((group) => group.nodes.length > 0)
            .map((group) => ({
                name: group.name,
                nodes: group.nodes,
                total: group.nodes.reduce((sum, node) => sum + node.value, 0),
            }))
            .sort((a, b) => b.total - a.total);
        if (groups.length === 0) {
            return;
        }

        const groupRects: Rect[] = [];
        this._layout(
            groups.map((group) => ({ symbol: group.name, value: group.total, chg: 0 })),
            0, 0, width, height, groupRects,
        );
        const byName = new Map<string, Rect>();
        for (const rect of groupRects) {
            byName.set(rect.node.symbol, rect);
        }

        const labelHeight = this._showGroupLabels ? this._groupLabelHeight : 0;
        for (const group of groups) {
            const rect = byName.get(group.name);
            if (!rect) {
                continue;
            }
            const box = document.createElement('div');
            box.className = 'pylc-heat-group';
            box.style.left = `${rect.x}px`;
            box.style.top = `${rect.y}px`;
            box.style.width = `${rect.w}px`;
            box.style.height = `${rect.h}px`;
            this.element.appendChild(box);

            if (labelHeight > 0) {
                const label = document.createElement('div');
                label.className = 'pylc-heat-glabel';
                label.textContent = group.name;
                box.appendChild(label);
            }

            const inner: Rect[] = [];
            this._layout(group.nodes,
                         rect.x + 1, rect.y + labelHeight + 1,
                         Math.max(1, rect.w - 2), Math.max(1, rect.h - labelHeight - 2),
                         inner);
            this._drawTiles(inner);
        }
    }

    private _drawTiles(rects: Rect[]): void {
        const pad = this._padding;
        for (const rect of rects) {
            const node = rect.node;
            const tile = document.createElement('div');
            tile.className = 'pylc-heat-tile';
            tile.style.left = `${rect.x}px`;
            tile.style.top = `${rect.y}px`;
            tile.style.width = `${Math.max(0, rect.w - pad)}px`;
            tile.style.height = `${Math.max(0, rect.h - pad)}px`;
            tile.style.background = this._heatColor(node.chg);

            if (this._showLabels) {
                const innerW = rect.w - pad;
                const innerH = rect.h - pad;
                if (innerW >= this._labelMinWidth && innerH >= this._labelMinHeight) {
                    const showChange = innerH >= this._labelMinHeight * 1.9;
                    const fontSize = Math.max(9, Math.min(16,
                        Math.round(Math.min(innerW / 6, innerH / 3.2))));
                    const symbol = document.createElement('div');
                    symbol.className = 'pylc-heat-sym';
                    symbol.style.fontSize = `${fontSize}px`;
                    symbol.textContent = node.symbol;
                    tile.appendChild(symbol);
                    if (showChange) {
                        const change = document.createElement('div');
                        change.className = 'pylc-heat-chg';
                        change.style.fontSize = `${Math.max(8, fontSize - 3)}px`;
                        change.textContent = `${node.chg >= 0 ? '+' : ''}${node.chg.toFixed(2)}%`;
                        tile.appendChild(change);
                    }
                }
            }
            if (this._tooltip) {
                tile.addEventListener('mouseenter', (event) => this._showTip(node, event));
                tile.addEventListener('mousemove', (event) => this._moveTip(event));
                tile.addEventListener('mouseleave', () => this._hideTip());
            }
            tile.addEventListener('click', () => this._select(node.symbol));
            this.element.appendChild(tile);
        }
    }

    private _showTip(node: Node, event: MouseEvent): void {
        const cls = node.chg >= 0 ? 'up' : 'down';
        const sign = node.chg >= 0 ? '+' : '';
        const name = node.name && node.name !== node.symbol
            ? `<div>${node.name}</div>` : '';
        this._tip.innerHTML =
            `<div><b>${node.symbol}</b></div>${name}` +
            `<div>权重 ${node.value.toLocaleString('en-US')}</div>` +
            `<div class="${cls}">${sign}${node.chg.toFixed(2)}%</div>`;
        this._tip.style.display = 'block';
        this._moveTip(event);
    }

    private _moveTip(event: MouseEvent): void {
        if (this._tip.style.display !== 'block') {
            return;
        }
        const offset = 14;
        const rect = this._tip.getBoundingClientRect();
        let left = event.clientX + offset;
        let top = event.clientY + offset;
        if (left + rect.width > window.innerWidth) {
            left = event.clientX - rect.width - offset;
        }
        if (top + rect.height > window.innerHeight) {
            top = event.clientY - rect.height - offset;
        }
        this._tip.style.left = `${Math.max(0, left)}px`;
        this._tip.style.top = `${Math.max(0, top)}px`;
    }

    private _hideTip(): void {
        this._tip.style.display = 'none';
    }

    /** Scale the weights so their areas fill the rectangle, then squarify. */
    private _layout(
        nodes: Array<{ symbol: string; name?: string; value: number; chg: number }>,
        x: number, y: number, w: number, h: number, out: Rect[],
    ): void {
        if (nodes.length === 0 || w <= 0 || h <= 0) {
            return;
        }
        const sorted = nodes
            .map((node) => ({ node, value: Math.max(0.0001, node.value) }))
            .sort((a, b) => b.value - a.value);
        const total = sorted.reduce((sum, entry) => sum + entry.value, 0);
        if (total <= 0) {
            return;
        }
        const scale = (w * h) / total;
        const children: Child[] = sorted.map((entry) => ({
            node: entry.node, area: entry.value * scale,
        }));
        this._squarify(children, x, y, w, h, out);
    }

    /** Squarified treemap (Bruls et al.): greedy rows along the shorter side. */
    private _squarify(
        children: Child[], x: number, y: number, w: number, h: number, out: Rect[],
    ): void {
        let remaining = children;
        let rx = x, ry = y, rw = w, rh = h;
        while (remaining.length > 0 && rw > 0.0001 && rh > 0.0001) {
            const short = Math.min(rw, rh);
            let row: Child[] = [];
            let rowArea = 0;
            let best = Infinity;
            while (remaining.length > 0) {
                const candidate = remaining[0];
                const nextArea = rowArea + candidate.area;
                const candidateRow = row.concat([candidate]);
                const nextWorst = this._worst(candidateRow, nextArea, short);
                if (row.length === 0 || nextWorst <= best) {
                    row = candidateRow;
                    rowArea = nextArea;
                    best = nextWorst;
                    remaining = remaining.slice(1);
                } else {
                    break;
                }
            }
            if (row.length === 0) {
                break;
            }
            if (rw >= rh) {
                const rowWidth = rowArea / rh;
                let cursor = ry;
                for (const child of row) {
                    const childHeight = rowWidth > 0 ? child.area / rowWidth : 0;
                    out.push({ node: child.node, x: rx, y: cursor, w: rowWidth, h: childHeight });
                    cursor += childHeight;
                }
                rx += rowWidth;
                rw -= rowWidth;
            } else {
                const rowHeight = rowArea / rw;
                let cursor = rx;
                for (const child of row) {
                    const childWidth = rowHeight > 0 ? child.area / rowHeight : 0;
                    out.push({ node: child.node, x: cursor, y: ry, w: childWidth, h: rowHeight });
                    cursor += childWidth;
                }
                ry += rowHeight;
                rh -= rowHeight;
            }
        }
    }

    private _worst(row: Child[], area: number, short: number): number {
        if (area <= 0) {
            return Infinity;
        }
        let maxArea = 0;
        let minArea = Infinity;
        for (const child of row) {
            if (child.area > maxArea) maxArea = child.area;
            if (child.area < minArea) minArea = child.area;
        }
        const s2 = short * short;
        const a2 = area * area;
        return Math.max((s2 * maxArea) / a2, a2 / (s2 * minArea));
    }

    private _select(symbol: string): void {
        if (this.callbackName) {
            emitCallback(this.callbackName, symbol);
            return;
        }
        if (this._onItemClick) {
            this._onItemClick(symbol);
        }
    }
}

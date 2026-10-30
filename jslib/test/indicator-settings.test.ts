/**
 * 指标设置卡（`indicator-settings.ts`）与图层样式（`IndicatorLayer.applyStyle`）
 * 的回归用例：
 *
 *  * 选颜色（色块 / 最后的 ＋ 调色板）后，`onApply` 必须带**新颜色**；
 *  * `applyStyle` 必须真的改到序列颜色，并且后端下一次全量推送后仍然保留；
 *  * 「显示该指标」与图例眼睛是**同一份状态**（不能把指标标签也删掉）。
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { IndicatorLayer } from '../src/desk/indicator';
import { closeIndicatorSettings, openIndicatorSettings } from '../src/desk/indicator-settings';
import { DomStub, StubElement, installDom } from './dom';

let dom: DomStub;

beforeEach(() => {
    dom = installDom();
    (globalThis as any).window.LightweightCharts = {
        LineSeries: { kind: 'line' },
        HistogramSeries: { kind: 'hist' },
        CandlestickSeries: { kind: 'candles' },
    };
});

class FakeSeries {
    options: Record<string, unknown>;
    data: unknown[] = [];
    constructor(options: Record<string, unknown>) {
        this.options = { ...options };
    }
    applyOptions(patch: Record<string, unknown>): void {
        Object.assign(this.options, patch);
    }
    setData(rows: unknown[]): void { this.data = rows; }
    update(row: unknown): void {
        const point = row as { time?: unknown };
        const index = this.data.findIndex((item) =>
            (item as { time?: unknown }).time === point.time);
        if (index >= 0) this.data[index] = row;
        else this.data.push(row);
    }
    priceScale(): Record<string, unknown> {
        return { applyOptions: () => undefined, width: () => 0 };
    }
    createPriceLine(): Record<string, unknown> { return {}; }
    removePriceLine(): void { /* noop */ }
}

/** 假的 pylightcharts `Legend`：记录 `makeSeriesRow` 建的图例行 + 眼睛同步 ✓ */
function makeLegend(): { legend: Record<string, unknown>; eyes: boolean[] } {
    const eyes: boolean[] = [];
    const lines: Array<{ row?: StubElement }> = [];
    const legend = {
        _lines: lines,
        makeSeriesRow: () => {
            lines.push({ row: new StubElement('div') });
        },
        setSeriesVisible: (_series: unknown, visible: boolean) => {
            eyes.push(visible);
            return visible;
        },
    };
    return { legend, eyes };
}

function makeLayer(series: FakeSeries[], legend?: Record<string, unknown>): IndicatorLayer {
    const chart = {
        addSeries: (_def: unknown, options: Record<string, unknown>) => {
            const item = new FakeSeries(options);
            series.push(item);
            return item;
        },
        removeSeries: () => undefined,
        panes: () => [{ setHeight: () => undefined }],
        priceScale: () => ({ width: () => 0, applyOptions: () => undefined }),
        timeScale: () => ({}),
    } as never;
    return new IndicatorLayer(
        new StubElement('div') as never,
        () => chart,
        () => ({ background: '#000', text: '#fff', up: '#26a69a', down: '#ef5350' }),
        () => (legend || null) as never,
        () => null,
    );
}

const items = (color: string) => [{
    key: 'MA20', label: 'MA20', kind: 'line', overlay: true, color,
    lineWidth: 2, lineStyle: 0,
    data: [[1_700_000_000, 10], [1_700_000_060, 11]],
}];

const state = (color: string) => ({
    params: { length: 20 },
    lineStyle: 0,
    lineWidth: 2,
    color,
    priceLine: true,
    priceLabel: true,
    visible: true,
    crosshairMarker: true,
    overlay: true,
});

describe('IndicatorLayer.applyStyle', () => {
    it('changes the series colour right away', () => {
        const series: FakeSeries[] = [];
        const layer = makeLayer(series);
        layer.apply({ type: 'indicator', symbol: 'X', items: items('#f6c343') } as never);
        expect(series.length).toBe(1);
        expect(series[0].options.color).toBe('#f6c343');

        layer.applyStyle('MA20', state('#123456') as never);
        expect(series[0].options.color).toBe('#123456');
        expect(layer.styleOf('MA20').color).toBe('#123456');
    });

    it('keeps the colour after the next full push from the backend', () => {
        const series: FakeSeries[] = [];
        const layer = makeLayer(series);
        layer.apply({ type: 'indicator', symbol: 'X', items: items('#f6c343') } as never);
        layer.applyStyle('MA20', state('#123456') as never);
        // 后端每秒推一次（颜色还是原来的）→ 覆盖状态必须仍然生效 ✓
        layer.apply({ type: 'indicator', symbol: 'X', items: items('#f6c343') } as never);
        expect(series[0].options.color).toBe('#123456');
    });

    it('does not bake per-point colours onto the line data', () => {
        // ★ LWC 会拿**逐点** color 覆盖序列 color → 以前设置卡里改颜色
        //   一点反应都没有（用户实测 ✗）。有效点必须不带 color ✓
        const series: FakeSeries[] = [];
        const layer = makeLayer(series);
        layer.apply({ type: 'indicator', symbol: 'X',
                      items: items('#f6c343') } as never);
        const points = series[0].data as Array<Record<string, unknown>>;
        expect(points.length).toBe(2);
        expect(points.every((point) => point.color === undefined)).toBe(true);
        layer.applyStyle('MA20', state('#123456') as never);
        expect(series[0].options.color).toBe('#123456');
        // 重设数据后依然没有逐点颜色（否则颜色又被盖掉 ✓）
        const again = series[0].data as Array<Record<string, unknown>>;
        expect(again.every((point) => point.color === undefined)).toBe(true);
    });

    it('still paints gap points transparent so the line breaks', () => {
        const series: FakeSeries[] = [];
        const layer = makeLayer(series);
        layer.apply({ type: 'indicator', symbol: 'X', items: [{
            key: 'MA20', label: 'MA20', kind: 'line', overlay: true,
            color: '#f6c343',
            data: [[1_700_000_000, 10], [1_700_000_060, null],
                   [1_700_000_120, 12], [1_700_000_180, 13],
                   [1_700_000_240, 14], [1_700_000_300, 15],
                   [1_700_000_360, 16], [1_700_000_420, 17],
                   [1_700_000_480, 18], [1_700_000_540, 19]],
        }] } as never);
        const points = series[0].data as Array<Record<string, unknown>>;
        expect(points[1].color).toBe('rgba(0,0,0,0)');
        expect(points[0].color).toBeUndefined();
        expect(points[2].color).toBeUndefined();
    });

    it('setVisible only hides the line, the legend row stays', () => {
        const series: FakeSeries[] = [];
        const { legend, eyes } = makeLegend();
        const layer = makeLayer(series, legend);
        layer.apply({ type: 'indicator', symbol: 'X', items: items('#f6c343') } as never);
        expect(layer.keys).toEqual(['MA20']);
        layer.setVisible('MA20', false);
        expect(series[0].options.visible).toBe(false);
        expect(layer.styleOf('MA20').visible).toBe(false);
        // 图例的指标标签 / 眼睛都还在 ✓
        expect(layer.keys).toEqual(['MA20']);
        expect(layer.legendKeys).toEqual(['MA20']);
        expect(eyes).toEqual([false]);       // 眼睛图标同步成闭眼 ✓
        layer.setVisible('MA20', true);
        expect(series[0].options.visible).toBe(true);
        expect(eyes).toEqual([false, true]);
    });

    it('keeps a hidden line hidden after the next backend push', () => {
        const series: FakeSeries[] = [];
        const { legend } = makeLegend();
        const layer = makeLayer(series, legend);
        layer.apply({ type: 'indicator', symbol: 'X', items: items('#f6c343') } as never);
        layer.setVisible('MA20', false);
        // 后端每秒全量推一次（item 里没有 visible 字段）→ 仍然是隐藏 ✓
        layer.apply({ type: 'indicator', symbol: 'X', items: items('#f6c343') } as never);
        expect(series[0].options.visible).toBe(false);
        expect(layer.legendKeys).toEqual(['MA20']);
    });
});

describe('indicator settings card', () => {
    function open(hooks: Record<string, unknown>) {
        const base = state('');
        if (hooks.overlayLocked) base.overlayLocked = true;
        openIndicatorSettings(null, 'MA20', base as never, hooks as never, 'dark');
        const doc: any = (globalThis as any).document;
        const body: StubElement = doc.body;
        const box = body.children[body.children.length - 1] as StubElement;
        return box;
    }

    function findAll(box: StubElement, cls: string): StubElement[] {
        const out: StubElement[] = [];
        const walk = (node: StubElement) => {
            if ((node.className || '').split(/\s+/).includes(cls)) out.push(node);
            (node.children || []).forEach(walk);
        };
        walk(box);
        return out;
    }

    function clickAll(box: StubElement, cls: string, index = 0): void {
        const nodes = findAll(box, cls);
        expect(nodes.length).toBeGreaterThan(index);
        (nodes[index] as any).dispatch('click', { target: nodes[index], preventDefault: () => undefined });
    }

    it('reports the colour picked from the preset chips', () => {
        const applied: any[] = [];
        const box = open({ onApply: (value: unknown) => applied.push(value), onDelete: () => undefined });
        const chips = findAll(box, 'desk-is-color');
        expect(chips.length).toBeGreaterThan(3);
        // 第 4 个色块（索引 3 = #26a69a）
        clickAll(box, 'desk-is-color', 3);
        clickAll(box, 'desk-is-btn', 1);            // 「应用」
        expect(applied.length).toBe(1);
        expect(applied[0].color.toLowerCase()).toBe('#26a69a');
        closeIndicatorSettings();
    });

    it('previews the colour immediately (no need to press 应用)', () => {
        const previews: string[] = [];
        const box = open({
            onApply: () => undefined,
            onDelete: () => undefined,
            onColorPreview: (color: string) => previews.push(color),
        });
        clickAll(box, 'desk-is-color', 2);
        clickAll(box, 'desk-is-color', 5);
        expect(previews.map((color) => color.toLowerCase()))
            .toEqual(['#e91e63', '#ff9800']);
        closeIndicatorSettings();
    });

    it('locks 位置 when the indicator has lines on both panes', () => {
        const box = open({ onApply: () => undefined, onDelete: () => undefined,
                           overlayLocked: true });
        const selects = findAll(box, 'desk-is-select');
        const area = selects[selects.length - 1] as any;
        expect(area.disabled).toBe(true);
        const options = (area.children || []).map((node: any) => node.value);
        expect(options).toEqual(['1', '0', 'mixed']);
        const selected = (area.children || []).find((node: any) => node.selected);
        expect(selected && selected.value).toBe('mixed');
        closeIndicatorSettings();
    });

    it('keeps 位置 editable when all lines share the same pane', () => {
        const box = open({ onApply: () => undefined, onDelete: () => undefined });
        const selects = findAll(box, 'desk-is-select');
        const area = selects[selects.length - 1] as any;
        expect(area.disabled).toBe(false);
        const selected = (area.children || []).find((node: any) => node.selected);
        expect(selected && selected.value).toBe('1');       // 初始化 = 指标设置 ✓
        closeIndicatorSettings();
    });

    it('reports the colour picked from the + palette (input type=color)', () => {
        const applied: any[] = [];
        const box = open({ onApply: (value: unknown) => applied.push(value), onDelete: () => undefined });
        const pickers = findAll(box, 'desk-is-color-input');
        expect(pickers.length).toBe(1);
        const picker = pickers[0];
        // stub 不解析 innerHTML → 手动补上 ＋ 节点（真实 DOM 里由 innerHTML 建 ✓）
        const custom = picker.parentNode as StubElement;
        const plus = new StubElement('span');
        plus.className = 'desk-is-color-plus';
        custom.appendChild(plus);
        picker.value = '#abcdef';
        (picker as any).dispatch('input', { target: picker });
        clickAll(box, 'desk-is-btn', 1);
        expect(applied.length).toBe(1);
        expect(applied[0].color.toLowerCase()).toBe('#abcdef');
        closeIndicatorSettings();
    });
});

describe('IndicatorLayer incremental full push', () => {
    it('updates only the last point when history is unchanged', () => {
        const layer = makeLayer([]);
        const setCalls: unknown[][] = [];
        const updateCalls: unknown[] = [];
        const series = {
            data: () => [{ time: 1, value: 10 }, { time: 2, value: 11 }],
            setData: (rows: unknown[]) => setCalls.push(rows),
            update: (row: unknown) => updateCalls.push(row),
        };
        (layer as unknown as {
            _setSeriesData: (s: unknown, rows: unknown[]) => void;
        })._setSeriesData(series, [
            { time: 1, value: 10 }, { time: 2, value: 12 },
        ]);
        expect(setCalls).toHaveLength(0);
        expect(updateCalls).toEqual([{ time: 2, value: 12 }]);
    });
});


describe('IndicatorLayer multi-point last update', () => {
    it('applies two or more tail points after a new bar', () => {
        const series: FakeSeries[] = [];
        const layer = makeLayer(series);
        layer.apply({ type: 'indicator', symbol: 'X',
                      items: items('#f6c343') } as never);
        layer.applyLast({
            type: 'indicator', symbol: 'X', mode: 'last',
            items: [{
                key: 'MA20', label: 'MA20', kind: 'line',
                overlay: true, color: '#f6c343',
                data: [[1_700_000_060, 12], [1_700_000_120, 13]],
            }],
        } as never);
        expect(series[0].data).toEqual([
            { time: 1_700_000_000, value: 10 },
            { time: 1_700_000_060, value: 12 },
            { time: 1_700_000_120, value: 13 },
        ]);
    });
});

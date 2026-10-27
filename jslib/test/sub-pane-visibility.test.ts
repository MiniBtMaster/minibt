/**
 * 副图显示规则：一个 pane 里**所有指标线都隐藏**时收起副图；
 * 只要还有一条可见线就保留 / 重新显示 ✓
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { IndicatorLayer } from '../src/desk/indicator';
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
    priceScale(): Record<string, unknown> {
        return { applyOptions: () => undefined, width: () => 0 };
    }
    createPriceLine(): Record<string, unknown> { return {}; }
    removePriceLine(): void { /* noop */ }
}

function makeLegend(): { legend: Record<string, unknown>; lines: Array<{ row?: StubElement; series?: unknown }> } {
    const lines: Array<{ row?: StubElement; series?: unknown }> = [];
    const legend = {
        _lines: lines,
        makeSeriesRow: (_label: string, series: unknown) => {
            lines.push({ row: new StubElement('div'), series });
        },
        setSeriesVisible: (_series: unknown, visible: boolean) => visible,
    };
    return { legend, lines };
}

function makeChart() {
    const panes: Array<{ setHeight?: (value: number) => void }> = [{}];
    const series: FakeSeries[] = [];
    const calls: string[] = [];
    const chart = {
        addSeries: (_def: unknown, options: Record<string, unknown>) => {
            const item = new FakeSeries(options);
            series.push(item);
            return item;
        },
        removeSeries: (item: FakeSeries) => {
            calls.push('removeSeries');
            const index = series.indexOf(item);
            if (index >= 0) series.splice(index, 1);
        },
        panes: () => panes,
        addPane: () => {
            calls.push('addPane');
            panes.push({});
        },
        removePane: (index: number) => {
            calls.push(`removePane:${index}`);
            panes.splice(index, 1);
        },
        priceScale: () => ({ width: () => 0, applyOptions: () => undefined }),
        timeScale: () => ({}),
    };
    return { chart, panes, series, calls };
}

function line(key: string, pane: string, overlay = false) {
    return {
        key, label: key, kind: 'line', pane, overlay,
        color: '#2196f3', lineWidth: 1, lineStyle: 0,
        data: [[1_700_000_000, 10], [1_700_000_060, 11]],
    };
}

function makeLayer(chart: unknown, legend: Record<string, unknown>): IndicatorLayer {
    return new IndicatorLayer(
        new StubElement('div') as never,
        () => chart as never,
        () => ({ background: '#000', text: '#fff', up: '#26a26a', down: '#ef5350' }),
        () => legend as never,
        () => null,
    );
}

describe('sub pane visibility', () => {
    it('keeps the pane while one line is visible, hides it when all are hidden', () => {
        const { chart, panes, calls } = makeChart();
        const { legend, lines } = makeLegend();
        const layer = makeLayer(chart, legend);
        layer.apply({
            type: 'indicator', symbol: 'X',
            items: [line('dif', 'macd'), line('dea', 'macd')],
        } as never);
        expect(panes.length).toBe(2);
        expect(lines.length).toBe(2);

        layer.setVisible('dif', false);
        expect(panes.length).toBe(2);       // dea 还在 → 副图保留
        expect(lines.length).toBe(2);       // 指标标签不动

        layer.setVisible('dea', false);
        expect(panes.length).toBe(1);       // 全部隐藏 → 副图收起
        expect(calls.some((item) => item.startsWith('removePane'))).toBe(true);
        expect(lines.length).toBe(2);       // 标签仍在

        layer.setVisible('dif', true);
        expect(panes.length).toBe(2);       // 重新显示 → 副图回来
        expect(lines.length).toBe(2);       // 没有重复标签
    });

    it('does not recreate a hidden pane on the next backend push', () => {
        const { chart, panes } = makeChart();
        const { legend } = makeLegend();
        const layer = makeLayer(chart, legend);
        const items = [line('dif', 'macd'), line('dea', 'macd')];
        layer.apply({ type: 'indicator', symbol: 'X', items } as never);
        layer.setVisible('dif', false);
        layer.setVisible('dea', false);
        expect(panes.length).toBe(1);
        // 后端每秒全量推送：item 默认 visible=true，但覆盖状态仍是隐藏 ✓
        layer.apply({ type: 'indicator', symbol: 'X', items } as never);
        expect(panes.length).toBe(1);
    });

    it('hides only the sub pane of a mixed overlay indicator', () => {
        const { chart, panes } = makeChart();
        const { legend } = makeLegend();
        const layer = makeLayer(chart, legend);
        const main = { ...line('mixed_main', 'mixed', true) };
        const sub = { ...line('mixed_sub', 'mixed', false) };
        layer.apply({ type: 'indicator', symbol: 'X',
                      items: [main, sub] } as never);
        expect(panes.length).toBe(2);

        layer.setVisible('mixed_sub', false);
        expect(panes.length).toBe(1);       // 主图线还在，副图收起
        // 主图系列仍在（apply 时 overlay 分支不受副图影响）
        expect(chart.panes().length).toBe(1);

        layer.setVisible('mixed_sub', true);
        expect(panes.length).toBe(2);
    });

    it('settings visibility follows the same pane rule', () => {
        const { chart, panes } = makeChart();
        const { legend } = makeLegend();
        const layer = makeLayer(chart, legend);
        layer.apply({ type: 'indicator', symbol: 'X',
                      items: [line('dif', 'macd')] } as never);
        expect(panes.length).toBe(2);
        layer.applyStyle('dif', {
            params: {}, lineStyle: 0, lineWidth: 1, color: '#2196f3',
            priceLine: true, priceLabel: true, visible: false,
            crosshairMarker: true, overlay: false,
        } as never);
        expect(panes.length).toBe(1);
        layer.applyStyle('dif', {
            params: {}, lineStyle: 0, lineWidth: 1, color: '#2196f3',
            priceLine: true, priceLabel: true, visible: true,
            crosshairMarker: true, overlay: false,
        } as never);
        expect(panes.length).toBe(2);
    });
});

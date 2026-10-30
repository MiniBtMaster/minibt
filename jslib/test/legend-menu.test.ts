import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LegendMenu, LegendMenuConfig } from '../src/general/legend-menu';
import { DomStub, StubElement, installDom } from './dom';

let dom: DomStub;
let applied: any[];

function makeSeries() {
    applied = [];
    return { applyOptions: (options: any) => { applied.push(options); } } as any;
}

function baseConfig(extra: Partial<LegendMenuConfig> = {}): LegendMenuConfig {
    return {
        title: 'UT_Bot_Alerts指标参数',
        params: [{ name: 'a', value: 1.0, type: 'float' }],
        lineStyle: 'solid',
        lineWidth: 2,
        lineColor: '#ffffff',
        priceLine: false,
        priceLabel: false,
        ...extra,
    };
}

const panel = () => dom.body.children[0];
const sub = () => dom.body.children[1];

function item(label: string): StubElement | undefined {
    return panel().children.find((c) => c.children[0]?.textContent === label);
}

function openItem(label: string): void {
    item(label)!.click();
}

const choices = () => sub().children;

beforeEach(() => {
    dom = installDom();
});

describe('legend menu structure', () => {
    it('builds the groups with Chinese labels (no title row)', () => {
        new LegendMenu(makeSeries(), 'w.abc', baseConfig(), 'cb');
        const labels = panel().children
            .map((c) => c.children[0].textContent);
        expect(labels).toEqual(['参数', '线型', '线宽', '线颜色', '其它设置']);
        expect(sub().classList.contains('legend-menu-sub')).toBe(true);
    });

    it('hides the line-style group for histograms', () => {
        new LegendMenu(makeSeries(), 'w.abc',
                       baseConfig({ showStyle: false }), 'cb');
        const labels = panel().children.map((c) => c.children[0].textContent);
        expect(labels).not.toContain('线型');
    });

    it('omits the params group when there are no params', () => {
        new LegendMenu(makeSeries(), 'w.abc', baseConfig({ params: [] }), 'cb');
        const labels = panel().children.map((c) => c.children[0].textContent);
        expect(labels).not.toContain('参数');
    });
});

describe('legend menu apply', () => {
    it('applies line style and reports to python', () => {
        new LegendMenu(makeSeries(), 'w.abc', baseConfig(), 'cb');
        openItem('线型');
        choices().find((c) => c.textContent === '点线')!.click();
        expect(applied).toContainEqual({ lineStyle: 1 });
        expect(dom.messages)
            .toContain('cb_~_w.abc;;;style;;;{"value":"dotted","source":""}');
    });

    it('applies line width', () => {
        new LegendMenu(makeSeries(), 'w.abc', baseConfig(), 'cb');
        openItem('线宽');
        choices().find((c) => c.textContent === '5')!.click();
        expect(applied).toContainEqual({ lineWidth: 5 });
        expect(dom.messages.some((m) => m.includes(';;;width;;;'))).toBe(true);
    });

    it('applies colour (area series uses lineColor/top/bottom)', () => {
        new LegendMenu(makeSeries(), 'w.abc',
                       baseConfig({ isArea: true }), 'cb');
        openItem('线颜色');
        choices().find((c) => c.textContent === '#f23645')!.click();
        expect(applied).toContainEqual({
            lineColor: '#f23645', topColor: '#f2364555',
            bottomColor: '#f2364500',
        });
    });

    it('applies a plain colour for line series', () => {
        new LegendMenu(makeSeries(), 'w.abc', baseConfig(), 'cb');
        openItem('线颜色');
        choices().find((c) => c.textContent === '#2196f3')!.click();
        expect(applied).toContainEqual({ color: '#2196f3' });
    });

    it('toggles the price line on and back off', () => {
        new LegendMenu(makeSeries(), 'w.abc', baseConfig(), 'cb');
        openItem('其它设置');
        choices()[0].click();                 // 开
        expect(applied).toContainEqual({
            priceLineVisible: true, lastValueVisible: false,
        });
        expect(dom.messages.some((m) => m.includes(';;;price;;;'))).toBe(true);

        openItem('其它设置');                 // 重新打开子菜单
        choices()[0].click();                 // 关
        expect(applied).toContainEqual({
            priceLineVisible: false, lastValueVisible: false,
        });
    });

    it('coerces param types on confirm', () => {        new LegendMenu(makeSeries(), 'w.abc', baseConfig({
            params: [
                { name: 'a', value: 1.0, type: 'float' },
                { name: 'c', value: 10, type: 'int' },
                { name: 'h', value: false, type: 'bool' },
            ],
        }), 'cb');
        openItem('参数');
        const inputs = choices().map((row) => row.children[2])
            .filter(Boolean) as StubElement[];
        inputs[0].value = '2.5';
        inputs[1].value = '20';
        inputs[2].value = 'true';
        choices().find((c) => c.classList.contains('legend-menu-confirm'))!.click();
        const message = dom.messages.find((m) => m.includes(';;;params;;;'));
        expect(message).toBeTruthy();
        expect(JSON.parse(message!.split(';;;params;;;')[1]))
            .toEqual({ values: { a: 2.5, c: 20, h: true }, source: '' });
    });

    it('excludes readonly object params from the callback', () => {
        // sym1 这类对比合约参数只在菜单里“看”，绝不回传（写回去会把
        // KLine 对象弄丢 ✗）
        new LegendMenu(makeSeries(), 'w.abc', baseConfig({
            params: [
                { name: 'length', value: 3, type: 'int' },
                { name: 'sym1', value: 'KLine(pp2609)', type: 'str', readonly: true },
            ],
        }), 'cb');
        openItem('参数');
        const rows = choices().filter(
            (c) => c.classList.contains('legend-menu-param-row'));
        const symRow = rows.find((r) => r.classList.contains('is-readonly'))!;
        expect(symRow).toBeTruthy();
        const symInput = symRow.children[2] as StubElement;
        expect(symInput.disabled).toBe(true);
        expect(symInput.readOnly).toBe(true);
        symInput.value = 'garbage';
        choices().find((c) => c.classList.contains('legend-menu-confirm'))!.click();
        const message = dom.messages.find((m) => m.includes(';;;params;;;'));
        expect(message).toBeTruthy();
        expect(JSON.parse(message!.split(';;;params;;;')[1]))
            .toEqual({ values: { length: 3 }, source: '' });
    });
});

describe('legend menu flyout hover', () => {
    it('stays open while the pointer moves onto the flyout', () => {
        vi.useFakeTimers();
        try {
            new LegendMenu(makeSeries(), 'w.abc', baseConfig(), 'cb');
            openItem('线型');
            expect(sub().style.display).toBe('flex');

            // 指针从一级菜单移到二级菜单（兄弟元素）——不应被隐藏 ✓
            panel().dispatch('mouseleave');
            sub().dispatch('mouseenter');
            vi.advanceTimersByTime(500);
            expect(sub().style.display).toBe('flex');

            // 离开二级菜单且未再进入 → 延迟后隐藏
            sub().dispatch('mouseleave');
            vi.advanceTimersByTime(500);
            expect(sub().style.display).toBe('none');
        } finally {
            vi.useRealTimers();
        }
    });
});

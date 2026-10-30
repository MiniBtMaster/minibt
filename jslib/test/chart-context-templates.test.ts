/** 图表右键「我的模板 / 保存当前指标模板」（本地图表 + 实时图表共用 ✓） */
import { describe, expect, it, vi } from 'vitest';
import { installDom } from './dom';

const { menuSpy } = vi.hoisted(() => ({ menuSpy: vi.fn() }));
vi.mock('../src/desk/menu', () => ({
    showMenu: (_x: number, _y: number, items: unknown[]) => menuSpy(items),
    showMenuBelow: () => undefined,
    closeMenu: () => undefined,
}));

import { showChartContextMenu } from '../src/desk/chart-context-menu';

function baseSpec(over: Record<string, unknown> = {}) {
    return {
        favorites: [],
        strategies: [],
        templates: [],
        layouts: [],
        cycle: 60,
        cycleGroups: [],
        onIndicatorPicker: () => undefined,
        onAddFavorite: () => undefined,
        onRemove: () => undefined,
        onCycle: () => undefined,
        onLayoutPreset: () => undefined,
        onLayoutApply: () => undefined,
        onToggleToolBox: () => undefined,
        onClearDrawings: () => undefined,
        onAlert: () => undefined,
        onClearAlerts: () => undefined,
        onScreenshot: () => undefined,
        ...over,
    };
}

function reset(): void {
    installDom();
    menuSpy.mockClear();
}

function itemsOf(): Array<Record<string, unknown>> {
    return menuSpy.mock.calls[0][0] as Array<Record<string, unknown>>;
}

describe('图表右键：我的模板 / 保存当前指标模板 ✓', () => {
    it('列出模板，点了就是「应用模板到当前格」✓', () => {
        const applied: string[] = [];
        reset();
        showChartContextMenu(baseSpec({
            templates: [
                { key: 'tpl:1', name: '均线三兄弟' },
                { key: 'tpl:2', name: 'MACD 组合' },
            ],
            onApplyTemplate: (key: string) => applied.push(key),
            onSaveTemplate: () => undefined,
        }) as never, 10, 10);

        const items = itemsOf();
        const labels = items.map((item) => item.label);
        expect(labels).toContain('我的模板');
        expect(labels).toContain('保存当前指标模板');

        const sub = items.find((item) => item.label === '我的模板')!
            .submenu as Array<Record<string, unknown>>;
        expect(sub.map((item) => item.label))
            .toEqual(['均线三兄弟', 'MACD 组合']);
        (sub[1].run as () => void)();
        expect(applied).toEqual(['tpl:2']);
    });

    it('没有模板 → 子菜单给提示（不可点）✓', () => {
        reset();
        showChartContextMenu(baseSpec({
            onApplyTemplate: () => undefined,
            onSaveTemplate: () => undefined,
        }) as never, 10, 10);
        const sub = itemsOf().find((item) => item.label === '我的模板')!
            .submenu as Array<Record<string, unknown>>;
        expect(sub[0].label).toBe('（还没有保存过模板）');
        expect(sub[0].disabled).toBe(true);
    });

    it('「保存当前指标模板」= 工具栏同一条命令 ✓', () => {
        let saved = 0;
        reset();
        showChartContextMenu(baseSpec({
            onSaveTemplate: () => { saved += 1; },
        }) as never, 10, 10);
        const item = itemsOf().find(
            (row) => row.label === '保存当前指标模板')!;
        expect(item.disabled).toBeFalsy();
        (item.run as () => void)();
        expect(saved).toBe(1);
    });
});

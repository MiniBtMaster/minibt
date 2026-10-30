/** 回放实验室：弹菜单选本地图表（本地图表1 / 2 / 3…）✓
 *
 * 用户 2026-10-30 要求：
 * * 「打开并进入回放」/「只打开本地图表」→ 点击弹出菜单，列出已创建的本地图表；
 * * 一个也没建过 → 两个按钮都直接新建一个本地图表页并转过去。
 */
import { describe, expect, it, vi } from 'vitest';
import { installDom } from './dom';

const { menuSpy } = vi.hoisted(() => ({ menuSpy: vi.fn() }));
vi.mock('../src/desk/menu', () => ({
    showMenuBelow: (anchor: unknown, items: unknown[]) => menuSpy(anchor, items),
    showMenu: vi.fn(),
}));

import { ReplayLabPage } from '../src/desk/workspace-pages';

interface Tab { id: string; label: string; kind: string }

function makePage(locals: Tab[]) {
    installDom();
    menuSpy.mockClear();
    const calls: string[] = [];
    const page = new ReplayLabPage({
        theme: 'dark',
        getLocals: () => locals,
        onOpenLocal: (id) => calls.push(`open:${id}`),
        onStartReplay: (id) => calls.push(`replay:${id}`),
        onNewLocal: () => calls.push('new'),
    });
    return { page, calls };
}

/** 假按钮：`closest('[data-replay-start]')` 命中 / 不命中 ✓ */
function fakeButton(start: boolean) {
    const anchor = { getBoundingClientRect: () => ({ left: 0, bottom: 0 }) };
    return {
        closest: (selector: string) => {
            if (start && selector === '[data-replay-start]') return anchor;
            if (!start && selector === '[data-replay-open]') return anchor;
            return null;
        },
    };
}

describe('回放实验室：选本地图表 ✓', () => {
    it('没有本地图表 → 两个按钮都是「新建一个并转过去」✓', () => {
        for (const start of [true, false]) {
            const { page, calls } = makePage([]);
            page.element.dispatch('click', { target: fakeButton(start) });
            expect(calls).toEqual(['new']);
            expect(menuSpy).not.toHaveBeenCalled();
        }
    });

    it('有本地图表 → 弹菜单列出「本地图表1 / 2 / 3…」✓', () => {
        const { page, calls } = makePage([
            { id: 'local:1', label: '本地图表1', kind: 'local' },
            { id: 'local:2', label: '本地图表2', kind: 'local' },
            { id: 'local:3', label: '本地图表3', kind: 'local' },
        ]);
        page.element.dispatch('click', { target: fakeButton(true) });
        expect(menuSpy).toHaveBeenCalledTimes(1);
        const items = menuSpy.mock.calls[0][1] as Array<{
            label: string; run?: () => void; separator?: boolean }>;
        expect(items.map((item) => item.label)).toEqual([
            '本地图表1', '本地图表2', '本地图表3', '＋ 新建本地图表…',
        ]);

        // 选第 2 个 → 打开并进入回放 ✓
        items[1].run?.();
        expect(calls).toEqual(['replay:local:2']);

        // 最后一项 → 新建副本 ✓
        expect(items[3].separator).toBe(true);
        items[3].run?.();
        expect(calls).toEqual(['replay:local:2', 'new']);
    });

    it('「只打开本地图表」→ 菜单里选的是「打开」而不是回放 ✓', () => {
        const { page, calls } = makePage([
            { id: 'local:7', label: '本地图表7', kind: 'local' },
        ]);
        page.element.dispatch('click', { target: fakeButton(false) });
        const items = menuSpy.mock.calls[0][1] as Array<{ run?: () => void }>;
        items[0].run?.();
        expect(calls).toEqual(['open:local:7']);
    });
});

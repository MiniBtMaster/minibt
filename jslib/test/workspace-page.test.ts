/** 图表工作台：左侧「本地图表」列表 / 右侧新建入口（本地图表可多开 ✓） */
import { describe, expect, it } from 'vitest';
import { installDom } from './dom';
import { WorkspacePage } from '../src/desk/workspace-pages';

interface Tab {
    id: string; label: string; kind: string;
}

function makePage(tabs: Tab[]) {
    installDom();
    const opened: string[] = [];
    let created = 0;
    const page = new WorkspacePage({
        theme: 'dark',
        getTabs: () => tabs,
        onActivate: (id) => opened.push(id),
        onNewQuote: () => undefined,
        onNewLocal: () => { created += 1; },
    });
    return { page, opened, created: () => created };
}

describe('WorkspacePage（多开本地图表）', () => {
    it('左边只列本地图表页，右边是新建入口 ✓', () => {
        const { page } = makePage([
            { id: 'local:1', label: '本地图表1', kind: 'local' },
            { id: 'chart:DCE.a2701', label: 'DCE.a2701', kind: 'chart' },
        ]);
        const html = page.element.innerHTML;
        expect(html).toContain('desk-workspace-body');
        // 本地图表行 ✓
        expect(html).toContain('data-work-tab="local:1"');
        expect(html).toContain('本地图表1');
        // 实时图表不在「本地图表」区（它在右栏的实时图表里）✓
        const left = html.slice(html.indexOf('desk-workspace-list'),
                                html.indexOf('desk-workspace-side'));
        expect(left).not.toContain('DCE.a2701');
        // 右侧新建入口 ✓
        expect(html).toContain('data-work-local');
        expect(html).toContain('新建本地图表');
    });

    it('refresh() 跟着顶栏 tab 变化（新建 / 关闭后马上能看到 ✓）', () => {
        const tabs: Tab[] = [
            { id: 'local:1', label: '本地图表1', kind: 'local' },
        ];
        const { page } = makePage(tabs);
        expect(page.element.innerHTML).toContain('本地图表1');

        tabs.push({ id: 'local:2', label: '本地图表2', kind: 'local' });
        page.refresh();
        expect(page.element.innerHTML).toContain('本地图表2');

        tabs.shift();
        page.refresh();
        // 行没了（标题里的示例文案还在，所以按 data-work-tab 判 ✓）
        expect(page.element.innerHTML).not.toContain('data-work-tab="local:1"');
        expect(page.element.innerHTML).toContain('data-work-tab="local:2"');
    });

    it('没有本地图表时不罗列行，只给新建提示 ✓', () => {
        const { page } = makePage([
            { id: 'chart:DCE.a2701', label: 'DCE.a2701', kind: 'chart' },
        ]);
        const html = page.element.innerHTML;
        expect(html).not.toContain('data-work-tab="local:');
        expect(html).toContain('还没有新建本地图表');
    });

    it('show() 时重新渲染（切回工作台就是最新的 ✓）', () => {
        const tabs: Tab[] = [];
        const { page } = makePage(tabs);
        expect(page.element.innerHTML).toContain('还没有新建本地图表');
        tabs.push({ id: 'local:3', label: '本地图表3', kind: 'local' });
        page.show();                        // 不手动 refresh
        expect(page.element.innerHTML).toContain('本地图表3');
        expect(page.element.style.display).toBe('block');
    });
});

/** Home 左侧三个真正的工作区页面：图表工作台 / 回放实验室 / 预警中心。 */
import type { DeskTheme } from './theme';

function esc(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch] as string));
}

export interface WorkspaceTabInfo {
    id: string;
    label: string;
    kind: string;
}

interface WorkspaceOptions {
    theme: DeskTheme;
    getTabs: () => WorkspaceTabInfo[];
    onActivate: (id: string) => void;
    onNewQuote: () => void;
    onNewLocal: () => void;
}

/** 图表工作台：列出当前打开的图表 / 本地图表，快速激活或新建。 */
export class WorkspacePage {
    public readonly element: HTMLDivElement;
    private readonly options: WorkspaceOptions;
    private theme: DeskTheme;

    constructor(options: WorkspaceOptions) {
        this.options = options;
        this.theme = options.theme;
        this.element = document.createElement('div');
        this.element.className = `desk-workspace-page theme-${this.theme}`;
        this.element.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            const row = target.closest<HTMLElement>('[data-work-tab]');
            if (row) {
                this.options.onActivate(String(row.dataset.workTab || ''));
                return;
            }
            if (target.closest('[data-work-quote]')) {
                this.options.onNewQuote();
            } else if (target.closest('[data-work-local]')) {
                this.options.onNewLocal();
            }
        });
        this.render();
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-workspace-page theme-${theme}`;
    }

    private render(): void {
        const tabs = this.options.getTabs().filter((tab) =>
            tab.kind === 'chart' || tab.kind === 'local');
        const rows = tabs.map((tab) => `
            <button class="desk-workspace-row" data-work-tab="${esc(tab.id)}">
                <span>${tab.kind === 'local' ? '本地图表' : '图表'} · ${esc(tab.label)}</span>
                <span class="desk-muted">打开 ›</span>
            </button>`).join('');
        this.element.innerHTML = `
            <div class="desk-workspace-head">
                <div><h2>图表工作台</h2>
                    <p class="desk-muted">当前打开的图表集中在这里，快速切换或新建。</p></div>
                <div class="desk-workspace-actions">
                    <button class="desk-tool" data-work-quote>新建行情报价</button>
                    <button class="desk-tool" data-work-local>新建本地图表</button>
                </div>
            </div>
            <div class="desk-workspace-list">
                ${rows || '<div class="desk-workspace-empty">还没有打开图表。先新建行情报价或本地图表。</div>'}
            </div>`;
    }
}

interface ReplayLabOptions {
    theme: DeskTheme;
    onOpenLocal: () => void;
    onStartReplay: () => void;
}

/** 回放实验室：进入本地图表回放的明确入口。 */
export class ReplayLabPage {
    public readonly element: HTMLDivElement;
    private theme: DeskTheme;

    constructor(options: ReplayLabOptions) {
        this.theme = options.theme;
        this.element = document.createElement('div');
        this.element.className = `desk-replay-lab theme-${this.theme}`;
        this.element.innerHTML = `
            <div class="desk-workspace-head">
                <div><h2>回放实验室</h2>
                    <p class="desk-muted">用本地 CSV 逐根复盘；指标与策略会跟随回放进度。</p></div>
            </div>
            <div class="desk-replay-lab-body">
                <div class="desk-replay-lab-card">
                    <h3>从本地 CSV 开始</h3>
                    <p>打开本地图表，选择 CSV 后点工具栏 ▶▶ 即可进入回放。</p>
                    <div class="desk-workspace-actions">
                        <button class="desk-tool primary" data-replay-start>打开并进入回放</button>
                        <button class="desk-tool" data-replay-open>只打开本地图表</button>
                    </div>
                </div>
                <div class="desk-replay-lab-card">
                    <h3>回放能做什么</h3>
                    <ul class="desk-muted">
                        <li>指标按回放进度切片，不提前显示未来数据</li>
                        <li>带交易逻辑的策略自动成交到本地模拟账户</li>
                        <li>支持多布局 / 配对策略逐格同步</li>
                    </ul>
                </div>
            </div>`;
        this.element.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            if (target.closest('[data-replay-start]')) options.onStartReplay();
            else if (target.closest('[data-replay-open]')) options.onOpenLocal();
        });
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-replay-lab theme-${theme}`;
    }
}

export interface AlertItem {
    id?: number;
    symbol?: string;
    price?: number;
    cross?: string;
    action?: string;
    qty?: number;
    message?: string;
    fired?: boolean;
    expired?: boolean;
    decimals?: number;
}

interface AlertCenterOptions {
    theme: DeskTheme;
    onRefresh: () => void;
    onDrop: (id: number) => void;
    onClear: () => void;
    onOpen: (symbol: string) => void;
}

/** 预警中心：全局预警列表 + 删除 / 清空 / 跳转合约。 */
export class AlertCenterPage {
    public readonly element: HTMLDivElement;
    private readonly options: AlertCenterOptions;
    private theme: DeskTheme;
    private items: AlertItem[] = [];

    constructor(options: AlertCenterOptions) {
        this.options = options;
        this.theme = options.theme;
        this.element = document.createElement('div');
        this.element.className = `desk-alert-center theme-${this.theme}`;
        this.element.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            if (target.closest('[data-alert-refresh]')) {
                this.options.onRefresh();
                return;
            }
            if (target.closest('[data-alert-clear]')) {
                this.options.onClear();
                return;
            }
            const drop = target.closest<HTMLElement>('[data-alert-drop]');
            if (drop) {
                this.options.onDrop(Number(drop.dataset.alertDrop));
                return;
            }
            const open = target.closest<HTMLElement>('[data-alert-open]');
            if (open) this.options.onOpen(String(open.dataset.alertOpen || ''));
        });
        this.render();
        this.options.onRefresh();
    }

    setAlerts(items: AlertItem[]): void {
        this.items = Array.isArray(items) ? items : [];
        this.render();
    }

    show(): void { this.element.style.display = 'block'; }
    hide(): void { this.element.style.display = 'none'; }
    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.className = `desk-alert-center theme-${theme}`;
    }

    private render(): void {
        const rows = this.items.map((item) => {
            const state = item.expired ? '已过期' : (item.fired ? '已触发' : '等待中');
            const action = item.action === 'buy' ? '买'
                : (item.action === 'sell' ? '卖'
                    : (item.action === 'close' ? '平' : '无操作'));
            return `<div class="desk-alert-row">
                <button class="desk-alert-symbol" data-alert-open="${esc(item.symbol)}"
                    title="打开合约">${esc(item.symbol)}</button>
                <span>${esc(item.cross || '穿过')} ${esc(item.price)}</span>
                <span>${action} ${Number(item.qty || 1)} 手</span>
                <span class="desk-muted">${esc(item.message || '')}</span>
                <span class="desk-alert-state ${item.fired ? 'on' : ''}">${state}</span>
                <button class="desk-tool" data-alert-drop="${esc(item.id)}">删除</button>
            </div>`;
        }).join('');
        this.element.innerHTML = `
            <div class="desk-workspace-head">
                <div><h2>预警中心</h2>
                    <p class="desk-muted">所有图表的全局价格预警。</p></div>
                <div class="desk-workspace-actions">
                    <button class="desk-tool" data-alert-refresh>刷新</button>
                    <button class="desk-tool" data-alert-clear>清空全部</button>
                </div>
            </div>
            <div class="desk-alert-list">
                ${rows || '<div class="desk-workspace-empty">还没有价格预警。在图表工具栏 🔔 里添加。</div>'}
            </div>`;
    }
}

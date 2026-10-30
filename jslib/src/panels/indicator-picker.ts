/**
 * IndicatorPicker — 「指标、衡量标准和策略」选择器（复刻 miniqt 的指标面板）。
 *
 *   ┌ 指标、衡量标准和策略                                ✕ ┐
 *   │ [搜索 …]                                          🔍 │
 *   │ 个人      │ ☆ AndeanOsc                       BtInd │
 *   │  收藏     │   安第斯振荡器指标 (Andean Oscillator)     │
 *   │  我的脚本 │ ☆ Coral_Trend_Candles …                  │
 *   │  我的策略 │ …                                        │
 *   │ 内置指标  │                                          │
 *   │  BtInd    │                                          │
 *   └──────────────────────────────────────────────────────┘
 *
 * 事件（``;;;`` 分隔）：``pick;;;<key>`` / ``favorite;;;<key>;;;<0|1>``。
 */
import { emitCallback, ensureStyle } from './emit';

export interface PickerSection {
    key: string;
    label: string;
}

export interface PickerGroup {
    key: string;
    label: string;
    sections: PickerSection[];
}

export interface PickerItem {
    key: string;
    label: string;
    desc?: string;
    provider?: string;
    section?: string;
    /** 主图叠加（true）/ 副图（false）；`undefined` = 未知（个人脚本）✓ */
    overlay?: boolean;
    favorite?: boolean;
    strategy?: boolean;
    params?: Array<Record<string, unknown>>;
}

export interface IndicatorPickerOptions {
    title?: string;
    groups?: PickerGroup[];
    items?: PickerItem[];
    /** 默认选中的 section（`favorites` → 收藏 ✓） */
    section?: string;
    theme?: 'light' | 'dark';
    callbackName?: string | null;
}

const STYLE_ID = 'pylightcharts-indicatorpicker-style';

const CSS = `
.pylc-ip-mask{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:11800;
  display:flex;align-items:center;justify-content:center}
.pylc-ip{width:840px;height:620px;max-height:88vh;display:flex;flex-direction:column;
  border-radius:10px;overflow:hidden;background:var(--ip-bg);color:var(--ip-text);
  border:1px solid var(--ip-border);box-shadow:0 20px 60px rgba(0,0,0,.45)}
.pylc-ip-head{display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px;font-size:15px;font-weight:600}
.pylc-ip-close{border:none;background:transparent;color:var(--ip-text);
  cursor:pointer;font-size:17px}
.pylc-ip-search-wrap{padding:0 16px 10px}
.pylc-ip-search{width:100%;height:30px;padding:0 10px;border-radius:6px;outline:none;
  border:1px solid var(--ip-border);background:var(--ip-input);color:var(--ip-text);
  font-size:12.5px}
.pylc-ip-search:focus{border-color:var(--ip-accent)}
.pylc-ip-body{flex:1;min-height:0;display:flex;border-top:1px solid var(--ip-border)}
.pylc-ip-tree{flex:0 0 190px;overflow:auto;padding:8px 0;
  border-right:1px solid var(--ip-border)}
.pylc-ip-group{padding:6px 14px 2px;color:var(--ip-accent);font-size:12px}
.pylc-ip-section{padding:4px 14px 4px 22px;cursor:pointer;font-size:12.5px;
  border-radius:0 6px 6px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pylc-ip-section:hover{background:var(--ip-hover)}
.pylc-ip-section.on{background:var(--ip-active);font-weight:600}
.pylc-ip-list{flex:1;min-width:0;overflow:auto}
.pylc-ip-row{display:grid;grid-template-columns:22px 1fr auto;gap:6px;
  align-items:start;padding:8px 14px;cursor:pointer;border-bottom:1px solid var(--ip-border)}
.pylc-ip-row:hover{background:var(--ip-hover)}
.pylc-ip-star{color:var(--ip-muted);font-size:13px;line-height:1.25;
  cursor:pointer;user-select:none}
.pylc-ip-star.on{color:#f6c343}
.pylc-ip-name{font-size:13px}
.pylc-ip-desc{color:var(--ip-muted);font-size:11.5px;line-height:1.45}
.pylc-ip-provider{color:var(--ip-muted);font-size:11.5px;white-space:nowrap}
.pylc-ip-empty{padding:20px 16px;color:var(--ip-muted);font-size:12.5px}
.pylc-ip-filters{display:flex;align-items:center;gap:6px;padding:0 16px 8px;
  font-size:12px;color:var(--ip-muted)}
.pylc-ip-filter{padding:2px 9px;border-radius:999px;cursor:pointer;
  border:1px solid var(--ip-border);background:transparent;color:var(--ip-muted);
  font-size:12px;line-height:1.5}
.pylc-ip-filter:hover{background:var(--ip-hover)}
.pylc-ip-filter.on{background:var(--ip-active);color:var(--ip-text);
  border-color:var(--ip-accent);font-weight:600}
.pylc-ip-filter-count{margin-left:auto;color:var(--ip-muted);font-size:11.5px}
`;

const PALS = {
    dark: {
        bg: '#161a20', text: '#d8d9db', muted: '#8b93a1', border: '#262c36',
        input: '#0f1115', hover: '#1e242d', active: '#263041', accent: '#4c8dff',
    },
    light: {
        bg: '#ffffff', text: '#1f2329', muted: '#6b7280', border: '#e3e6ea',
        input: '#f6f7f9', hover: '#eef1f5', active: '#e6efff', accent: '#1a73e8',
    },
};

export class IndicatorPicker {
    public readonly element: HTMLDivElement;
    public callbackName: string | null = null;
    public onPickCallback: ((item: PickerItem) => void) | null = null;
    public onFavoriteCallback:
        ((item: PickerItem, on: boolean) => void) | null = null;
    /** 二级筛选变了（宿主可以记住，下次打开接着用 ✓） */
    public onFilterCallback:
        ((kind: 'all' | 'main' | 'sub') => void) | null = null;
    /** 「重新加载」按钮（目录为空时自救 ✓） */
    public onReloadCallback: (() => void) | null = null;

    private groups: PickerGroup[];
    private items: PickerItem[];
    private section = 'favorites';
    private filterBar: HTMLDivElement | null = null;
    /** 载体统计 / 错误提示（`共 774 个指标` / 目录失败原因 ✓） */
    private infoBar: HTMLDivElement | null = null;
    private total = 0;
    private error = '';
    /** 二级筛选：全部 / 主图叠加 / 副图 ✓ */
    private overlayFilter: 'all' | 'main' | 'sub' = 'all';
    private readonly tree: HTMLDivElement;
    private readonly list: HTMLDivElement;
    private readonly search: HTMLInputElement;
    private readonly titleEl: HTMLSpanElement;

    constructor(options: IndicatorPickerOptions = {}) {
        ensureStyle(STYLE_ID, CSS);
        this.callbackName = options.callbackName || null;
        this.groups = options.groups || [];
        this.items = options.items || [];
        this.section = options.section || 'favorites';

        this.element = document.createElement('div');
        this.element.className = 'pylc-ip-mask';
        this.element.style.display = 'none';

        const box = document.createElement('div');
        box.className = 'pylc-ip';

        const head = document.createElement('div');
        head.className = 'pylc-ip-head';
        this.titleEl = document.createElement('span');
        this.titleEl.textContent = options.title || '指标、衡量标准和策略';
        const close = document.createElement('button');
        close.className = 'pylc-ip-close';
        close.textContent = '✕';
        close.title = '关闭';
        close.addEventListener('click', () => this.close());
        head.append(this.titleEl, close);

        const searchWrap = document.createElement('div');
        searchWrap.className = 'pylc-ip-search-wrap';
        this.search = document.createElement('input');
        this.search.className = 'pylc-ip-search';
        this.search.placeholder = '搜索';
        this.search.title = '按名称 / 代码搜索指标';
        this.search.addEventListener('input', () => this._render());
        searchWrap.appendChild(this.search);

        this.filterBar = document.createElement('div');
        this.filterBar.className = 'pylc-ip-filters';
        this.infoBar = document.createElement('div');
        this.infoBar.className = 'pylc-ip-info';
        this.tree = document.createElement('div');
        this.tree.className = 'pylc-ip-tree';
        this.list = document.createElement('div');
        this.list.className = 'pylc-ip-list';

        const body = document.createElement('div');
        body.className = 'pylc-ip-body';
        body.append(this.tree, this.list);

        box.append(head, searchWrap, this.filterBar, this.infoBar, body);
        this.element.appendChild(box);
        this.element.addEventListener('mousedown', (event) => {
            if (event.target === this.element) this.close();
        });
        document.body.appendChild(this.element);

        this.setTheme(options.theme === 'light' ? 'light' : 'dark');
        this.setGroups(this.groups);
        this._render();
    }

    // ------------------------------------------------------------- 数据
    setGroups(groups: PickerGroup[]): void {
        this.groups = groups || [];
        this._renderTree();
    }

    /** 载体统计 / 错误（后端 `indicator_picker` 补丁里的 `total` / `error` ✓） */
    setInfo(total: number, error = ''): void {
        this.total = Number(total) || 0;
        this.error = String(error || '');
        this._renderInfo();
        this._render();
    }

    private _renderInfo(): void {
        const bar = this.infoBar;
        if (!bar) return;
        bar.textContent = '';
        bar.classList.toggle('error', !!this.error);
        if (this.error) {
            bar.append(`⚠ ${this.error}`);
            const reload = document.createElement('button');
            reload.className = 'pylc-ip-reload';
            reload.textContent = '重新加载';
            reload.addEventListener('mousedown', (event) => {
                event.preventDefault();
                this.onReloadCallback?.();
            });
            bar.appendChild(reload);
            return;
        }
        bar.textContent = this.total ? `共 ${this.total} 个指标` : '';
    }

    setItems(items: PickerItem[]): void {
        this.items = items || [];
        this._render();
    }

    setFavorites(keys: string[]): void {
        const set = new Set(keys || []);
        for (const item of this.items) item.favorite = set.has(item.key);
        this._render();
    }

    /** 二级筛选（`all` / `main` 主图叠加 / `sub` 副图 ✓） */
    setOverlayFilter(kind: 'all' | 'main' | 'sub', notify = false): void {
        this.overlayFilter = kind === 'main' || kind === 'sub' ? kind : 'all';
        this._render();
        if (notify) this.onFilterCallback?.(this.overlayFilter);
    }

    get filter(): 'all' | 'main' | 'sub' {
        return this.overlayFilter;
    }

    setSection(section: string): void {
        this.section = section || 'favorites';
        this._renderTree();
        this._render();
    }

    open(section = 'favorites'): void {
        this.element.style.display = '';
        this.search.value = '';
        this.setSection(section);
        this.search.focus();
    }

    close(): void {
        this.element.style.display = 'none';
    }

    get visible(): boolean {
        return this.element.style.display !== 'none';
    }

    setTheme(theme: 'light' | 'dark'): void {
        const pal = PALS[theme === 'light' ? 'light' : 'dark'];
        for (const [key, value] of Object.entries(pal)) {
            this.element.style.setProperty(`--ip-${key}`, value);
        }
    }

    // ------------------------------------------------------------- 渲染
    private _renderTree(): void {
        this.tree.textContent = '';
        for (const group of this.groups) {
            const title = document.createElement('div');
            title.className = 'pylc-ip-group';
            title.textContent = group.label;
            this.tree.appendChild(title);
            for (const section of group.sections) {
                const row = document.createElement('div');
                row.className = 'pylc-ip-section'
                    + (section.key === this.section ? ' on' : '');
                row.textContent = section.label;
                row.addEventListener('click', () => this.setSection(section.key));
                this.tree.appendChild(row);
            }
        }
    }

    /** 当前 section（+ 搜索 + 二级筛选）下的条目 ✓ */
    private _visibleRows(): PickerItem[] {
        const needle = this.search.value.trim().toLowerCase();
        const favorite = this.section === 'favorites';
        const rows = this.items.filter((item) => {
            if (needle) {
                return item.key.toLowerCase().includes(needle)
                    || (item.label || '').toLowerCase().includes(needle);
            }
            if (favorite) return !!item.favorite;
            // 「全部指标」= 不筛（774 个全在这 ✓）
            if (this.section === 'all') return true;
            if (this.section === 'my_strategies') return !!item.strategy;
            if (this.section === 'my_scripts') return item.section === 'my_scripts';
            return item.section === this.section;
        });
        // 二级筛选：主图叠加 / 副图（未知 overlay 的一律当副图看，别藏起来 ✗）
        if (this.overlayFilter === 'main') {
            return rows.filter((item) => item.overlay === true);
        }
        if (this.overlayFilter === 'sub') {
            return rows.filter((item) => item.overlay !== true);
        }
        return rows;
    }

    /** 筛选按钮（全部 / 主图叠加 / 副图 + 计数 ✓） */
    private _renderFilters(): void {
        if (!this.filterBar) return;
        const rows = this._visibleRows();
        this.filterBar.textContent = '';
        const label = document.createElement('span');
        label.textContent = '显示：';
        this.filterBar.appendChild(label);
        for (const [key, text] of [['all', '全部'],
                                   ['main', '主图叠加'],
                                   ['sub', '副图']] as const) {
            const chip = document.createElement('button');
            chip.className = 'pylc-ip-filter'
                + (this.overlayFilter === key ? ' on' : '');
            chip.textContent = text;
            chip.addEventListener('click',
                                  () => this.setOverlayFilter(key, true));
            this.filterBar.appendChild(chip);
        }
        const count = document.createElement('span');
        count.className = 'pylc-ip-filter-count';
        count.textContent = `${rows.length} 个`;
        this.filterBar.appendChild(count);
    }

    private _render(): void {
        this._renderFilters();
        const rows = this._visibleRows();
        const favorite = this.section === 'favorites';
        this.list.textContent = '';
        if (!rows.length) {
            const empty = document.createElement('div');
            empty.className = 'pylc-ip-empty';
            empty.textContent = this.error
                ? `（加载失败：${this.error}）`
                : favorite
                ? '（还没有收藏指标：点条目左侧的 ☆ 收藏）'
                : (this.overlayFilter === 'main'
                    ? '（这个分组里没有主图叠加的指标，换「全部」看看）'
                    : (this.overlayFilter === 'sub'
                        ? '（这个分组里没有副图指标，换「全部」看看）'
                        : '（没有匹配的指标）'));
            this.list.appendChild(empty);
            return;
        }
        for (const item of rows) {
            const row = document.createElement('div');
            row.className = 'pylc-ip-row';
            const star = document.createElement('span');
            star.className = 'pylc-ip-star' + (item.favorite ? ' on' : '');
            star.textContent = item.favorite ? '★' : '☆';
            star.title = item.favorite ? '取消收藏' : '收藏（工具栏下拉可用）';
            star.addEventListener('click', (event) => {
                event.stopPropagation();
                item.favorite = !item.favorite;
                star.textContent = item.favorite ? '★' : '☆';
                star.classList.toggle('on', !!item.favorite);
                emitCallback(this.callbackName,
                    `favorite;;;${item.key};;;${item.favorite ? 1 : 0}`);
                this.onFavoriteCallback?.(item, !!item.favorite);
            });
            const text = document.createElement('div');
            text.innerHTML = `<div class="pylc-ip-name">${item.label}</div>`
                + (item.desc ? `<div class="pylc-ip-desc">${item.desc}</div>` : '');
            const provider = document.createElement('div');
            provider.className = 'pylc-ip-provider';
            provider.textContent = item.provider || '';
            row.append(star, text, provider);
            row.addEventListener('click', () => {
                emitCallback(this.callbackName, `pick;;;${item.key}`);
                this.onPickCallback?.(item);
                this.close();
            });
            this.list.appendChild(row);
        }
    }
}

/**
 * SymbolSearch — 商品搜索（复刻 miniqt 顶栏的合约搜索）。
 *
 *   ┌ 搜索商品 / 代码 ────────────────────────────┐
 *   │ SHFE.rb2610   螺纹钢2610   SHFE   期货       │
 *   │ HK.00700      腾讯控股      HK     股票       │
 *   └────────────────────────────────────────────┘
 *
 * 支持两种模式：
 *   - **本地**：`setItems(items)` → 输入时前端自己过滤；
 *   - **远程**：不给 items → 输入防抖后发 `query;;;<text>`，后端用
 *     `setResults()` 回填（几千个合约时更省 ✓）。
 *
 * 事件（``;;;`` 分隔）：`query;;;<text>` / `pick;;;<symbol>`。
 */
import { emitCallback, ensureStyle } from './emit';

export interface SearchItem {
    symbol: string;
    name?: string;
    exchange?: string;
    type?: string;
    /** 中文类型（`期货` / `股票` / …） */
    type_label?: string;
    /** 市场（`上期所` / `港股` / …） */
    market?: string;
}

export interface SearchMarket {
    key: string;
    label: string;
}

export interface SymbolSearchOptions {
    placeholder?: string;
    items?: SearchItem[];
    /** 顶部市场 chips（全部 / 期货 / 股票 / … ✓） */
    markets?: SearchMarket[];
    /** 当前选中的市场 key（空 = 全部） */
    market?: string;
    /** 不传 items 时 = 远程模式（默认 true 时也会先本地过滤 ✓） */
    remote?: boolean;
    limit?: number;
    width?: number;
    callbackName?: string | null;
    theme?: 'light' | 'dark';
    /** 传了就多一个按钮（本地图表用：`＋ 数据文件夹`） */
    addLabel?: string;
}

const STYLE_ID = 'pylightcharts-symbolsearch-style';

const CSS = `
.pylc-ss-mask{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:11500;
  display:flex;align-items:flex-start;justify-content:center;padding-top:12vh}
.pylc-ss{width:520px;max-height:60vh;display:flex;flex-direction:column;
  border-radius:10px;overflow:hidden;background:var(--ss-bg);color:var(--ss-text);
  border:1px solid var(--ss-border);box-shadow:0 18px 48px rgba(0,0,0,.45)}
.pylc-ss-head{display:flex;align-items:center;gap:8px;padding:8px 10px;
  border-bottom:1px solid var(--ss-border)}
.pylc-ss-input{flex:1;height:28px;padding:0 10px;border-radius:6px;outline:none;
  border:1px solid var(--ss-border);background:var(--ss-input);color:var(--ss-text);
  font-size:13px}
.pylc-ss-input:focus{border-color:var(--ss-accent)}
.pylc-ss-close{border:none;background:transparent;color:var(--ss-text);
  cursor:pointer;font-size:15px}
.pylc-ss-add{height:26px;padding:0 9px;border-radius:6px;cursor:pointer;
  border:1px solid var(--ss-border);background:transparent;color:var(--ss-text);
  font-size:12px;white-space:nowrap}
.pylc-ss-add:hover{background:var(--ss-hover)}
.pylc-ss-chips{display:flex;flex-wrap:wrap;gap:6px;padding:6px 10px;
  border-bottom:1px solid var(--ss-border)}
.pylc-ss-chips:empty{display:none}
.pylc-ss-chip{padding:2px 11px;border-radius:999px;cursor:pointer;
  border:1px solid var(--ss-border);background:transparent;color:var(--ss-muted);
  font-size:12px;line-height:1.6}
.pylc-ss-chip:hover{background:var(--ss-hover)}
.pylc-ss-chip.on{background:var(--ss-accent);border-color:var(--ss-accent);
  color:#fff;font-weight:600}
.pylc-ss-list{flex:1;min-height:0;overflow:auto;padding:4px 0}
.pylc-ss-item{display:grid;grid-template-columns:auto 1.4fr auto auto;gap:10px;
  align-items:center;padding:6px 12px;font-size:12.5px;cursor:pointer;
  white-space:nowrap}
.pylc-ss-badge{width:20px;height:20px;border-radius:50%;display:flex;
  align-items:center;justify-content:center;color:#fff;font-size:11px;
  font-weight:700;text-transform:uppercase}
.pylc-ss-item .sym{font-weight:600;display:block}
.pylc-ss-item .nm{color:var(--ss-muted);font-size:11.5px;display:block}
.pylc-ss-item .meta{color:var(--ss-muted);font-size:11.5px}
.pylc-ss-item:hover,.pylc-ss-item.on{background:var(--ss-hover)}
.pylc-ss-empty{padding:14px 12px;color:var(--ss-muted);font-size:12px}
.pylc-ss-foot{padding:4px 12px;border-top:1px solid var(--ss-border);
  color:var(--ss-muted);font-size:11px}
`;

const PALS = {
    dark: {
        bg: '#161a20', text: '#d8d9db', muted: '#8b93a1',
        border: '#262c36', input: '#0f1115', hover: '#1e242d',
        accent: '#2962ff',
    },
    light: {
        bg: '#ffffff', text: '#1f2329', muted: '#6b7280',
        border: '#e3e6ea', input: '#f6f7f9', hover: '#eef1f5',
        accent: '#1a73e8',
    },
};

export class SymbolSearch {
    public readonly element: HTMLDivElement;
    public callbackName: string | null = null;
    /** 直接回调（同页应用用，不走 bridge ✓） */
    public onQueryCallback: ((text: string) => void) | null = null;
    public onPickCallback: ((item: SearchItem) => void) | null = null;
    /** 市场 chips 变了（`''` = 全部 ✓） */
    public onMarketCallback: ((market: string) => void) | null = null;
    /** 顶部「添加…」按钮（本地图表：添加数据文件夹 ✓） */
    public onAddCallback: (() => void) | null = null;

    private readonly input: HTMLInputElement;
    private readonly list: HTMLDivElement;
    private items: SearchItem[] = [];
    /** 市场 chips / 当前选择 ✓ */
    private markets: SearchMarket[] = [];
    private market = '';
    private chips: HTMLDivElement | null = null;
    private foot: HTMLDivElement | null = null;
    private results: SearchItem[] = [];
    private active = 0;
    private timer: number | undefined;
    private readonly limit: number;
    private readonly remote: boolean;

    constructor(options: SymbolSearchOptions = {},
                parent?: HTMLElement | null) {
        ensureStyle(STYLE_ID, CSS);
        this.callbackName = options.callbackName || null;
        this.items = options.items || [];
        this.results = this.items.slice();
        this.limit = options.limit || 200;
        this.remote = options.remote ?? !options.items;

        this.element = document.createElement('div');
        this.element.className = 'pylc-ss-mask';
        this.element.style.display = 'none';

        const box = document.createElement('div');
        box.className = 'pylc-ss';
        if (options.width) box.style.width = `${options.width}px`;

        const head = document.createElement('div');
        head.className = 'pylc-ss-head';
        this.input = document.createElement('input');
        this.input.className = 'pylc-ss-input';
        this.input.placeholder = options.placeholder
            || '商品代码、名称（全市场：期货 / 股票 / 期权…）';
        this.input.title = '输入代码或名称，回车选中第一项，Esc 关闭';
        const close = document.createElement('button');
        close.className = 'pylc-ss-close';
        close.textContent = '✕';
        close.title = '关闭';
        close.addEventListener('click', () => this.close());
        if (options.addLabel) {
            const add = document.createElement('button');
            add.className = 'pylc-ss-add';
            add.textContent = options.addLabel;
            add.title = '添加数据文件夹（该目录下所有 CSV）';
            add.addEventListener('click', () => this.onAddCallback?.());
            head.append(this.input, add, close);
        } else {
            head.append(this.input, close);
        }

        this.chips = document.createElement('div');
        this.chips.className = 'pylc-ss-chips';

        this.markets = options.markets || [];
        this.market = options.market || '';
        this.list = document.createElement('div');
        this.list.className = 'pylc-ss-list';
        const foot = document.createElement('div');
        foot.className = 'pylc-ss-foot';
        foot.textContent = '↑↓ 选择 · Enter 打开 · Esc 关闭';
        this.foot = foot;

        box.append(head, this.chips, this.list, foot);
        this.element.appendChild(box);
        this.element.addEventListener('mousedown', (event) => {
            if (event.target === this.element) this.close();
        });
        (parent ?? document.body).appendChild(this.element);

        this.input.addEventListener('input', () => this._schedule());
        this.input.addEventListener('keydown', (event) => this._onKey(event));
        this.setTheme(options.theme === 'light' ? 'light' : 'dark');
        this.setItems(this.items);
    }

    // ------------------------------------------------------------- 数据
    setItems(items: SearchItem[]): void {
        this.items = items || [];
        this._filter(this.input.value);
    }

    /** 后端返回的搜索结果（远程模式 ✓） */
    /** 底部小字（`正在建立全市场索引…` / `共 16305 个合约` ✓） */
    setHint(text: string): void {
        if (this.foot) {
            this.foot.textContent = text
                || '↑↓ 选择 · Enter 打开 · Esc 关闭';
        }
    }

    /** 市场 chips（后端 `symbol_search` 补丁带过来的 ✓） */
    setMarkets(markets: SearchMarket[], market = ''): void {
        this.markets = Array.isArray(markets) ? markets : [];
        if (market) this.market = String(market);
        this._renderChips();
    }

    setMarket(market: string): void {
        this.market = String(market || '');
        this._renderChips();
    }

    private _renderChips(): void {
        if (!this.chips) return;
        this.chips.textContent = '';
        if (!this.markets.length) {
            this.chips.style.display = 'none';
            return;
        }
        this.chips.style.display = '';
        for (const item of this.markets) {
            const chip = document.createElement('button');
            chip.className = 'pylc-ss-chip'
                + (item.key === this.market ? ' on' : '');
            chip.textContent = item.label;
            chip.addEventListener('mousedown', (event) => {
                event.preventDefault();
                this.setMarket(item.key);
                this.onMarketCallback?.(item.key);
            });
            this.chips.appendChild(chip);
        }
    }

    setResults(items: SearchItem[]): void {
        this.results = (items || []).slice(0, this.limit);
        this.active = 0;
        this._render();
    }

    open(symbol = ''): void {
        this._renderChips();
        this.element.style.display = '';
        this.input.value = symbol;
        if (this.remote) {
            // 远程模式：立刻查一次（后端用 setResults 回填 ✓）
            this.results = [];
            this.active = 0;
            this._render();
            emitCallback(this.callbackName, `query;;;${symbol.trim()}`);
            this.onQueryCallback?.(symbol.trim());
        } else {
            this._filter(symbol);
        }
        this.input.focus();
        this.input.select();
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
            this.element.style.setProperty(`--ss-${key}`, value);
        }
    }

    destroy(): void {
        this.element.remove();
    }

    // ------------------------------------------------------------- 内部
    private _schedule(): void {
        if (this.timer !== undefined) window.clearTimeout(this.timer);
        this.timer = window.setTimeout(() => {
            const text = this.input.value.trim();
            if (this.remote) {
                emitCallback(this.callbackName, `query;;;${text}`);
                this.onQueryCallback?.(text);
                if (!text) this.setResults([]);
            } else {
                this._filter(text);
            }
        }, 150);
    }

    private _filter(text: string): void {
        const needle = text.trim().toLowerCase();
        if (!needle) {
            this.results = this.items.slice(0, this.limit);
        } else {
            this.results = this.items.filter((item) =>
                item.symbol.toLowerCase().includes(needle)
                || (item.name || '').toLowerCase().includes(needle))
                .slice(0, this.limit);
        }
        this.active = 0;
        this._render();
    }

    private _render(): void {
        this.list.textContent = '';
        if (!this.results.length) {
            const empty = document.createElement('div');
            empty.className = 'pylc-ss-empty';
            empty.textContent = this.input.value
                ? '没有匹配的合约（换个关键字试试）'
                : '（输入代码或名称开始搜索）';
            this.list.appendChild(empty);
            return;
        }
        this.results.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = 'pylc-ss-item' + (index === this.active ? ' on' : '');
            const badge = document.createElement('span');
            badge.className = 'pylc-ss-badge';
            badge.style.background = badgeColor(item.symbol);
            badge.textContent = (item.symbol.split('.').pop() || '?')
                .slice(0, 1);
            const main = document.createElement('span');
            main.innerHTML = `<span class="sym">${escapeHtml(item.symbol)}</span>`
                + (item.name
                    ? `<span class="nm">${escapeHtml(item.name)}</span>` : '');
            const exchange = document.createElement('span');
            exchange.className = 'meta';
            exchange.textContent = item.exchange || '';
            const kind = document.createElement('span');
            kind.className = 'meta';
            kind.textContent = item.type_label || item.type || '';
            row.append(badge, main, exchange, kind);
            row.addEventListener('mousedown', (event) => {
                event.preventDefault();
                this._pick(item);
            });
            this.list.appendChild(row);
        });
    }

    private _onKey(event: KeyboardEvent): void {
        if (event.key === 'Escape') {
            this.close();
            return;
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            if (!this.results.length) return;
            const step = event.key === 'ArrowDown' ? 1 : -1;
            this.active = (this.active + step + this.results.length)
                % this.results.length;
            this._render();
            const node = this.list.children[this.active] as HTMLElement | undefined;
            node?.scrollIntoView({ block: 'nearest' });
            return;
        }
        if (event.key === 'Enter') {
            const item = this.results[this.active];
            if (item) this._pick(item);
        }
    }

    private _pick(item: SearchItem): void {
        emitCallback(this.callbackName, `pick;;;${item.symbol}`);
        this.onPickCallback?.(item);
        this.close();
    }
}


/** 首字母圆角色块（miniqt 那个彩色圆 ✓）—— 按代码哈希取色，稳定不闪 */
const BADGE_COLORS = ['#9c27b0', '#2196f3', '#8d6e63', '#26a69a', '#e91e63',
                      '#7e57c2', '#42a5f5', '#ef5350', '#ffa726', '#66bb6a'];

function badgeColor(symbol: string): string {
    let hash = 0;
    for (let i = 0; i < symbol.length; i += 1) {
        hash = (hash * 31 + symbol.charCodeAt(i)) % 9973;
    }
    return BADGE_COLORS[hash % BADGE_COLORS.length];
}

function escapeHtml(text: string): string {
    return String(text).replace(/[&<>"]/g, (char) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]
        || char));
}

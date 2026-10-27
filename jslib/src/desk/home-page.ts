/**
 * HomePage — minibt desk 的初始首页（方案 B：专业工作台）。
 *
 * 设计原则：
 *   - 首页只做「账户 / 市场 / 自选 / 信号 / 最近打开」的聚合，不复制报价表；
 *   - 行情报价按需打开（顶栏「＋ 新建」或首页按钮），不在启动时拉全市场；
 *   - 期货优先（天勤更稳定）；只有股票时自动切到股票数据；
 *   - 最近打开 / 收藏 / 自定义分组存在 localStorage，不依赖后端。
 */
import type { DeskTheme } from './theme';

export interface HomeMarkets {
    futures: boolean;
    stocks: boolean;
    offline: boolean;
    no_service?: boolean;
}

export interface HomeRow {
    symbol: string;
    name?: string;
    last?: number | null;
    chg?: number | null;
    chg_pct?: number | null;
    volume?: number | null;
    open?: number | null;
    high?: number | null;
    low?: number | null;
    decimals?: number | null;
    spark?: number[] | null;
    quote_time?: string;
}

export interface HomeSignal {
    tone: 'blue' | 'amber' | 'violet' | 'red';
    badge: string;
    symbol: string;
    name?: string;
    text: string;
    meta?: string;
    time?: string;
}

export interface HomeEvent {
    time: string;
    text: string;
    tail?: string;
    tone?: 'amber' | 'blue';
}

export interface HomeAccountChoice {
    kind: 'futures' | 'stocks';
    label: string;
    available: boolean;
}

export interface HomeAccount {
    kind?: string;
    label?: string;
    labels?: string[];
    index?: number;
    choices?: HomeAccountChoice[];
    values?: Record<string, number | null | undefined>;
    empty?: boolean;
}

export interface HomePayload {
    markets?: HomeMarkets;
    indices?: HomeRow[];
    watchlist?: HomeRow[];
    rows?: HomeRow[];
    signals?: HomeSignal[];
    events?: HomeEvent[];
    account?: HomeAccount;
    empty?: boolean;
}

interface HomeGroup {
    id: string;
    label: string;
    kind: 'recent' | 'favorites' | 'all' | 'filter' | 'custom' | 'main';
    /** `kind='main'` 时对应的交易所（`CFFEX` / `SHFE` …） */
    exchange?: string;
    symbols?: string[];
    prefixes?: string[];
}

interface RecentItem {
    symbol: string;
    name?: string;
    kind: 'chart' | 'local' | 'replay';
    at?: number;
}

export interface HomePageOptions {
    theme: DeskTheme;
    markets: HomeMarkets;
    onCommand: (cmd: string, payload?: Record<string, unknown>) => void;
    onOpenQuote: () => void;
    onOpenLocal: (name?: string) => void;
    onOpenChart: (symbol: string, name?: string) => void;
    onNew: () => void;
    /** 点「主力行情」某交易所 → 让后端取该交易所的主力合约 ✓ */
    onMainRows?: (exchange: string) => void;
    /** 左键选中自选行 / 切周期 → 让后端取该合约的 K 线（带周期 ✓） */
    onPreviewBars?: (symbol: string, cycle: number) => void;
    /** 左下角「数据源」点一下 → 打开对应登录框（离线也能接入服务 ✓） */
    onLogin?: (kind: 'futures' | 'stocks') => void;
    onToast: (level: string, text: string) => void;
    /** 设置 → 个性化：首页默认自选分组（recent / all / favorites） */
    defaultGroup?: string;
    /** Home 左侧三个真正的工作区页面 ✓ */
    onOpenWorkspace?: () => void;
    onOpenReplayLab?: () => void;
    onOpenAlerts?: () => void;
}

import { showMenuBelow } from './menu';
import {
    createGroup as storeCreateGroup, customGroups,
    favorites as storeFavorites, pinnedSymbols, saveGroupSymbols,
    toggleFavorite as storeToggleFavorite, WATCH_EVENT,
} from './watch-store';

//: 迷你图可选周期（和行情报价右键「周期」一致 ✓）
const PREVIEW_CYCLES: Array<{ cycle: number; label: string }> = [
    { cycle: 60, label: '1分' },
    { cycle: 300, label: '5分' },
    { cycle: 900, label: '15分' },
    { cycle: 1800, label: '30分' },
    { cycle: 3600, label: '1时' },
    { cycle: 86400, label: '1天' },
];

//: 「主力行情」快速入口（4 个交易所 ✓）
const MAIN_EXCHANGES: Array<{ exchange: string; label: string }> = [
    { exchange: 'CFFEX', label: '中金所' },
    { exchange: 'SHFE', label: '上期所' },
    { exchange: 'DCE', label: '大商所' },
    { exchange: 'CZCE', label: '郑商所' },
];

const RECENT_KEY = 'minibt.desk.home.recent';
const FAVORITES_KEY = 'minibt.desk.home.favorites';
const GROUPS_KEY = 'minibt.desk.home.groups';
const MAX_RECENT = 8;

const FUTURES_PREFIXES = ['RB', 'I', 'JM', 'J', 'HC', 'SS', 'SF', 'SM'];
const METAL_PREFIXES = ['CU', 'AL', 'ZN', 'NI', 'AU', 'AG', 'SN', 'PB'];
const INDEX_PREFIXES = ['IF', 'IM', 'IH', 'IC', 'T', 'TF', 'TS'];
const ENERGY_PREFIXES = ['SC', 'MA', 'TA', 'PP', 'L', 'V', 'EG', 'RU'];

function esc(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch] || ch));
}

function num(value: unknown): number | null {
    const parsed = Number(value);
    return value === null || value === undefined || value === ''
        || !Number.isFinite(parsed) ? null : parsed;
}

function decimalsOf(row: HomeRow): number {
    const value = Number(row.decimals);
    return Number.isFinite(value) ? Math.max(0, Math.min(6, value)) : 2;
}

function money(value: unknown, digits = 2): string {
    const parsed = num(value);
    if (parsed === null) return '--';
    return parsed.toLocaleString('zh-CN', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

function compact(value: unknown): string {
    const parsed = num(value);
    if (parsed === null) return '--';
    const abs = Math.abs(parsed);
    if (abs >= 1e8) return `${(parsed / 1e8).toFixed(2)}亿`;
    if (abs >= 1e4) return `${(parsed / 1e4).toFixed(2)}万`;
    return String(Math.round(parsed));
}

function pct(value: unknown): string {
    const parsed = num(value);
    if (parsed === null) return '--';
    return `${parsed >= 0 ? '+' : ''}${parsed.toFixed(2)}%`;
}

function signClass(value: unknown): string {
    const parsed = num(value);
    if (parsed === null || parsed === 0) return 'muted';
    return parsed > 0 ? 'up' : 'down';
}

/** 行情列的价格（按合约 decimals，缺数据 `--` ✓） */
function cellPrice(row: HomeRow, key: string): string {
    const value = num((row as unknown as Record<string, unknown>)[key]);
    return value === null ? '--' : money(value, decimalsOf(row));
}

/** 行情列的数量（买一量 / 卖一量，整数 ✓） */
function cellQty(row: HomeRow, key: string): string {
    const value = num((row as unknown as Record<string, unknown>)[key]);
    return value === null ? '--' : String(Math.round(value));
}

function price(row: HomeRow): string {
    return money(row.last, decimalsOf(row));
}

function codeOf(symbol: string): string {
    const text = String(symbol || '');
    const bare = text.includes('.') ? text.split('.').pop() || text : text;
    return bare.toUpperCase();
}

function sparkPath(values: number[] | null | undefined, width = 150,
                   height = 24): string {
    const list = (values || []).map(Number).filter(Number.isFinite);
    if (list.length < 2) return '';
    const min = Math.min(...list);
    const max = Math.max(...list);
    const span = max - min || 1;
    const pad = 2;
    return list.map((value, index) => {
        const x = pad + index * (width - pad * 2) / (list.length - 1);
        const y = height - pad - (value - min) / span * (height - pad * 2);
        return `${index ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(' ');
}

function sparkSvg(values: number[] | null | undefined, color: string,
                  width = 150, height = 24): string {
    const path = sparkPath(values, width, height);
    if (!path) return '<svg class="desk-home-spark" viewBox="0 0 150 24"></svg>';
    return `<svg class="desk-home-spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
        <path d="${path}" fill="none" stroke="${color}" stroke-width="1.5"
              stroke-linecap="round" stroke-linejoin="round"
              vector-effect="non-scaling-stroke"/></svg>`;
}

export interface PreviewBar {
    time?: number;
    open?: number;
    high?: number;
    low?: number;
    close?: number;
}

/** 迷你 **K 线**（首页下方那张图；用户要求把折线换成蜡烛 ✓） */
function candleSvg(bars: PreviewBar[] | null | undefined,
                   width = 600, height = 130): string {
    const list = (bars || []).filter((bar) => Number.isFinite(Number(bar.close)));
    if (list.length < 2) {
        return `<svg class="desk-home-preview-chart-svg" viewBox="0 0 ${width} ${height}"></svg>`;
    }
    const highs = list.map((bar) => Number(bar.high ?? bar.close));
    const lows = list.map((bar) => Number(bar.low ?? bar.close));
    const max = Math.max(...highs);
    const min = Math.min(...lows);
    const span = max - min || Math.abs(max) * 0.001 || 1;
    const pad = 6;
    const inner = height - pad * 2;
    const step = width / list.length;
    const body = Math.max(1.2, step * 0.62);
    const y = (value: number) => pad + (max - value) / span * inner;
    const parts: string[] = [];
    list.forEach((bar, index) => {
        const open = Number(bar.open ?? bar.close);
        const close = Number(bar.close);
        const high = Number(bar.high ?? Math.max(open, close));
        const low = Number(bar.low ?? Math.min(open, close));
        const up = close >= open;
        const color = up ? 'var(--desk-up)' : 'var(--desk-down)';
        const cx = step * index + step / 2;
        parts.push(`<line x1="${cx.toFixed(1)}" y1="${y(high).toFixed(1)}"
            x2="${cx.toFixed(1)}" y2="${y(low).toFixed(1)}"
            stroke="${color}" stroke-width="1"/>`);
        const top = Math.min(y(open), y(close));
        const bh = Math.max(1, Math.abs(y(open) - y(close)));
        parts.push(`<rect x="${(cx - body / 2).toFixed(1)}"
            y="${top.toFixed(1)}" width="${body.toFixed(1)}"
            height="${bh.toFixed(1)}" fill="${color}"/>`);
    });
    return `<svg class="desk-home-preview-chart-svg"
        viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"
        aria-hidden="true">${parts.join('')}</svg>`;
}

function areaSvg(values: number[] | null | undefined, color: string): string {
    const list = (values || []).map(Number).filter(Number.isFinite);
    if (list.length < 2) {
        return '<svg class="desk-home-account-chart" viewBox="0 0 280 62"></svg>';
    }
    const width = 280;
    const height = 62;
    const min = Math.min(...list);
    const max = Math.max(...list);
    const span = max - min || 1;
    const pad = 4;
    const pts = list.map((value, index) => {
        const x = pad + index * (width - pad * 2) / (list.length - 1);
        const y = height - pad - (value - min) / span * (height - pad * 2);
        return { x, y };
    });
    let line = `M${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
    for (let index = 1; index < pts.length; index += 1) {
        const previous = pts[index - 1];
        const point = pts[index];
        const mid = (previous.x + point.x) / 2;
        line += ` C${mid.toFixed(1)} ${previous.y.toFixed(1)},`
            + `${mid.toFixed(1)} ${point.y.toFixed(1)},`
            + `${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
    }
    const area = `${line} L${pts[pts.length - 1].x.toFixed(1)} ${height}`
        + ` L${pts[0].x.toFixed(1)} ${height} Z`;
    return `<svg class="desk-home-account-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="desk-home-acct-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${color}" stop-opacity=".28"/>
            <stop offset="1" stop-color="${color}" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${area}" fill="url(#desk-home-acct-grad)" stroke="none"/>
        <path d="${line}" fill="none" stroke="${color}" stroke-width="1.8"
              stroke-linecap="round" stroke-linejoin="round"
              vector-effect="non-scaling-stroke"/>
        <circle cx="${pts[pts.length - 1].x.toFixed(1)}" cy="${pts[pts.length - 1].y.toFixed(1)}"
                r="3" fill="${color}" stroke="var(--desk-panel)" stroke-width="2"/>
    </svg>`;
}

function readJson<T>(key: string, fallback: T): T {
    try {
        const text = window.localStorage.getItem(key);
        return text ? JSON.parse(text) as T : fallback;
    } catch {
        return fallback;
    }
}

function writeJson(key: string, value: unknown): void {
    try {
        window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
        /* 隐私模式忽略 */
    }
}

export class HomePage {
    public readonly element: HTMLDivElement;

    private readonly options: HomePageOptions;
    private markets: HomeMarkets;
    private theme: DeskTheme;
    private rowMap = new Map<string, HomeRow>();
    private indexRows: HomeRow[] = [];
    private watchRows: HomeRow[] = [];
    private signals: HomeSignal[] = [];
    private events: HomeEvent[] = [];
    private account: HomeAccount | null = null;
    private equity: number[] = [];
    private activeGroup = 'all';
    private recent: RecentItem[] = [];
    private favorites: string[] = [];
    private groups: HomeGroup[] = [];
    private customGroups: HomeGroup[] = [];

    constructor(options: HomePageOptions) {
        this.options = options;
        this.markets = options.markets;
        this.theme = options.theme;
        const recent = readJson<RecentItem[]>(RECENT_KEY, []);
        const favorites = readJson<string[]>(FAVORITES_KEY, []);
        const groups = readJson<HomeGroup[]>(GROUPS_KEY, []);
        this.recent = (Array.isArray(recent) ? recent : []).slice(0, MAX_RECENT);
        this.favorites = Array.isArray(favorites) ? favorites : [];
        this.customGroups = Array.isArray(groups) ? groups : [];
        this.groups = this._buildGroups();
        const preferred = String(options.defaultGroup || '');
        this.activeGroup = this.groups.some((group) => group.id === preferred)
            ? preferred : (this.recent.length ? 'recent' : 'all');
        try {
            // 记住上次的 K 线开关（默认开 ✓）
            this.klineOn = window.localStorage.getItem(
                'minibt.desk.home.kline') !== '0';
        } catch {
            this.klineOn = true;
        }

        this.element = document.createElement('div');
        this.element.className = `desk-home theme-${this.theme}`;
        this.element.innerHTML = this._template();
        this._bind();
        // ★ 双击自选行 = 打开合约标的（左键只是气泡 ✓）
        this.element.addEventListener('dblclick', (event) => {
            const row = (event.target as HTMLElement)
                .closest<HTMLElement>('[data-watch-row]');
            if (!row) return;
            this.options.onOpenChart(row.dataset.openSymbol || '',
                                     row.dataset.openName || '');
        });
        // ★ 首页禁用浏览器默认右键菜单（用户要求 ✓）
        this.element.addEventListener('contextmenu', (event) => {
            event.preventDefault();
        });
        // ★ 行情报价改了收藏 / 分组 → 这里重画（同一份 localStorage ✓）
        window.addEventListener(WATCH_EVENT, () => this.refreshWatch());
        this.render();
    }

    // ------------------------------------------------------------- lifecycle
    /** 设置变化：切到新的默认自选分组（下一帧生效 ✓） */
    setDefaultGroup(group: string): void {
        const wanted = String(group || '');
        if (!this.groups.some((item) => item.id === wanted)) return;
        this.activeGroup = wanted;
        this.render();
    }

    show(): void { this.element.style.display = 'block'; }

    hide(): void { this.element.style.display = 'none'; }

    applyTheme(theme: DeskTheme): void {
        this.theme = theme;
        this.element.classList.toggle('theme-light', theme === 'light');
        this.element.classList.toggle('theme-dark', theme !== 'light');
        this.renderAccount();
    }

    setMarkets(markets: HomeMarkets): void {
        this.markets = { ...this.markets, ...markets };
        this.renderSidebar();
    }

    setPayload(payload: HomePayload): void {
        if (payload.markets) this.setMarkets(payload.markets);
        if (payload.indices) this.indexRows = payload.indices;
        if (payload.watchlist) this.watchRows = payload.watchlist;
        this._mergeRows([
            ...(payload.indices || []),
            ...(payload.watchlist || []),
            ...(payload.rows || []),
        ]);
        if (payload.signals) this.signals = payload.signals;
        if (payload.events) this.events = payload.events;
        if (payload.account) this.setAccount(payload.account);
        this.render();
    }

    setUpdate(payload: HomePayload): void {
        if (payload.indices) this.indexRows = payload.indices;
        if (payload.watchlist) this.watchRows = payload.watchlist;
        // ★ 指数 / 自选也要进 rowMap：下方迷你图读的是 rowMap（否则不更新 ✗）
        this._mergeRows([
            ...(payload.indices || []),
            ...(payload.watchlist || []),
            ...(payload.rows || []),
        ]);
        if (payload.signals) this.signals = payload.signals;
        if (payload.account) this.setAccount(payload.account);
        this.renderIndices();
        this.renderWatch();
        this.renderSignals();
        this.renderAccount();
        this.renderSidebar();
        this.renderPreview();
        this.renderQuickStats();
    }

    setAccount(account: HomeAccount): void {
        this.account = account;
        const balance = num(account.values?.balance);
        if (balance !== null) {
            const history = this.equity;
            if (!history.length || history[history.length - 1] !== balance) {
                history.push(balance);
                if (history.length > 80) history.shift();
            }
        }
        this.renderAccount();
        this.renderSidebar();
    }

    recordRecent(symbol: string, name = '',
                 kind: 'chart' | 'local' | 'replay' = 'chart'): void {
        if (!symbol) return;
        this.recent = [
            { symbol, name, kind, at: Date.now() },
            ...this.recent.filter((item) => item.symbol !== symbol),
        ].slice(0, MAX_RECENT);
        writeJson(RECENT_KEY, this.recent);
        this.renderGroups();
        this.renderWatch();
        this.renderRecent();
    }

    // --------------------------------------------------------------- template
    private _template(): string {
        return `
<div class="desk-home-shell">
    <aside class="desk-home-side">
        <div class="desk-home-side-label">工作区</div>
        <nav class="desk-home-nav">
            <button class="desk-home-nav-item on" data-nav="home">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="3" width="7" height="7" rx="1.2"/><rect x="14" y="3" width="7" height="7" rx="1.2"/><rect x="3" y="14" width="7" height="7" rx="1.2"/><rect x="14" y="14" width="7" height="7" rx="1.2"/></svg>
                首页
            </button>
            <button class="desk-home-nav-item" data-nav="watch">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 5h16M4 12h16M4 19h10"/><circle cx="19" cy="19" r="2.2"/></svg>
                自选行情 <span class="tail" data-count="watch">0</span>
            </button>
            <button class="desk-home-nav-item" data-nav="quote">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="4" width="18" height="16" rx="1.6"/><path d="M3 9h18M9 9v11M15 9v11"/></svg>
                行情报价
            </button>
            <button class="desk-home-nav-item" data-nav="workspace">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 4-6"/></svg>
                图表工作台
            </button>
            <button class="desk-home-nav-item" data-nav="replay">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 4v16"/><path d="m4 4 7 4-7 4"/><path d="m11 4 7 4-7 4"/></svg>
                回放实验室
            </button>
            <button class="desk-home-nav-item" data-nav="alerts">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M18 15V10a6 6 0 1 0-12 0v5l-1.6 2.4h15.2L18 15z"/><path d="M10 19a2 2 0 0 0 4 0"/></svg>
                预警中心
            </button>
        </nav>
        <div class="desk-home-side-gap"></div>
        <div class="desk-home-side-label">自选分组 <button class="desk-home-side-add" data-group-add title="新建分组">＋</button></div>
        <div class="desk-home-groups" data-groups></div>
        <div class="desk-home-side-gap"></div>
        <div class="desk-home-side-label">主力行情</div>
        <div class="desk-home-main-list" data-main-list></div>
        <div class="desk-home-side-bottom">
            <button class="desk-home-new-page" data-act="new"><span>＋</span> 新建页面</button>
            <div class="desk-home-source">
                <div class="desk-home-source-title">数据源 <span data-source-count>0</span></div>
                <div data-sources></div>
            </div>
            <div class="desk-home-side-account" data-side-account></div>
        </div>
    </aside>

    <main class="desk-home-center">
        <header class="desk-home-head">
            <div>
                <div class="desk-home-breadcrumb">首页 <b>/ 今日概览</b></div>
                <h2>市场全景</h2>
                <div class="desk-home-date" data-date>--</div>
            </div>
            <div class="desk-home-head-actions">
                <button class="desk-btn desk-btn-ghost" data-act="refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>
                    刷新
                </button>
                <button class="desk-btn desk-btn-primary" data-act="quote"><span class="plus">＋</span> 打开行情报价</button>
            </div>
        </header>
        <div class="desk-home-indices" data-indices></div>
        <section class="desk-home-card desk-home-watch">
            <div class="desk-home-card-head">
                <div><div class="desk-home-card-title" data-watch-title>自选行情</div><div class="desk-home-card-sub" data-watch-sub>--</div></div>
                <div class="desk-home-card-actions">
                    <span class="desk-home-chip" data-watch-chip>全部</span>
                    <button class="desk-btn desk-btn-ghost desk-btn-sm" data-act="manage">管理</button>
                </div>
            </div>
            <div class="desk-home-table" data-watch-table></div>
        </section>
        <div class="desk-home-bottom">
            <section class="desk-home-card desk-home-preview" data-preview></section>
            <section class="desk-home-card desk-home-recent" data-recent></section>
        </div>
    </main>

    <aside class="desk-home-right">
        <section class="desk-home-card desk-home-account" data-account></section>
        <section class="desk-home-card desk-home-signals" data-signals></section>
        <section class="desk-home-card desk-home-quick">
            <div class="desk-home-quick-title">快捷入口</div>
            <div class="desk-home-quick-grid">
                <button class="desk-home-quick-item primary" data-act="quote"><span class="row"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="3" width="7" height="7" rx="1.2"/><rect x="14" y="3" width="7" height="7" rx="1.2"/><rect x="3" y="14" width="7" height="7" rx="1.2"/><rect x="14" y="14" width="7" height="7" rx="1.2"/></svg>行情报价</span><span class="sub">全市场</span></button>
                <button class="desk-home-quick-item" data-act="local"><span class="row"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/></svg>本地图表</span><span class="sub">CSV</span></button>
                <button class="desk-home-quick-item" data-act="workspace"><span class="row"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 4-6"/></svg>新建看盘</span><span class="sub">K 线 / 指标</span></button>
                <button class="desk-home-quick-item" data-act="replay"><span class="row"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 4v16"/><path d="m4 4 7 4-7 4"/><path d="m11 4 7 4-7 4"/></svg>回放今日</span><span class="sub">30% 起</span></button>
            </div>
            <div class="desk-home-quick-stats" data-quick-stats></div>
            <div class="desk-home-temp" data-temp></div>
            <div class="desk-home-quick-note"><span class="dot"></span><span data-market-note>等待行情连接…</span></div>
        </section>
    </aside>
</div>`;
    }

    private _bind(): void {
        this.element.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            const action = target.closest<HTMLElement>('[data-act]');
            if (action) {
                const name = action.dataset.act || '';
                if (name === 'preview-cycle') {
                    showMenuBelow(action, PREVIEW_CYCLES.map((item) => ({
                        label: `${item.label}${item.cycle === this.previewCycle
                            ? '  ✓' : ''}`,
                        run: () => {
                            this.previewCycle = item.cycle;
                            this.renderPreview();
                            const row = this._previewRow();
                            if (row) this._requestBars(row);
                        },
                    })));
                    return;
                }
                if (name === 'kline-toggle') {
                    this.klineOn = !this.klineOn;
                    try {
                        window.localStorage.setItem(
                            'minibt.desk.home.kline',
                            this.klineOn ? '1' : '0');
                    } catch {
                        /* ignore */
                    }
                    this.renderPreview();
                    return;
                }
                if (name === 'quote') this.options.onOpenQuote();
                else if (name === 'local') this.options.onOpenLocal();
                else if (name === 'new') this.options.onNew();
                else if (name === 'refresh') {
                    this.options.onCommand('home_refresh', {});
                } else if (name === 'manage') this._manageGroup();
                else if (name === 'workspace') this._openFirstChart();
                else if (name === 'replay') this.options.onOpenLocal();
                return;
            }
            const loginRow = target.closest<HTMLElement>('[data-login]');
            if (loginRow) {
                const kind = loginRow.dataset.login === 'stocks'
                    ? 'stocks' : 'futures';
                if (this.options.onLogin) this.options.onLogin(kind);
                else this.options.onToast('info', '登录入口未就绪');
                return;
            }
            const accountButton = target.closest<HTMLElement>(
                '[data-home-account]');
            if (accountButton) {
                const choices = this.account?.choices || [];
                showMenuBelow(accountButton, choices.map((choice) => ({
                    label: `${choice.label}${choice.kind === this.account?.kind
                        ? '  ✓' : ''}`,
                    disabled: !choice.available,
                    run: () => this.options.onCommand(
                        'home_account_kind', { kind: choice.kind }),
                })));
                return;
            }
            const nav = target.closest<HTMLElement>('[data-nav]');
            if (nav) {
                const name = nav.dataset.nav || '';
                if (name === 'watch') {
                    this.activeGroup = 'all';
                    this.renderGroups();
                    this.renderWatch();
                    this.element.querySelector('.desk-home-watch')
                        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                } else if (name === 'quote') this.options.onOpenQuote();
                else if (name === 'workspace') {
                    if (this.options.onOpenWorkspace) {
                        this.options.onOpenWorkspace();
                    } else this._openFirstChart();
                } else if (name === 'replay') {
                    if (this.options.onOpenReplayLab) {
                        this.options.onOpenReplayLab();
                    } else this.options.onOpenLocal();
                } else if (name === 'alerts') {
                    if (this.options.onOpenAlerts) {
                        this.options.onOpenAlerts();
                    } else this.options.onToast('info', '价格预警在图表工具栏里设置');
                }
                return;
            }
            const mainItem = target.closest<HTMLElement>('[data-main-exchange]');
            if (mainItem) {
                const exchange = mainItem.dataset.mainExchange || 'CFFEX';
                this.activeGroup = `main:${exchange}`;
                this.previewSymbol = '';
                this.renderGroups();
                this.renderMainList();
                this.renderWatch();
                this.renderPreview();
                if (!(this.mainRows[exchange] || []).length) {
                    this.options.onMainRows?.(exchange);     // 后端去取 ✓
                }
                return;
            }
            const group = target.closest<HTMLElement>('[data-group]');
            if (group) {
                this.activeGroup = group.dataset.group || 'all';
                this.previewSymbol = '';
                this.renderGroups();
                this.renderMainList();
                this.renderWatch();
                this.renderPreview();
                return;
            }
            if (target.closest('[data-group-add]')) {
                this._createGroup();
                return;
            }
            const fav = target.closest<HTMLElement>('[data-fav]');
            if (fav) {
                event.stopPropagation();
                const symbol = fav.dataset.fav || '';
                if (symbol) this._toggleFavorite(symbol);
                return;
            }
            const open = target.closest<HTMLElement>('[data-open-symbol]');
            if (open) {
                const symbol = open.dataset.openSymbol || '';
                const group = open.dataset.openGroup || 'chart';
                if (group === 'local') {
                    this.options.onOpenLocal(symbol);
                    return;
                }
                // ★ 自选行：左键 → **下面那张迷你图**显示该合约（用户要求 ✓）
                //   双击才是打开合约标的（见下面的 dblclick ✓）
                if (open.dataset.watchRow) {
                    this.previewSymbol = symbol;
                    // ★ 不要 `renderWatch()`：整表重建会让**双击失效**
                    //   （第一下就把节点换掉了 → 浏览器不再派发 dblclick ✗）
                    for (const node of Array.from(this.element
                        .querySelectorAll<HTMLElement>('[data-watch-row]'))) {
                        node.classList.toggle(
                            'on', node === open);
                    }
                    this.renderPreview();                   // 只重画下面那张图 ✓
                    this._requestBars();                    // K 线 / 折线都要数据 ✓
                    return;
                }
                this.options.onOpenChart(symbol, open.dataset.openName || '');
                return;
            }
            const openIndex = target.closest<HTMLElement>('[data-index-symbol]');
            if (openIndex) {
                this.options.onOpenChart(
                    openIndex.dataset.indexSymbol || '',
                    openIndex.dataset.indexName || '');
            }
        });
    }

    // ------------------------------------------------------------------ groups
    private _buildGroups(): HomeGroup[] {
        const defaults: HomeGroup[] = [
            { id: 'recent', label: '最近打开', kind: 'recent' },
            { id: 'favorites', label: '收藏', kind: 'favorites' },
            { id: 'all', label: '自选', kind: 'all' },
            { id: 'black', label: '黑色系', kind: 'filter', prefixes: FUTURES_PREFIXES },
            { id: 'metal', label: '有色金属', kind: 'filter', prefixes: METAL_PREFIXES },
            { id: 'index', label: '股指期货', kind: 'filter', prefixes: INDEX_PREFIXES },
            { id: 'energy', label: '能源化工', kind: 'filter', prefixes: ENERGY_PREFIXES },
        ];
        const mains: HomeGroup[] = MAIN_EXCHANGES.map((item) => ({
            id: `main:${item.exchange}`,
            label: `主力 · ${item.label}`,
            kind: 'main' as const,
            exchange: item.exchange,
        }));
        const custom = (this.customGroups || []).map((item) => ({
            ...item,
            kind: 'custom' as const,
            symbols: Array.isArray(item.symbols) ? item.symbols : [],
        }));
        return defaults.concat(mains).concat(custom);
    }

    private _currentGroup(): HomeGroup {
        return this.groups.find((item) => item.id === this.activeGroup)
            || this.groups[0];
    }

    private _groupRows(group: HomeGroup): HomeRow[] {
        if (group.kind === 'recent') {
            return this.recent.map((item) => this._rowOf(item.symbol, item.name));
        }
        if (group.kind === 'favorites') {
            return this.favorites.map((symbol) => this._rowOf(symbol));
        }
        if (group.kind === 'all') {
            // ★ 自选**只放用户自己加的**（右键「加入自选」→ pins.all ✓）
            //   后端默认清单不再塞进来（用户要求：除收藏 / 最近打开外都由用户添加 ✓）
            return pinnedSymbols('all').map((symbol) => this._rowOf(symbol));
        }
        if (group.kind === 'main') {
            return (this.mainRows[group.exchange || ''] || [])
                .map((row) => this._rowOf(String(row.symbol),
                                          String(row.name || '')));
        }
        if (group.kind === 'filter') {
            // ★ 黑色系 / 有色金属 / … 同样只放用户主动加进来的合约 ✓
            return pinnedSymbols(group.id).map((symbol) => this._rowOf(symbol));
        }
        return (group.symbols || []).map((symbol) => this._rowOf(symbol));
    }

    private _rowOf(symbol: string, name = ''): HomeRow {
        return this.rowMap.get(symbol) || { symbol, name: name || symbol };
    }

    private _createGroup(): void {
        const label = window.prompt('新建分组名称', '我的分组');
        if (!label || !label.trim()) return;
        const text = window.prompt(
            '输入分组里的合约代码（逗号分隔，可留空稍后添加）',
            this.watchRows.slice(0, 5).map((row) => row.symbol).join(', '));
        if (text === null) return;
        const symbols = text.split(/[,，\s]+/).map((item) => item.trim())
            .filter(Boolean);
        const group = storeCreateGroup(label.trim(), symbols);
        if (!group) return;
        this.customGroups = customGroups();
        this.groups = this._buildGroups();
        this.activeGroup = group.id;
        if (symbols.length) this.options.onCommand('home_symbols', { symbols });
        this.renderGroups();
        this.renderWatch();
    }

    private _manageGroup(): void {
        const group = this._currentGroup();
        if (group.kind === 'recent') {
            this.recent = [];
            writeJson(RECENT_KEY, this.recent);
            this.renderGroups();
            this.renderWatch();
            this.renderRecent();
            return;
        }
        if (group.kind === 'favorites') {
            for (const symbol of storeFavorites()) storeToggleFavorite(symbol);
            this.favorites = storeFavorites();
            this.renderGroups();
            this.renderWatch();
            return;
        }
        if (group.kind === 'all' || group.kind === 'filter') {
            this.options.onToast('info', '内置分组不能编辑；请用「＋」新建自定义分组');
            return;
        }
        const text = window.prompt(
            `编辑「${group.label}」的合约代码（逗号分隔）`,
            (group.symbols || []).join(', '));
        if (text === null) return;
        group.symbols = text.split(/[,，\s]+/).map((item) => item.trim())
            .filter(Boolean);
        saveGroupSymbols(group.id, group.symbols || []);
        this.customGroups = customGroups();
        if (group.symbols.length) {
            this.options.onCommand('home_symbols', { symbols: group.symbols });
        }
        this.renderWatch();
    }

    private _toggleFavorite(symbol: string): void {
        if (!symbol) return;
        storeToggleFavorite(symbol);
        this.favorites = storeFavorites();
        this.renderGroups();
        this.renderWatch();
    }

    /** 外部（行情报价 ★ / 右键「加入自选」）改了数据 → 重新读一遍 ✓ */
    refreshWatch(): void {
        this.favorites = storeFavorites();
        this.customGroups = customGroups();
        this.groups = this._buildGroups();
        this.renderGroups();
        this.renderWatch();
    }

    // ----------------------------------------------------------------- render
    private _mergeRows(rows: HomeRow[]): void {
        for (const row of rows || []) {
            if (!row || !row.symbol) continue;
            const old = this.rowMap.get(row.symbol) || {} as HomeRow;
            this.rowMap.set(row.symbol, { ...old, ...row });
        }
    }

    render(): void {
        this.renderSidebar();
        this.renderIndices();
        this.renderGroups();
        this.renderMainList();
        this.renderWatch();
        this.renderAccount();
        this.renderSignals();
        this.renderRecent();
        this.renderPreview();
        this.renderQuickStats();
        const date = new Date();
        const weekday = ['日', '一', '二', '三', '四', '五', '六'][date.getDay()];
        const text = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} 周${weekday} · ${date.toLocaleTimeString('zh-CN', { hour12: false })}`;
        const node = this.element.querySelector('[data-date]');
        if (node) node.textContent = `${text} · 延迟 0.5s`;
    }

    private renderSidebar(): void {
        const markets = this.markets;
        const sources = [
            { key: 'futures', label: '期货', value: 'TqSdk', on: !!markets.futures },
            { key: 'stocks', label: '股票', value: 'Futu', on: !!markets.stocks },
        ];
        const active = sources.filter((item) => item.on).length;
        const count = this.element.querySelector('[data-source-count]');
        if (count) count.textContent = String(active);
        const sourceHost = this.element.querySelector('[data-sources]');
        if (sourceHost) {
            // ★ 两行都**可点**：未连接 → 登录；已连接 → 重新登录 / 换网关 ✓
            sourceHost.innerHTML = sources.map((item) => `
                <button class="desk-home-source-row" data-login="${item.key}"
                        title="${item.on
        ? `${item.label}已连接 · 点击可重新登录`
        : `点击登录${item.label}（${item.key === 'stocks'
            ? '富途 OpenD 网关' : '天勤账号'}）`}">
                    <i style="background:${item.on ? 'var(--desk-down)' : 'var(--desk-muted)'}"></i>
                    <b>${item.label}</b><span>${item.value}</span>
                    <em>${item.on ? '已连接' : '未连接 · 点此登录'}</em>
                </button>`).join('');
        }
        const watchCount = this.element.querySelector('[data-count="watch"]');
        if (watchCount) watchCount.textContent = String(this.watchRows.length);
        const note = this.element.querySelector('[data-market-note]');
        if (note) {
            note.textContent = markets.futures && markets.stocks
                ? '期货 + 股票已连接 · 优先使用天勤数据'
                : (markets.futures ? '期货已连接 · 天勤模拟账户'
                    : (markets.stocks ? '股票已连接 · 富途行情'
                        : '未连接行情源 · 离线模式'));
        }
        const accountHost = this.element.querySelector('[data-side-account]');
        if (accountHost) {
            const values = this.account?.values || {};
            const label = this.account?.label
                || this.account?.labels?.[this.account?.index || 0]
                || (this.account?.kind === 'stock' ? '股票账户' : '天勤模拟账户');
            const balanceValue = num(values.balance) || 0;
            const profitPct = num(values.position_profit) !== null && balanceValue
                ? (Number(values.position_profit) / balanceValue * 100) : null;
            accountHost.innerHTML = `
                <div><div class="k">${esc(label)}</div>
                    <div class="v">${this.account ? `¥${money(values.balance, 2)}` : '--'}</div></div>
                <div class="pct ${signClass(profitPct)}">${profitPct === null ? '--' : pct(profitPct)}</div>`;
        }
    }

    /** 渲染「主力行情」4 个交易所入口（点击 → 中间表格显示该所主力 ✓） */
    private renderMainList(): void {
        const host = this.element.querySelector('[data-main-list]');
        if (!host) return;
        host.innerHTML = MAIN_EXCHANGES.map((item) => {
            const on = this.activeGroup === `main:${item.exchange}`;
            return `<button class="desk-home-main-item${on ? ' on' : ''}"
                data-main-exchange="${item.exchange}"
                title="显示${item.label}的主力合约">${item.label}</button>`;
        }).join('');
    }

    private renderGroups(): void {
        const host = this.element.querySelector('[data-groups]');
        if (!host) return;
        // ★ 主力分类不进「自选分组」列表（用户要求：只留下面的「主力行情」✓）
        host.innerHTML = this.groups.filter((group) => group.kind !== 'main')
            .map((group) => {
            let count = '';
            if (group.kind === 'recent') count = String(this.recent.length);
            else if (group.kind === 'favorites') count = String(this.favorites.length);
            else if (group.kind === 'custom') count = String((group.symbols || []).length);
            return `<button class="desk-home-group${group.id === this.activeGroup ? ' on' : ''}"
                data-group="${esc(group.id)}">
                <span class="dot"></span>${esc(group.label)}
                ${count ? `<em>${count}</em>` : ''}
            </button>`;
            }).join('');
    }

    private renderIndices(): void {
        const host = this.element.querySelector('[data-indices]');
        if (!host) return;
        const rows = this.indexRows.length ? this.indexRows : this.watchRows.slice(0, 4);
        host.innerHTML = rows.slice(0, 4).map((row) => {
            const color = num(row.chg_pct) !== null && Number(row.chg_pct) >= 0
                ? 'var(--desk-up)' : 'var(--desk-down)';
            return `<button class="desk-home-index" data-index-symbol="${esc(row.symbol)}"
                data-index-name="${esc(row.name || '')}">
                <div class="desk-home-index-text">
                    <div class="top"><span>${esc(row.name || row.symbol)}</span>
                        <em>${esc(codeOf(row.symbol))}</em></div>
                    <div class="val">${price(row)}</div>
                    <div class="pct ${signClass(row.chg_pct)}">${pct(row.chg_pct)}</div>
                </div>
                <div class="desk-home-index-spark">${sparkSvg(row.spark, color, 96, 44)}</div>
            </button>`;
        }).join('') || '<div class="desk-home-empty">暂无行情数据</div>';
    }

    private renderWatch(): void {
        const host = this.element.querySelector('[data-watch-table]');
        if (!host) return;
        const group = this._currentGroup();
        const rows = this._groupRows(group);
        const chip = this.element.querySelector('[data-watch-chip]');
        if (chip) chip.textContent = group.label;
        const title = this.element.querySelector('[data-watch-title]');
        if (title) {
            title.textContent = group.kind === 'main' ? '主力'
                : (group.kind === 'all' ? '自选行情' : group.label);
        }
        const sub = this.element.querySelector('[data-watch-sub]');
        if (sub) {
            sub.textContent = `${rows.length} 个合约 · ${group.label}`
                + (this.markets.futures && this.markets.stocks
                    ? ' · 优先天勤' : '');
        }
        if (!rows.length) {
            const hint = group.kind === 'recent'
                ? '还没有最近打开的记录；打开一个图表后会出现在这里。'
                : (group.kind === 'favorites'
                    ? '还没有收藏；点自选行右侧的星标即可收藏。'
                    : (group.kind === 'custom'
                        ? '这个分组还是空的；右键行情报价里的合约 →「加入自选」。'
                        : '还没有合约；在「行情报价」里右键合约 →「加入自选」'
                          + '（选「自选」或某个分组）'));
            host.innerHTML = `<div class="desk-home-empty">${hint}</div>`;
            return;
        }
        host.innerHTML = `<div class="desk-home-tr desk-home-th">
            <span>合约 / 名称</span><span>最新价</span>
            <span>买一价</span><span>买一量</span>
            <span>卖一价</span><span>卖一量</span>
            <span>涨跌</span><span>涨跌幅</span>
            <span>成交量</span><span>最小变动</span>
            <span>日内走势</span><span></span></div>`
            + rows.map((row) => {
                const fav = this.favorites.includes(row.symbol);
                const color = num(row.chg_pct) !== null && Number(row.chg_pct) >= 0
                    ? 'var(--desk-up)' : 'var(--desk-down)';
                const picked = row.symbol === this.previewSymbol;
                return `<div class="desk-home-tr desk-home-row${picked ? ' on' : ''}" data-watch-row="1" data-open-symbol="${esc(row.symbol)}" data-open-name="${esc(row.name || '')}">
                    <div class="desk-home-sym"><b>${esc(codeOf(row.symbol))}</b><span>${esc(row.name || '')}</span></div>
                    <div class="desk-home-num">${price(row)}</div>
                    <div class="desk-home-num muted">${cellPrice(row, 'bid_price1')}</div>
                    <div class="desk-home-num muted">${cellQty(row, 'bid_volume1')}</div>
                    <div class="desk-home-num muted">${cellPrice(row, 'ask_price1')}</div>
                    <div class="desk-home-num muted">${cellQty(row, 'ask_volume1')}</div>
                    <div class="desk-home-num ${signClass(row.chg)}">${cellPrice(row, 'chg')}</div>
                    <div class="desk-home-pct ${signClass(row.chg_pct)}">${pct(row.chg_pct)}</div>
                    <div class="desk-home-num">${compact(row.volume)}</div>
                    <div class="desk-home-num muted">${cellPrice(row, 'price_tick')}</div>
                    <div class="desk-home-spark-cell">${sparkSvg(row.spark, color)}</div>
                    <button class="desk-home-fav${fav ? ' on' : ''}" data-fav="${esc(row.symbol)}" title="${fav ? '取消收藏' : '收藏'}">${fav ? '★' : '☆'}</button>
                </div>`;
            }).join('');
    }

    private renderAccount(): void {
        const host = this.element.querySelector('[data-account]');
        if (!host) return;
        const values = this.account?.values || {};
        const label = this.account?.label
            || this.account?.labels?.[this.account?.index || 0]
            || (this.account?.kind === 'stock' ? '股票账户' : '天勤模拟账户');
        const balance = num(values.balance);
        const available = values.available;
        const position = values.position_profit;
        const positionPct = position !== null && position !== undefined
            && balance ? Number(position) / balance * 100 : null;
        const risk = values.risk_ratio;
        const equity = this.equity.length > 1
            ? this.equity : (balance !== null ? [balance, balance] : []);
        host.innerHTML = `
            <div class="desk-home-card-head">
                <div class="desk-home-card-title">账户概览</div>
                <button class="desk-home-chip accent" data-home-account
                    title="切换快期模拟 / 富途模拟">${esc(label)} ▾</button>
            </div>
            <div class="desk-home-account-big">${balance === null ? '--' : `¥ ${money(balance, 2)}`}</div>
            <div class="desk-home-account-delta">
                <span class="desk-home-delta-pill ${signClass(position)}">${position === null || position === undefined ? '--' : `${Number(position) >= 0 ? '+' : ''}${money(position, 2)}`}</span>
                <span class="${signClass(positionPct)}">${positionPct === null ? '' : pct(positionPct)}</span>
                <span class="muted">持仓盈亏</span>
            </div>
            ${areaSvg(equity, this.theme === 'light' ? '#1a73e8' : '#38bdf8')}
            <div class="desk-home-account-chart-label"><span>权益曲线</span><span>本次运行</span></div>
            <div class="desk-home-kpis">
                <div><span>可用资金</span><b>${money(available, 2)}</b></div>
                <div><span>资金使用率</span><b>${risk === null || risk === undefined ? '--' : `${(Number(risk) * 100).toFixed(1)}%`}</b></div>
                <div><span>账户类型</span><b>${esc(label)}</b></div>
                <div><span>连接</span><b>${this.markets.futures || this.markets.stocks ? '实时' : '离线'}</b></div>
            </div>`;
    }

    private renderSignals(): void {
        const host = this.element.querySelector('[data-signals]');
        if (!host) return;
        host.innerHTML = `
            <div class="desk-home-card-head">
                <div class="desk-home-card-title">今日信号</div>
                <span class="desk-home-chip accent">${this.signals.length} 个</span>
            </div>
            <div class="desk-home-signal-list">
                ${this.signals.length ? this.signals.slice(0, 3).map((item) => `
                    <div class="desk-home-signal ${esc(item.tone)}">
                        <span class="desk-home-signal-bar"></span>
                        <div class="main"><div class="title"><b>${esc(codeOf(item.symbol))}</b> ${esc(item.text)}</div>
                            <div class="meta">${esc(item.meta || '')}</div></div>
                        <span class="time">${esc(item.time || '')}</span>
                    </div>`).join('') : '<div class="desk-home-empty">暂无信号</div>'}
            </div>
            <div class="desk-home-calendar">
                <div class="title">事件日历 <span>今天</span></div>
                ${this.events.slice(0, 2).map((item) => `
                    <div class="row"><span>${esc(item.time)}</span><i class="${esc(item.tone || '')}"></i>${esc(item.text)}</div>`).join('')}
            </div>`;
    }

    private renderRecent(): void {
        const host = this.element.querySelector('[data-recent]');
        if (!host) return;
        host.innerHTML = `<div class="desk-home-card-head">
            <div class="desk-home-card-title">最近打开</div>
            <span class="desk-home-chip">${this.recent.length}</span></div>
            <div class="desk-home-recent-list">${this.recent.length ? this.recent.slice(0, 3).map((item) => `
                <button class="desk-home-recent-row" data-open-symbol="${esc(item.symbol)}"
                    data-open-group="${item.kind === 'local' ? 'local' : 'chart'}"
                    data-open-name="${esc(item.name || '')}">
                    <span class="icon">${item.kind === 'local'
                        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/></svg>'
                        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 4-6"/></svg>'}</span>
                    <span class="main"><b>${esc(item.name || item.symbol)}</b>
                        <em>${item.kind === 'local' ? '本地图表' : (item.kind === 'replay' ? '回放' : '看盘')} · ${item.at ? new Date(item.at).toLocaleTimeString('zh-CN', { hour12: false }).slice(0, 5) : ''}</em></span>
                    <span class="arrow">›</span>
                </button>`).join('') : '<div class="desk-home-empty">还没有最近打开</div>'}</div>`;
    }

    /** 左键选中的合约（下面迷你图显示它；空 = 用第一行 ✓） */
    private previewSymbol = '';
    /** 「主力行情」缓存：`{交易所: rows}`（后端 `home_main` 补丁 ✓） */
    private mainRows: Record<string, Array<Record<string, unknown>>> = {};
    /** 迷你K线开关（默认**开**：显示 K 线；关掉 → 迷你折线 ✓） */
    private klineOn = true;
    /** 迷你图的周期（秒；默认 5 分 = 300 ✓） */
    private previewCycle = 300;
    /** 迷你 K 线的数据（后端 `home_preview` 补丁 ✓） */
    private previewBars: PreviewBar[] = [];
    private previewBarsKey = '';
    /** 已经发过的「合约+周期」请求：空 bars 时不要无限重发 ✓ */
    private previewRequestKey = '';

    /** 后端推来的「主力 · 某交易所」合约（`{type:'home_main'}` ✓） */
    setMainRows(payload: Record<string, unknown>): void {
        const exchange = String(payload.exchange || '');
        if (!exchange) return;
        const rows = (payload.rows || []) as Array<Record<string, unknown>>;
        this.mainRows[exchange] = rows;
        // ★ 主力合约的**报价**要并进 rowMap（否则表格里只有代码没有价格 ✗）
        this._mergeRows(rows as never);
        this.renderMainList();
        if (this.activeGroup === `main:${exchange}`) this.renderWatch();
    }

    /** 后端推来的迷你 K 线（`{type:'home_preview', symbol, bars}` ✓） */
    setPreviewBars(payload: Record<string, unknown>): void {
        const symbol = String(payload.symbol || '');
        const cycle = Number(payload.cycle);
        if (Number.isFinite(cycle) && cycle > 0) this.previewCycle = cycle;
        if (symbol && this.previewSymbol && symbol !== this.previewSymbol) {
            return;                     // 期间又选了别的合约 → 丢掉旧结果 ✓
        }
        this.previewBars = (payload.bars || []) as PreviewBar[];
        this.previewBarsKey = symbol;
        this.renderPreview();
    }

    private _previewRow(): HomeRow | undefined {
        const symbol = this.previewSymbol;
        if (symbol) {
            const found = this.rowMap.get(symbol)
                || this.watchRows.find((item) => item.symbol === symbol)
                || this.indexRows.find((item) => item.symbol === symbol);
            if (found) return found;
        }
        return this.watchRows[0] || this.indexRows[0];
    }

    private renderPreview(): void {
        const host = this.element.querySelector('[data-preview]');
        if (!host) return;
        const row = this._previewRow();
        if (!row) {
            host.innerHTML = '<div class="desk-home-empty">暂无行情</div>';
            return;
        }
        const color = num(row.chg_pct) !== null && Number(row.chg_pct) >= 0
            ? 'var(--desk-up)' : 'var(--desk-down)';
        host.innerHTML = `<div class="desk-home-card-head">
                <div class="desk-home-preview-title"><b>${esc(codeOf(row.symbol))}</b>
                    <span>${esc(row.name || '')}</span>
                    <em class="${signClass(row.chg_pct)}">${pct(row.chg_pct)}</em></div>
                <div class="desk-home-card-actions">
                    <button class="desk-home-kline-toggle${this.klineOn ? ' on' : ''}"
                        data-act="kline-toggle"
                        title="K线 / 迷你图（默认 K 线）">K线</button>
                    <button class="desk-home-period on" data-act="preview-cycle"
                        title="切换迷你图周期">${PREVIEW_CYCLES.find(
        (item) => item.cycle === this.previewCycle)?.label || '5分'}</button>
                    <button class="desk-btn desk-btn-ghost desk-btn-sm" data-open-symbol="${esc(row.symbol)}"
                        data-open-name="${esc(row.name || '')}">打开图表 ↗</button>
                </div>
            </div>
            <div class="desk-home-preview-chart">${this._previewChart(row, color)}</div>
            <div class="desk-home-preview-meta"><span>最新 ${price(row)}</span><span>高 ${money(row.high ?? row.last, decimalsOf(row))}</span><span>低 ${money(row.low ?? row.last, decimalsOf(row))}</span><span>量 ${compact(row.volume)}</span><span>09:00 — 15:00</span></div>`;
    }

    /** 当前迷你图对应的合约（没手动点选 = 第一行 ✓） */
    private _previewSymbolOf(row: HomeRow): string {
        return String(this.previewSymbol || row.symbol || '');
    }

    /** 请求迷你图数据（K 线 / 折线都靠它；带周期 ✓） */
    private _requestBars(row?: HomeRow): void {
        const target = row || this._previewRow();
        const symbol = target ? this._previewSymbolOf(target)
            : this.previewSymbol;
        if (!symbol) return;
        const key = `${symbol}|${this.previewCycle}`;
        if (key === this.previewRequestKey) return;
        this.previewRequestKey = key;
        this.options.onPreviewBars?.(
            String(symbol), this.previewCycle);
    }

    /** 迷你图：K 线 → 蜡烛；关掉 → 用**同一份数据的收盘价**画折线 ✓ */
    private _previewChart(row: HomeRow, color: string): string {
        const symbol = this._previewSymbolOf(row);
        const bars = (this.previewBarsKey && this.previewBarsKey === symbol)
            ? this.previewBars : [];
        if (this.klineOn) {
            if (bars.length >= 2) return candleSvg(bars, 600, 130);
            this._requestBars(row);          // 没有就请求（会自动重画 ✓）
            return sparkSvg(row.spark, color, 600, 130);
        }
        // ★ 非 K 线：优先用 K 线数据的**收盘价**画折线（否则没图 ✗）
        const closes = bars.map((bar) => Number(bar.close))
            .filter((value) => Number.isFinite(value));
        if (closes.length >= 2) return sparkSvg(closes, color, 600, 130);
        if (!bars.length) this._requestBars(row);
        return sparkSvg(row.spark, color, 600, 130);
    }

    private renderQuickStats(): void {
        const host = this.element.querySelector('[data-quick-stats]');
        if (!host) return;
        const volume = this.watchRows.reduce(
            (total, row) => total + (num(row.volume) || 0), 0);
        const up = this.watchRows.filter((row) => (num(row.chg_pct) || 0) > 0).length;
        const down = this.watchRows.filter((row) => (num(row.chg_pct) || 0) < 0).length;
        host.innerHTML = `
            <div class="row"><span>自选成交量</span><b>${compact(volume)}</b></div>
            <div class="row"><span>上涨 / 下跌</span><b><em class="up">${up}</em> / <em class="down">${down}</em></b></div>`;
        const temp = this.element.querySelector('[data-temp]');
        if (temp) {
            const total = Math.max(1, up + down);
            const ratio = Math.round(up / total * 100);
            temp.innerHTML = `<div class="temp-label">市场温度</div>
                <div class="temp-row"><span>自选涨跌比</span><div class="bar"><i style="width:${ratio}%"></i></div><b>${ratio}%</b></div>
                <div class="temp-row"><span>活跃合约</span><b>${this.watchRows.length}</b></div>`;
        }
    }

    private _openFirstChart(): void {
        const row = this.watchRows[0] || this.indexRows[0];
        if (row) this.options.onOpenChart(row.symbol, row.name || '');
        else this.options.onToast('info', '当前没有可打开的合约');
    }
}

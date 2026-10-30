/**
 * ChartPage — one chart tab (mirrors miniqt 看盘窗口).
 *
 * Structure:
 *
 *   ┌ toolbar ─────────────────────────────────────────────┐
 *   │ symbol │ + │ 1分 ▾ │ 图表类型 ▾ │ 指标 ▾ │ 🔔 ▶ │ …  │
 *   ├ chart host (Lib.Handler → LWC) ───────────────────────┤
 *   │  candles + volume + position line                    │
 *   ├ ohlc line ───────────────────────────────────────────┤
 *   └ (bottom dock + right quote panel live in P3/P2) ──────┘
 *
 * P0 renders the toolbar, an empty chart and the OHLC line; data arrives in P2.
 */
import { Handler } from '../general/handler';
import { Drawing } from '../drawing/drawing';
import { showChartContextMenu } from './chart-context-menu';
// 图例图标（齿轮 / 眼睛）和 miniqt 共用同一套 SVG ✓
import { EYE_CLOSED, EYE_OPEN, GEAR } from '../general/legend';
import { HorizontalLine } from '../horizontal-line/horizontal-line';
import { AccountDock, type AccountPayload } from './account-dock';
// 「代码」页签（个人指标 / 策略编辑器，CodeMirror 懒加载 ✓）
import { EditorPanel } from './editor-panel';
import { AlertDialog } from '../panels/alert-dialog';
import { IndicatorPicker } from '../panels/indicator-picker';
import { showExportHistory, type ExportRow } from './export-history';
import { SymbolSearch, type SearchItem } from '../panels/symbol-search';
import { TemplatePicker } from '../panels/template-picker';
import {
    AreaSeries, BarSeries, BaselineSeries, LineSeries,
} from 'lightweight-charts';
import { LayoutManager, LayoutParamsDialog,
    SaveLayoutDialog } from './layout-dialogs';
import { REPLAY_SEEKS, REPLAY_SPEEDS, Replay, type ReplayBar } from './replay';
import { openParamPopover } from './param-popover';
import { openIndicatorSettings,
    type IndicatorStyleState } from './indicator-settings';
import { chartOptions, chartPalette, uiPalette } from './theme';
import { crosshairOptions } from './crosshair';
import { VpOverlay } from './vp-overlay';
import { IndicatorLayer, type IndicatorLine,
    type IndicatorPayload } from './indicator';
import { showMenuBelow, type MenuItem } from './menu';
import { KeyboardSprite, isTypingTarget, type SpriteItem } from './keyboard-sprite';
import { DrawingsSync } from './drawings-sync';
// 回放时的本地模拟交易控件（和本地图表同一个 ✓）
import { buildReplayTicket, type ReplayTicket } from './replay-ticket';
// 工具栏图标：单色 SVG（`currentColor`）→ 深浅主题都对 ✓
import {
    ICON_BELL, ICON_CAMERA, ICON_ERASER, ICON_PAUSE, ICON_PENCIL,
    ICON_STEP,
    ICON_PLAY, ICON_REWIND, ICON_TRASH,
} from './icons';
import { QuotePanel, type BookData } from './quote-panel';

export interface ChartBar {
    time: number;          // unix seconds
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export interface ChartPageOptions {
    symbol: string;
    name?: string;
    cycle?: number;
    /** toolbar → backend */
    onCycleChange?: (cycle: number) => void;
    onChartTypeChange?: (kind: string) => void;
    onIndicatorMenu?: () => void;
    onClose?: () => void;
    /** dock 里的动作（切账户 / 平反全 / 刷新）→ 交给 DeskApp 转发 ✓ */
    onCommand?: (cmd: string, payload?: unknown) => void;
    /** 加指标（快捷收藏 / 选择器）→ 交给 DeskApp ✓ */
    onAddIndicator?: (key: string, params?: Record<string, unknown>) => void;
    /** 前端自己弹个提示（`app.toast` ✓） */
    onToast?: (level: string, text: string) => void;
    /** ★ 收藏的指标（`{key,label,provider,params}`） */
    favorites?: Array<Record<string, unknown>>;
    /** ★ 收藏的策略 */
    strategyFavorites?: Array<Record<string, unknown>>;
    /** 主题（副图背景色要用 ✓） */
    theme?: 'light' | 'dark';
}

/** Chart kinds miniqt really supports (the other 11 are disabled placeholders). */
/** 回放按钮的图标（miniqt 的 rewind ✓） */
const REWIND_SVG = ICON_REWIND;

/** 回放工具条里「更换周期」的选项（和 miniqt 的 PERIODS 一致 ✓） */
const REPLAY_CYCLES: Array<{ cycle: number; label: string }> = [
    { cycle: 30, label: '30秒' }, { cycle: 60, label: '1分' },
    { cycle: 300, label: '5分' }, { cycle: 900, label: '15分' },
    { cycle: 1800, label: '30分' }, { cycle: 3600, label: '1时' },
    { cycle: 86400, label: '1日' },
];

/**
 * 布局预设（**支持跨格**）✓
 *
 * `cells` 里每项是 `[列, 行, 列跨, 行跨]`（都从 0 开始）——「上下左下右」
 * 这种要让上边一格横跨两列，所以不能再用「cols×rows 个等宽格子」✗
 */
export interface DeskLayoutSpec {
    key: string;
    label: string;
    cols: number;
    rows: number;
    cells: Array<[number, number, number, number]>;
}

/** 回放初始窗口：显示最近多少根（和右边留白 ✓） */
export const REPLAY_WINDOW = 200;
export const REPLAY_PADDING = 3;

export const DESK_LAYOUTS: DeskLayoutSpec[] = [
    { key: 'single', label: '单图', cols: 1, rows: 1,
      cells: [[0, 0, 1, 1]] },
    { key: 'h2', label: '左右两图', cols: 2, rows: 1,
      cells: [[0, 0, 1, 1], [1, 0, 1, 1]] },
    { key: 'v2', label: '上下两图', cols: 1, rows: 2,
      cells: [[0, 0, 1, 1], [0, 1, 1, 1]] },
    { key: 't1b2', label: '上下左下右（上 1 下 2）', cols: 2, rows: 2,
      cells: [[0, 0, 2, 1], [0, 1, 1, 1], [1, 1, 1, 1]] },
    { key: 't2b1', label: '上左上右下（上 2 下 1）', cols: 2, rows: 2,
      cells: [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 2, 1]] },
    { key: 'h3', label: '横排三个', cols: 3, rows: 1,
      cells: [[0, 0, 1, 1], [1, 0, 1, 1], [2, 0, 1, 1]] },
    { key: 'v3', label: '竖排三个', cols: 1, rows: 3,
      cells: [[0, 0, 1, 1], [0, 1, 1, 1], [0, 2, 1, 1]] },
    { key: 'grid4', label: '四图', cols: 2, rows: 2,
      cells: [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 1, 1], [1, 1, 1, 1]] },
];

/** `cols × rows` → 等分布局（老调用 / 已保存布局都走它 ✓） */
export function layoutSpecOf(cols: number, rows: number,
                             key = ''): DeskLayoutSpec {
    const c = Math.max(1, Math.round(cols) || 1);
    const r = Math.max(1, Math.round(rows) || 1);
    const found = DESK_LAYOUTS.find((item) => item.cols === c
        && item.rows === r && item.key !== 't1b2' && item.key !== 't2b1');
    if (found && !key) return found;
    const cells: Array<[number, number, number, number]> = [];
    for (let row = 0; row < r; row += 1) {
        for (let col = 0; col < c; col += 1) cells.push([col, row, 1, 1]);
    }
    return { key: key || `grid${c}x${r}`, label: `${c}×${r}`, cols: c, rows: r,
        cells };
}

/** 布局 key → 规格（未知 key 返回单图 ✓） */
export function layoutSpecByKey(key: string): DeskLayoutSpec {
    return DESK_LAYOUTS.find((item) => item.key === key) || DESK_LAYOUTS[0];
}

/** 按格数挑一个「最像」的预设（关闭一格后回退用 ✓） */
export function layoutSpecForCount(count: number): DeskLayoutSpec {
    const n = Math.max(1, Math.round(count) || 1);
    const exact = DESK_LAYOUTS.filter((item) => item.cells.length === n);
    const prefer = ['single', 'h2', 'h3', 'grid4'];
    for (const key of prefer) {
        const found = exact.find((item) => item.key === key);
        if (found) return found;
    }
    return exact[0] || DESK_LAYOUTS[0];
}

export const CHART_KINDS: Array<{ key: string; label: string }> = [
    { key: 'candle', label: '蜡烛图' },
    { key: 'hollow', label: '空心蜡烛' },
    { key: 'line', label: '线形图' },
    { key: 'area', label: '面积图' },
    { key: 'baseline', label: '基准图' },
    { key: 'bar', label: '柱状图' },
];

/**
 * 周期预设（复刻 miniqt / TradingView 的 `周期` 菜单 ✓）
 *
 * 结构照 `tradingview/周期菜单.png`：`秒 / 分 / 时 / 天` **二级菜单** +
 * 顶部「＋ 添加自定义周期…」+ 底部「范围」；`值` 单位是**秒**。
 */
export const CYCLE_GROUPS: Array<{
    label: string;
    items: Array<{ value: number; label: string }>;
}> = [
    { label: '秒', items: [{ value: 1, label: '1秒' },
                          { value: 5, label: '5秒' },
                          { value: 15, label: '15秒' },
                          { value: 30, label: '30秒' }] },
    { label: '分', items: [{ value: 60, label: '1分' },
                          { value: 180, label: '3分' },
                          { value: 300, label: '5分' },
                          { value: 900, label: '15分' },
                          { value: 1800, label: '30分' },
                          { value: 2700, label: '45分' }] },
    { label: '时', items: [{ value: 3600, label: '1时' },
                          { value: 7200, label: '2时' },
                          { value: 14400, label: '4时' }] },
    { label: '天', items: [{ value: 86400, label: '1天' },
                          { value: 172800, label: '2天' },
                          { value: 259200, label: '3天' },
                          { value: 604800, label: '1周' },
                          { value: 2592000, label: '1月' }] },
];

/** 扁平列表（兼容旧代码 / 找 label 用 ✓） */
export const CYCLES: Array<{ value: number; label: string }> =
    CYCLE_GROUPS.flatMap((group) => group.items);

/** 周期数值 → 中文标签（`60` → `1分`，自定义的 → `90秒` / `1时30分` ✓） */
export function cycleLabel(cycle: number): string {
    const known = CYCLES.find((item) => item.value === cycle);
    if (known) return known.label;
    const value = Math.max(1, Math.round(Number(cycle) || 60));
    if (value % 86400 === 0) return `${value / 86400}天`;
    if (value % 3600 === 0) return `${value / 3600}时`;
    if (value % 60 === 0) return `${value / 60}分`;
    return `${value}秒`;
}

export interface PosSide {
    volume?: number | null;
    avg?: number | null;
    profit?: number | null;
    side?: string;
}

export class ChartPage {
    public readonly element: HTMLDivElement;
    public cycle: number;


    private readonly legend: HTMLDivElement;
    private readonly host: HTMLDivElement;
    private readonly cycleLabel: HTMLSpanElement;
    private handler: Handler | null = null;
    private readonly cells: Handler[] = [];
    private grid: HTMLDivElement | null = null;
    private layout: { cols: number; rows: number } = { cols: 1, rows: 1 };
    /** 当前布局规格（哪格跨几列 / 几行 ✓） */
    private spec: DeskLayoutSpec = layoutSpecByKey('single');
    /** 「设置」里的图表项（字号 / 涨跌色 / 鼠标标签色 ✓） */
    private fontSize = 14;
    private customUp = '';
    private customDown = '';
    private customCrosshair = '';
    private crosshairStyle = 'classic';
    private toolBoxOn = false;
    /** 每格的 handler id（画线保存回调 `save_drawings<id>` 用它找格 ✓） */
    private readonly cellHandlerIds: string[] = [];
    /** 多布局画线：共用一个工具 + 按 `合约|周期` 持久化 ✓ */
    private drawingsSync: DrawingsSync | null = null;
    /** 左侧「画线」导航栏（整个图表区共用一条，对称于右侧二级报价 ✓） */
    private drawRail: HTMLDivElement | null = null;
    /** 当前被搬进导航栏的那个工具箱（换格 / 关闭时要能放回去 ✓） */
    private railBox: { div: HTMLElement; parent: HTMLElement | null } | null
        = null;
    /** 「预警」对话框（Lib.AlertDialog，复刻 miniqt 的创建预警 ✓） */
    private alertDialog: AlertDialog | null = null;
    /** 已知的预警列表（右键「清除预警」是否可用 ✓） */
    private alertItems: Array<Record<string, unknown>> = [];
    private tradeButton: HTMLButtonElement | null = null;
    /** 键盘精灵（空格键：搜指标 / 策略 / 合约 / 股票 ✓） */
    private sprite: KeyboardSprite | null = null;
    private spriteHotkey: ((event: KeyboardEvent) => void) | null = null;
    /** 底部「代码」编辑器（第一次点「编辑器」才创建 ✓） */
    private editor: EditorPanel | null = null;
    private editorButton: HTMLButtonElement | null = null;
    private dockSplitter: HTMLDivElement | null = null;
    /** 底部面板高度（可拖；存 settings.dock_height ✓） */
    private dockHeight = 232;
    /** 底部面板占整个图表页的比例（窗口缩放时按它一起缩放 ✓） */
    private dockRatio = 1 / 3;
    /** 第一次拿到数据 / 页面还没宽度时 → 等 resize 完成后 fit 一次 ✓ */
    private needsFit = true;
    /** 底部面板是否被「最大化」（隐藏图表区 ✓） */
    private dockMaximized = false;
    /** 最大化前的高度 / 比例（恢复用 ✓） */
    private dockRestoreHeight = 0;
    private dockRestoreRatio = 1 / 3;
    /** 有没有按「页面 1/3」定过初始高度 ✓ */
    private _dockSized = false;
    /** 回放时的本地模拟交易控件（进回放才显示 ✓） */
    /** 统一交易面板（天勤模拟 / 实盘 / 回放的本地模拟 共用 ✓） */
    private ticket: ReplayTicket | null = null;
    /** 交易是否可用（后端 `trading_state` ✓） */
    private tradeEnabled = false;
    /** 交易面板的**标的**（默认 = 本页合约；未锁定时跟随图表点击 ✓） */
    private tradeSymbol = '';
    /** 锁定：不跟随图表点击 / 🔍 不可用 ✓ */
    private tradeLocked = false;
    /** 🔍 的用途（`trade` = 只换交易标的；`chart` = 换图表合约 ✓） */
    private searchFor: 'chart' | 'trade' = 'chart';

    get canTrade(): boolean {
        return this.tradeEnabled;
    }
    /** 进回放前记住的可视范围（退出时恢复 ✓） */
    private savedRanges: Array<{ from: number; to: number } | null> = [];
    /** 无限历史：正在加载 / 已经到头 / 上次请求时间 ✓ */
    private historyLoading = false;
    private historyExhausted = false;
    private historyAt = 0;
    /** 刚打开时别马上补历史（用户还没往左翻 ✓） */
    private historyGrace = 0;
    private symbolButton: HTMLButtonElement | null = null;
    private symbolSearch: SymbolSearch | null = null;
    private indicatorPicker: IndicatorPicker | null = null;
    private templatePicker: TemplatePicker | null = null;
    /** K 线类型（candle / hollow / line / area / baseline / bar ✓） */
    private chartType = 'candle';
    /** 非蜡烛类型时每格挂的序列（切换时先 remove ✓） */
    private readonly typedSeries = new Map<unknown, unknown>();
    /** 每格的合约 / K 线（布局多图用 ✓） */
    private readonly cellSymbols: string[] = [];
    private readonly cellBars: ChartBar[][] = [];
    /** 当前点中的格子（工具栏商品搜索跟随它 ✓） */
    private activeCell = 0;
    /** 回放 */
    private replay: Replay | null = null;
    private replayBar: HTMLDivElement | null = null;
    private replayLabel: HTMLSpanElement | null = null;
    private replaying = false;
    /** 回放参数（「选择时间段 / 更换周期」改完就地重放 ✓） */
    private replaySeek = 0.1;
    private replayCycle = 0;
    /** 回放总根数：0 = 交给后端（用「图表历史长度」✓） */
    private replayCount = 0;
    private replaySpeed = 5;
    /** 回放时上一次可见根数（用来区分「播放 +1 根」和「seek 跳到别处」）✓ */
    private replayViewLengths: number[] = [];
    private playButton: HTMLButtonElement | null = null;
    private replayPlayButton: HTMLButtonElement | null = null;
    private replayCycleLabel: HTMLSpanElement | null = null;
    /** 联动：多格时间轴同步 ✓ */
    private linked = true;
    /** 持仓线开关 */
    private positionLineVisible = true;
    /** 指标隐藏集合（👁 关掉的 key） + 图例数据 */
    private readonly hiddenIndicators = new Set<string>();
    private legendItems: IndicatorLine[] = [];
    /** 多格图例：每格一节（合约 + K 线信息 + 指标行 ✓） */
    private legendOhlc!: HTMLDivElement;
    private legendRows!: HTMLDivElement;
    private readonly cellLegendOhlc: HTMLDivElement[] = [];
    /** 每格图例标题（`#1 SHFE.rb2610`；切某一格合约时要改它 ✓） */
    private readonly cellLegendTitles: HTMLDivElement[] = [];
    private readonly cellLegendRows: HTMLDivElement[] = [];
    private readonly cellItems: IndicatorLine[][] = [];
    /** 每格的策略名（`payload.strategy`；空 = 没挂策略 ✓） */
    private readonly cellStrategy: string[] = [];
    private readonly cellHidden: Array<Set<string>> = [];
    /** 图上买卖盘 */
    private orderTicket: HTMLDivElement | null = null;
    private orderTicketVisible = false;
    private orderQty = 1;
    private orderPrice: number | null = null;
    private ticketAsks: Array<{ price?: number | null }> = [];
    private ticketBids: Array<{ price?: number | null }> = [];
    /** 买一 / 卖一 / 净仓（正=多、负=空）✓ */
    private ticketBid: number | null = null;
    private ticketAsk: number | null = null;
    private ticketNet = 0;
    private ticketDecimals = 2;
    private ticketBuy: {
        node: HTMLButtonElement; price: HTMLSpanElement; label: HTMLSpanElement;
    } | null = null;
    private ticketSell: {
        node: HTMLButtonElement; price: HTMLSpanElement; label: HTMLSpanElement;
    } | null = null;
    private ticketSpread: HTMLDivElement | null = null;
    /** 指标选择器的二级筛选（后端偏好 `indicator_overlay_filter` ✓） */
    private indicatorFilter: 'all' | 'main' | 'sub' = 'all';
    /** 导出历史（后端 `exports` 补丁；看盘页也能打开 ✓） */
    private exportRows: ExportRow[] = [];
    private exportButton: HTMLButtonElement | null = null;
    /** 网格轨道比例（拖动分隔条改它 ✓，参考 miniqt） */
    private colSizes: number[] = [1];
    private rowSizes: number[] = [1];
    /** 每格的外层 DOM（`.desk-chart-cell`）—— resize 要按**实际尺寸**算 ✓ */
    private cellElements: HTMLDivElement[] = [];
    private resizeRaf = 0;
    private splitterLayer: HTMLDivElement | null = null;
    private layoutButton: HTMLButtonElement | null = null;
    private layoutLabel: HTMLSpanElement | null = null;
    /** 播放条：只显示有报价的合约（settings.ticker_only_quoted ✓） */
    private tickerOnlyQuoted = false;
    private tickerButton: HTMLButtonElement | null = null;
    /** 商品搜索：市场 chips + 当前选择（`''` = 全部市场 ✓） */
    private searchMarkets: Array<{ key: string; label: string }> = [];
    private searchMarket = '';
    /** 布局对话框（保存 / 管理）+ 已保存布局 */
    private saveLayoutDialog: SaveLayoutDialog | null = null;
    private layoutManager: LayoutManager | null = null;
    private layoutParams: LayoutParamsDialog | null = null;
    private layouts: Array<Record<string, unknown>> = [];
    private bookButton: HTMLButtonElement | null = null;
    private linkButton: HTMLButtonElement | null = null;
    private ticketButton: HTMLButtonElement | null = null;
    /** 画线工具箱按钮（开启时高亮 ✓） */
    private lineButton: HTMLButtonElement | null = null;
    /** 交易面板 / 二级报价**默认隐藏**，点按钮才显示 ✓ */
    private dockVisible = false;
    private bookVisible = false;
    private observer: ResizeObserver | null = null;
    private bars: ChartBar[] = [];
    private attached = false;
    private readonly book: QuotePanel;
    private readonly dock: AccountDock;
    /** 第 1 格的指标图层（兼容旧逻辑 ✓） */
    private readonly indicators: IndicatorLayer;
    private readonly subHost: HTMLDivElement;
    /** **每格**各一个指标图层（布局多图，各自副图 / 各自指标 ✓） */
    private readonly layers: IndicatorLayer[] = [];
    /** 回放时的指标（后端一次算好，按可见时间切片 ✓） */
    private replayIndicators: IndicatorLine[] = [];
    private replaySymbol = '';
    /** 多图回放：每格的 K 线 / 指标 ✓ */
    private replayCells: Array<{ cell: number; bars: ReplayBar[];
                                indicators: IndicatorLine[] }> = [];
    /** 多空可以同时持仓：每条腿各一条线 / 一个左侧标签（**按格**✓） */
    private readonly positionLinesByCell =
        new Map<number, Array<{ side: string; line: HorizontalLine }>>();
    private positionBadges: HTMLDivElement[] = [];
    private positionKey = '';
    /** 挂单线（未成交委托）：价格 + 买/卖 + 手数，标签在左侧（**按格**✓） */
    private orderLineVisible = true;
    private readonly orderItemsByCell =
        new Map<number, Array<Record<string, unknown>>>();
    private readonly orderLinesByCell = new Map<number,
        Array<{ line: HorizontalLine; badge: HTMLDivElement; price: number }>>();
    /** 预警线（可多条；标签同样在图内左侧 ✓） */
    private alertLines: Array<{ line: HorizontalLine; badge: HTMLDivElement;
                                price: number }> = [];

    constructor(private readonly options: ChartPageOptions) {
        // ★ 股票默认**日线**（1 分钟对股票没意义），期货默认 1 分钟；
        //   右键菜单显式选了周期时以后端给的为准 ✓
        this.cycle = options.cycle
            || (/^(SSE|SZSE|SH|SZ|HK|US|BSE)\./.test(options.symbol || '')
                ? 86400 : 60);

        this.element = document.createElement('div');
        this.element.className = 'desk-chart-page';

        // ---- toolbar -------------------------------------------------------
        const toolbar = document.createElement('div');
        toolbar.className = 'desk-chart-toolbar';

        const symbol = document.createElement('button');
        symbol.className = 'desk-symbol desk-symbol-btn';
        symbol.title = '搜索 / 切换合约（点这里）';
        symbol.textContent = `${options.symbol} 🔍`;
        if (options.name) {
            const name = document.createElement('span');
            name.className = 'desk-muted';
            name.textContent = ` ${options.name}`;
            symbol.appendChild(name);
        }
        symbol.addEventListener('click', () => this.openSymbolSearch());
        this.symbolButton = symbol;

        const cycleButton = document.createElement('button');
        cycleButton.className = 'desk-tool desk-tool-arrow';
        cycleButton.title = 'K 线周期（秒 / 分 / 时 / 天 / 自定义…）';
        this.cycleLabel = document.createElement('span');
        this.cycleLabel.className = 'desk-tool-label';
        this.cycleLabel.textContent = this._cycleText(this.cycle);
        const cycleArrow = document.createElement('span');
        cycleArrow.className = 'desk-tool-caret';
        cycleArrow.textContent = '▾';
        cycleButton.append(this.cycleLabel, cycleArrow);
        cycleButton.addEventListener('click', () => this._openCycleMenu(cycleButton));
        cycleButton.classList.add('desk-strategy-hide');

        const kindButton = this._toolButton('图表类型', () => {
            showMenuBelow(kindButton, CHART_KINDS.map((item) => ({
                label: item.label,
                run: () => this.options.onChartTypeChange?.(item.key),
            })));
        });
        kindButton.title = '图表类型（蜡烛 / 空心 / 线 / 面积 / 基准 / 柱）';
        const indicatorButton = this._toolButton('指标', (button) => {
            this.openIndicatorMenu(button);
        }, '技术指标（★ 收藏 / 更多指标和策略 / 个人指标）');
        indicatorButton.classList.add('desk-strategy-hide');
        const templateButton = this._toolButton('模板', () => {
            this.openTemplatePicker();
        }, '指标模板（保存 / 应用当前图的指标组合）');
        templateButton.classList.add('desk-strategy-hide');
        const alertButton = this._toolButton('', () => this._openAlertDialog(),
                                             '价格预警（到价提醒 / 可转下单）');
        alertButton.innerHTML = ICON_BELL;
        alertButton.classList.add('desk-strategy-hide');
        // ★ 回放按钮（复刻 miniqt：rewind 图标，选中时主题色底 ✓）
        const playButton = this._toolButton(
            '', () => this.toggleReplay(),
            '回放：进入后逐根播放历史 K 线（再点一次回到实时）');
        playButton.classList.add('desk-tool-replay');
        playButton.classList.add('desk-strategy-hide');
        playButton.innerHTML = REWIND_SVG;
        this.playButton = playButton;
        // ★ 布局四合一（P27）：单图/左右/四图 + 已保存布局 + 保存 + 管理
        const layoutButton = this._toolButton('布局', (button) => {
            this.openLayoutMenu(button);
        }, '布局：单图 / 上下·左右两图 / 上1下2 / 上2下1 / 横排·竖排三图 / '
            + '四图 / 已保存布局 / 保存布局 / 布局管理');
        layoutButton.classList.add('desk-tool-arrow');
        layoutButton.classList.add('desk-strategy-hide');
        const layoutLabel = document.createElement('span');
        layoutLabel.className = 'desk-tool-label';
        layoutLabel.textContent = '布局';
        const layoutCaret = document.createElement('span');
        layoutCaret.className = 'desk-tool-caret';
        layoutCaret.textContent = '▾';
        layoutButton.textContent = '';
        layoutButton.append(layoutLabel, layoutCaret);
        this.layoutButton = layoutButton;
        this.layoutLabel = layoutLabel;
        this._syncTickerButton();
        void this.layoutButton;            // 保留引用（以后要加状态点 ✓）
        this._syncLayoutButton();
        const lineButton = this._toolButton('', () => this.toggleToolBox(),
                                            '画线工具箱（趋势线 / 斐波那契 / 测量…）');
        lineButton.innerHTML = ICON_PENCIL;
        this.lineButton = lineButton;
        // ★ 「编辑器」和「交易」合并成一个按钮：显示 / 隐藏底部面板 ✓
        const tradeButton = this._toolButton(
            '交易/编辑器', () => this.toggleDock(),
            '显示 / 隐藏下方「交易账户 / 运行日志 / 代码」页面');
        const editorButton = tradeButton;
        const bookButton = this._toolButton('二级报价', () => this.toggleBook(),
                                            '显示 / 隐藏右侧「二级报价」面板');
        this.tradeButton = tradeButton;
        this.bookButton = bookButton;
        tradeButton.classList.add('desk-strategy-hide');
        bookButton.classList.add('desk-strategy-hide');
        // ---- 右侧工具组（按 miniqt 的顺序 ✓）---
        const deleteIndicator = this._toolButton(
            '', (button) => this.openRemoveMenu(button),
            '删除指标（按图表汇总，可删单个 / 全部）');
        deleteIndicator.innerHTML = ICON_TRASH;
        deleteIndicator.classList.add('desk-strategy-hide');
        const clearDrawings = this._toolButton('', () => this.clearDrawings(),
                                               '清除全部画线');
        clearDrawings.innerHTML = ICON_ERASER;
        const linkButton = this._toolButton('联动', () => this.toggleLink(),
                                            '多图联动（时间轴 / 十字线同步）');
        const ticketButton = this._toolButton('买卖盘', () => this.toggleOrderTicket(),
                                              '图上买卖盘（买入 / 点差 / 卖出，有仓→平仓）');
        this.ticketButton = ticketButton;
        ticketButton.classList.add('desk-strategy-hide');
        const shotButton = this._toolButton('', () => this.screenshot(),
                                            '截图（PNG）');
        shotButton.innerHTML = ICON_CAMERA;
        // ⚠ 「播放条」「导出历史」只对**行情报价页**有意义，看盘窗口不放
        //   （用户要求移除 ✓）——所以这里不再建这两个按钮。
        const spacer = document.createElement('span');
        spacer.className = 'desk-toolbar-spacer';

        this.linkButton = linkButton;
        linkButton.classList.add('desk-strategy-hide');

        // 左侧：周期 / 图表类型 / 指标 / 模板 ；右侧（miniqt 顺序）：
        // 删除指标 / 清空画线 / 持仓线 / 联动 / 买卖盘 / **布局 / 画线** / 交易 /
        // 二级报价 / 截图（布局与画线工具放在「交易」左边 ✓，用户要求）
        toolbar.append(symbol, this._separator(), cycleButton, kindButton,
                       indicatorButton, templateButton,
                       this._separator(), alertButton, playButton,
                       spacer,
                       deleteIndicator, clearDrawings, lineButton,
                       linkButton, ticketButton,
                       layoutButton, editorButton, tradeButton, bookButton,
                       shotButton);
        void kindButton;

        // ---- OHLC line -----------------------------------------------------
        this.legend = document.createElement('div');
        this.legend.className = 'desk-legend';
        this.legend.style.display = 'none';   // 原生图例接管（P15 ✓）
        this.legendOhlc = document.createElement('div');
        this.legendOhlc.className = 'desk-legend-ohlc';
        this.legendOhlc.textContent = '--';
        this.legendRows = document.createElement('div');
        this.legendRows.className = 'desk-legend-rows';
        this.legend.append(this.legendOhlc, this.legendRows);

        // ---- chart host ----------------------------------------------------
        this.host = document.createElement('div');
        this.host.className = 'desk-chart-host';
        // ★ 图表右键菜单（复刻 miniqt）——只挂在图表区域上，工具栏 / 面板
        //   自身的右键不受影响；画线图形上右键让画线自己的菜单处理 ✓
        this.host.addEventListener('contextmenu', (event) => {
            const target = event.target as HTMLElement | null;
            if (target?.closest('input,textarea,select,.toolbox,.context-menu')) {
                return;
            }
            if (Drawing.hoveredObject) return;
            // ★ 右键也先切到鼠标所在格；否则指标 / 关闭图表仍作用在格 1 ✗
            const cell = target?.closest('.desk-chart-cell') as
                HTMLDivElement | null;
            const index = cell ? this.cellElements.indexOf(cell) : -1;
            if (index >= 0) this._activateCell(index);
            event.preventDefault();
            this._openChartContextMenu(event.clientX, event.clientY);
        });

        this.subHost = document.createElement('div');
        this.subHost.className = 'desk-ind-host';
        const main = document.createElement('div');
        main.className = 'desk-chart-main';
        main.append(this.host, this.subHost);

        // 二级报价只负责看盘 / 点档填价（下单按钮统一到交易面板 ✓）
        this.book = new QuotePanel();
        // 二级报价点档位 → 只把价格填进下单框（买卖盘本身是市价调仓 ✓）
        this.book.onPricePick = (price) => this.setTicketPrice(price);
        this.book.onLevelClick = (_side, price) => this.setTicketPrice(price);
        const body = document.createElement('div');
        body.className = 'desk-chart-body';
        // ★ 画线工具箱做成**左侧导航条**（工具栏下面、账户面板上面，
        //   对称于右侧二级报价，只是窄一些）；由工具栏「画线」按钮显隐 ✓
        this.drawRail = document.createElement('div');
        this.drawRail.className = 'desk-draw-rail';
        this.drawRail.style.display = 'none';
        body.append(this.drawRail, main, this.book.element);

        this.dock = new AccountDock((cmd, payload) => this.options.onCommand?.(
            cmd, payload));
        // ★ 底部面板最右的「最大化 / 恢复」按钮（P60）—— 构造时就接上 ✓
        this.dock.onToggleMaximize = () => this.toggleDockMaximize();
        // ★ 「代码」页签：第一次切过去时才建编辑器（P60 合并按钮后必须在这里接 ✗）
        this.dock.onEditorOpen = () => {
            this._ensureEditor().show();
            this.resize();
        };
        this.dock.onTabChange = (tab) => {
            if (tab === 'code') this._ensureEditor().show();
            else this.editor?.hide();
        };
        // 账户四张表的「导出 CSV」→ 走后端落盘（Qt 里能看见路径 ✓）
        this.dock.onExport = (filename, text) => {
            this.options.onCommand?.('export_csv', {
                name: filename, text,
            });
            return true;
        };
        this.element.append(toolbar, this.legend, body, this.dock.element);
        this._bindSpriteHotkey();       // 空格键 → 键盘精灵 ✓
        // ★ 记住「鼠标最后点击的那张图」（市价平仓/反手/撤单作用在它上面 ✓）
        this.element.addEventListener('pointerdown', () => {
            this.options.onCommand?.('focus_chart', {
                symbol: this.tradeSymbol || this.options.symbol,
            });
        });
        // 默认隐藏（用户要求：点了按钮才出现 ✓）
        this.dock.element.style.display = 'none';
        this.book.element.style.display = 'none';
        this._syncToggles();

        this.indicators = new IndicatorLayer(
            this.subHost,
            () => (this.handler
                ? (this.handler as unknown as { chart: never }).chart
                : null),
            () => ({
                background: this.options.theme === 'light' ? '#ffffff' : '#0f1115',
                text: this.options.theme === 'light' ? '#1f2329' : '#d8d9db',
            }),
            // 第 4 个参数是 `getLegend`（该格图例），第 5 个才是 `getHandler`
            () => ((this.handler as unknown as { legend?: unknown })
                ?.legend as never) || null,
            () => (this.handler as unknown as any) || null);
        // ★ 画线工具箱 / 右键菜单 / tooltip 的根 CSS 变量：默认是深色，
        //   浅色主题必须重设，否则工具箱一直黑底（用户实测 ✗）
        this._applyRootStyles(this.options.theme === 'light' ? 'light' : 'dark');
    }

    /** 把当前主题写进 pylightcharts 的根 CSS 变量（工具箱 / 菜单 ✓） */
    private _applyRootStyles(theme: 'light' | 'dark'): void {
        const ui = uiPalette(theme);
        try {
            Handler.setRootStyles({
                backgroundColor: ui.background,
                hoverBackgroundColor: ui.hoverBackground,
                clickBackgroundColor: ui.clickBackground,
                activeBackgroundColor: ui.activeBackground,
                mutedBackgroundColor: ui.mutedBackground,
                borderColor: ui.border,
                color: ui.color,
                activeColor: ui.activeColor,
            });
        } catch {
            /* 非浏览器环境 / 旧 bundle：忽略 ✓ */
        }
    }

    // ------------------------------------------------------------ lifecycle
    /** Create the LWC chart the first time the tab becomes visible. */
    mount(): void {
        if (this.attached) return;
        this.attached = true;
        this.book.setSymbol(this.options.symbol);
        this._buildCells();
        // ★ 统一交易面板（持仓 / 委托右侧；实时 + 回放共用 ✓）
        this._ensureDockTicket(this.replaying);
        this.observer = new ResizeObserver(() => this.resize());
        this.observer.observe(this.host);
        this.resize();
        if (this.bars.length) this.setBars(this.bars, true);
        this._renderAlertLines();
        // 页面刚建好时宽度可能是 0 → 下一帧再量一次并 fit（否则「只有几根K线」✗）
        const raf = (globalThis as unknown as {
            requestAnimationFrame?: (cb: () => void) => number;
        }).requestAnimationFrame;
        if (typeof raf === 'function') {
            raf(() => { this.resize(); this._fitIfNeeded(); });
        } else {
            this._fitIfNeeded();
        }
    }

    /** 1×1 / 1×2 / 2×2：每格一个 LWC（同合约、同周期 ✓） */
    setLayout(cols: number, rows: number, key = ''): void {
        const spec = key ? layoutSpecByKey(key) : layoutSpecOf(cols, rows);
        this.setLayoutSpec(spec);
    }

    /** 直接按预设切布局（含跨格：上下左下右 / 上左上右下 ✓） */
    setLayoutSpec(spec: DeskLayoutSpec): void {
        const target = (spec || layoutSpecByKey('single')).cells.length;
        // ★ 加载了策略：格数不能少于策略合约数（否则策略放不下 ✗）
        if (this.strategyCells && target < this.strategyCells) {
            this.toast(
                `策略需要 ${this.strategyCells} 个图表，不能切到更少的布局`);
            return;
        }
        this.spec = spec || layoutSpecByKey('single');
        this.layout = { cols: Math.max(1, this.spec.cols),
            rows: Math.max(1, this.spec.rows) };
        if (!this.attached) {
            this.mount();
            this._syncLayoutButton();
            return;
        }
        const items = this.indicators?.keys || [];
        this._buildCells();
        this.resize();
        if (this.bars.length) this.setBars(this.bars, true);
        void items;
        this._syncLayoutButton();
        // ★ 布局是**前端**切的（工具栏「布局」）→ 必须告诉后端 ✓
        //   以前后端完全不知道有第 2..N 格：那几格拿不到自己的 K 线 / 持仓线
        //   （显示的是第 1 格复制过来的数据），商品搜索切合约也会退化成
        //   「整页重开」→ 所有格一起换（用户实测 ✗）
        this._syncLayoutToBackend();
    }

    /** 把当前布局（几行几列、每格合约）同步给后端 ✓ */
    private _syncLayoutToBackend(): void {
        this.options.onCommand?.('layout_sync', {
            symbol: this.options.symbol,
            cols: this.layout.cols,
            rows: this.layout.rows,
            symbols: this.cellSymbols.slice(),
        });
    }

    /** 按 key 切布局（`v2` / `t1b2` / `h3` … ✓） */
    setLayoutByKey(key: string): void {
        this.setLayoutSpec(layoutSpecByKey(key));
    }

    /** 关掉某一格的图表（布局里只剩一格时不允许 ✓） */
    closeCell(index = -1): boolean {
        if (this.cells.length <= 1) return false;
        const target = index < 0
            ? Math.max(0, this.cells.indexOf(this.handler as never))
            : Math.max(0, Math.min(index, this.cells.length - 1));
        const symbols = this.cellSymbols.slice();
        const bars = this.cellBars.map((list) => list.slice());
        const items = this.cellItems.map((list) => (list || []).slice());
        const symbols2 = symbols.filter((_, i) => i !== target);
        const bars2 = bars.filter((_, i) => i !== target);
        const items2 = items.filter((_, i) => i !== target);
        this.setLayoutSpec(layoutSpecForCount(symbols2.length));
        symbols2.forEach((symbol, cell) => {
            this.cellSymbols[cell] = symbol;
            this.setCellBars(cell, bars2[cell] || []);
            this.setCellIndicators(cell, {
                type: 'indicator', symbol,
                items: items2[cell] || [],
            });
        });
        this.handler = this.cells[Math.min(target, this.cells.length - 1)]
            || this.cells[0] || null;
        this.resize();
        this._syncLayoutToBackend();
        this._refreshDrawings();
        return true;
    }

    /** 激活鼠标最后点击的格：指标 / 交易 / 右键关闭都按它走 ✓ */
    private _activateCell(index: number): void {
        if (index < 0 || index >= this.cells.length) return;
        this.activeCell = index;
        this.handler = this.cells[index] || this.handler;
        const symbol = this.cellSymbols[index] || this.options.symbol;
        if (symbol) this._setSymbolButton(symbol);
        if (!this.tradeLocked && symbol) this.setTradeSymbol(symbol);
        // 画线导航条跟着活动格（多布局共用一个 ✓）
        if (this.toolBoxOn) this._applyToolBoxMode();
    }

    private _buildCells(): void {
        // ★ 换布局会把旧 handler（连同工具箱 DOM）销毁 → 先放回去再清空 ✓
        this._detachToolBoxFromRail();
        if (this.drawRail) this.drawRail.textContent = '';
        for (const handler of this.cells) {
            try {
                (handler as unknown as { destroy?: Function }).destroy?.();
            } catch {
                /* ignore */
            }
        }
        this.cells.length = 0;
        this.grid?.remove();
        const grid = document.createElement('div');
        grid.className = 'desk-chart-grid';
        // ★ 轨道尺寸用数组存（拖动分隔条时改它 ✓，参考 miniqt 能拖）
        this.colSizes = Array.from({ length: this.layout.cols }, () => 1);
        this.rowSizes = Array.from({ length: this.layout.rows }, () => 1);
        this.host.appendChild(grid);
        this.grid = grid;
        this._applyGridTracks();
        // `cells` 里每项 `[列, 行, 列跨, 行跨]`（上下左下右要跨格 ✓）
        const spec = this.spec || layoutSpecByKey('single');
        // ★ 换布局 **保留每格原来的合约 / K 线**（同格数的布局切换要保持策略
        //   的多合约映射：以前一律重置成主合约 → 左右换上下后两格同一个合约 ✗）
        const oldSymbols = this.cellSymbols.slice();
        const oldBars = this.cellBars.map((list) => (list || []).slice());
        this.cellSymbols.length = 0;
        this.cellBars.length = 0;
        this.layers.length = 0;
        this.cellElements.length = 0;
        for (let index = 0; index < spec.cells.length; index += 1) {
            const [col, row, colSpan, rowSpan] = spec.cells[index];
            const cell = document.createElement('div');
            cell.className = 'desk-chart-cell';
            if (colSpan > 1 || rowSpan > 1) cell.classList.add('span');
            cell.style.gridColumn = `${col + 1} / span ${Math.max(1, colSpan)}`;
            cell.style.gridRow = `${row + 1} / span ${Math.max(1, rowSpan)}`;
            grid.appendChild(cell);
            this.cellElements.push(cell);
            cell.addEventListener('pointerdown', () => {
                this._activateCell(index);
            });
            // 每格：主图（flex 1）+ 该格自己的副图容器 + 指标图层 ✓
            const main = document.createElement('div');
            main.className = 'desk-cell-main';
            const sub = document.createElement('div');
            sub.className = 'desk-cell-sub';
            cell.append(main, sub);
            const handler = new Handler(`${this._nextId()}${index}`, 1, 1,
                                        'absolute', false);
            const wrapper = (handler as unknown as {
                wrapper: HTMLElement }).wrapper;
            wrapper.style.position = 'relative';
            wrapper.style.width = '100%';
            wrapper.style.height = '100%';
            main.appendChild(wrapper);
            this.cells.push(handler);
            this.cellHandlerIds[index] = `${(handler as unknown as {
                id?: string }).id || ''}`;
            this.cellSymbols.push(oldSymbols[index] || oldSymbols[0]
                || this.options.symbol);
            this.cellBars.push(oldBars[index] || []);
            // ★ 无限历史：可视范围到左边界就补一批（只对第 1 格 ✓）
            if (index === 0) this._bindHistory(handler);
            const chart = () => (handler as unknown as { chart: never }).chart;
            const legend = (handler as unknown as {
                legend?: Record<string, unknown>;
            }).legend;
            if (legend) {
                // ★ 用 pylightcharts 原生图例（眼睛图标就是 minibt 那个 ✓）
                const div = legend.div as HTMLElement;
                div.style.display = 'flex';
                div.style.fontSize = `${this.fontSize}px`;
                div.style.color = this.options.theme === 'light'
                    ? '#1f2329' : '#d8d9db';   // 之后 applyTheme 还会再刷 ✓
                legend.ohlcEnabled = true;
                legend.percentEnabled = true;
                legend.linesEnabled = true;
                legend.colorBasedOnCandle = true;
                // ★ 复刻 miniqt 看盘窗口的图例「收起 / 下拉」按钮：
                //   指标标签下方一行 `∧`，收起后变成 `∨ N`（TradingView 同款 ✓）
                (legend as unknown as {
                    enableCollapse?: () => void }).enableCollapse?.();
                const text = legend.text as HTMLElement;
                if (text) text.style.display = 'none';
            }
            const layer = new IndicatorLayer(sub, chart, () => {
                // 主题色（柱状指标的涨/跌基础色也从这里取 ✓）
                const pal = chartPalette(this.options.theme || 'dark');
                return {
                    background: pal.background, text: pal.text,
                    up: pal.up, down: pal.down,
                };
            }, () => (handler as unknown as {
                legend?: Record<string, unknown> } | null)?.legend || null,
            // 第 5 个参数：Handler（自定义序列画信号箭头用 ✓）
            () => (handler as unknown as {
                createCustomSeries?: Function } | null) || null);
            layer.onToggle = (item) =>
                this.toggleIndicator(item.key, undefined, index);
            layer.onSettings = (item, anchor) =>
                this._openIndicatorSettings(item, anchor, index);
            this.layers.push(layer);
        }
        this._buildSplitters();
        this._buildLegend();
        this.handler = this.cells[0] || null;
        // ★ 切布局不重置「画线」开关：重建后 `_refreshDrawings()` 会把新
        //   工具箱重新搬进左侧导航条（以前这里置 false → 导航条空着、图标
        //   全没了，切回单图也回不来 ✗）
        this._applyChartType();
        this._bindLegendCrosshair();
        this._applyCrosshairStyle();
        // ★ 新布局 / 新格子使用当前主题；否则切浅色后再分屏，新图仍是深色 ✗
        const chartTheme = chartOptions(
            this.options.theme === 'light' ? 'light' : 'dark');
        for (const handler of this.cells) {
            try {
                (handler as unknown as { chart: { applyOptions: Function } })
                    .chart.applyOptions(chartTheme);
            } catch { /* ignore */ }
        }
        if (this.orderTicketVisible) this._ensureOrderTicket();
        this._restoreCellLines();
        this._refreshDrawings();
    }

    /** 画线同步器（惰性建；`cells()` 每次都现算 key ✓） */
    private _drawings(): DrawingsSync {
        if (!this.drawingsSync) {
            this.drawingsSync = new DrawingsSync({
                cells: () => this.cells.map((handler, index) => ({
                    id: this.cellHandlerIds[index]
                        || (handler as unknown as { id?: string }).id || '',
                    key: this._drawingKey(index),
                    handler,
                })),
                save: (key, items) => this.options.onCommand?.(
                    'save_drawings', { key, items }),
                request: (key) => this.options.onCommand?.(
                    'drawings', { key }),
            });
        }
        return this.drawingsSync;
    }

    /** 画线存储键：`合约|周期`（同品种不同周期各画各的 ✓） */
    private _drawingKey(index = this.activeCell): string {
        const symbol = this.cellSymbols[index] || this.options.symbol || '';
        return `${symbol}|${Number(this.cycle) || 0}`;
    }

    /** 重建格子 / 换合约 / 换周期后：按新键把画线画回来 ✓ */
    private _refreshDrawings(): void {
        this._drawings().refresh();
        this._applyToolBoxMode();        // 新工具箱 → 重新搬进 / 搬出导航条 ✓
    }

    private _activeHandlerId(): string {
        return this.cellHandlerIds[this.activeCell]
            || (this.cells[this.activeCell] as unknown as { id?: string })
                ?.id || '';
    }

    /** 后端推来的画线（`{type:'drawings', key, items}` ✓） */
    applyDrawings(payload: { key?: string; items?: unknown[] }): void {
        this._drawings().apply(payload);
    }

    /** 合约在第几格（多布局；找不到 → -1 ✓） */
    cellIndexOf(symbol: string): number {
        return this.cellSymbols.findIndex((item) => item === symbol);
    }

    /** 刷新某一格的图例标题（`#2 SHFE.au2612` ✓） */
    private _refreshCellTitle(index = 0): void {
        const title = this.cellLegendTitles[index];
        if (!title) return;
        const symbol = this.cellSymbols[index] || this.options.symbol;
        title.textContent = this.cells.length > 1
            ? `#${index + 1} ${symbol}` : symbol;
    }

    /**
     * 只切换**某一格**的合约（多布局；商品搜索 / 键盘精灵 ✓）
     *
     * 用户实测：以前搜索一个合约会把**所有**格子都换掉（后端把整页当成
     * “切合约”重开）→ 现在只换鼠标最后点击的那一格：
     * 该格的 K 线 / 指标 / 持仓线先清空，随后由后端推这一格的数据 ✓。
     */
    setCellSymbol(cell: number, symbol: string, name = ''): void {
        const index = Math.max(0, Math.min(Number(cell) || 0,
                                         Math.max(0, this.cellSymbols.length - 1)));
        if (!symbol) return;
        if ((this.cellSymbols[index] || '') === symbol) return;
        this.cellSymbols[index] = symbol;
        // ① 该格旧数据作废（后端马上推新的 ✓）
        this.cellBars[index] = [];
        this._updateLegend(undefined, index);
        this._applyCellBars(index);
        this.hidePositionLine(index);
        this.lastPositions.delete(index);
        // ② 该格指标线 / 图例行清空（换合约不保留旧指标的线 ✓）
        this.setCellIndicators(index, {
            type: 'indicator', symbol, cell: index, items: [],
        } as never);
        this._refreshCellTitle(index);
        // ③ 活动格：工具栏商品按钮 / 交易标的跟着换 ✓
        if (index === this.activeCell) {
            this._setSymbolButton(symbol, name);
            if (!this.tradeLocked) this.setTradeSymbol(symbol);
        }
        // ④ 第 1 格 = 页面主合约：报价面板 / 预警按它走（tab 名不变 ✓）
        if (index === 0) {
            this.options.symbol = symbol;
            if (name) this.options.name = name;
            this.book.setSymbol(symbol);
            this._renderAlertLines();
        }
        this._placePositionBadge();
        // ★ 换了合约 → 这一格的画线换成新键（合约|周期）✓
        this._refreshDrawings();
    }

    /**
     * 重建格子（换布局 / 首次挂载）后，把**持仓线 / 挂单线**画回来。
     *
     * `_buildCells()` 会把所有 LWC 序列重造，挂在序列上的 primitive（持仓线 /
     * 挂单线）也跟着没了。以前只能等后端下一次推送：第 1 格最多 1 秒就回来了，
     * 但**第 2..N 格**的补丁带的是该格自己的合约（≠ 页面 key），后端每秒推的
     * 那份又被路由丢掉 → 右图的持仓线永远不会出现（用户实测 ✗）。
     *
     * 这里直接用早就收到过的 `lastPositions` / `orderItemsByCell` 重画：
     * 布局、显隐、窗口尺寸变化后都不会丢 ✓。
     */
    private _restoreCellLines(): void {
        this.hidePositionLine();          // 旧线挂在旧序列上，先断引用 ✓
        this._clearOrderLines();
        for (const [cell, payload] of this.lastPositions) {
            this._applyPositionLine(payload, cell);
        }
        for (const cell of this.orderItemsByCell.keys()) {
            this._renderOrderLines(cell);
        }
    }

    /** 多格图例：每格一节（`#1 SHFE.rb2610` + K 线信息 + 指标行 ✓） */
    private _buildLegend(): void {
        this.cellLegendOhlc.length = 0;
        this.cellLegendTitles.length = 0;
        this.cellLegendRows.length = 0;
        this.cellItems.length = 0;
        this.cellStrategy.length = 0;
        this.cellHidden.length = 0;
        this.legend.textContent = '';
        this.legend.className = 'desk-legend';
        this.legend.style.display = 'none';
        this.cells.forEach((_handler, index) => {
            const block = document.createElement('div');
            block.className = 'desk-legend-cell';
            const title = document.createElement('div');
            title.className = 'desk-legend-title';
            const symbol = this.cellSymbols[index] || this.options.symbol;
            title.textContent = this.cells.length > 1
                ? `#${index + 1} ${symbol}` : symbol;
            const ohlc = document.createElement('div');
            ohlc.className = 'desk-legend-ohlc';
            ohlc.textContent = '--';
            const rows = document.createElement('div');
            rows.className = 'desk-legend-rows';
            block.append(title, ohlc, rows);
            this.legend.appendChild(block);
            this.cellLegendTitles.push(title);
            this.cellLegendOhlc.push(ohlc);
            this.cellLegendRows.push(rows);
            this.cellItems.push([]);
            this.cellStrategy.push('');
            this.cellHidden.push(new Set());
        });
        this.legendOhlc = this.cellLegendOhlc[0] as HTMLDivElement;
        this.legendRows = this.cellLegendRows[0] as HTMLDivElement;
        this.legendItems = this.cellItems[0] || [];
    }

    /** Tabs keep charts alive but hidden; resize only the visible one. */
    /** 把 `colSizes/rowSizes` 应用到 CSS 网格（`N fr` 之和 ✓） */
    private _applyGridTracks(): void {
        const grid = this.grid;
        if (!grid) return;
        const cols = this.colSizes.length ? this.colSizes : [1];
        const rows = this.rowSizes.length ? this.rowSizes : [1];
        grid.style.gridTemplateColumns =
            cols.map((value) => `${Math.max(0.12, value)}fr`).join(' ');
        grid.style.gridTemplateRows =
            rows.map((value) => `${Math.max(0.12, value)}fr`).join(' ');
        this._positionSplitters();
    }

    /**
     * 多图之间的**可拖动分隔条**（和 miniqt 一样能拖 ✓）
     *
     * 绝对定位在网格上方；拖动时改相邻两轨的比例，松手后 `resize()`
     * 让每格 chart 重算宽高 ✓
     */
    private _buildSplitters(): void {
        this.splitterLayer?.remove();
        const grid = this.grid;
        if (!grid) return;
        const layer = document.createElement('div');
        layer.className = 'desk-grid-splitters';
        this.splitterLayer = layer;
        grid.appendChild(layer);

        const drag = (event: MouseEvent, axis: 'col' | 'row',
                      index: number) => {
            event.preventDefault();
            const box = grid.getBoundingClientRect();
            const sizes = axis === 'col' ? this.colSizes : this.rowSizes;
            const total = axis === 'col' ? box.width : box.height;
            if (!total || sizes.length < 2) return;
            const start = axis === 'col' ? event.clientX : event.clientY;
            const before = sizes[index];
            const after = sizes[index + 1];
            const sum = sizes.reduce((acc, value) => acc + value, 0);
            const unit = total / sum;
            const move = (moveEvent: MouseEvent) => {
                const current = axis === 'col' ? moveEvent.clientX
                    : moveEvent.clientY;
                const pair = before + after;
                const next = Math.min(Math.max(0.15, before
                    + (current - start) / unit), pair - 0.15);
                sizes[index] = next;
                sizes[index + 1] = pair - next;
                this._applyGridTracks();
                this._positionSplitters();
                this._scheduleResize();          // 边拖边改尺寸 ✓
            };
            const up = () => {
                window.removeEventListener('mousemove', move);
                window.removeEventListener('mouseup', up);
                document.body.classList.remove('desk-resizing-grid');
                this.resize();
            };
            document.body.classList.add('desk-resizing-grid');
            window.addEventListener('mousemove', move);
            window.addEventListener('mouseup', up);
        };

        for (let index = 0; index < this.layout.cols - 1; index += 1) {
            const bar = document.createElement('div');
            bar.className = 'desk-grid-splitter col';
            bar.title = '拖动调整左右宽度';
            // 位置由 `_positionSplitters()` 按真实比例算（不再一刀切 1/cols ✓）
            bar.addEventListener('mousedown',
                                 (event) => drag(event, 'col', index));
            layer.appendChild(bar);
        }
        for (let index = 0; index < this.layout.rows - 1; index += 1) {
            const bar = document.createElement('div');
            bar.className = 'desk-grid-splitter row';
            bar.title = '拖动调整上下高度';
            // 同上 ✓
            bar.addEventListener('mousedown',
                                 (event) => drag(event, 'row', index));
            layer.appendChild(bar);
        }
        this._positionSplitters();
    }

    /** 把分隔条摆到**真实边界**（按 colSizes/rowSizes 的比例 ✓） */
    private _positionSplitters(): void {
        const layer = this.splitterLayer;
        if (!layer) return;
        const cols = this.colSizes.length ? this.colSizes : [1];
        const rows = this.rowSizes.length ? this.rowSizes : [1];
        const colSum = cols.reduce((acc, value) => acc + value, 0) || 1;
        const rowSum = rows.reduce((acc, value) => acc + value, 0) || 1;
        let x = 0;
        const colLeft: number[] = [];
        for (let index = 0; index < cols.length - 1; index += 1) {
            x += cols[index];
            colLeft.push((x / colSum) * 100);
        }
        let y = 0;
        const rowTop: number[] = [];
        for (let index = 0; index < rows.length - 1; index += 1) {
            y += rows[index];
            rowTop.push((y / rowSum) * 100);
        }
        const bars = Array.from(layer.children) as HTMLElement[];
        let ci = 0;
        let ri = 0;
        for (const bar of bars) {
            if (bar.classList.contains('col')) {
                bar.style.left = `${colLeft[ci] ?? 50}%`;
                ci += 1;
            } else {
                bar.style.top = `${rowTop[ri] ?? 50}%`;
                ri += 1;
            }
        }
    }

    /** 窗口缩放时让底部面板保持比例（不是固定 232px）✓ */
    private _applyDockRatio(total?: number): void {
        if (!this.dockVisible || this.dockMaximized) return;
        const height = total || this.element.getBoundingClientRect().height
            || this.element.clientHeight;
        if (height <= 240) return;
        const ratio = Math.max(0.16, Math.min(0.72, this.dockRatio || 1 / 3));
        const next = Math.round(height * ratio);
        if (Math.abs(next - this.dockHeight) < 1) return;
        this.dockHeight = next;
        this.dock.element.style.height = `${next}px`;
    }

    resize(): void {
        this._applyDockRatio();
        if (!this.handler || !this.grid) return;
        const box = this.grid.getBoundingClientRect();
        if (!box.width) return;
        this._sizeCells(box);
        this._fitIfNeeded();
    }

    /**
     * 第一次有宽度 + 有数据 → `fitContent()` 一次 ✓
     *
     * 以前页面刚挂载时容器宽度是 0，LWC 按 0 宽算出一屏只能放几根，
     * 之后 resize 只改画布**不改可视范围** → 第一次打开只有几根 K 线，
     * 关掉重开（容器已有宽度）就正常了（用户实测 ✗）
     */
    private _fitIfNeeded(): void {
        if (!this.needsFit || this.replaying) return;
        if (!this.bars.length) return;
        // 容器还没宽度时 fitContent 会按 0 宽算 → 一屏只显示几根；
        // 这里直接等下一次 resize 再 fit ✓
        const box = this.grid?.getBoundingClientRect();
        if (!box || !box.width) return;
        const chart = this.handler?.chart as unknown as {
            timeScale?: () => { fitContent?: () => void };
        } | undefined;
        if (!chart?.timeScale) return;
        try {
            chart.timeScale()?.fitContent?.();
            this.needsFit = false;
        } catch {
            /* ignore */
        }
    }

    /** 逐格量尺寸后 resize（拆出来给 `resize()` 复用 ✓） */
    private _sizeCells(box: DOMRect | { width: number; height: number }): void {
        if (!this.handler) return;
        // ⚠ 以前一律用 `box.width / cols` —— 拖过分隔条后左右宽窄不同，
        //   图表还按平均宽算 → 右边图表“平移”、和中缝之间留空白 ✗
        //   （用户实测）。现在逐格量 `.desk-chart-cell` 的真实尺寸 ✓
        const fallback = { width: box.width / this.layout.cols,
            height: box.height / this.layout.rows };
        let first = { width: Math.floor(fallback.width),
            height: Math.floor(fallback.height) };
        this.cells.forEach((handler, index) => {
            const cell = this.cellElements[index];
            const size = cell ? cell.getBoundingClientRect() : null;
            const width = Math.max(60, Math.floor(
                size && size.width ? size.width : fallback.width));
            const height = Math.max(60, Math.floor(
                size && size.height ? size.height : fallback.height));
            if (index === 0) first = { width, height };
            const chart = (handler as unknown as {
                chart: { resize: Function } }).chart;
            chart.resize(width, height);
            const wrapper = (handler as unknown as { wrapper: HTMLElement })
                .wrapper;
            wrapper.style.width = `${width}px`;
            wrapper.style.height = `${height}px`;
        });
        this.indicators?.resize(first.width);
        for (const layer of this.layers) layer.resize(first.width);
    }

    /** 拖动过程中也要重算（节流到一帧一次，不然每格 chart 跟不上 ✓） */
    private _scheduleResize(): void {
        if (this.resizeRaf) return;
        const raf = (globalThis as unknown as {
            requestAnimationFrame?: (cb: () => void) => number;
        }).requestAnimationFrame;
        if (typeof raf !== 'function') {
            this.resize();
            return;
        }
        this.resizeRaf = raf(() => {
            this.resizeRaf = 0;
            this.resize();
        });
    }

    destroy(): void {
        if (this.spriteHotkey) {
            document.removeEventListener('keydown', this.spriteHotkey);
            this.spriteHotkey = null;
        }
        this.sprite?.close();
        this.observer?.disconnect();
        this.observer = null;
        for (const handler of this.cells) {
            try {
                (handler as unknown as { destroy?: Function }).destroy?.();
            } catch {
                /* ignore */
            }
        }
        this._clearAlertLines();
        this.cells.length = 0;
        this.handler = null;
        this.attached = false;
    }

    /** 画线工具箱（LWC 的 TrendLine/Fib/Measure…）开关 ✓ */
    toggleToolBox(): void {
        this.toolBoxOn = !this.toolBoxOn;
        this._drawings().refresh();
        this._applyToolBoxMode();
        this.resize();                   // 左侧多出一条 → 图表要重排 ✓
    }

    /**
     * 应用「画线」开关：**左侧导航条**显示 / 隐藏 + 把当前格的工具箱搬进去 ✓
     *
     * 只显示鼠标最后点击那一格的工具箱（多布局共用一个），其余隐藏；
     * 关掉时把节点放回原来的格子（不影响绘制逻辑，`DrawingTool` 仍绑在该格）。
     */
    private _applyToolBoxMode(): void {
        const sync = this._drawings();
        if (this.toolBoxOn) {
            if (this.drawRail) this.drawRail.style.display = '';
            this._attachToolBoxToRail();
        } else {
            this._detachToolBoxFromRail();
            if (this.drawRail) this.drawRail.style.display = 'none';
        }
        sync.showToolBox(this.toolBoxOn, this._activeHandlerId());
        this.lineButton?.classList.toggle('on', this.toolBoxOn);
    }

    /** 把**当前格**的工具箱搬进左侧导航条 ✓ */
    private _attachToolBoxToRail(): void {
        const handler = this.cells[this.activeCell] as unknown as {
            toolBox?: { div?: HTMLElement };
            createToolBox?: () => void;
        } | null;
        if (!handler) return;
        if (!handler.toolBox) handler.createToolBox?.();
        const box = handler.toolBox;
        if (!box?.div || !this.drawRail) return;
        if (this.railBox?.div === box.div) return;
        this._detachToolBoxFromRail();
        this.railBox = { div: box.div, parent: box.div.parentElement };
        box.div.classList.add('desk-draw-rail-box');
        this.drawRail.appendChild(box.div);
    }

    /** 把导航条里的工具箱放回它原来的格子（关闭 / 换格 / 重建前 ✓） */
    private _detachToolBoxFromRail(): void {
        const current = this.railBox;
        this.railBox = null;
        if (!current) return;
        current.div.classList.remove('desk-draw-rail-box');
        try {
            if (current.parent && current.parent.isConnected) {
                current.parent.appendChild(current.div);
            } else {
                current.div.remove();
            }
        } catch {
            /* 旧格子已销毁 → 直接丢掉 ✓ */
        }
    }

    /** 右键菜单的「布局」子菜单（和工具栏一样按策略禁用更小的布局 ✓） */
    private _contextLayoutItems(): MenuItem[] {
        const currentKey = this.spec?.key || '';
        return DESK_LAYOUTS.map((item) => ({
            label: `${item.label}${currentKey === item.key ? '  ✓' : ''}`,
            disabled: !!this.strategyCells
                && item.cells.length < this.strategyCells,
            run: () => this.setLayoutSpec(item),
        }));
    }

    /** 图表右键菜单（miniqt 同款）✓ */
    private _openChartContextMenu(x: number, y: number): void {
        this.options.onCommand?.('templates', {});   // 列表刷新（下一次最准 ✓）
        const anchor = document.createElement('div');
        anchor.style.cssText = `position:fixed;left:${x}px;top:${y}px;`
            + 'width:1px;height:1px;pointer-events:none;';
        document.body.appendChild(anchor);
        showChartContextMenu({
            favorites: this.options.favorites || [],
            strategies: this.options.strategyFavorites || [],
            templates: this.templateRows,
            layouts: this.layouts,
            layoutItems: this._contextLayoutItems(),
            cycle: this.cycle,
            cycleGroups: CYCLE_GROUPS,
            hasAlerts: this.alertItems.length > 0,
            onIndicatorPicker: () => this.options.onCommand?.(
                'indicator_picker', {
                    symbol: this.symbolForCell(this.activeCell),
                    cell: this.activeCell,
                }),
            onAddFavorite: (key) => this.options.onAddIndicator?.(key, {}),
            // ★ 右键「我的模板 / 保存当前指标模板」：和工具栏「模板」同一条命令 ✓
            onApplyTemplate: (key) => this.applyTemplate(key),
            onSaveTemplate: () => this.saveCurrentTemplate(),
            onAddStrategy: (path) => this.options.onCommand?.(
                'editor_add_indicator', {
                    path, symbol: this.symbolForCell(this.activeCell),
                    cell: this.activeCell,
                }),
            onRemove: () => {
                this.openRemoveMenu(anchor);
                window.setTimeout(() => anchor.remove(), 0);
            },
            onCycle: (cycle) => {
                this.setCycle(cycle);
                this.options.onCycleChange?.(cycle);
            },
            onLayoutPreset: (cols, rows) => this.setLayout(cols, rows),
            onLayoutApply: (key) => this.options.onCommand?.(
                'layout_apply', { symbol: this.options.symbol, key }),
            onToggleToolBox: () => this.toggleToolBox(),
            onClearDrawings: () => this.clearDrawings(),
            onAlert: () => this._openAlertDialog(),
            onClearAlerts: () => this.clearAlerts(),
            onScreenshot: () => this.screenshot(),
            // ★ 全部K线 / 最新K线（作用在鼠标最后点击的那格 ✓）
            onFitAll: () => this.fitAllBars(),
            onLastBars: () => this.showLastBars(),
            // 「关闭图表」：多布局时关掉**鼠标最后点击的那一格** ✓
            canCloseChart: this.cells.length > 1,
            onCloseChart: () => {
                const index = Math.max(0,
                    this.cells.indexOf(this.handler as never));
                if (!this.closeCell(index)) {
                    this.toast('多布局才能关闭图表');
                }
            },
        }, x, y);
        window.setTimeout(() => anchor.remove(), 0);
    }

    /**
     * 预警（复刻 miniqt 的「创建预警」）：价格 / 方向 / 到期 / 消息 /
     * 触发动作 / 手数 + 已有预警列表 ✓
     */
    private _openAlertDialog(): void {
        if (!this.alertDialog) {
            this.alertDialog = new AlertDialog({
                symbol: this.options.symbol,
                price: this.book.lastPrice ?? null,
                decimals: this.ticketDecimals,
                theme: this.options.theme === 'light' ? 'light' : 'dark',
            });
            // ⚠ 不要设 callbackName：0.1.5 的 emit_callback 碰到未注册的名字
            //   会 TypeError: 'NoneType' object is not callable（用户实测 ✗）
            //    这里用**直接回调**（同页应用，不需要过 bridge ✓）
            this._bindAlertCallbacks(this.alertDialog);
        }
        this.alertDialog.setSymbol(this.options.symbol);
        this.alertDialog.setDecimals(this.ticketDecimals);
        this.alertDialog.setPrice(this.book.lastPrice ?? null);
        this.alertDialog.open();
    }

    private _bindAlertCallbacks(dialog: AlertDialog): void {
        dialog.onCreateCallback = (payload: Record<string, unknown>) => {
            this.options.onCommand?.('add_alert', {
                symbol: this.options.symbol, ...payload,
            });
        };
        dialog.onDeleteCallback = (id: unknown) => {
            this.options.onCommand?.('drop_alert', { id });
        };
    }

    // ------------------------------------------------------------ data
    /** Full replace (`replace=true`) or append/update the last bar. */
    /**
     * 把最后几根 **update** 进各个序列（增量，不重建 ✓）
     *
     * 返回 `false` = 没法增量（格子数不对 / 序列不支持 / 需要补历史），
     * 调用方退回全量 `setData`。
     */
    private _updateTail(tail: ChartBar[], changed: number): boolean {
        if (!tail.length || changed > 3) return false;   // 变化太多 → 全量更稳
        const toCandle = (bar: ChartBar) => ({
            time: bar.time as never,
            open: bar.open, high: bar.high, low: bar.low, close: bar.close,
        });
        const toVolume = (bar: ChartBar) => ({
            time: bar.time as never,
            value: bar.volume ?? 0,
            color: bar.close >= bar.open
                ? 'rgba(239,83,80,0.5)' : 'rgba(38,166,154,0.5)',
        });
        for (let index = 0; index < this.cells.length; index += 1) {
            const handler = this.cells[index] as unknown as {
                series?: { update?: Function };
                volumeSeries?: { update?: Function };
            };
            const series = handler.series;
            const volume = handler.volumeSeries;
            if (!series || typeof series.update !== 'function') return false;
            const cellData = this.cellBars[index] || [];
            // 多格：只更新「本格」那几根（`cellData` 里最后 changed 根）
            const rows = index === 0 ? tail : cellData.slice(-changed);
            if (!rows.length) continue;
            try {
                for (const bar of rows) {
                    series.update(toCandle(bar) as never);
                    volume?.update?.(toVolume(bar) as never);
                }
            } catch {
                return false;      // LWC 报错（时间倒序等）→ 全量兜底 ✓
            }
        }
        return true;
    }

    setBars(bars: ChartBar[], replace = false): void {
        if (this.replaying) return;       // 回放中：忽略实时推送 ✓
        if (replace) this.historyGrace = Date.now() + 900;
        // ★ 实时推送按**时间合并**（同一根替换、新的追加）——
        //   以前直接 `concat` 会出现重复时间戳，LWC 的 `setData` 要求时间严格递增，
        //   一重复就抛错 → 图表从此不再更新（用户实测 ✗）
        const before = this.bars.length;
        this.bars = replace ? bars.slice() : mergeBars(this.bars, bars);
        this.cellBars[0] = this.bars;
        this.vpOverlays[0]?.setBars(this.bars as never);
        // ★ 第 1 格的 K 线也交给图层（VP 横条要按"可视最后一根"定位 ✓；
        //   以前只在 `_applyCellBars()` 里同步，而 cell 0 走的是这里 ✗）
        try {
            (this.indicators as unknown as {
                setBars?: (rows: Array<{ time: number }>) => void;
            })?.setBars?.(this.bars);
        } catch { /* ignore */ }
        if (!this.handler) return;

        // ★ 增量：`replace=false` 时只 `series.update()` 变化的那几根
        //   （同 miniqt 的 `series.update(row)` —— 不再整表 setData，省一次全量 ✓）
        if (!replace) {
            const tail = this.bars.slice(-Math.max(1, bars.length));
            if (this._updateTail(tail, bars.length)) {
                this._setSeriesData();
                this._updateLegend(this.bars[this.bars.length - 1]);
                this._refreshLiveTables();
                return;
            }
        }
        void before;
        const series = this.handler.series as unknown as { setData: Function; update: Function };
        const volume = (this.handler as unknown as { volumeSeries: unknown }).volumeSeries as
            unknown as { setData: Function; update: Function } | undefined;
        const candles = this.bars.map((bar) => ({
            time: bar.time as never,
            open: bar.open, high: bar.high, low: bar.low, close: bar.close,
        }));
        const volumes = this.bars.map((bar) => ({
            time: bar.time as never,
            value: bar.volume ?? 0,
            color: bar.close >= bar.open ? 'rgba(239,83,80,0.5)' : 'rgba(38,166,154,0.5)',
        }));
        for (let index = 0; index < this.cells.length; index += 1) {
            const handler = this.cells[index];
            const cellData = this.cellBars[index] || [];
            const cellCandles = cellData.map((bar) => ({
                time: bar.time as never,
                open: bar.open, high: bar.high, low: bar.low, close: bar.close,
            }));
            const cellVolumes = cellData.map((bar) => ({
                time: bar.time as never, value: bar.volume ?? 0,
                color: bar.close >= bar.open
                    ? 'rgba(239,83,80,0.5)' : 'rgba(38,166,154,0.5)',
            }));
            const eachSeries = handler.series as unknown as {
                setData: Function };
            const eachVolume = (handler as unknown as {
                volumeSeries?: { setData: Function } }).volumeSeries;
            eachSeries.setData((cellData.length ? cellCandles : candles) as never);
            eachVolume?.setData((cellData.length ? cellVolumes : volumes) as never);
        }
        void series; void volume;
        this._setSeriesData();
        this._updateLegend(this.bars[this.bars.length - 1]);
        this._placePositionBadge();
        // ★ 初始 TqSdk 可能先给 2 根占位 K 线，随后 full replace 才补齐；
        //   这时必须重新 fit，否则可视范围还停在之前那 2 根（用户实测 ✗）
        if (replace && this.bars.length > before + 1) {
            this.needsFit = true;
            this._fitIfNeeded();
        }
        this._refreshLiveTables();
    }

    /** 实时 K 线更新时，没有鼠标时让 `tablestyle` 跟随最后一根 ✓ */
    private _refreshLiveTables(): void {
        if (this.replaying) return;
        const items = (this.cellItems[0] || []).filter(
            (item) => item.kind === 'table');
        if (!items.length) return;
        // 鼠标在历史某根上时，表格以鼠标为准；离开后由这里恢复实时 ✓
        if ([...this.tableMouseAt.values()].some((value) => value !== null)) {
            return;
        }
        const tail = this.bars[this.bars.length - 1];
        const barTime = Number(tail?.time) || 0;
        if (this.tableNewBarOnly) {
            if (barTime === this.tableBarTime) return;
            this.tableBarTime = barTime;
        } else {
            const now = Date.now();
            if (now - this.tableLiveAt < this.tableIntervalMs) return;
            this.tableLiveAt = now;
        }
        this._syncTableIndex(null, true);
    }

    /** 收藏列表（后端 `favorites` 补丁 → 工具栏下拉 ✓） */
    setFavorites(favorites: Array<Record<string, unknown>>,
                 strategies: Array<Record<string, unknown>> = []): void {
        this.options.favorites = favorites;
        this.options.strategyFavorites = strategies;
    }

    /** 「指标」下拉：★ 收藏指标 / 收藏策略 / ＋更多… / 添加个人…（同 miniqt ✓） */
    openIndicatorMenu(anchor: HTMLElement): void {
        const favorites = this.options.favorites || [];
        const strategies = this.options.strategyFavorites || [];
        const items = [
            { label: '收藏指标', disabled: true },
            ...favorites.map((row: Record<string, unknown>) => ({
                label: String(row.label || row.key),
                // ⚠ 收藏项的 `params` 是**参数表**（[{name, default}…]），
                //   不能当 dict 发（否则后端 `dict(list)` 会报
                //   `dictionary update sequence element #0 has length 4`）✓
                run: () => this.options.onAddIndicator?.(String(row.key), {}),
            })),
            { label: '收藏策略', disabled: true },
            ...(strategies.length ? strategies.map((row: Record<string, unknown>) => ({
                label: String(row.label || row.key),
                disabled: !row.path,
                run: () => this.options.onCommand?.('editor_add_indicator', {
                    path: String(row.path || ''),
                    symbol: this.symbolForCell(this.activeCell),
                    cell: this.activeCell,
                }),
            })) : [{ label: '（暂无）', disabled: true }]),
            { label: '＋ 更多指标和策略…', separator: true,
              run: () => this.options.onCommand?.('indicator_picker', {
                  symbol: this.symbolForCell(this.activeCell),
                  cell: this.activeCell }) },
            { label: '添加个人指标…',
              run: () => this.options.onCommand?.('pick_personal', {
                  kind: 'indicator' }) },
            { label: '添加个人策略…',
              run: () => this.options.onCommand?.('pick_personal', {
                  kind: 'strategy' }) },
            // 用户要求：在「添加个人策略」下面加「个人指标策略管理」✓
            { label: '个人指标策略管理…',
              run: () => this.options.onCommand?.('personal_menu', {}) },
            // ★ 策略管理：列出**所有图表（含多布局每格）**加载的策略 ✓
            { label: '策略管理…',
              run: () => this.options.onCommand?.('strategy_manage', {}) },
        ];
        showMenuBelow(anchor, items as never);
    }

    /** 「更多指标和策略…」选择器（pylightcharts `IndicatorPicker` ✓） */
    setPicker(payload: Record<string, unknown>): void {
        if (!this.indicatorPicker) {
            this.indicatorPicker = new IndicatorPicker({
                theme: this.options.theme === 'light' ? 'light' : 'dark',
            });
            this.indicatorPicker.onPickCallback = (item) => {
                this.options.onAddIndicator?.(item.key, {});
            };
            this.indicatorPicker.onFavoriteCallback = (item, on) => {
                this.options.onCommand?.('toggle_favorite', {
                    key: item.key, on, strategy: !!item.strategy,
                });
            };
            // ★ 二级筛选记住（下次打开还是「主图叠加」✓）
            this.indicatorPicker.onReloadCallback = () => {
                this.options.onCommand?.('indicator_picker', {
                    symbol: this.options.symbol, reload: true,
                });
            };
            this.indicatorPicker.onFilterCallback = (kind) => {
                this.indicatorFilter = kind;
                this.options.onCommand?.('set_setting', {
                    key: 'indicator_overlay_filter', value: kind,
                });
            };
        }
        this.indicatorPicker.setGroups((payload.groups || []) as never);
        this.indicatorPicker.setItems((payload.items || []) as never);
        this.indicatorPicker.setInfo(Number(payload.total || 0),
                                     String(payload.error || ''));
        this.indicatorPicker.setFavorites((payload.favorites || []) as never);
        this.indicatorPicker.setOverlayFilter(this.indicatorFilter);
        // 有收藏看收藏；没有收藏停在「全部指标」（「常用」组已删除 ✓）
        const favorites = (payload.favorites || []) as unknown[];
        this.indicatorPicker.open(favorites.length ? 'favorites' : 'all');
    }

    /** 「模板」对话框（pylightcharts `TemplatePicker` ✓） */
    openTemplatePicker(): void {
        if (!this.templatePicker) {
            this.templatePicker = new TemplatePicker({
                theme: this.options.theme === 'light' ? 'light' : 'dark',
            });
            this.templatePicker.onApplyCallback = (item) => {
                // ★ 以前只刷新模板列表，根本没有 apply（用户点了没反应 ✗）
                this.applyTemplate(String((item as { key?: string }).key
                    || (item as { name?: string }).name || ''));
            };
            this.templatePicker.onDeleteCallback = (key) => {
                this.options.onCommand?.('delete_template', { key });
            };
            this.templatePicker.onEditCallback = (row) => {
                this.editTemplateParams(row as unknown as
                    Record<string, unknown>);
            };
            this.templatePicker.onSaveCallback = (name) => {
                this.options.onCommand?.('save_template', {
                    symbol: this.options.symbol, name,
                    cell: this.activeCell,
                });
            };
        }
        this.templatePicker.open();
        this.options.onCommand?.('templates', {});
    }

    /** 模板列表 / 应用（后端 `templates` 补丁 ✓） */
    setTemplates(items: Array<Record<string, unknown>>): void {
        this.templateRows = Array.isArray(items) ? items.slice() : [];
        this.templatePicker?.setTemplates(items as never);
    }

    /** 应用模板（可带参数覆盖；作用在**当前格** ✓） */
    applyTemplate(key: string, params?: Record<string, Record<string, unknown>>): void {
        this.options.onCommand?.('apply_template', {
            symbol: this.options.symbol, key, params: params || {},
            cell: this.activeCell,
        });
    }

    /** 右键「保存当前指标模板」= 工具栏「保存当前指标为模板」✓ */
    saveCurrentTemplate(): void {
        const cell = this.activeCell;
        const symbol = this.symbolForCell(cell) || this.options.symbol;
        const fallback = `${symbol || '图表'} `
            + new Date().toLocaleString('zh-CN', { hour12: false })
                .slice(0, 16);
        const name = window.prompt('模板名称', fallback);
        if (name === null) return;              // 取消 ✓
        this.options.onCommand?.('save_template', {
            symbol, cell, name: String(name || '').trim(),
        });
    }

    /** 模板行上的「参数」按钮：把每个指标的参数摊平后编辑 ✓ */
    editTemplateParams(row: Record<string, unknown>): void {
        const items = (row.items || []) as IndicatorLine[];
        const flat: Record<string, unknown> = {};
        for (const item of items) {
            for (const [name, value] of Object.entries(item.params || {})) {
                flat[`${item.key}.${name}`] = value;
            }
        }
        if (!Object.keys(flat).length) {
            this.toast('这个模板没有可调参数');
            return;
        }
        openParamPopover(null, String(row.name || row.key), flat, (values) => {
            const overrides: Record<string, Record<string, unknown>> = {};
            for (const [compound, value] of Object.entries(values)) {
                const index = compound.lastIndexOf('.');
                if (index <= 0) continue;
                const key = compound.slice(0, index);
                const name = compound.slice(index + 1);
                overrides[key] = { ...(overrides[key] || {}), [name]: value };
            }
            this.applyTemplate(String(row.key || row.name), overrides);
        }, this.options.theme === 'light' ? 'light' : 'dark');
    }


    /** 按 `chartType` 重建每格的序列（蜡烛隐藏 / 换成线、面积、基准、柱 ✓） */
    private _applyChartType(): void {
        const kind = this.chartType;
        const pal = this.options.theme === 'light'
            ? { up: '#d93b3b', down: '#1f9d55', line: '#1a73e8' }
            : { up: '#ef5350', down: '#26a69a', line: '#4c8dff' };
        for (const handler of this.cells) {
            const h = handler as unknown as {
                chart: { addSeries: Function; removeSeries: Function };
                series: { applyOptions: Function; setData: Function };
            };
            const previous = this.typedSeries.get(handler);
            if (previous) {
                try {
                    h.chart.removeSeries(previous);
                } catch {
                    /* ignore */
                }
                this.typedSeries.delete(handler);
            }
            const candle = kind === 'candle' || kind === 'hollow';
            // 「设置 → 图表颜色」里的涨 / 跌色优先（空 = 跟主题 ✓）
            const up = this.customUp || pal.up;
            const down = this.customDown || pal.down;
            try {
                h.series.applyOptions({
                    visible: candle,
                    upColor: kind === 'hollow' ? 'rgba(0,0,0,0)' : up,
                    borderUpColor: up,
                    wickUpColor: up,
                    downColor: down,
                    borderDownColor: down,
                    wickDownColor: down,
                });
            } catch {
                /* ignore */
            }
            if (candle) {
                this._setSeriesData();
                continue;
            }
            let series: unknown = null;
            try {
                if (kind === 'line') {
                    series = h.chart.addSeries(LineSeries, {
                        color: pal.line, lineWidth: 2,
                        priceLineVisible: true, lastValueVisible: true,
                    });
                } else if (kind === 'area') {
                    series = h.chart.addSeries(AreaSeries, {
                        lineColor: pal.line, topColor: `${pal.line}66`,
                        bottomColor: `${pal.line}05`, lineWidth: 2,
                    });
                } else if (kind === 'baseline') {
                    series = h.chart.addSeries(BaselineSeries, {
                        baseValue: { type: 'price', price: this.bars.length
                            ? this.bars[0].close : 0 },
                        topLineColor: pal.up, topFillColor1: `${pal.up}55`,
                        topFillColor2: `${pal.up}08`,
                        bottomLineColor: pal.down,
                        bottomFillColor1: `${pal.down}08`,
                        bottomFillColor2: `${pal.down}55`,
                    });
                } else if (kind === 'bar') {
                    series = h.chart.addSeries(BarSeries, {
                        upColor: pal.up, downColor: pal.down,
                    });
                }
            } catch {
                series = null;
            }
            if (series) {
                this.typedSeries.set(handler, series);
            }
        }
        this._setSeriesData();
    }

    /** 把当前 `this.bars` 写到蜡烛 / 非蜡烛序列（类型切换后复用 ✓） */
    private _setSeriesData(): void {
        if (!this.handler) return;
        this.cells.forEach((handler, index) => {
            const data = this.cellBars[index] || [];
            const typed = this.typedSeries.get(handler) as unknown as
                { setData?: Function } | undefined;
            if (!typed?.setData) return;
            if (this.chartType === 'bar') {
                typed.setData(data.map((bar) => ({
                    time: bar.time as never, open: bar.open, high: bar.high,
                    low: bar.low, close: bar.close,
                })) as never);
            } else {
                typed.setData(data.map((bar) => ({
                    time: bar.time as never, value: bar.close,
                })) as never);
            }
        });
    }

    /** K 线类型：candle / hollow / line / area / baseline / bar ✓ */
    setChartType(kind: string): void {
        this.chartType = String(kind || 'candle');
        this._applyChartType();
    }

    get type(): string {
        return this.chartType;
    }

    /** 当前合约（切合约后也会变 ✓） */
    get symbol(): string {
        return this.options.symbol;
    }

    /** 工具栏「模板 → 我的模板」的列表（右键「我的模板」直接用 ✓） */
    private templateRows: Array<Record<string, unknown>> = [];

    /** 策略需要的最少格数（布局菜单：比它小的布局禁用 ✓） */
    private strategyCells = 0;

    /** 当前页面的策略名（`删除` 菜单里只显示一条 ✓） */
    private strategyName = '';

    /** 鼠标最后点击的格子（指标 / 策略命令按它走 ✓） */
    get activeCellIndex(): number {
        return this.activeCell;
    }

    /** 第 N 格当前合约（多布局各自不同 ✓） */
    symbolForCell(index = this.activeCell): string {
        return String(this.cellSymbols[index] || this.options.symbol || '');
    }

    // ------------------------------------------------------------- 键盘精灵
    /** 空格键 → 键盘精灵（搜指标 / 策略 / 合约 / 股票 ✓） */
    private _bindSpriteHotkey(): void {
        const handler = (event: KeyboardEvent) => {
            if (event.key !== ' ' && event.code !== 'Space') return;
            if (event.ctrlKey || event.altKey || event.metaKey) return;
            // 正在输入框里打字 → 空格就是空格 ✓
            if (isTypingTarget(event.target)) return;
            event.preventDefault();
            this.openSprite();
        };
        document.addEventListener('keydown', handler);
        this.spriteHotkey = handler;
    }

    /** 关闭键盘精灵，并清掉可能残留的遮罩 / 面板（切合约后尤其重要）✓ */
    closeSprite(): void {
        this.sprite?.close();
        document.querySelectorAll<HTMLElement>(
            '.desk-sprite-mask, .desk-sprite').forEach((node) => node.remove());
    }

    /** 打开键盘精灵（默认把当前输入/选中状态清空 ✓） */
    openSprite(text = ''): void {
        if (!this.sprite) {
            this.sprite = new KeyboardSprite({
                theme: this.options.theme === 'light' ? 'light' : 'dark',
                onQuery: (value: string) => {
                    this.options.onCommand?.('sprite_search', {
                        text: value, limit: 12,
                    });
                },
                onPick: (item: SpriteItem) => this.pickSprite(item),
            });
        }
        this.sprite.open(text);
    }

    /** 键盘精灵的搜索结果（后端 `{type:'sprite'}` 补丁 ✓） */
    setSpriteResults(items: Array<Record<string, unknown>>, hint = ''): void {
        this.sprite?.setResults(items as unknown as SpriteItem[], hint);
    }

    /** 选中一行：指标/策略 → 加到**鼠标最后点击的图**；合约 → 切到它 ✓ */
    pickSprite(item: SpriteItem): void {
        if (!item) return;
        if (item.kind === 'symbol') {
            const target = String(item.symbol || item.key || '');
            const cell = this.activeCell;
            const current = this.cellSymbols[cell] || this.options.symbol;
            if (!target || target === current) return;
            // 先关掉精灵；切换完成后 App 还会调用 resetForSymbol 再兜底清理 ✓
            this.closeSprite();
            // ★ 多布局：只换**鼠标最后点击的那一格**（`cell`）✓
            this.options.onCommand?.('switch_symbol', {
                from: this.options.symbol, to: target,
                name: item.name || '', cell,
                prev: current, multi: this.cells.length > 1,
                cells: this.cellSymbols.slice(),
            });
            return;
        }
        if (item.kind === 'strategy') {
            // 策略没法画在图上（和 miniqt 一样，只有指标能加 ✓）
            this.options.onToast?.(
                'warning', '个人策略不能画在图上（请用 Bt 运行）');
            return;
        }
        // 指标 → 加到鼠标最后点击的那张图（`focus_chart` 已记在后端 ✓）
        this.options.onAddIndicator?.(item.key, {});
    }

    /** 打开「商品搜索」（pylightcharts `SymbolSearch` ✓） */
    /** 空白图表提示（`openBlankChart()` 用 ✓） */
    setBlankHint(text: string): void {
        const hint = document.querySelector(
            `[data-blank="${this.options.symbol}"]`) as HTMLElement | null;
        if (hint) hint.textContent = text;
    }

    openSymbolSearch(target: 'chart' | 'trade' = 'chart'): void {
        this.searchFor = target;
        if (!this.symbolSearch) {
            // ★ 和 miniqt「商品代码搜索」一样：**全市场**（期货 / 股票 / 期权…）
            //   不再受报价页当前类型 / 交易所限制 ✓
            this.symbolSearch = new SymbolSearch({
                placeholder: '商品代码、名称（全市场：rb / 600000 / 00700 / AAPL）',
                markets: this.searchMarkets,
                market: this.searchMarket,
                remote: true,          // 合约太多 → 由后端搜 ✓
                theme: this.options.theme === 'light' ? 'light' : 'dark',
            });
            this.symbolSearch.onQueryCallback = (text: string) => {
                this.options.onCommand?.('symbol_search', {
                    text, market: this.searchMarket,
                });
            };
            this.symbolSearch.onMarketCallback = (market: string) => {
                this.searchMarket = market || '';
                this.options.onCommand?.('symbol_search', {
                    text: this.symbolSearch?.element
                        ? (this.symbolSearch as unknown as {
                            input?: HTMLInputElement }).input?.value || ''
                        : '',
                    market: this.searchMarket,
                });
            };
            this.symbolSearch.onPickCallback = (item: SearchItem) => {
                if (!item.symbol) return;
                if (this.searchFor === 'trade') {
                    // ★ 只换**交易标的**（图上合约不变 ✓）
                    this.setTradeSymbol(item.symbol);
                    return;
                }
                const cell = this.activeCell;
                const current = this.cellSymbols[cell] || this.options.symbol;
                if (item.symbol === current) return;
                // ★ 多布局：只换**鼠标最后点击的那一格**（`cell`）✓
                this.options.onCommand?.('switch_symbol', {
                    from: this.options.symbol, to: item.symbol,
                    name: item.name || '', cell,
                    prev: current, multi: this.cells.length > 1,
                    cells: this.cellSymbols.slice(),
                });
            };
        }
        this.symbolSearch.setTheme(
            this.options.theme === 'light' ? 'light' : 'dark');
        this.symbolSearch.setMarkets(this.searchMarkets, this.searchMarket);
        const current = this.cellSymbols[this.activeCell] || this.options.symbol;
        this.symbolSearch.open(this.searchFor === 'trade'
            ? (this.tradeSymbol || current)
            : current);
    }

    /** 交易面板切换标的（锁定 → 忽略；也会同步到后端 `focus_chart` ✓） */
    setTradeSymbol(symbol: string): void {
        if (!symbol || this.tradeLocked) return;
        if (symbol === this.tradeSymbol) return;
        this.tradeSymbol = symbol;
        this.ticket?.setSymbol(symbol);
        this.ticket?.setInfo(`交易标的 → ${symbol}`);
        // ★ 多布局点第 2/3 格时，价格框必须换成**那个合约**的最新价
        //   （以前只换标题、价格还是上一个合约的 → 用户实测 ✗）
        const price = this._priceOfSymbol(symbol);
        if (price !== null) {
            (this.ticket as unknown as {
                resetPrice?: (value: number | null) => void;
            })?.resetPrice?.(price);
        }
        this.book.setSymbol(symbol);
        this.options.onCommand?.('focus_chart', { symbol });
    }

    /** 某个合约的最新价（多格布局：取那一格的最后一根 K 线收盘 ✓） */
    private _priceOfSymbol(symbol: string): number | null {
        const index = this.cellSymbols.indexOf(symbol);
        if (index >= 0) {
            const bars = this.cellBars[index] || [];
            const tail = bars[bars.length - 1];
            const value = tail ? Number(tail.close) : NaN;
            if (Number.isFinite(value) && value > 0) return value;
        }
        if (!this.tradeSymbol || symbol === this.options.symbol) {
            return this._lastPriceValue();
        }
        return null;
    }

    /** 后端返回的搜索结果（全市场索引 ✓） */
    setSearchResults(items: Array<Record<string, unknown>>,
                     markets?: Array<{ key: string; label: string }>,
                     market = '', total = 0,
                     loading = false): void {
        if (markets && markets.length) {
            this.searchMarkets = markets;
            this.symbolSearch?.setMarkets(markets, market || this.searchMarket);
        }
        this.symbolSearch?.setResults(items as never);
        this.symbolSearch?.setHint(
            loading
                ? '正在建立全市场索引…（先搜缓存里的合约）'
                : (total ? `全市场 ${total} 个合约 · ↑↓ 选择 · Enter 打开`
                    : '↑↓ 选择 · Enter 打开 · Esc 关闭'));
    }

    /** 索引建好（后端 `symbol_index` 补丁）→ 只更新 chips / 提示 ✓ */
    setSearchMarkets(markets?: Array<{ key: string; label: string }>,
                     total = 0): void {
        if (markets && markets.length) this.searchMarkets = markets;
        this.symbolSearch?.setMarkets(this.searchMarkets, this.searchMarket);
        if (total) {
            this.symbolSearch?.setHint(
                `全市场 ${total} 个合约 · ↑↓ 选择 · Enter 打开`);
        }
    }

    /** 切换合约前：把上一个合约的**所有图元 / 缓存**清干净 ✓
     *
     * 只 resetIndicators 不够：持仓线 / 预警线 / 挂单线 / 旧 K 线 / 旧价格线
     * 都会留到新合约上（用户实测：ag 切换后旧价位还有一条虚线 ✗）。
     */
    resetForSymbol(): void {
        // 切合约时键盘精灵可能还开着 → 旧输入框 / 遮罩必须一起清掉 ✓
        this.closeSprite();
        // 旧回放时钟 / 旧回放数据必须停掉，否则它会继续把旧 K 线写回来 ✗
        if (this.replaying || this.replay?.active) {
            this.exitReplay();
        }
        // 旧 K 线的蜡烛 / 成交量 / 最后价格线全部清空；等后端新补丁
        this.bars = [];
        for (let index = 0; index < this.cellBars.length; index += 1) {
            this.cellBars[index] = [];
            this.cellItems[index] = [];
            this.cellStrategy[index] = '';
        }
        for (let index = 0; index < this.cells.length; index += 1) {
            const handler = this.cells[index] as unknown as {
                series?: { setData?: Function };
                volumeSeries?: { setData?: Function };
                chart?: { panes?: () => Array<{ getHTMLElement?: Function }> };
            };
            try { handler.series?.setData?.([]); } catch { /* ignore */ }
            try { handler.volumeSeries?.setData?.([]); } catch { /* ignore */ }
        }
        this._clearAlertLines();
        this.alertItems = [];
        this.alertDialog?.setItems([]);
        this._clearOrderLines();
        this.orderItemsByCell.clear();
        this.hidePositionLine();
        this.lastPositions.clear();
        this.ticketNet = 0;
        this.ticket?.setNet(0);
        this.setPosition({});
        this.legendItems = [];
        this._renderLegendRows(0);
        // 线 / 面积 / 基准 / 柱这些“非蜡烛”序列也要清空（typedSeries）
        try { this._setSeriesData(); } catch { /* ignore */ }
        try {
            const box = (this.handler as unknown as {
                toolBox?: { clearDrawings?: Function } } | null)?.toolBox;
            box?.clearDrawings?.();
        } catch { /* ignore */ }
    }

    /** 切换合约（后端 `switch_symbol` 补丁 → 这里只改标题 ✓） */
    /** 只刷新工具栏商品搜索按钮（不改变 tab 的主合约 ✓） */
    private _setSymbolButton(symbol: string, name = ''): void {
        if (!this.symbolButton) return;
        this.symbolButton.textContent = `${symbol} 🔍`;
        if (name) {
            const span = document.createElement('span');
            span.className = 'desk-muted';
            span.textContent = ` ${name}`;
            this.symbolButton.appendChild(span);
        }
    }

    setSymbol(symbol: string, name = ''): void {
        this.options.symbol = symbol;
        this.options.name = name;
        this.activeCell = 0;
        this._setSymbolButton(symbol, name);
        this.book.setSymbol(symbol);
    }

    /** 布局多图：后端 `{type:'layout'}` 补丁 → 网格 + 每格合约 ✓ */
    applyLayout(payload: {
        cols?: number; rows?: number; symbols?: string[];
        count?: number; key?: string;
    }): void {
        const symbols = (payload.symbols || []).map(String);
        // ★ `count` = 策略需要的合约数（2 → 左右两图 / 3 → 横排三图）。
        //   以前只改 `this.layout` 但没改 `this.spec` → `_buildCells()`
        //   仍按旧布局（单图）建格，导致第二格根本不存在 ✗
        const count = Math.max(1, Number(payload.count)
            || symbols.length || (Number(payload.cols) || 1)
                * (Number(payload.rows) || 1));
        // ★ `payload.key` 可能是**用户保存的布局 key**（如「布局1」），
        //   不是 `single/h2/h3/grid4` 预设 → 不能直接 `layoutSpecByKey`
        //   （它找不到会回退 single，导致 2 格布局只显示 1 张图 ✗）。
        const preset = payload.key
            ? DESK_LAYOUTS.find((item) => item.key === String(payload.key))
            : undefined;
        const spec = preset || (payload.count !== undefined
            ? layoutSpecForCount(count)
            : layoutSpecOf(Number(payload.cols) || 1,
                           Number(payload.rows) || 1));
        this.spec = spec;
        const cols = Math.max(1, spec.cols);
        const rows = Math.max(1, spec.rows);
        const keepBars = this.cellBars.map((bars) => bars.slice());
        this.layout = { cols, rows };
        this._buildCells();
        symbols.forEach((symbol, index) => {
            if (index < this.cellSymbols.length) this.cellSymbols[index] = symbol;
        });
        this.activeCell = 0;
        this._setSymbolButton(this.cellSymbols[0] || this.options.symbol);
        this._buildLegend();          // 标题用新的合约 ✓
        keepBars.forEach((bars, index) => {
            if (index < this.cellBars.length && bars.length) {
                this.cellBars[index] = bars;
            }
        });
        this._applyChartType();
        this.resize();
        this._refreshDrawings();
    }

    /** 第 N 格的 K 线（后端 `{type:'kline', cell:n}` ✓） */
    setCellBars(index: number, bars: ChartBar[], replace = true): void {
        const cell = Math.max(0, Math.min(Number(index) || 0,
                                         this.cells.length - 1));
        if (cell === 0) {
            this.setBars(bars, replace);
            return;
        }
        this.cellBars[cell] = replace ? bars.slice()
            : (this.cellBars[cell] || []).concat(bars);
        this._applyCellBars(cell);
        const list = this.cellBars[cell] || [];
        const tail = list[list.length - 1];
        this._updateLegend(tail, cell);
        // ★ 这一格的 K 线变了 → 持仓色块 / 挂单色块重新贴高度（每格各自量 ✓）
        this._placePositionBadge();
        this._stackLineBadges();
        // ★ 这一格正是**交易标的** → 价格框跟着它的最新价（用户手填过不动 ✓）
        if (tail && this.cellSymbols[cell] === this.tradeSymbol) {
            const close = Number(tail.close);
            if (Number.isFinite(close) && close > 0) {
                this.ticket?.setPrice(close);
            }
        }
    }

    private _applyCellBars(index: number): void {
        const handler = this.cells[index];
        if (!handler) return;
        const data = this.cellBars[index] || [];
        const candles = data.map((bar) => ({
            time: bar.time as never,
            open: bar.open, high: bar.high, low: bar.low, close: bar.close,
        }));
        const volumes = data.map((bar) => ({
            time: bar.time as never, value: bar.volume ?? 0,
            color: bar.close >= bar.open
                ? 'rgba(239,83,80,0.5)' : 'rgba(38,166,154,0.5)',
        }));
        // ★ 把 K 线交给该格图层（VP 横条要贴"可视最后一根"✓）
        try {
            (this.layers[index] as unknown as {
                setBars?: (rows: Array<{ time: number }>) => void;
            })?.setBars?.(data);
        } catch { /* ignore */ }
        const series = handler.series as unknown as { setData: Function };
        const volume = (handler as unknown as {
            volumeSeries?: { setData: Function } }).volumeSeries;
        series.setData(candles as never);
        volume?.setData(volumes as never);
        this._setSeriesData();
    }

    // ------------------------------------------------------------- 回放
    // ------------------------------------------------------------- 回放
    /** 「回放」按钮：没在回放 → 进入；在回放 → 回到实时 ✓ */
    toggleReplay(): void {
        if (this.replaying) {
            this.exitReplay();
            return;
        }
        this.startReplay();
    }

    /**
     * 请求一段回放（后端算好整段数据交给前端逐根播 ✓）
     *
     * `seek` = 从哪开始（0.3 = 30%，miniqt 同款）；`cycle` / `symbol` 用来
     * 「选择合约 / 更换周期」后重新回放 ✓
     */
    startReplay(options: {
        seek?: number; cycle?: number; symbol?: string; count?: number;
    } = {}): void {
        this.replayViewLengths = [];      // 新一段回放 → 重新摆窗口 ✓
        this.replaySeek = options.seek !== undefined
            ? options.seek : this.replaySeek;
        if (options.cycle) this.replayCycle = options.cycle;
        this.options.onCommand?.('replay', {
            symbol: options.symbol || this.options.symbol,
            cycle: this.replayCycle || this.cycle,
            count: options.count || this.replayCount,
            seek: this.replaySeek,
            speed: this.replaySpeed,
        });
    }

    /** 进入回放（后端 `{type:'replay'}`；带 `indicators` 就一起回放 ✓） */
    setReplay(payload: {
        bars?: ReplayBar[]; speed?: number; seek?: number;
        indicators?: IndicatorLine[]; symbol?: string;
        cells?: Array<{ cell?: number; bars?: ReplayBar[];
                        indicators?: IndicatorLine[]; symbol?: string }>;
    }): void {
        const bars = payload.bars || [];
        if (!bars.length) return;
        this.replayIndicators = payload.indicators || [];
        this.replaySymbol = String(payload.symbol || this.options.symbol);
        // ★ 多图回放：每格自己的 bars / 指标（后端已对齐长度 ✓）
        this.replayCells = (payload.cells || []).map((item, index) => ({
            cell: Number(item.cell ?? index),
            bars: item.bars || [],
            indicators: item.indicators || [],
        }));
        if (!this.replay) {
            this.replay = new Replay({
                onBars: (visible, finished) => {
                    // 只有引擎真的装着数据才算「回放中」——否则 `stop()`
                    // 的那次空回调会把「已退出」又翻回「回放中」✗
                    this.replaying = !!this.replay?.active;
                    const step = visible.length;
                    this.cellBars[0] = visible.slice();
                    this.bars = visible.slice();
                    // 其它格跟着同一个「步数」走（各播各的合约 ✓）
                    for (let index = 1; index < this.cells.length; index += 1) {
                        const cell = this.replayCells[index];
                        this.cellBars[index] = cell
                            ? cell.bars.slice(0, step) : [];
                    }
                    // ★ 回放是直接改 `cellBars`（不走 `setBars`，否则被
                    //   `replaying` 拦掉）—— 以前只 `_setSeriesData()` 刷
                    //   指标型序列，**蜡烛图从来不动**，所以“回放不会按
                    //   初始比例截取 K 线”（用户实测 ✗）。
                    for (let index = 0; index < this.cells.length; index += 1) {
                        this._applyCellBars(index);
                    }
                    this._applyChartType();
                    this._applyReplayIndicators();
                    // ★ 表格（`tablestyle`）也要跟着回放走：
                    //   按**当前回放最后一根**的行号重算（不能用鼠标那个 ✓）
                    this._syncTableIndex(Math.max(0, visible.length - 1));
                    this._syncReplayViewport(visible.length, false);
                    // ★ 回放价 → 后端本地模拟账户（成交 / 盈亏按回放价 ✓）
                    const tailBar = visible[visible.length - 1];
                    this.ticket?.setPrice(
                        tailBar ? Number(tailBar.close) : null);
                    if (tailBar && Number(tailBar.close) > 0) {
                        this.options.onCommand?.('replay_price', {
                            symbol: this.options.symbol,
                            price: Number(tailBar.close),
                            time: tailBar.time,
                        });
                    }
                    if (finished) {
                        if (this.replayLabel) {
                            this.replayLabel.textContent =
                                `回放结束（${visible.length} 根）`;
                        }
                        this.toast('回放结束，已切回实时');
                        this.options.onCommand?.('replay_exit', {
                            symbol: this.options.symbol,
                        });
                    }
                },
                onState: (state) => this._syncReplayBar(state),
            });
            this._ensureReplayBar();
        }
        this.replaying = true;
        this.replayViewLengths = [];
        this.needsFit = false;            // 回放自己摆窗口，别再 fit ✗
        this._saveViewRanges();           // ★ 记住进回放前的可视范围 ✓
        this._ensureDockTicket(true);         // ★ 交易账户换成「本地模拟交易」✓
        this.replaySpeed = Number(payload.speed) || this.replaySpeed || 5;
        // ★ 后端回传的 seek 优先（`选择时间段` / 「从 60% 开始」要生效 ✓）
        if (Number.isFinite(Number(payload.seek))) {
            this.replaySeek = Number(payload.seek);
        }
        this.replay.load(bars, this.replaySpeed, this.replaySeek);
        this.replay.start();
        this._syncReplayButton();
    }

    /**
     * 回放工具条（底部，**复刻 miniqt** ✓）
     *
     * 从左到右：``[选择K线 ▾] [▶ 播放] [↦ 前进] [1x ▾] [1分 ▾] … [rewind 实时]``
     *
     * * 选择K线 → 二级菜单「选择合约 / 选择时间段（10%–90%）」；
     * * 播放 / 暂停、前进一根、速度（0.5x/1x/2x/4x）、更换周期；
     * * 最后的 rewind 图标 = 跳转到实时图表（退出回放）✓
     */
    private _ensureReplayBar(): void {
        if (this.replayBar) return;
        const bar = document.createElement('div');
        bar.className = 'desk-replay-bar';

        // ① 选择K线 ▾（合约 / 时间段）
        const select = document.createElement('button');
        select.className = 'desk-tool desk-tool-arrow';
        select.title = '选择K线（合约 / 时间段）';
        const selectLabel = document.createElement('span');
        selectLabel.className = 'desk-tool-label';
        selectLabel.textContent = '选择K线';
        const selectCaret = document.createElement('span');
        selectCaret.className = 'desk-tool-caret';
        selectCaret.textContent = '▾';
        select.append(selectLabel, selectCaret);
        select.addEventListener('click', () => {
            const contracts = this.cellSymbols.map((symbol, index) => ({
                label: `${index + 1}. ${symbol}`,
                run: () => this.startReplay({ symbol, seek: 0.3 }),
            }));
            showMenuBelow(select, [
                {
                    label: '选择合约',
                    submenu: contracts.length ? contracts
                        : [{ label: this.options.symbol, disabled: true }],
                },
                {
                    label: '选择时间段',
                    submenu: REPLAY_SEEKS.map((fraction) => ({
                        label: `从 ${Math.round(fraction * 100)}% 处开始`,
                        run: () => this.startReplay({ seek: fraction }),
                    })),
                },
            ]);
        });

        // ② 播放 / 暂停
        const play = document.createElement('button');
        // 和右上「退出回放（rewind）」按钮同款：`desk-tool-replay` 负责描边/高亮 ✓
        play.className = 'desk-tool desk-tool-replay desk-replay-play';
        play.innerHTML = ICON_PLAY;
        play.title = '播放 / 暂停';
        play.addEventListener('click', () => {
            if (this.replay?.isPlaying) this.replay.pause();
            else this.replay?.start();
        });
        this.replayPlayButton = play;

        // ③ 前进一根
        const step = document.createElement('button');
        step.className = 'desk-tool';
        step.innerHTML = ICON_STEP;
        step.title = '前进一根';
        step.addEventListener('click', () => this.replay?.step());

        // ④ 速度 ▾
        const speed = document.createElement('button');
        speed.className = 'desk-tool desk-tool-arrow';
        speed.title = '回放速度';
        const speedLabel = document.createElement('span');
        speedLabel.className = 'desk-tool-label';
        speedLabel.textContent = this._speedText(this.replaySpeed);
        const speedCaret = document.createElement('span');
        speedCaret.className = 'desk-tool-caret';
        speedCaret.textContent = '▾';
        speed.append(speedLabel, speedCaret);
        speed.addEventListener('click', () => {
            showMenuBelow(speed, REPLAY_SPEEDS.map(([label, perSecond]) => ({
                label,
                run: () => {
                    this.replaySpeed = perSecond;
                    speedLabel.textContent = label;
                    this.replay?.setSpeed(perSecond);
                },
            })));
        });

        // ⑤ 更换周期 ▾（换完重新从 30% 开始 ✓）
        const cycle = document.createElement('button');
        cycle.className = 'desk-tool desk-tool-arrow';
        cycle.title = '更换周期';
        const cycleLabel = document.createElement('span');
        cycleLabel.className = 'desk-tool-label';
        cycleLabel.textContent = this._cycleText(this.replayCycle || this.cycle);
        const cycleCaret = document.createElement('span');
        cycleCaret.className = 'desk-tool-caret';
        cycleCaret.textContent = '▾';
        cycle.append(cycleLabel, cycleCaret);
        cycle.addEventListener('click', () => {
            showMenuBelow(cycle, REPLAY_CYCLES.map((item) => ({
                label: item.label,
                run: () => {
                    this.replayCycle = item.cycle;
                    cycleLabel.textContent = item.label;
                    this.startReplay({ cycle: item.cycle, seek: 0.3 });
                },
            })));
        });
        this.replayCycleLabel = cycleLabel;

        // ⑥ 进度文字
        this.replayLabel = document.createElement('span');
        this.replayLabel.className = 'desk-muted';
        this.replayLabel.textContent = '回放中…';

        // ⑦ 跳转到实时图表（rewind 图标 ✓）
        const exit = document.createElement('button');
        exit.className = 'desk-tool desk-tool-replay on';
        exit.title = '跳转到实时图表（退出回放）';
        exit.innerHTML = REWIND_SVG;
        exit.addEventListener('click', () => this.exitReplay());

        bar.append(select, play, step, speed, cycle, this.replayLabel, exit);
        this.element.insertBefore(bar, this.dock.element);
        this.replayBar = bar;
    }

    /** 速度数值 → 显示文字（`5` → `1x` ✓） */
    private _speedText(perSecond: number): string {
        const found = REPLAY_SPEEDS.find(([, value]) => value === perSecond);
        return found ? found[0] : '1x';
    }

    /** 回放按钮的选中态（回放中高亮 ✓） */
    private _syncReplayButton(): void {
        this.playButton?.classList.toggle('on', this.replaying);
        if (this.playButton) {
            this.playButton.title = this.replaying
                ? '回到实时（再点一次）' : '回放：逐根播放历史 K 线';
        }
    }

    private _syncReplayBar(state: { playing: boolean; index: number; total: number }): void {
        if (!this.replayBar) return;
        this.replayBar.classList.toggle('on', this.replaying);
        if (this.replayPlayButton) {
            this.replayPlayButton.innerHTML = state.playing
                ? ICON_PAUSE : ICON_PLAY;
            this.replayPlayButton.classList.toggle('on', state.playing);
        }
        if (this.replayLabel) {
            const percent = state.total
                ? Math.round((state.index / state.total) * 100) : 0;
            this.replayLabel.textContent = `${state.playing ? '回放中' : '已暂停'}`
                + ` · ${state.index}/${state.total}（${percent}%）`;
        }
        this._syncReplayButton();
    }

    get isReplaying(): boolean {
        return this.replaying;
    }

    /** 回放指标：只画到「当前可见最后一根」为止（和 K 线同步 ✓） */
    /**
     * 回放视窗：首次 / seek 时把可见范围**收到当前切片长度**，之后播放
     * 每加一根只滚动到最新（不重新缩放，否则会越播越小 ✗）。
     */
    /**
     * 回放时的视窗：**可视根数不变、最新 K 线到右边的距离也不变** ✓
     *
     * 以前简单地 `range.from+1 / range.to+1`：LWC 在 `setData` 之后本来就会
     * 把视窗**锚在右边**（多一根就自动右移一格），再手动 +1 就变成「整体向左
     * 滑、右边越来越空、可视根数越来越少」（用户实测 ✗）。
     *
     * 现在显式计算：`可视根数` 和 `右端空隙` 都沿用上一帧的值，只是整体跟着
     * 最新一根移动 —— 等价于「更新一根，左边少一根」✓
     */
    /**
     * 回放视窗（P60 重写，和 miniqt / 本地图表一致 ✓）
     *
     * **播放中不再改视窗** —— LWC 自己会在新 K 线到达时按 `rightOffset`
     * 自动右移（`shiftVisibleRangeOnNewBar` 默认 true）：
     * 最新一根到右边的距离、可视根数都不变 ✓；
     * 用户拖动 / 缩放后也不会被强行拉回来（以前每拍
     * `setVisibleLogicalRange` → 永远贴右边，用户实测 ✗）。
     *
     * 只在**首次 / seek** 时给一个初始窗口：最近 `REPLAY_WINDOW` 根 + 右侧留白。
     */
    private _syncReplayViewport(_length: number, reset = false): void {
        const previous = this.replayViewLengths;
        const next: number[] = [];
        this.cells.forEach((handler, index) => {
            const bars = this.cellBars[index] || [];
            const current = bars.length;
            const prev = previous[index] || 0;
            const scale = (handler as unknown as {
                chart?: { timeScale?: () => {
                    setVisibleLogicalRange?: (range: {
                        from: number; to: number }) => void;
                } };
            }).chart?.timeScale?.();
            const setRange = scale?.setVisibleLogicalRange;
            if (!setRange) {
                next[index] = current;
                return;
            }
            // 只有「第一次」或「seek/换周期」才摆窗口：整段 + 右侧留白 ✓
            if (reset || prev === 0 || Math.abs(current - prev) > 1) {
                const apply = () => {
                    try {
                        setRange.call(scale, {
                            from: Math.max(-0.5, current - REPLAY_WINDOW),
                            to: current - 1 + REPLAY_PADDING,
                        });
                    } catch {
                        /* ignore */
                    }
                };
                apply();
                // 页面刚挂载时宽度可能还是 0 → 下一帧再摆一次 ✓
                const raf = (globalThis as unknown as {
                    requestAnimationFrame?: (cb: () => void) => number;
                }).requestAnimationFrame;
                if (typeof raf === 'function') raf(() => apply());
            }
            next[index] = current;
        });
        this.replayViewLengths = next;
    }

    private _applyReplayIndicators(): void {
        for (let index = 0; index < this.cells.length; index += 1) {
            const source = this.replayCells[index];
            const items = index === 0
                ? this.replayIndicators : (source?.indicators || []);
            const bars = this.cellBars[index] || [];
            const head = bars[0];
            const tail = bars[bars.length - 1];
            const first = head ? Number(head.time) : Infinity;
            const last = tail ? Number(tail.time) : -Infinity;
            this.setCellIndicators(index, {
                type: 'indicator',
                symbol: this.replaySymbol,
                items: items.map((item) => {
                    const rows = (item as unknown as { shapeRows?: Array<{
                        time?: number }> }).shapeRows;
                    const markers = (item as unknown as {
                        markers?: NonNullable<IndicatorLine['markers']>;
                    }).markers;
                    const inside = (time?: number) => {
                        const value = Number(time);
                        return value >= first && value <= last;
                    };
                    return {
                        ...item,
                        // ★ 必须**同时**裁掉左右两边：指标是在更长的一段 K 线上
                        //   算出来的，只裁 `<= last` 会让指标比 K 线左右都长 ✗
                        data: (item.data || []).filter(([time]) =>
                            Number(time) >= first && Number(time) <= last),
                        // 未来信号不能留给 LWC 自动钉在最新一根 ✓
                        ...(rows ? {
                            shapeRows: rows.filter((row) => inside(row.time)),
                        } : {}),
                        ...(markers ? {
                            markers: markers.filter((row) => inside(row.time)),
                        } : {}),
                    };
                }),
            });
        }
        // ★ 表格（`tablestyle`）跟着回放走：按回放最后一根重算 ✓
        if (this.replaying) {
            const shown = (this.cellBars[0] || this.bars || []).length;
            this._syncTableIndex(Math.max(0, shown - 1));
        }
    }

    /** 退出回放：清掉回放指标、恢复实时指标 ✓ */
    exitReplay(): void {
        this.replaying = false;
        this.replayViewLengths = [];
        this.replayIndicators = [];
        this.replayCells = [];
        this.replay?.stop();
        this.replayBar?.classList.remove('on');
        this._syncReplayButton();
        this.tableMouseAt.clear();             // ★ 表格回到实时（最后一根 ✓）
        this._syncTableIndex(null);
        this._ensureDockTicket(false);         // 交易账户回到天勤 ✓
        this._restoreViewRangesSoon();    // ★ 恢复进回放前的可视范围 ✓
        this.options.onCommand?.('replay_exit', { symbol: this.options.symbol });
    }

    // ------------------------------------------------------------- 删除 / 联动 / 持仓线
    /** 「🗑」删除菜单 —— 复刻 miniqt「删除指标策略」菜单 ✓
     *
     * 菜单按**格（多布局）**分组列出每个指标（一个指标可能有多条线，按
     * `source` 归组 ✓），点一下删这一个；最后一行「删除全部指标」清空整页。
     */
    openRemoveMenu(anchor: HTMLElement): void {
        const items: MenuItem[] = [];
        // ★ 策略是**页面级**的（不属于某一格）→ 菜单里只出现一次；
        //   点它 = 删除策略（和「策略管理」里的删除等效 ✓）
        const strategy = this.strategyName
            || this.cellStrategy.find((name) => !!name) || '';
        if (strategy) {
            items.push({
                label: `策略 · ${strategy}（删除）`,
                run: () => this.removeStrategy(this.activeCell),
            });
        }
        let total = 0;
        this.cellItems.forEach((list, cell) => {
            const seen = new Map<string, string>();
            for (const item of list || []) {
                const key = String(item.key || '');
                // 策略线不按格列（上面那条统一删 ✓）
                if (key.startsWith('st:') || key.startsWith('editor:')) continue;
                const source = String(item.source || key.split(':')[0]);
                if (seen.has(source)) continue;
                seen.set(source, this._sourceLabel(source, item.label));
            }
            if (!seen.size) return;
            total += seen.size;
            items.push({
                label: this._cellTitle(cell),
                disabled: true,
                separator: true,
            });
            let index = 0;
            for (const [source, label] of seen) {
                index += 1;
                items.push({
                    label: `${index}  ${label}`,
                    run: () => this.removeIndicator(source, cell),
                });
            }
        });
        if (!total && !strategy) {
            items.push({ label: '（本页还没有指标）', disabled: true });
        } else if (total) {
            items.push({ label: '删除全部指标（保留策略）', separator: true,
                run: () => this.clearIndicators() });
        }
        showMenuBelow(anchor, items);
    }

    /** 删掉某格上的策略（指标保留 ✓） */
    removeStrategy(cell = 0): void {
        // `symbol` 必须是 tab key；格子的合约只用来定位 cell ✓
        const symbol = this.options.symbol;
        this.options.onCommand?.('remove_strategy', { symbol, cell });
        // 本地先撤掉（后端补丁回来后再对齐 ✓）
        const keep = (this.cellItems[cell] || []).filter((item) => {
            const key = String(item.key);
            return !(key.startsWith('st:') || key.startsWith('editor:'));
        });
        this.cellItems[cell] = keep;
        this.cellStrategy[cell] = '';
        if (cell === 0) this.legendItems = keep;
        const layer = this.layers[cell];
        try {
            layer?.removeSource?.('st');
            layer?.removeSource?.('editor');
            layer?.apply({
                type: 'indicator', symbol: this.options.symbol,
                items: this._drawItems(cell, keep),
            } as never);
        } catch { /* ignore */ }
        this._renderLegendRows(cell);
    }

    /** 右键「显示全部 K 线」：按格自适应 ✓ */
    fitAllBars(cell = -1): void {
        const index = cell >= 0 ? cell
            : Math.max(0, this.cells.indexOf(this.handler as never));
        const scale = (this.cells[index] as unknown as {
            chart?: { timeScale?: () => { fitContent?: () => void } };
        })?.chart?.timeScale?.();
        try {
            scale?.fitContent?.();
        } catch { /* ignore */ }
    }

    /** 右键「只显示最近 N 根」✓ */
    showLastBars(count = 300, cell = -1): void {
        const index = cell >= 0 ? cell
            : Math.max(0, this.cells.indexOf(this.handler as never));
        const bars = this.cellBars[index] || [];
        const total = bars.length;
        if (!total) return;
        const scale = (this.cells[index] as unknown as {
            chart?: { timeScale?: () => { setVisibleLogicalRange?: Function } };
        })?.chart?.timeScale?.();
        try {
            scale?.setVisibleLogicalRange?.({
                from: Math.max(0, total - count), to: total + 2 });
        } catch { /* ignore */ }
    }

    /** 指标 key → 菜单上的一行文字（`pta_macd` → `pta.macd` ✓） */
    private _sourceLabel(source: string, fallback?: string): string {
        const text = String(source || '');
        if (text.startsWith('tv:')) return text.slice(3);
        if (text.startsWith('pi:')) return text.slice(3);
        const cut = text.indexOf('_');
        if (cut > 0 && cut < text.length - 1) {
            return `${text.slice(0, cut)}.${text.slice(cut + 1)}`;
        }
        return text || String(fallback || '');
    }

    /** 菜单里的格标题：`格 1 · SHFE.ag2612` ✓ */
    private _cellTitle(cell: number): string {
        const name = String(this.cellSymbols[cell] || this.options.symbol || '');
        const index = cell + 1;
        if (this.cellItems.length <= 1) return `格 ${index} · ${name}`;
        return `格 ${index} · ${name}`;
    }

    /** 删某格的某个指标（`source` = 目录 key，不是线 key ✓） */
    removeIndicator(source: string, cell = 0): void {
        // ★ 后端按 tab key 找图表；格子合约（如 au）不是 tab key ✗
        this.options.onCommand?.('remove_indicator', {
            symbol: this.options.symbol, key: source, cell,
        });
        // 本格立即先撤掉（后端补丁回来后再对齐 ✓）
        const layer = this.layers[cell] || this.indicators;
        try {
            layer.removeSource?.(source);
        } catch { /* ignore */ }
        // 图例 / 隐藏状态用的 `cellItems` 也要同步，否则菜单还列着它 ✗
        const keep = (this.cellItems[cell] || []).filter((item) =>
            (item.source || String(item.key).split(':')[0]) !== source);
        this.cellItems[cell] = keep;
        if (cell === 0) this.legendItems = keep;
        this._renderLegendRows(cell);
    }

    /** 「🗑」删除本图全部指标 ✓ */
    clearIndicators(): void {
        this.options.onCommand?.('remove_indicator', {
            symbol: this.options.symbol, key: '*', cell: this.activeCell,
        });
    }

    /** 「🧹」清除全部画线（含副图）✓ */
    clearDrawings(): void {
        // ★ 只清**当前格**这个键（合约|周期）：同键的格一起清，
        //   别的合约 / 别的周期的画线不动 ✓
        this._drawings().clear(this._drawingKey());
    }

    /** 工具栏「买卖盘」→ 图上浮动买卖盘 ✓ */
    toggleOrderTicket(visible?: boolean): boolean {
        this.orderTicketVisible = visible === undefined
            ? !this.orderTicketVisible : !!visible;
        this.ticketButton?.classList.toggle('on', this.orderTicketVisible);
        if (this.orderTicketVisible) this._ensureOrderTicket();
        else this.orderTicket?.classList.remove('on');
        return this.orderTicketVisible;
    }

    /**
     * 买卖盘数据（二级报价 5 档 → 取买一 / 卖一 ✓）
     *
     * 形态和 **minibt 实时图**一致：`买入 | 点差 | 卖出`；
     * 有仓位时变成 `买入 | 点差 | 平仓`（多仓）或 `平仓 | 点差 | 卖出`（空仓）。
     */
    setTicketBook(data: {
        bids?: Array<{ price?: number | null }>;
        asks?: Array<{ price?: number | null }>;
    }): void {
        this.ticketAsks = (data.asks || []).slice(0, 5);
        this.ticketBids = (data.bids || []).slice(0, 5);
        const bid = Number(this.ticketBids[0]?.price);
        const ask = Number(this.ticketAsks[0]?.price);
        if (Number.isFinite(bid)) this.ticketBid = bid;
        if (Number.isFinite(ask)) this.ticketAsk = ask;
        this._renderTicket();
    }

    /** 外部（二级报价 / 5 档点击）同步价格 → 填进「价格」输入框 ✓ */
    setTicketPrice(price: number | null, force = false): void {
        if (price === null || !Number.isFinite(Number(price))) return;
        this.orderPrice = Number(price);
        const input = this.orderTicket?.querySelector<HTMLInputElement>(
            '.desk-ticket-price');
        if (input) input.value = this.orderPrice.toFixed(this.ticketDecimals);
        // ★ 点二级报价 10 档 → 强制填进**统一交易面板**的价格框（用户要求 ✓）
        this.ticket?.setPriceForce(this.orderPrice);
        void force;
    }

    /** 点差 = |卖一 − 买一| ✓ */
    private _spread(): number | null {
        if (this.ticketBid === null || this.ticketAsk === null) return null;
        return Math.abs(this.ticketAsk - this.ticketBid);
    }

    private _ensureOrderTicket(): void {
        if (!this.orderTicket) {
            const box = document.createElement('div');
            box.className = 'desk-ticket';
            const row = document.createElement('div');
            row.className = 'desk-ticket-row';
            const makeSide = (side: 'buy' | 'sell') => {
                const node = document.createElement('button');
                node.className = `desk-ticket-side ${side}`;
                node.title = side === 'buy'
                    ? '买入（市价加多；空头时＝平仓）' : '卖出（市价加空；多头时＝平仓）';
                const price = document.createElement('span');
                price.className = 'desk-ticket-price';
                price.textContent = '--';
                const label = document.createElement('span');
                label.className = 'desk-ticket-label';
                label.textContent = side === 'buy' ? '买入' : '卖出';
                node.append(price, label);
                node.addEventListener('click', () => this._ticketClick(side));
                return { node, price, label };
            };
            const buy = makeSide('buy');
            const spread = document.createElement('div');
            spread.className = 'desk-ticket-spread';
            spread.textContent = '--';
            spread.title = '点差（卖一 − 买一）';
            const sell = makeSide('sell');
            row.append(buy.node, spread, sell.node);
            this.ticketBuy = buy;
            this.ticketSell = sell;
            this.ticketSpread = spread;
            // ★ 只有三个格子：**没有手数 / 价格 / 档位输入**，
            //   手数取二级报价里的手数，下单是市价（set_target_volume ✓）
            box.append(row);
            // 和 minibt 实时图一样插进**原生图例**（OHLC 行下面、指标行上面）
            const cell = this.cells[0] as unknown as {
                legend?: { div?: HTMLElement; seriesContainer?: HTMLElement };
            } | undefined;
            const legend = cell?.legend;
            let placed = false;
            const legendDiv = legend?.div;
            if (legendDiv instanceof HTMLElement) {
                const wrapper = legend?.seriesContainer?.parentNode;
                if (wrapper && wrapper.parentNode === legendDiv) {
                    legendDiv.insertBefore(box, wrapper);
                } else {
                    legendDiv.appendChild(box);
                }
                placed = true;
            }
            if (placed) box.classList.add('in-legend');
            else this.element.appendChild(box);
            this.orderTicket = box;
        }
        this._renderTicket();
        this.orderTicket.classList.add('on');
    }

    /**
     * 买卖盘一点下单（市价 / 目标仓位 ✓）
     *
     * 多头：`买入` 继续加多、`平仓` 全平；空头：`平仓` 全平、`卖出` 继续加空。
     * 手数取**二级报价里的手数**；期货走天勤 `TargetPosTask.set_target_volume` ✓
     */
    private _ticketClick(side: 'buy' | 'sell'): void {
        const qty = this.ticket?.qtyValue() || this.orderQty;
        this.options.onCommand?.('ticket_order', {
            symbol: this.options.symbol, side, qty,
        });
    }

    /** 刷新买卖盘（价格 / 点差 / 标签 / 颜色 ✓） */
    private _renderTicket(): void {
        if (!this.orderTicket) return;
        const decimals = this.ticketDecimals;
        const bid = this.ticketBid;
        const ask = this.ticketAsk;
        const net = this.ticketNet;
        const leftClose = net < 0;
        const rightClose = net > 0;
        const left = this.ticketBuy;
        const right = this.ticketSell;
        if (left) {
            left.price.textContent = ask === null ? '--' : ask.toFixed(decimals);
            left.label.textContent = leftClose ? '平仓' : '买入';
            left.node.classList.toggle('flat', leftClose);
        }
        if (right) {
            right.price.textContent = bid === null ? '--' : bid.toFixed(decimals);
            right.label.textContent = rightClose ? '平仓' : '卖出';
            right.node.classList.toggle('flat', rightClose);
        }
        const spread = this._spread();
        if (this.ticketSpread) {
            this.ticketSpread.textContent = spread === null
                ? '--' : spread.toFixed(decimals);
        }
        this.orderTicket.classList.toggle('has-position', !!net);
    }

    /** 轻提示（回放结束等 ✓） */
    toast(text: string): void {
        const tip = document.createElement('div');
        tip.className = 'desk-toast on';
        tip.textContent = text;
        this.element.appendChild(tip);
        window.setTimeout(() => {
            tip.classList.remove('on');
            window.setTimeout(() => tip.remove(), 250);
        }, 2600);
    }

    /** 跨 tab（不同周期）联动：可视**时间区间**变化回调 ✓ */
    onRangeChange: ((from: number, to: number) => void) | null = null;

    /** 外部把时间区间套过来（不同周期也能对齐 ✓） */
    applyTimeRange(from: number, to: number): void {
        const chart = (this.handler as unknown as {
            chart: { timeScale: () => {
                setVisibleRange: Function } } } | null)?.chart;
        if (!chart || !(from < to)) return;
        try {
            this._rangeGuard = true;
            chart.timeScale().setVisibleRange({
                from: from as never, to: to as never,
            });
        } catch {
            /* 数据还没到，忽略 ✓ */
        } finally {
            this._rangeGuard = false;
        }
    }

    private _rangeGuard = false;

    /** 「联动」：多格时间轴 / 十字线同步 ✓ */
    toggleLink(linked?: boolean): boolean {
        this.linked = linked === undefined ? !this.linked : !!linked;
        this.linkButton?.classList.toggle('on', this.linked);
        if (this.linked) this._bindLink();
        return this.linked;
    }

    private _linkBound = false;

    private _linkGuard = false;

    /**
     * 联动：**时间轴 + 十字线**都同步（多格 / 回放都生效 ✓）
     *
     * LWC 没有「把十字线设到某个时间」的公开 API 之外的办法，
     * 这里用 `setCrosshairPosition(price, time, series)`：
     * 价格取对方格同一时间最近的收盘价（回放时每格数据进度一致 ✓）。
     */
    private _bindLink(): void {
        if (this._linkBound || this.cells.length < 2) return;
        this._linkBound = true;
        type Api = {
            timeScale: () => {
                subscribeVisibleLogicalRangeChange: Function;
                setVisibleLogicalRange: Function;
            };
            subscribeCrosshairMove: Function;
            setCrosshairPosition: Function;
            clearCrosshairPosition?: Function;
        };
        const charts = this.cells.map((handler) => (handler as unknown as {
            chart: Api;
        }).chart);
        const series = this.cells.map((handler) => (handler as unknown as {
            series: unknown;
        }).series);

        charts.forEach((chart, index) => {
            // ① 可视区间同步
            chart.timeScale().subscribeVisibleLogicalRangeChange(
                (range: unknown) => {
                    if (!this.linked || !range) return;
                    charts.forEach((other, otherIndex) => {
                        if (otherIndex === index) return;
                        try {
                            other.timeScale().setVisibleLogicalRange(range);
                        } catch {
                            /* ignore */
                        }
                    });
                });
            // ★ 跨周期联动：把**时间区间**广播给别的 tab ✓
            (chart.timeScale() as unknown as {
                subscribeVisibleTimeRangeChange?: Function;
            }).subscribeVisibleTimeRangeChange?.((range: {
                from?: unknown; to?: unknown;
            } | null) => {
                if (!this.linked || this._rangeGuard || !range) return;
                const from = Number(range.from);
                const to = Number(range.to);
                if (!Number.isFinite(from) || !Number.isFinite(to)) return;
                this.onRangeChange?.(from, to);
            });
            // ② 十字线同步（回放时也会走这里 ✓）
            chart.subscribeCrosshairMove((param: Record<string, unknown>) => {
                if (!this.linked || this._linkGuard || !param) return;
                const time = param.time as never;
                this._linkGuard = true;
                try {
                    charts.forEach((other, otherIndex) => {
                        if (otherIndex === index) return;
                        if (time === undefined || time === null) {
                            other.clearCrosshairPosition?.();
                            return;
                        }
                        const price = this._priceAt(otherIndex, time);
                        if (price === null) {
                            other.clearCrosshairPosition?.();
                            return;
                        }
                        other.setCrosshairPosition(price, time, series[otherIndex]);
                    });
                } catch {
                    /* ignore */
                } finally {
                    this._linkGuard = false;
                }
            });
        });
    }

    /** 第 N 格在某个时间点的收盘价（没有就取最近一根 ✓） */
    private _priceAt(index: number, time: unknown): number | null {
        const bars = this.cellBars[index] || [];
        if (!bars.length) return null;
        let best: ChartBar | null = null;
        let bestDelta = Infinity;
        for (const bar of bars) {
            const delta = Math.abs(Number(bar.time) - Number(time));
            if (delta < bestDelta) {
                bestDelta = delta;
                best = bar;
            }
        }
        return best ? Number(best.close) : null;
    }

    /** 「持仓线」开关 ✓ */
    togglePositionLine(visible?: boolean): boolean {
        this.positionLineVisible =
            visible === undefined ? !this.positionLineVisible : !!visible;
        if (!this.positionLineVisible) {
            this.hidePositionLine();
        } else {
            // 重新显示 → 每格的持仓线都画回来 ✓
            for (const [cell, payload] of this.lastPositions) {
                this._applyPositionLine(payload, cell);
            }
        }
        return this.positionLineVisible;
    }

    // ------------------------------------------------------------- 布局对话框
    /** 「保存布局」对话框 ✓ */
    openSaveLayout(): void {
        if (!this.saveLayoutDialog) {
            this.saveLayoutDialog = new SaveLayoutDialog();
            this.saveLayoutDialog.setTheme(
                this.options.theme === 'light' ? 'light' : 'dark');
            this.saveLayoutDialog.onSaveCallback = (name) => {
                const cells = this.cellSymbols.map((symbol, index) => {
                    const layer = this.layers[index] || this.indicators;
                    const hidden = this.cellHidden[index]
                        || this.hiddenIndicators;
                    const rows = (this.cellItems[index] || []) as
                        unknown as Array<Record<string, unknown>>;
                    return {
                        symbol,
                        indicators: rows.map((item) => {
                            const key = String(item.key || '');
                            const style = (layer?.styleOf?.(key) || {}) as
                                Record<string, unknown>;
                            return {
                                ...item,
                                ...style,
                                visible: style.visible !== undefined
                                    ? style.visible
                                    : (hidden.has(key) ? false
                                        : item.visible !== false),
                            };
                        }),
                    };
                });
                this.options.onCommand?.('layout_save', {
                    symbol: this.options.symbol, name, cells,
                });
            };
        }
        const cols = this.layout.cols;
        const rows = this.layout.rows;
        const names: Record<string, string> = {
            '1x1': '单图', '2x1': '左右两图', '1x2': '上下两图',
            '2x2': '四图',
        };
        this.saveLayoutDialog.open({
            shape: names[`${cols}x${rows}`] || `${cols}×${rows}`,
            cycle: this.cycleLabel?.textContent || String(this.cycle),
            symbols: this.cellSymbols.slice(),
            existing: this.layouts.map((row) => String(row.name || '')),
        });
    }

    /** 「布局管理」对话框 ✓ */
    openLayoutManager(): void {
        if (!this.layoutManager) {
            this.layoutManager = new LayoutManager();
            this.layoutManager.setTheme(
                this.options.theme === 'light' ? 'light' : 'dark');
            this.layoutManager.onApplyCallback = (key) => {
                this.options.onCommand?.('layout_apply', {
                    symbol: this.options.symbol, key,
                });
            };
            this.layoutManager.onDeleteCallback = (key) => {
                this.options.onCommand?.('layout_delete', { key, local: false });
            };
            this.layoutManager.onFavoriteCallback = (key, on) => {
                this.options.onCommand?.('layout_favorite', {
                    key, on, local: false,
                });
            };
            this.layoutManager.onEditCallback = (row) => {
                this.openLayoutParams(row as unknown as
                    Record<string, unknown>);
            };
            this.layoutManager.onExportCallback = () => {
                this.options.onCommand?.('layouts_export', { local: false });
            };
            this.layoutManager.onImportCallback = (text) => {
                this.options.onCommand?.('layouts_import', { text,
                                                              local: false });
            };
        }
        this.layoutManager.open();
        this.options.onCommand?.('layouts', { local: false });
    }

    /** 编辑某个布局的指标参数（✎）✓ */
    openLayoutParams(row: Record<string, unknown>): void {
        if (!this.layoutParams) {
            this.layoutParams = new LayoutParamsDialog();
            this.layoutParams.setTheme(
                this.options.theme === 'light' ? 'light' : 'dark');
            this.layoutParams.onSaveCallback = (cells) => {
                this.options.onCommand?.('layout_update', {
                    key: row.key, cells, local: false,
                });
            };
        }
        this.layoutParams.open(String(row.name || row.key),
                               (row.cells || []) as never);
    }

    /** 后端 `{type:'layouts'}` ✓ */
    setLayouts(items: Array<Record<string, unknown>>,
               exportText = ''): void {
        this.layouts = items || [];
        this.layoutManager?.setExportText(exportText);
        this.layoutManager?.setRows(this.layouts as never);
    }

    /** 「布局 ▾」：已保存布局快速切换 ✓ */
    /**
     * 布局菜单（P27 四合一 ✓）
     *
     * ```
     * 单图 / 左右两图 / 四图          ← 预设（当前那个打 ✓）
     * ── 已保存的布局 ›  收藏的 / 全部  ← 二级菜单
     * ── 保存当前布局…
     * 布局管理…
     * 导出 / 导入布局…
     * ```
     */
    /** 布局按钮上带一格小字（`1×1` / `2×2`… ✓） */
    private _syncLayoutButton(): void {
        const label = this.layoutLabel;
        if (!label) return;
        label.textContent = this.cells.length > 1
            ? `布局 ${this.spec?.label || this.cells.length}` : '布局';
        this.layoutButton?.classList.toggle('on', this.cells.length > 1);
    }

    openLayoutMenu(anchor: HTMLElement): void {
        const currentKey = this.spec?.key || '';
        const presets: MenuItem[] = DESK_LAYOUTS.map((item) => ({
            label: `${item.label}${currentKey === item.key ? '  ✓' : ''}`
                + (this.strategyCells && item.cells.length < this.strategyCells
                    ? `（策略需要 ${this.strategyCells} 格）` : ''),
            // ★ 加载策略后：比策略合约数少的布局**禁用**（用户要求 ✓）
            disabled: !!this.strategyCells
                && item.cells.length < this.strategyCells,
            run: () => this.setLayoutSpec(item),
        }));
        const saved = this.layouts.map((row) => {
            // 缩略信息：`4格 · 1分`（`shape` 后端已经算好，直接用 ✓）
            const count = Number(row.count || (Number(row.cols || 1)
                * Number(row.rows || 1)));
            const cycle = Number(row.cycle || 60);
            // 布局菜单只显示布局 / 合约 / 周期；指标和参数不展示 ✓
            const desc = String(row.desc || '').trim();
            return {
                label: `${row.name || row.key}`
                    + (row.favorite ? '  ★' : '')
                    + (desc ? `   ${desc.slice(0, 80)}`
                        : `   ${count}格 · ${cycleLabel(cycle)}`),
                disabled: !!this.strategyCells
                    && count < this.strategyCells,
                run: () => this.options.onCommand?.('layout_apply', {
                    symbol: this.options.symbol, key: row.key,
                }),
            };
        });
        const items: MenuItem[] = [...presets];
        items.push({
            label: '已保存的布局', separator: true,
            submenu: saved.length ? saved : [{ label: '（还没有保存的布局）',
                                              disabled: true }],
            disabled: !saved.length,
        });
        items.push({ label: '保存当前布局…', run: () => this.openSaveLayout() });
        items.push({ label: '布局管理…', run: () => this.openLayoutManager() });
        items.push({
            label: '导出 / 导入', separator: true,
            submenu: [
                { label: '导出布局到文件…',
                  run: () => this.options.onCommand?.('layouts_export', {}) },
                { label: '从文件导入布局…',
                  run: () => this.options.onCommand?.('layouts_import', {}) },
            ],
        });
        showMenuBelow(anchor, items);
    }


    // ------------------------------------------------------------- 无限历史
    /** 订阅可视范围：贴到左边就请求更早的 K 线（`history_load` ✓） */
    private _bindHistory(handler: unknown): void {
        const chart = (handler as unknown as {
            chart?: { timeScale?: () => {
                subscribeVisibleLogicalRangeChange?: (fn: () => void) => void;
            } };
        }).chart;
        const scale = chart?.timeScale?.();
        scale?.subscribeVisibleLogicalRangeChange?.(() => {
            this._maybeHistory();
            this._placePositionBadge();
        });
    }

    /** 视窗接近最左边（<= 3 根）→ 要一批历史（500ms 节流 ✓） */
    private _maybeHistory(): void {
        if (this.historyLoading || this.historyExhausted || this.replaying) return;
        if (Date.now() < this.historyGrace) return;      // 打开后的宽限期 ✓
        if (Date.now() - this.historyAt < 500) return;
        const chart = (this.handler as unknown as {
            chart?: { timeScale?: () => {
                getVisibleLogicalRange?: () => { from: number; to: number } | null;
            } };
        } | null)?.chart;
        const range = chart?.timeScale?.()?.getVisibleLogicalRange?.();
        if (!range || range.from > 3) return;
        const bars = this.cellBars[0] || [];
        const first = bars.length ? Number(bars[0].time) : 0;
        if (!first) return;
        this.historyAt = Date.now();
        this.historyLoading = true;
        this.options.onCommand?.('history_load', {
            symbol: this.options.symbol, cell: 0, before: first, page: 500,
        });
    }

    /** 后端补来一批更早的 K 线 → 前插并保持当前视窗 ✓ */
    prependHistory(bars: ChartBar[], exhausted = false): void {
        this.historyLoading = false;
        this.historyExhausted = !!exhausted;
        const list = (bars || []).slice();
        if (!list.length) {
            this.historyExhausted = true;
            return;
        }
        const current = this.cellBars[0] || [];
        const firstTime = current.length ? Number(current[0].time) : Infinity;
        const older = list.filter((bar) => Number(bar.time) < firstTime);
        if (!older.length) {
            this.historyExhausted = true;
            return;
        }
        const chart = (this.handler as unknown as {
            chart?: { timeScale?: () => {
                getVisibleLogicalRange?: () => { from: number; to: number } | null;
                setVisibleLogicalRange?: (range: { from: number; to: number }) => void;
            } };
        } | null)?.chart;
        const scale = chart?.timeScale?.();
        const range = scale?.getVisibleLogicalRange?.();
        this.cellBars[0] = older.concat(current);
        if (!this.replaying) this.bars = this.cellBars[0];
        this._applyCellBars(0);
        // 视窗整体右移「新增根数」，用户看到的位置不变 ✓
        if (range && scale?.setVisibleLogicalRange) {
            const added = this.cellBars[0].length - current.length;
            try {
                scale.setVisibleLogicalRange({
                    from: range.from + added, to: range.to + added,
                });
            } catch {
                /* ignore */
            }
        }
    }

    // ------------------------------------------------------------- 回放交易 / 视窗
    /** 记住每格当前的可视范围（进回放前调 ✓） */
    private _saveViewRanges(): void {
        this.savedRanges = this.cells.map((handler) => {
            const scale = (handler as unknown as {
                chart?: { timeScale?: () => {
                    getVisibleLogicalRange?: () =>
                        { from: number; to: number } | null;
                } };
            }).chart?.timeScale?.();
            try {
                const range = scale?.getVisibleLogicalRange?.();
                return range ? { from: range.from, to: range.to } : null;
            } catch {
                return null;
            }
        });
    }

    /** 退出回放后恢复可视范围（等后端把实时 K 线推下来再套 ✓） */
    private _restoreViewRangesSoon(): void {
        const apply = () => this._restoreViewRanges();
        const raf = (globalThis as unknown as {
            requestAnimationFrame?: (cb: () => void) => number;
        }).requestAnimationFrame;
        if (typeof raf === 'function') raf(() => raf(apply));
        else window.setTimeout(apply, 120);
        window.setTimeout(apply, 800);     // 后端补丁晚到也兜一次 ✓
    }

    private _restoreViewRanges(): void {
        const saved = this.savedRanges;
        if (!saved.length) return;
        this.cells.forEach((handler, index) => {
            const range = saved[index];
            if (!range) return;
            const scale = (handler as unknown as {
                chart?: { timeScale?: () => {
                    setVisibleLogicalRange?: (
                        r: { from: number; to: number }) => void;
                } };
            }).chart?.timeScale?.();
            try {
                scale?.setVisibleLogicalRange?.(range);
            } catch {
                /* ignore */
            }
        });
    }

    /**
     * 统一交易面板：持仓 / 委托右侧（本地模拟 + 天勤模拟 + 实盘共用 ✓）
     *
     * * 回放（`replaying=true`）→ `replay_order` / `replay_action`
     *   （本地模拟账户，价格跟随回放 K 线收盘价 ✓）；
     * * 实时 → `place_order`（限价买入 / 卖出 / 平仓）+ `account_action`
     *   （主价平仓 / 反手 / 撤单）；
     * * 实盘账户 → 下单前**二次确认**（`trading_state.real` ✓）。
     */
    private _ensureDockTicket(replaying = false): void {
        if (!this.ticket) {
            this.tradeSymbol = this.options.symbol;
            const stock = /^(SH|SZ|HK|US|JP)\./i.test(this.tradeSymbol);
            this.ticket = buildReplayTicket({
                title: '交易',
                symbol: this.tradeSymbol,
                qtyLabel: stock ? '股数' : '手数',
                qtyDefault: stock ? 100 : 1,
                searchable: true,
                onSearch: () => this.openSymbolSearch('trade'),
                onLockChange: (locked) => {
                    this.tradeLocked = locked;
                    this.ticket?.setInfo(locked
                        ? '已锁定：不会跟随图表点击切换标的'
                        : '未锁定：跟随最后点击的图表切换标的');
                },
                onOrder: (side, close) => {
                    const payload = {
                        symbol: this.tradeSymbol || this.options.symbol, side,
                        qty: this.ticket?.qtyValue() || 1,
                        price: this.ticket?.priceValue() || 0,
                        close,
                    };
                    if (this.replaying) {
                        this.options.onCommand?.('replay_order', payload);
                        return;
                    }
                    const label = close ? '平仓'
                        : (side === 'buy' ? '买入' : '卖出');
                    const priceText = payload.price
                        ? `@ ${payload.price}` : '@ 市价';
                    if (this.accountReal && !window.confirm(
                        `【实盘】${label} ${payload.symbol} `
                        + `${payload.qty} 手 ${priceText}

确认下单？`)) {
                        return;
                    }
                    this.options.onCommand?.('place_order', payload);
                },
                onAction: (action) => {
                    const payload = { symbol: this.tradeSymbol
                        || this.options.symbol, action };
                    if (this.replaying) {
                        this.options.onCommand?.('replay_action', payload);
                        return;
                    }
                    const names: Record<string, string> = {
                        close_main: '按最新价市价平仓',
                        reverse: '反手（多空反转）',
                        cancel: '撤掉未成交的挂单',
                    };
                    const tip = names[action] || action;
                    if (this.accountReal && !window.confirm(
                        `【实盘】${this.options.symbol}：${tip}

确认执行？`)) {
                        return;
                    }
                    this.options.onCommand?.('account_action', payload);
                },
                info: '平仓 = 按上面的价格平当前持仓',
            });
        }
        const ticket = this.ticket;
        ticket.setTitle(replaying ? '本地模拟交易（回放）' : '交易');
        ticket.setSymbol(this.tradeSymbol || this.options.symbol);
        ticket.setInfo(replaying
            ? '回放中按当前 K 线价成交 · 退出回放自动切回天勤账户'
            : '点二级报价档位可填价格 · 平仓=按价格；市价平仓=市价');
        ticket.setPrice(this._lastPriceValue());
        this.dock.setTicket(ticket.element);
        if (replaying) {
            if (!this.dockVisible) this.toggleDock();
            this.dock.setTab('account');
            this.dock.setTable('positions');
        }
        this._bindTicketPositionQuantity();
    }

    /** 实盘账户（下单前二次确认 ✓） */
    private accountReal = false;

    /** 交易状态（后端 `trading_state` 补丁：是否可交易 / 实盘 ✓） */
    setTradingState(enabled: boolean, real: boolean): void {
        this.accountReal = !!real;
        this.tradeEnabled = !!enabled;
        this._ensureDockTicket(this.replaying);
    }

    /** 已有持仓时把手数默认成持仓量（平仓一键成交 ✓） */
    private _bindTicketPositionQuantity(): void {
        const net = Math.abs(this.ticketNet || 0);
        if (net > 0) this.ticket?.setNet(this.ticketNet || 0);
    }

    /** 最后一根收盘价（控件价格输入框的默认值 ✓） */
    private _lastPriceValue(): number | null {
        const bars = this.cellBars[0] || [];
        const tail = bars[bars.length - 1];
        const value = tail ? Number(tail.close) : NaN;
        return Number.isFinite(value) && value > 0 ? value : null;
    }

    /** 第 N 格重新套主题（新建 pane 后必须调用） */
    private _applyPaneTheme(cell: number): void {
        const handler = this.cells[cell];
        if (!handler) return;
        try {
            (handler as unknown as { chart: { applyOptions: Function } })
                .chart.applyOptions(chartOptions(
                    this.options.theme === 'light' ? 'light' : 'dark'));
        } catch {
            /* ignore */
        }
    }

    /** 跟随主题：图表 canvas / 副图 / 预警对话框一起换色 ✓ */
    applyTheme(theme: 'light' | 'dark'): void {
        this.options.theme = theme;
        this._applyRootStyles(theme);
        const options = chartOptions(theme);
        this._applyLegendColors();          // 图例文字 / 眼睛齿轮描边 ✓
        for (const handler of this.cells) {
            try {
                (handler as unknown as { chart: { applyOptions: Function } })
                    .chart.applyOptions(options);
            } catch {
                /* ignore */
            }
        }
        this.indicators?.applyTheme(theme);
        for (const layer of this.layers) layer.applyTheme(theme);
        this.alertDialog?.setTheme(theme);
        this.symbolSearch?.setTheme(theme);
        this.indicatorPicker?.setTheme(theme);
        this.templatePicker?.setTheme(theme);
        this.editor?.setTheme(theme);
        this._applyChartType();          // 换主题后重建非蜡烛序列（颜色）✓
        this._applyCrosshairColor();      // 鼠标标签色也跟主题走 ✓
    }

    /**
     * 图例（左上角 K 线信息 + 指标标签）的颜色跟着主题走 ✓
     *
     * 以前只在建格时设一次 `style.color` → 切到浅色主题后文字和图标描边
     * 还是 `#d8d9db`（白底上几乎看不见 ✗，用户反馈）。眼睛 / 齿轮 / 收起按钮
     * 都用 `stroke: currentColor`，所以**只改这一处**整套图标就跟着亮 ✓
     */
    private _applyLegendColors(): void {
        const color = this.options.theme === 'light' ? '#1f2329' : '#d8d9db';
        for (const handler of this.cells) {
            const legend = (handler as unknown as {
                legend?: { div?: HTMLElement; color?: string };
            }).legend;
            const div = legend?.div;
            if (div) {
                div.style.color = color;
                div.style.fontSize = div.style.fontSize || '11.5px';
            }
            if (legend) legend.color = color;
        }
    }

    // ------------------------------------------------------------- 编辑器
    /**
     * 打开底部「代码」编辑器（个人指标 / 策略）✓
     *
     * 底部的「交易账户 / 运行日志」一直是固定的 232px；现在有了编辑器，
     * 面板高度可以**拖着改**（`_ensureDockSplitter`），并记住上次高度 ✓
     */
    /**
     * 「交易/编辑器」按钮：显示 / 隐藏底部面板 ✓
     *
     * 首次显示时高度取**页面高度的 1/3**（以前固定 232px，太矮 ✗）；
     * 用户拖过就记住（`settings.dock_height`）。
     */
    toggleDock(visible?: boolean): boolean {
        const show = visible === undefined ? !this.dockVisible : !!visible;
        this.dockVisible = show;
        this.dock.element.style.display = show ? '' : 'none';
        if (show) {
            this._ensureDockSplitter();
            const total = this.element.getBoundingClientRect().height
                || this.element.clientHeight;
            if (!this._dockSized && total > 240) {
                this.dockRatio = 1 / 3;
                this.dockHeight = Math.round(total * this.dockRatio);
                this._dockSized = true;
            }
            this._applyDockRatio(total);
            this.dock.element.style.height = `${this.dockHeight}px`;
            this.dock.setTab(this.dock.currentTab || 'account');
        }
        this._syncToggles();
        this.resize();
        return this.dockVisible;
    }

    /**
     * 惰性创建「代码」编辑器（**第一次切到该页签时才建** ✓）
     *
     * P60 把「编辑器 / 交易」按钮合并后，点合并按钮只是 `toggleDock()`，
     * 不会走 `openEditor()` —— 如果 `dock.onEditorOpen` 在 `openEditor()`
     * 里才接，点「代码」页签就是**空白**（用户实测 ✗）。
     * 所以这里统一成 `_ensureEditor()`，构造时就把回调接好 ✓
     */
    private _ensureEditor(): EditorPanel {
        if (!this.editor) {
            this.editor = new EditorPanel({
                theme: this.options.theme === 'light' ? 'light' : 'dark',
                // ★ 编辑器「加到图表」必须用**当前**合约（切合约后自动更新）✓
                symbol: () => this.options.symbol,
                onCommand: (cmd: string, payload?: unknown) =>
                    this.options.onCommand?.(cmd, payload),
                onToast: (level: string, text: string) =>
                    this.toastLevel(level, text),
            });
            this.dock.editorPane.appendChild(this.editor.element);
        }
        return this.editor;
    }

    openEditor(): void {
        this._ensureEditor();
        if (!this.dockVisible) this.toggleDock(true);
        this._ensureDockSplitter();
        this.dock.setTab('code');          // → onEditorOpen → editor.show() ✓
        this.resize();
    }

    /** 编辑器相关补丁（`editor_files` / `editor_file` / … ✓） */
    get editorPanel(): EditorPanel | null {
        return this.editor;
    }

    /** 策略实盘状态（运行中 / 停止按钮）→ 转给编辑器面板 ✓
     *
     *  ★ 以前 app.ts 只遍历 LocalChartPage → 看盘窗口的策略实盘按钮永远
     *    不更新、「停止实盘」一直是禁用状态（用户实测 ✗）
     */
    setStrategyLive(patch: Record<string, any>): void {
        this.editorPanel?.setStrategyLive?.(patch);
    }

    /** 收起编辑器（点「编辑器」再点一次 / 关面板 ✓） */
    closeEditor(): void {
        this.editor?.hide();
        this.editorButton?.classList.remove('on');
        if (this.dock.currentTab === 'code') this.dock.setTab('account');
    }

    /** 底部面板「最大化 / 恢复」（隐藏图表区 ✓） */
    toggleDockMaximize(force?: boolean): boolean {
        const next = force === undefined ? !this.dockMaximized : !!force;
        if (next === this.dockMaximized) return this.dockMaximized;
        this.dockMaximized = next;
        const body = this.element.querySelector('.desk-chart-body') as HTMLElement | null;
        if (next) {
            this.dockRestoreHeight = this.dockHeight;
            this.dockRestoreRatio = this.dockRatio;
            if (body) body.style.display = 'none';
            if (this.dockSplitter) this.dockSplitter.style.display = 'none';
            this.dock.element.style.height = 'auto';
            this.dock.element.style.flex = '1 1 auto';
            // ★ 必须能「收缩到父容器高度」：否则代码区把面板顶高、页面被裁剪 ✗
            this.dock.element.style.minHeight = '0';
            this.dock.element.style.overflow = 'hidden';
        } else {
            if (body) body.style.display = '';
            if (this.dockSplitter) this.dockSplitter.style.display = '';
            this.dock.element.style.flex = '0 0 auto';
            this.dock.element.style.minHeight = '';
            this.dock.element.style.overflow = '';
            this.dockHeight = this.dockRestoreHeight || this.dockHeight;
            this.dockRatio = this.dockRestoreRatio || this.dockRatio;
            this._applyDockRatio();
            this.dock.element.style.height = `${this.dockHeight}px`;
        }
        this.dock.setMaximized(next);
        this.resize();
        return next;
    }

    /** 底部面板与图表之间的**可拖动分隔条** ✓ */
    private _ensureDockSplitter(): void {
        if (this.dockSplitter) return;
        const bar = document.createElement('div');
        bar.className = 'desk-dock-splitter';
        bar.title = '拖动调整下方面板高度（双击恢复默认）';
        this.element.insertBefore(bar, this.dock.element);
        this.dock.element.style.height = `${this.dockHeight}px`;
        this.dock.element.style.flex = '0 0 auto';
        const drag = (event: MouseEvent) => {
            event.preventDefault();
            if (this.dockMaximized) this.toggleDockMaximize(false);
            const startY = event.clientY;
            const startHeight = this.dock.element.getBoundingClientRect().height;
            const total = this.element.getBoundingClientRect().height;
            const move = (moveEvent: MouseEvent) => {
                const delta = startY - moveEvent.clientY;
                const next = Math.max(140,
                    Math.min(total * 0.72, startHeight + delta));
                this.dockHeight = Math.round(next);
                this.dockRatio = this.dockHeight / total;
                this.dock.element.style.height = `${this.dockHeight}px`;
                this.resize();
            };
            const up = () => {
                window.removeEventListener('mousemove', move);
                window.removeEventListener('mouseup', up);
                document.body.classList.remove('desk-resizing-dock');
                this.options.onCommand?.('set_setting', {
                    key: 'dock_height', value: this.dockHeight,
                });
                this.resize();
            };
            document.body.classList.add('desk-resizing-dock');
            window.addEventListener('mousemove', move);
            window.addEventListener('mouseup', up);
        };
        bar.addEventListener('mousedown', drag);
        bar.addEventListener('dblclick', () => {
            const total = this.element.getBoundingClientRect().height
                || this.element.clientHeight || 696;
            this.dockRatio = 1 / 3;
            this.dockHeight = Math.round(total * this.dockRatio);
            this.dock.element.style.height = `${this.dockHeight}px`;
            this.options.onCommand?.('set_setting', {
                key: 'dock_height', value: this.dockHeight,
            });
            this.resize();
        });
        this.dockSplitter = bar;
    }

    /** 带级别的轻提示（编辑器用 ✓） */
    toastLevel(level: string, text: string): void {
        this.toast(text);
        void level;
    }


    /** 「二级报价」按钮：显示/隐藏右侧面板（显示时按钮高亮 ✓） */
    toggleBook(visible?: boolean): boolean {
        this.bookVisible = visible === undefined ? !this.bookVisible : !!visible;
        this.book.element.style.display = this.bookVisible ? '' : 'none';
        this._syncToggles();
        this.resize();
        return this.bookVisible;
    }

    /** 两个开关按钮的选中态（与报价页 chip 同色 ✓） */
    private _syncToggles(): void {
        this.tradeButton?.classList.toggle('on', this.dockVisible);
        this.bookButton?.classList.toggle('on', this.bookVisible);
    }

    /** 预警列表（后端 `{type:'alerts'}` 补丁 → 对话框列表 ✓） */
    setAlerts(items: Array<Record<string, unknown>>): void {
        this.alertItems = items || [];
        this.alertDialog?.setItems(items as never);
        this._renderAlertLines();
    }

    /** 右键「清除预警」✓ */
    clearAlerts(): void {
        this.alertItems = [];
        this.alertDialog?.setItems([]);
        this._renderAlertLines();
        this.options.onCommand?.('clear_alerts', {});
    }

    /** 截图：LWC 自带 `takeScreenshot()` → 直接下 PNG ✓ */
    screenshot(): void {
        const chart = (this.handler as unknown as {
            chart?: { takeScreenshot?: () => HTMLCanvasElement };
        } | null)?.chart;
        const canvas = chart?.takeScreenshot?.();
        if (!canvas) {
            this.toast('当前图表暂不支持截图');
            return;
        }
        const link = document.createElement('a');
        link.download = `${this.options.symbol.replace(/[.\/]/g, '_')}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
    }

    /** 增量合并：把后端 last 点写回本地完整 items（回放 / 下次全量都用 ✓） */
    private _mergeLastItems(target: IndicatorLine[], incoming: IndicatorLine[]): void {
        const byKey = new Map(target.map((item) => [item.key, item]));
        for (const item of incoming) {
            const old = byKey.get(item.key);
            const rows = item.data || [];
            if (!old || !rows.length) continue;
            const data = old.data || (old.data = []);
            // 新 K 线 / 重连缺口可能是 2+ 根，全部合并；不能只吃最后 1 根 ✓
            for (const row of rows) {
                if (!row || row[0] === undefined) continue;
                if (data.length && data[data.length - 1]?.[0] === row[0]) {
                    data[data.length - 1] = row;
                } else if (!data.length
                    || row[0] > (data[data.length - 1]?.[0] ?? 0)) {
                    data.push(row);
                } else {
                    const index = data.findIndex((entry) =>
                        entry?.[0] === row[0]);
                    if (index >= 0) data[index] = row;
                }
            }
        }
    }

    /** 指标线（MA/BOLL 叠主图；MACD/KDJ/RSI 各开一个副图 ✓） */
    setIndicators(payload: IndicatorPayload): void {
        if (this.replaying) {
            if (payload.mode === 'last') {
                this._mergeLastItems(this.replayIndicators, payload.items || []);
                if (this.replayCells[0]) {
                    this.replayCells[0].indicators = this.replayIndicators;
                }
                this._applyReplayIndicators();
                return;
            }
            // 回放期间后端推来的实时指标是**完整历史**，不能直接铺上去；
            // 只更新回放数据，再按当前可见最后一根切片 ✓
            this.replayIndicators = payload.items || [];
            if (this.replayCells[0]) {
                this.replayCells[0].indicators = this.replayIndicators;
            }
            this._applyReplayIndicators();
            return;
        }
        // ★ 实时多布局：第 2..N 格的策略线（后端 `cell`）→ 写到对应格 ✓
        if (payload.cell !== undefined && payload.cell !== null) {
            this.setCellIndicators(Number(payload.cell) || 0, payload);
            return;
        }
        this.setCellIndicators(0, payload);
    }

    /** 记录策略需要的最少格数（后端 payload 里的 `strategyContracts` ✓） */
    private _noteStrategyCells(payload: Record<string, unknown>): void {
        if (!('strategy' in payload)) return;
        const name = String(payload.strategy || '');
        const contracts = payload.strategyContracts;
        this.strategyName = name;
        if (!name) {
            this.strategyCells = 0;
            return;
        }
        if (Array.isArray(contracts)) {
            this.strategyCells = contracts.length;
        }
    }

    /** 第 N 格的指标（后端 `{type:'indicator', cell:n}` ✓） */
    setCellIndicators(index: number, payload: IndicatorPayload): void {
        // ★ 「加载了策略」时的最少格数（布局菜单据此禁用更小的布局 ✓）
        this._noteStrategyCells(payload as unknown as Record<string, unknown>);
        const cell = Math.max(0, Math.min(Number(index) || 0,
                                         Math.max(0, this.layers.length - 1)));
        const layer = this.layers[cell] || this.indicators;
        let items = (payload.items || []) as IndicatorLine[];
        if (payload.mode === 'last') {
            const current = this.cellItems[cell] || [];
            this._mergeLastItems(current, items);
            this.cellItems[cell] = current;
            if (cell === 0) this.legendItems = current;
            layer.applyLast({ ...payload, items });
            this._renderLegendRows(cell);
            return;
        }
        if (payload.strategyOnly) {
            // ★ 只换策略线：保留这一格原有的内置 / 个人指标 ✓
            const kept = (this.cellItems[cell] || []).filter((item) => {
                const text = String(
                    (item as unknown as { source?: string }).source
                    || item.key || '');
                return !text.startsWith('editor:');
            });
            items = kept.concat(items);
        }
        // ★ 完整库指标（VP / 动态表格）是后台线程算的：同步这一拍
        //   payload.pending=true 时暂时没有它们，不能把上一份 VP/表格删掉
        //   （否则每次新 K 线 VP 都会闪一下 / 看起来“不支持 VP” ✗）。
        if (payload.pending) {
            const incoming = new Set(items.map((item) => item.key));
            const keep = (this.cellItems[cell] || []).filter((item) =>
                !incoming.has(item.key)
                && (item.kind === 'vp' || item.kind === 'table'));
            if (keep.length) items = items.concat(keep);
        }
        this.cellItems[cell] = items;
        if ('strategy' in (payload as unknown as Record<string, unknown>)) {
            this.cellStrategy[cell] = String(
                (payload as unknown as { strategy?: string }).strategy || '');
        }
        if (cell === 0) this.legendItems = items;
        // ★ 隐藏的指标**不再从 items 里删掉**（删了指标标签也会消失 ✗）：
        //   给它们打上 `visible=false`，由图层只隐藏指标线 ✓
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        this._ensureCrosshair();          // ★ 表格跟随鼠标依赖它（无 VP 也要装）
        layer.apply({ ...payload, items: this._drawItems(cell, items) });
        // 新建 pane 会使用 LWC 默认分隔线颜色（常为浅灰/白）→ 重套主题
        this._applyPaneTheme(cell);
        this._syncVpOverlay(cell, items.filter((item) => !hidden.has(item.key)));
        this._renderLegendRows(cell);
        this.resize();
    }

    // ------------------------------------------------------------- VP 自绘层
    private readonly vpOverlays: Array<VpOverlay | null> = [];

    /** 确保第 N 格有 VP 覆盖层（canvas，贴右边缘 + 鼠标跟随 ✓） */
    private _ensureVpOverlay(cell: number): VpOverlay | null {
        const existing = this.vpOverlays[cell];
        if (existing) return existing;
        const chart = (this.handler as unknown as {
            chart?: unknown } | null)?.chart;
        if (!chart) return null;
        const host = cell === 0 ? this.host : this.subHost;
        const overlay = new VpOverlay(host, chart as never,
            () => this.options.theme || 'dark');
        this.vpOverlays[cell] = overlay;
        this._ensureCrosshair();
        overlay.resize();
        return overlay;
    }

    /** 十字线订阅（**始终**装上：VP 和表格都靠它 ✓，只装一次） */
    private crosshairBound = false;

    private _ensureCrosshair(): void {
        if (this.crosshairBound) return;
        const chart = (this.handler as unknown as {
            chart?: unknown } | null)?.chart as unknown as {
                subscribeCrosshairMove?: (cb: (param: {
                    time?: unknown }) => void) => void;
            } | undefined;
        if (!chart?.subscribeCrosshairMove) return;
        this.crosshairBound = true;
        try {
            chart.subscribeCrosshairMove((param) => {
                const time = typeof param?.time === 'number'
                    ? param.time : Number((param?.time as number)) || null;
                // ★ 鼠标优先；离开 → 回实时（minibt `MouseLeave` 同款 ✓）
                for (const overlay of this.vpOverlays) {
                    overlay?.onCrosshair(time);
                }
                this._syncTableMouse(time);
            });
        } catch { /* ignore */ }
    }

    /**
     * 表格跟随鼠标（与 VP 同一个 `crosshairMove`；**鼠标优先** ✓）
     *
     * `param.time` → 二分查 `bars` 下标 → 命令 `table_row_at`；
     * 鼠标离开 / 新数据 → `index = null`（回到最后一根，实时优先）✓
     */
    private _syncTableMouse(time: number | null): void {
        const items = (this.cellItems[0] || []).filter(
            (item) => item.kind === 'table');
        if (!items.length) return;
        const bars = this.cellBars[0] || this.bars;
        let index: number | null = null;
        if (time && bars.length) {
            let low = 0;
            let high = bars.length - 1;
            while (low <= high) {
                const mid = (low + high) >> 1;
                const value = Number((bars[mid] as { time: number }).time);
                if (value === time) { index = mid; break; }
                if (value < time) low = mid + 1; else high = mid - 1;
            }
        }
        // ★ 鼠标在「最后一根 K 线 ~ 可视区右边缘」之间（空白区）时
        //   `param.time` 不是任何真实 bar → `index === null`；
        //   **回放中**必须回落到「回放最后一根」，不能回落成 `null`
        //   （`null` = 后端数据的最后一根 → 会和回放刷新来回切、闪烁 ✗）
        let target = index;
        if (target === null && this.replaying) {
            const shown = (this.cellBars[0] || this.bars || []).length;
            target = Math.max(0, shown - 1);
        }
        this._syncTableIndex(target);
    }

    /** 按**行号**刷新表格（回放 / 鼠标共用 ✓；`null` = 最后一根） */
    private _syncTableIndex(index: number | null, force = false): void {
        const items = (this.cellItems[0] || []).filter(
            (item) => item.kind === 'table');
        for (const item of items) {
            const key = String(item.key).replace(/:table$/, '');
            if (!force && this.tableMouseAt.get(key) === index) continue;
            this.tableMouseAt.set(key, index);
            this.options.onCommand?.('table_row_at', { key, index });
        }
    }

    private readonly tableMouseAt = new Map<string, number | null>();
    private tableLiveAt = 0;
    /** 设置 → 图表设置：VP / 表格刷新间隔 + 是否仅新 K 线 ✓ */
    private tableIntervalMs = 1000;
    private tableNewBarOnly = false;
    private tableBarTime = 0;

    /** 后端按行重算的表格 → 只刷 tbody ✓ */
    setTableRows(payload: { key?: string; rows?: string[][] }): void {
        const key = String(payload.key || '');
        const rows = (payload.rows || []) as string[][];
        for (const layer of this.layers) {
            layer.updateTableRows(`${key}:table`, rows);
        }
        this.indicators.updateTableRows(`${key}:table`, rows);
    }

    /** 指标补丁里带 `vpMatrix` → 交给自绘层（不再走 custom series ✗） */
    private _syncVpOverlay(cell: number, items: IndicatorLine[]): void {
        const item = items.find((entry) => entry.kind === 'vp');
        if (!item) {
            // ★ 删掉指标 / 👁 隐藏 → 覆盖层必须清空（否则残留一屏 ✗）
            this.vpOverlays[cell]?.setData(null);
            return;
        }
        const overlay = this._ensureVpOverlay(cell);
        if (!overlay) return;
        const raw = item as unknown as {
            vpMatrix?: number[][]; vpLo?: number[]; vpHi?: number[];
            vpStyle?: Record<string, unknown>;
        };
        overlay.setBars((this.cellBars[cell] || []) as never);
        overlay.setData({
            matrix: raw.vpMatrix || [],
            lo: raw.vpLo || [],
            hi: raw.vpHi || [],
            style: raw.vpStyle || {},
        });
    }


    /** 切换合约时先清空指标图层，等后端按新合约重算后再重建 ✓ */
    resetIndicators(): void {
        for (let index = 0; index < this.cells.length; index += 1) {
            this.cellItems[index] = [];
            this.cellHidden[index]?.clear();
            const layer = this.layers[index] || this.indicators;
            try {
                layer.clear();
            } catch {
                /* ignore */
            }
            this._renderLegendRows(index);
        }
        this.legendItems = [];
    }

    /** 图例里的指标行（色点 / 名称 / 值 / 👁 / ⚙；按格 ✓） */
    private _renderLegendRows(cell = 0): void {
        const host = this.cellLegendRows[cell] || this.legendRows;
        const items = this.cellItems[cell] || this.legendItems;
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        const layer = this.layers[cell] || this.indicators;
        host.textContent = '';
        for (const item of items) {
            const row = document.createElement('div');
            row.className = 'desk-legend-row';
            const dot = document.createElement('i');
            // ★ 设置卡里改过颜色 → 图例的点也要跟着（后端推送的 item.color
            //   还是老颜色，`styleOf()` 里才是用户选的新颜色 ✓）
            dot.style.background = layer.styleOf(item.key).color
                || item.color || '#90a4ae';
            const name = document.createElement('span');
            name.className = 'k';
            name.textContent = item.label || item.key;
            const value = document.createElement('b');
            const data = item.data || [];
            const last = data[data.length - 1];
            value.textContent = last ? Number(last[1]).toFixed(3) : '--';
            const eye = document.createElement('button');
            const isHidden = hidden.has(item.key);
            eye.className = 'desk-legend-icon' + (isHidden ? ' off' : '');
            // 真·眼睛 SVG（和 miniqt 看盘窗口同一个 ✓，以前是 emoji ✗）
            eye.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24"
                aria-hidden="true">${isHidden ? EYE_CLOSED : EYE_OPEN}</svg>`;
            eye.title = isHidden ? '显示这个指标' : '隐藏这个指标';
            eye.addEventListener('click', () =>
                this.toggleIndicator(item.key, undefined, cell));
            const gear = document.createElement('button');
            gear.className = 'desk-legend-icon desk-legend-gear';
            // 齿轮也用 miniqt 那张（以前是 ⚙ 文本，用户嫌丑 ✗）
            gear.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24"
                aria-hidden="true">${GEAR}</svg>`;
            gear.title = '修改指标参数';
            gear.addEventListener('click', () => this.editIndicator(item, gear, cell));
            row.append(dot, name, value, eye, gear);
            host.appendChild(row);
        }
    }

    /** 这一格要画的 items：被 👁 / 「显示该指标」隐藏的只打标记，
     *  **不删**（指标标签/图例行必须一直在 ✓）
     */
    private _drawItems(cell = 0, items?: IndicatorLine[]): IndicatorLine[] {
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        const source = items || this.cellItems[cell] || this.legendItems || [];
        return source.map((item) => (hidden.has(item.key)
            ? { ...item, visible: false } : item));
    }

    /** 👁 显示 / 隐藏某个指标（按格 ✓）
     *
     * ⚠ **只隐藏指标线**：图例行 / 指标标签 / 齿轮永远都在（用户要求 ✓）。
     * 以前这里会把指标从 items 里过滤掉再 `layer.apply()` →
     * 序列和指标标签一起消失，还无法再点眼睛恢复 ✗。
     */
    toggleIndicator(key: string, visible?: boolean, cell = 0): void {
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        const show = visible === undefined ? hidden.has(key) : !!visible;
        if (show) hidden.delete(key);
        else hidden.add(key);
        const layer = this.layers[cell] || this.indicators;
        // 眼睛与设置菜单的「显示该指标」共用同一份样式状态 ✓
        layer.setVisible(key, show);
        // ★ VP 是 canvas 覆盖层，不在 `IndicatorLayer.apply()` 里：
        //   👁 隐藏 / 显示时必须同步清理 / 重画，否则 VP 始终留在图上 ✗
        //   （这里只算“该画哪些”，**不**去删 items ✓）
        this._syncVpOverlay(cell, (this.cellItems[cell] || [])
            .filter((item) => !hidden.has(item.key)));
        this._renderLegendRows(cell);
    }

    /** 指标（一个 source 的所有线）是否**主图 + 副图混在一起** ✓
     *
     * `overlap` 在 Python 侧可以是字典（每条线一个布尔）→ 前端拿到的是
     * 每条线各自的 `overlay`。只要出现 True/False 混合，「位置」就不能
     * 单独设成“主图叠加 / 独立副图”（用户要求 ✓）。
     */
    private _overlayLocked(item: IndicatorLine, cell = 0): boolean {
        const sourceOf = (row: IndicatorLine) => String(
            (row as unknown as { source?: string }).source
            || String(row.key).split(':')[0]);
        const source = sourceOf(item);
        const lines = (this.cellItems[cell] || [])
            .filter((row) => sourceOf(row) === source);
        if (lines.length < 2) return false;
        const first = !!lines[0].overlay;
        return lines.some((row) => !!row.overlay !== first);
    }

    /** ⚙ 指标设置菜单（参数 / 线型 / 线宽 / 颜色 / 价格线 / 删除 ✓） */
    private _openIndicatorSettings(item: IndicatorLine, anchor: HTMLElement,
                                   cell = 0): void {
        const layer = this.layers[cell] || this.indicators;
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        const saved = layer.styleOf(item.key);
        const overlayLocked = this._overlayLocked(item, cell);
        // ★ 当前样式（选颜色时“立即预览”用同一套默认值 ✓）
        const currentState = (color?: string): IndicatorStyleState => ({
            params: { ...(item.params || {}) },
            lineStyle: saved.lineStyle ?? (Number(item.lineStyle) || 0),
            lineWidth: saved.lineWidth ?? (Number(item.lineWidth) || 2),
            color: color || saved.color || item.color || '#f6c343',
            priceLine: saved.priceLine ?? (item.priceLine !== false),
            priceLabel: saved.priceLabel ?? (item.priceLabel !== false),
            visible: saved.visible ?? !hidden.has(item.key),
            crosshairMarker: saved.crosshairMarker
                ?? (item.crosshairMarker !== false),
            overlay: !!item.overlay,
            overlayLocked,
        });
        /** 把新颜色同时写回前端缓存的指标行（自定义图例的点也要变 ✓） */
        const rememberColor = (color?: string) => {
            if (!color) return;
            const row = (this.cellItems[cell] || [])
                .find((entry) => entry.key === item.key);
            if (row) row.color = color;
        };
        openIndicatorSettings(
            anchor,
            item.label || item.key,
            currentState(),
            {
                onApply: (state) => {
                    const wasHidden = hidden.has(item.key);
                    // 样式立刻生效 + 记住（后端全量推送时会重新套上 ✓）
                    layer.applyStyle(item.key, state);
                    rememberColor(state.color);
                    if (wasHidden === state.visible) {
                        // ★ 显示 / 隐藏 走**和图例眼睛完全同一条路径**：
                        //   以前这里把指标从 items 里删掉 → 指标线**和标签**
                        //   一起消失，和眼睛的行为不一致（用户实测 ✗）
                        this.toggleIndicator(item.key, !!state.visible, cell);
                    } else {
                        this._renderLegendRows(cell);
                    }
                    // 显示区域变了 → 重新加一次（主图 ↔ 副图）
                    if (!overlayLocked && !!state.overlay !== !!item.overlay) {
                        this.options.onCommand?.('add_indicator', {
                            symbol: this.symbolForCell(cell),
                            key: (item as unknown as { source?: string }).source
                                || String(item.key).split(':')[0],
                            params: state.params,
                            overlay: state.overlay,
                            cell,
                        });
                        return;
                    }
                    // 参数变了 → 让后端重算
                    const before = JSON.stringify(item.params || {});
                    if (JSON.stringify(state.params) !== before) {
                        this.options.onCommand?.('add_indicator', {
                            symbol: this.symbolForCell(cell),
                            key: (item as unknown as { source?: string }).source
                                || String(item.key).split(':')[0],
                            params: state.params,
                            cell,
                        });
                    }
                },
                onDelete: () => {
                    this.options.onCommand?.('remove_indicator', {
                        symbol: this.symbolForCell(cell),
                        key: (item as unknown as { source?: string }).source
                            || String(item.key).split(':')[0],
                        cell,
                    });
                },
                // ★ 选颜色 → 立即预览（不用等「应用」，用户要求 ✓）
                onColorPreview: (color) => {
                    layer.applyStyle(item.key, currentState(color));
                    rememberColor(color);
                    this._renderLegendRows(cell);
                },
            },
            this.options.theme === 'light' ? 'light' : 'dark',
            (item as unknown as {
                paramMeta?: Record<string, Record<string, number>> }).paramMeta
                || {},
        );
    }

    /** ⚙ 改参数：**就地输入**（保留旧 API ✓） */
    editIndicator(item: IndicatorLine, anchor?: HTMLElement | null,
                  cell = 0): void {
        const params = { ...(item.params || {}) } as Record<string, unknown>;
        if (!Object.keys(params).length) {
            this.toast(`${item.label || item.key} 没有可调参数`);
            return;
        }
        openParamPopover(
            anchor || null,
            item.label || item.key,
            params,
            (values) => {
                this.options.onCommand?.('add_indicator', {
                    symbol: this.symbolForCell(cell),
                    key: (item as unknown as { source?: string }).source
                        || String(item.key).split(':')[0],
                    params: values,
                    cell,
                });
            },
            this.options.theme === 'light' ? 'light' : 'dark',
        );
    }

    /** 每格指标一起换（布局应用时用 ✓） */
    setCellIndicatorMap(map: Record<string, IndicatorPayload>): void {
        Object.entries(map || {}).forEach(([key, payload]) => {
            this.setCellIndicators(Number(key) || 0, payload);
        });
    }

    /** 交易开关（实盘 → 前端二次确认 ✓） */
    setTrading(enabled: boolean, real = false): void {
        this.book.setTrading(enabled, real);
        this.setTradingState(enabled, real);
    }

    /** 底部「交易账户」面板（11 卡 + 4 表 + 多账户）✓ */
    setAccount(payload: AccountPayload): void {
        this.dock.setAccount(payload);
    }

    /** 运行日志（成交/委托/切换账户…）✓ */
    appendLog(text: string, level = 'info', ts = ''): void {
        this.dock.appendLog(text, level, ts);
    }

    /** 净仓 → 买卖盘标签（多仓右侧平仓 / 空仓左侧平仓 ✓） */
    private _setTicketPosition(
            payload: { long?: PosSide | null; short?: PosSide | null }): void {
        const long = Number(payload?.long?.volume || 0);
        const short = Number(payload?.short?.volume || 0);
        const net = Math.round(long - short);
        if (net === this.ticketNet) return;
        this.ticketNet = net;
        this._renderTicket();
    }

    /** 导出历史（`app.ts` 收到 `exports` 补丁时分发过来 ✓） */
    setExports(items: ExportRow[]): void {
        this.exportRows = Array.isArray(items) ? items : [];
    }

    /** 导出历史菜单（**看盘页不再有入口**，留给报价页共用实现 ✓） */
    openExportHistory(anchor?: HTMLElement): void {
        const button = anchor || this.exportButton;
        if (!button) return;
        this.options.onCommand?.('exports', {});
        showExportHistory(button, this.exportRows, {
            onOpen: (path, folder) => this.options.onCommand?.(
                'open_export', { path, folder: !!folder }),
            onDelete: (path) => this.options.onCommand?.(
                'export_remove', { path }),
            onClear: () => this.options.onCommand?.('exports_clear', {}),
        });
    }

    /** 播放条开关只看「行情报价页」了 —— 这里保留状态同步（无按钮 ✓） */
    private _syncTickerButton(): void {
        void this.tickerButton;
        void this.tickerOnlyQuoted;
    }

    /** 偏好设置（`ticket_click_orders` 等，后端落盘 ✓） */
    setSettings(settings: Record<string, unknown>): void {
        const ticker = settings?.ticker_only_quoted;
        this.tickerOnlyQuoted = ticker === true || ticker === 1
            || ticker === 'true';
        this._syncTickerButton();
        const dockHeight = Number(settings?.dock_height);
        if (Number.isFinite(dockHeight) && dockHeight >= 140) {
            this.dockHeight = Math.round(dockHeight);
            const total = this.element.getBoundingClientRect().height
                || this.element.clientHeight;
            if (total > 240) this.dockRatio = this.dockHeight / total;
            if (this.dockSplitter) {
                this._applyDockRatio(total);
                this.dock.element.style.height = `${this.dockHeight}px`;
            }
        }
        const filter = String(settings?.indicator_overlay_filter || 'all');
        this.indicatorFilter = filter === 'main' || filter === 'sub'
            ? filter : 'all';
        this.indicatorPicker?.setOverlayFilter(this.indicatorFilter);
        const refreshMs = Number(settings?.indicator_refresh_interval_ms);
        this.tableIntervalMs = Number.isFinite(refreshMs)
            ? Math.max(10, Math.min(3000, refreshMs)) : 1000;
        this.tableNewBarOnly = settings?.indicator_custom_new_bar === true;
    }

    /**
     * 「设置 → 图表设置」：字号 / 涨跌色 / 鼠标标签色（立即生效 ✓）
     *
     * 键名和后端 `user_prefs.SETTING_KEYS` 一致（`chart_font_size` …）。
     */
    setChartConfig(values: Record<string, unknown>): void {
        if (!values) return;
        if ('chart_font_size' in values) {
            const size = Math.max(9, Math.min(28,
                Number(values.chart_font_size) || 13));
            this.fontSize = size;
            for (const handler of this.cells) {
                const legend = (handler as unknown as {
                    legend?: { div?: HTMLElement } }).legend;
                if (legend?.div) legend.div.style.fontSize = `${size}px`;
            }
            this._renderLegendRows(0);
        }
        if ('chart_color_up' in values) {
            this.customUp = String(values.chart_color_up || '');
        }
        if ('chart_color_down' in values) {
            this.customDown = String(values.chart_color_down || '');
        }
        if ('chart_color_up' in values || 'chart_color_down' in values) {
            this._applyChartType();          // 蜡烛 / 颜色重建 ✓
        }
        if ('chart_crosshair_style' in values) {
            this.crosshairStyle = String(
                values.chart_crosshair_style || 'classic');
            this._applyCrosshairStyle();
        }
        if ('chart_color_crosshair' in values) {
            this.customCrosshair = String(values.chart_color_crosshair || '');
            this._applyCrosshairStyle();
        }
        // ★ 设置 → 图表配置：持仓线 / 挂单线（全局开关，默认开 ✓）
        if ('position_line' in values) {
            this.positionLineVisible = values.position_line !== false;
            this.togglePositionLine(this.positionLineVisible);
        }
        if ('order_line' in values) this.setOrderLines(values.order_line !== false);
    }

    /** 十字线样式（默认跟随主题；设置里可选预设）✓ */
    private _applyCrosshairStyle(): void {
        const options = crosshairOptions(
            this.options.theme === 'light' ? 'light' : 'dark',
            this.crosshairStyle, this.customCrosshair);
        for (const handler of this.cells) {
            try {
                (handler as unknown as { chart: { applyOptions: Function } })
                    .chart.applyOptions(options);
            } catch {
                /* ignore */
            }
        }
    }

    /** 主题色（theme_accent）变化时刷新十字线标签 ✓ */
    refreshCrosshair(): void {
        this._applyCrosshairStyle();
    }

    /** 兼容旧调用名（主题切换时使用 ✓） */
    private _applyCrosshairColor(): void {
        this._applyCrosshairStyle();
    }

    /** 小数位（合约最小变动价位 → 2 位 / 3 位 ✓） */
    setDecimals(decimals: number): void {
        if (!Number.isFinite(decimals)) return;
        const value = Math.max(0, Math.min(6, Math.round(decimals)));
        if (value === this.ticketDecimals) return;
        this.ticketDecimals = value;
        this._renderTicket();
        this.alertDialog?.setDecimals(value);
    }

    /** 二级报价（5 档 + 信息 + 分笔）—— 只读，P4 才有下单按钮 ✓ */
    setBook(data: BookData): void {
        const decimals = Number((data as unknown as { decimals?: number })
            .decimals);
        if (Number.isFinite(decimals)) this.setDecimals(decimals);
        // ★ 价格步进 = 合约最小变动价位（上下键 / 箭头按它调 ✓）
        const tick = Number((data as unknown as { price_tick?: number })
            .price_tick);
        if (Number.isFinite(tick) && tick > 0) this.ticket?.setStep(tick);
        this.book.setBook(data);
        this.setTicketBook({ bids: data.bids || [], asks: data.asks || [] });
        // ★ 价格框跟随**当前交易标的**的最新价（用户手填过就不动 ✓）
        const target = this.tradeSymbol || this.options.symbol;
        if (!data.symbol || data.symbol === target) {
            const last = Number((data.info as unknown as { last?: number })?.last);
            if (Number.isFinite(last) && last > 0) this.ticket?.setPrice(last);
        }
        // 买卖盘价格跟买一/卖一走，不填最新价 ✓
    }

    /**
     * 持仓线：多/空取**手数多的那一侧**的均价画虚线（同 miniqt ✓）。
     * 没有持仓 → 移除。
     */
    /** 每格最近一次的持仓（`setPositionLines(true)` 重画时用 ✓） */
    private readonly lastPositions = new Map<number, {
        long?: PosSide | null; short?: PosSide | null; tradeable?: boolean;
    }>();

    setPosition(payload: {
        long?: PosSide | null; short?: PosSide | null; tradeable?: boolean;
    }, cell = 0): void {
        const index = Math.max(0, Math.min(Number(cell) || 0,
                                         Math.max(0, this.cells.length - 1)));
        this.lastPositions.set(index, payload);
        // 交易面板的净仓只跟**当前交易标的**走（多格时不能混在一起 ✓）
        const symbol = this.cellSymbols[index] || this.options.symbol;
        const focus = this.tradeSymbol || this.options.symbol;
        if (index === 0 || symbol === focus) {
            this._setTicketPosition(payload);
        }
        this._applyPositionLine(payload, index);
    }

    /** 真正画某一格的持仓线（`setPosition` 内部用 ✓） */
    private _applyPositionLine(payload: {
        long?: PosSide | null; short?: PosSide | null;
        tradeable?: boolean }, cell = 0): void {
        this.hidePositionLine(cell);
        if (!this.positionLineVisible) return;
        const handler = this.cells[cell];
        if (!handler) return;
        const tail = (this.cellBars[cell] || []).slice(-1)[0] as
            { close?: number } | undefined;
        const fallback = Number(tail?.close) || 0;
        const sides = [payload.long, payload.short].filter(
            (side): side is PosSide => !!side && !!side.volume
                && (Number(side.avg) > 0 || fallback > 0));
        if (!sides.length) return;
        const keys: string[] = [];
        for (const side of sides) {
            const short = side.side === '空';
            const avg = Number(side.avg) > 0 ? Number(side.avg) : fallback;
            const profit = Number(side.profit ?? 0);
            const text = `${short ? '空' : '多'}仓`
                + `${Math.round(side.volume || 0)}手 `
                + `${profit >= 0 ? '盈利' : '亏损'}${Math.abs(profit).toFixed(2)}`;
            const color = short ? '#ef5350' : '#26a69a';
            const line = new HorizontalLine(
                { time: null, logical: 0 as never, price: avg },
                {
                    lineColor: color,
                    lineStyle: 2 as never,
                    width: 1,
                    text,
                    axisLabelVisible: false,
                    labelVisible: false,
                },
                null,
            );
            try {
                const series = handler.series as unknown as
                    { attachPrimitive: Function };
                series.attachPrimitive(line);
                const bucket = this.positionLinesByCell.get(cell) || [];
                bucket.push({ side: short ? 'short' : 'long', line });
                this.positionLinesByCell.set(cell, bucket);
                keys.push(`${side.side}${side.volume}${avg}`);
                // ★ 标签绑在**持仓所在那一格**（多布局每格各一根 ✓）
                this._addPositionBadge(avg, text, color, cell);
            } catch {
                try { line.detach(); } catch { /* ignore */ }
            }
        }
        this.positionKey = keys.join('|');
        this._placePositionBadge();
    }

    get positionLineKey(): string {
        return this.positionKey;
    }

    private _addPositionBadge(price: number, text: string,
                              color: string, cell = 0): void {
        const badge = document.createElement('div');
        badge.className = 'desk-pos-badge';
        badge.textContent = text;
        badge.style.borderColor = color;
        badge.style.color = color;
        badge.dataset.price = String(price);
        badge.dataset.text = text;
        badge.dataset.cell = String(cell);
        badge.style.display = '';
        this.element.appendChild(badge);
        this.positionBadges.push(badge);
    }

    /**
     * 把持仓色块放到**对应格子**的左侧（跟着均价高度 ✓）
     *
     * 多布局：每格用自己的 `pane` / `priceToCoordinate`（以前全用 `cells[0]`，
     * 第二格的持仓线标签会跑到整页左下角 ✗）；均价在可视区间外时贴上下沿 ✓
     */
    private _placePositionBadge(): void {
        const hostRect = this.element.getBoundingClientRect();
        const groups = new Map<number, HTMLDivElement[]>();
        for (const badge of this.positionBadges) {
            const cell = Math.max(0, Number(badge.dataset.cell) || 0);
            const list = groups.get(cell) || [];
            list.push(badge);
            groups.set(cell, list);
        }
        for (const [cellIndex, badges] of groups) {
            const cell = this.cells[cellIndex] as unknown as {
                series?: { priceToCoordinate?: (p: number) => number | null };
                chart?: { panes?: () => Array<{ getHTMLElement?: Function }> };
            } | undefined;
            const pane = cell?.chart?.panes?.()?.[0]?.getHTMLElement?.();
            if (!pane) {
                for (const badge of badges) badge.style.display = 'none';
                continue;
            }
            const paneRect = pane.getBoundingClientRect();
            const left = paneRect.left - hostRect.left + 8;
            let topOffset = 0;
            let bottomOffset = 0;
            for (const badge of badges) {
                const price = Number(badge.dataset.price);
                const y = Number.isFinite(price)
                    ? cell?.series?.priceToCoordinate?.(price) : null;
                if (y === null || y === undefined || !Number.isFinite(y)) {
                    badge.style.display = 'none';
                    continue;
                }
                const text = String(badge.dataset.text || '');
                badge.style.left = `${left}px`;
                badge.style.display = '';
                if (y < 0) {
                    badge.textContent = `↑ ${text}`;
                    badge.style.top = `${paneRect.top - hostRect.top
                        + 4 + topOffset}px`;
                    topOffset += 20;
                } else if (y > paneRect.height) {
                    badge.textContent = `↓ ${text}`;
                    badge.style.top = `${paneRect.top - hostRect.top
                        + paneRect.height - 20 - bottomOffset}px`;
                    bottomOffset += 20;
                } else {
                    badge.textContent = text;
                    badge.style.top = `${paneRect.top - hostRect.top
                        + y - 9}px`;
                }
            }
        }
        this._placeAlertBadges();
    }

    /** 只清**这一格**（另一格的持仓线 / 标签不能被顺带删掉 ✗） */
    private hidePositionLine(cell = -1): void {
        const target = cell < 0 ? null : cell;
        this.positionBadges = this.positionBadges.filter((badge) => {
            if (target !== null && Number(badge.dataset.cell) !== target) {
                return true;
            }
            badge.remove();
            return false;
        });
        const cells = target === null
            ? [...this.positionLinesByCell.keys()] : [target];
        for (const index of cells) {
            for (const item of (this.positionLinesByCell.get(index) || [])) {
                try { item.line.detach(); } catch { /* ignore */ }
            }
            this.positionLinesByCell.delete(index);
        }
        this.positionKey = '';
    }

    // ------------------------------------------------------------ 挂单线
    /** 设置 → 图表配置「挂单线」开关 / 后端推来的未成交委托 ✓ */
    setOrderLines(visible?: boolean): void {
        if (visible !== undefined) this.orderLineVisible = !!visible;
        this._renderOrderLines();
    }

    /** 未成交委托（挂单）→ 每条一条虚线 + 左侧色块（参考持仓线 ✓）
     *
     * ``cell`` = 多布局的格号（每格只画自己那个合约的挂单 ✓）
     */
    setOrders(items: Array<Record<string, unknown>>, cell = 0): void {
        this.orderItemsByCell.set(Math.max(0, Number(cell) || 0),
                                 Array.isArray(items) ? items : []);
        this._renderOrderLines(Math.max(0, Number(cell) || 0));
    }

    private _renderOrderLines(cell = 0): void {
        this._clearOrderLines(cell);
        if (!this.orderLineVisible) return;
        const handler = this.cells[cell];
        if (!handler) return;
        const items = this.orderItemsByCell.get(cell) || [];
        for (const item of items) {
            const price = Number(item.price);
            if (!Number.isFinite(price) || price <= 0) continue;
            const side = String(item.side || '买');
            const color = side === '卖' ? '#ef5350' : '#26a69a';
            const line = new HorizontalLine(
                { time: null, logical: 0 as never, price },
                {
                    lineColor: color,
                    lineStyle: 2 as never,          // dashed（同持仓线 ✓）
                    width: 1,
                    text: '',
                    axisLabelVisible: false,
                    labelVisible: false,
                },
                null,
            );
            try {
                const series = handler.series as unknown as
                    { attachPrimitive: Function };
                series.attachPrimitive(line);
            } catch {
                continue;
            }
            const badge = document.createElement('div');
            badge.className = 'desk-order-badge';
            const qty = Number(item.qty) || 0;
            const text = `挂单${side}${qty ? Math.round(qty) : ''}手 `
                + price.toFixed(this.ticketDecimals);
            badge.textContent = text;
            badge.title = `${side}${String(item.offset || '开')} ${qty} 手`
                + ` @ ${price}（未成交）`;
            badge.style.borderColor = color;
            badge.style.color = color;
            badge.dataset.price = String(price);
            badge.dataset.cell = String(cell);
            this.element.appendChild(badge);
            const bucket = this.orderLinesByCell.get(cell) || [];
            bucket.push({ line, badge, price });
            this.orderLinesByCell.set(cell, bucket);
        }
        this._placeOrderBadges();
    }

    private _placeOrderBadges(): void {
        const hostRect = this.element.getBoundingClientRect();
        for (const [cellIndex, lines] of this.orderLinesByCell) {
            if (!lines.length) continue;
            const cell = this.cells[cellIndex] as unknown as {
                series?: { priceToCoordinate?: (p: number) => number | null };
                chart?: { panes?: () => Array<{ getHTMLElement?: Function }> };
            } | undefined;
            const pane = cell?.chart?.panes?.()?.[0]?.getHTMLElement?.();
            const paneRect = pane?.getBoundingClientRect();
            for (const item of lines) {
                const y = cell?.series?.priceToCoordinate?.(item.price);
                if (y === null || y === undefined || !paneRect) {
                    item.badge.style.display = 'none';
                    continue;
                }
                item.badge.style.left =
                    `${paneRect.left - hostRect.left + 8}px`;
                item.badge.style.top =
                    `${paneRect.top - hostRect.top + y - 9}px`;
                item.badge.style.display = '';
            }
        }
        this._stackLineBadges();
    }

    private _clearOrderLines(cell = -1): void {
        const cells = cell < 0
            ? [...this.orderLinesByCell.keys()] : [cell];
        for (const index of cells) {
            for (const item of (this.orderLinesByCell.get(index) || [])) {
                try {
                    item.line.detach();
                } catch {
                    /* ignore */
                }
                item.badge.remove();
            }
            this.orderLinesByCell.delete(index);
        }
    }

    /**
     * 左侧色块防重叠：持仓线 / 预警线 / 挂单线价格接近时依次往下让 ✓
     */
    private _stackLineBadges(): void {
        const nodes = Array.from(this.element.querySelectorAll<HTMLElement>(
            '.desk-pos-badge, .desk-alert-badge, .desk-order-badge'))
            .filter((node) => node.style.display !== 'none');
        nodes.sort((a, b) => (parseFloat(a.style.top) || 0)
            - (parseFloat(b.style.top) || 0));
        let last = -999;
        for (const node of nodes) {
            const top = parseFloat(node.style.top) || 0;
            const next = Math.max(top, last + 19);
            if (next !== top) node.style.top = `${next}px`;
            last = next;
        }
    }

    // ------------------------------------------------------------ 预警线
    /** 画/重画预警线：`line !== false` 的预警都画一条，标签在左侧 ✓ */
    private _renderAlertLines(): void {
        this._clearAlertLines();
        if (!this.handler) return;
        for (const item of this.alertItems) {
            const symbol = String(item.symbol || '');
            if (symbol && symbol !== this.options.symbol) continue;
            if (item.line === false) continue;
            const price = Number(item.price);
            if (!Number.isFinite(price) || price <= 0) continue;
            const fired = !!item.fired;
            const color = fired ? '#8b93a1' : '#f59e0b';
            const line = new HorizontalLine(
                { time: null, logical: 0 as never, price },
                {
                    lineColor: color,
                    lineStyle: 2 as never,
                    width: 1,
                    text: '',
                    axisLabelVisible: false,
                    labelVisible: false,
                },
                null,
            );
            try {
                const series = this.handler.series as unknown as
                    { attachPrimitive: Function };
                series.attachPrimitive(line);
            } catch {
                continue;
            }
            const badge = document.createElement('div');
            badge.className = 'desk-alert-badge';
            const text = `${fired ? '已触发' : '预警'} ${price.toFixed(
                this.ticketDecimals)}`;
            badge.textContent = text;
            badge.title = item.message ? String(item.message) : text;
            badge.style.borderColor = color;
            badge.style.color = color;
            badge.dataset.price = String(price);
            this.element.appendChild(badge);
            this.alertLines.push({ line, badge, price });
        }
        this._placeAlertBadges();
    }

    /** 预警线标签：贴左侧（和持仓线同一套坐标换算 ✓） */
    private _placeAlertBadges(): void {
        if (!this.alertLines.length) return;
        const cell = this.cells[0] as unknown as {
            series?: { priceToCoordinate?: (p: number) => number | null };
            chart?: { panes?: () => Array<{ getHTMLElement?: Function }> };
        } | undefined;
        const pane = cell?.chart?.panes?.()?.[0]?.getHTMLElement?.();
        const paneRect = pane?.getBoundingClientRect();
        const hostRect = this.element.getBoundingClientRect();
        for (const item of this.alertLines) {
            const y = cell?.series?.priceToCoordinate?.(item.price);
            if (y === null || y === undefined || !paneRect) {
                item.badge.style.display = 'none';
                continue;
            }
            item.badge.style.left = '8px';
            item.badge.style.top =
                `${paneRect.top - hostRect.top + y - 9}px`;
            item.badge.style.display = '';
        }
    }

    private _clearAlertLines(): void {
        for (const item of this.alertLines) {
            try {
                item.line.detach();
            } catch {
                /* ignore */
            }
            item.badge.remove();
        }
        this.alertLines = [];
    }

    setCycle(cycle: number): void {
        this.cycle = cycle;
        this.cycleLabel.textContent = this._cycleText(cycle);
        // ★ 画线按「合约|周期」存 → 换周期要换一套 ✓
        this._refreshDrawings();
        // 回放工具条上的「周期」按钮也跟着走（用户没手动换过才跟 ✓）
        if (this.replayCycleLabel && !this.replayCycle) {
            this.replayCycleLabel.textContent = this._cycleText(cycle);
        }
    }

    // ------------------------------------------------------------ helpers
    private _cycleText(cycle: number): string {
        return cycleLabel(cycle);
    }

    /** 周期菜单：`＋ 添加自定义周期…` + `秒/分/时/天` 二级 + `范围` ✓ */
    private _openCycleMenu(anchor: HTMLElement): void {
        const pick = (value: number) => {
            this.setCycle(value);
            this.options.onCycleChange?.(value);
        };
        const items: MenuItem[] = [
            { label: '＋ 添加自定义周期…', run: () => this._promptCycle() },
        ];
        for (const group of CYCLE_GROUPS) {
            items.push({
                label: group.label,
                separator: group.label === '秒',
                submenu: group.items.map((item) => ({
                    label: `${item.label}${item.value === this.cycle ? '  ✓' : ''}`,
                    run: () => pick(item.value),
                })),
            });
        }
        items.push({
            label: '范围', separator: true,
            submenu: [
                { label: '最近 100 根', run: () => this.setRange(100) },
                { label: '最近 200 根', run: () => this.setRange(200) },
                { label: '最近 500 根', run: () => this.setRange(500) },
                { label: '全部显示', run: () => this.setRange(0) },
            ],
        });
        showMenuBelow(anchor, items);
    }

    /** 自定义周期（秒；也认 `5分` / `2时` / `3天` 这种写法 ✓） */
    private _promptCycle(): void {
        const text = window.prompt(
            '自定义周期（数字=秒；也可写 5分 / 2时 / 3天 / 1周）',
            String(this.cycle));
        if (!text) return;
        const value = parseCycle(text);
        if (!value) {
            this.toast('周期要大于 0（例：90 / 5分 / 2时 / 3天）');
            return;
        }
        this.setCycle(value);
        this.options.onCycleChange?.(value);
    }

    /** 显示范围（`0` = 全部 ✓） */
    setRange(bars: number): void {
        const chart = this.handler?.chart;
        if (!chart) return;
        const scale = chart.timeScale();
        if (bars > 0) scale.setVisibleLogicalRange(
            { from: this.bars.length - bars, to: this.bars.length });
        else scale.fitContent();
    }

    private _toolButton(text: string,
                        onClick: (button: HTMLButtonElement) => void,
                        tip = ''): HTMLButtonElement {
        const button = document.createElement('button');
        button.className = 'desk-tool';
        button.textContent = text;
        if (tip) button.title = tip;
        button.addEventListener('click', () => onClick(button));
        return button;
    }

    private _separator(): HTMLSpanElement {
        const span = document.createElement('span');
        span.className = 'desk-sep';
        return span;
    }

    /** 十字线 / 最新 → 左上角 K 线信息 ✓ */
    private _bindLegendCrosshair(): void {
        const chart = (this.handler as unknown as {
            chart: { subscribeCrosshairMove: Function } } | null)?.chart;
        if (!chart) return;
        chart.subscribeCrosshairMove((param: Record<string, unknown>) => {
            const time = param && param.time ? Number(param.time) : null;
            for (let index = 0; index < this.cells.length; index += 1) {
                const bars = this.cellBars[index] || [];
                const matched = time === null ? undefined
                    : bars.find((item) => Number(item.time) === time);
                this._updateLegend(matched || bars[bars.length - 1], index);
            }
        });
    }

    private _updateLegend(bar?: ChartBar, cell = 0): void {
        const target = this.cellLegendOhlc[cell] || this.legendOhlc;
        if (!target) return;
        if (!bar) {
            target.textContent = '--';
            return;
        }
        const time = new Date(bar.time * 1000);
        const pad = (value: number) => String(value).padStart(2, '0');
        const stamp = `${time.getFullYear()}-${pad(time.getMonth() + 1)}-${pad(time.getDate())} `
            + `${pad(time.getHours())}:${pad(time.getMinutes())}`;
        const pct = bar.open ? ((bar.close - bar.open) / bar.open) * 100 : 0;
        const fmt = (value: number) => value.toFixed(3).padStart(8, ' ');
        target.innerHTML = `<span class="k">${stamp}</span>`
            + ` | O ${fmt(bar.open)} | H ${fmt(bar.high)}`
            + ` | L ${fmt(bar.low)} | C ${fmt(bar.close)}`
            + ` | V ${Math.round(bar.volume ?? 0)} | `
            + `<b class="${pct >= 0 ? 'up' : 'down'}">`
            + `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%</b>`;
    }

    private _nextId(): string {
        const alphabet = 'abcdefghijklmnopqrstuvwxyz';
        let id = 'desk';
        for (let i = 0; i < 6; i += 1) {
            id += alphabet[Math.floor(Math.random() * alphabet.length)];
        }
        return id;
    }

    show(): void {
        this.element.style.display = '';
        this.mount();
        this.resize();
    }

    hide(): void {
        this.element.style.display = 'none';
    }
}

/** `90` / `5分` / `2时` / `3天` / `1周` → 秒 ✓ */
export function parseCycle(text: string): number {
    const value = String(text || '').trim().toLowerCase();
    if (!value) return 0;
    const match = value.match(/^([0-9.]+)\s*(s|秒|m|分|min|h|时|小时|d|天|w|周|mo|月)?$/);
    if (!match) return 0;
    const amount = Number(match[1]);
    if (!Number.isFinite(amount) || amount <= 0) return 0;
    const unit = match[2] || 's';
    const scale: Record<string, number> = {
        s: 1, 秒: 1, m: 60, 分: 60, min: 60,
        h: 3600, 时: 3600, 小时: 3600,
        d: 86400, 天: 86400, w: 604800, 周: 604800,
        mo: 2592000, 月: 2592000,
    };
    return Math.max(1, Math.round(amount * (scale[unit] || 1)));
}

/**
 * 合并 K 线（按 `time` 去重、保持升序 ✓）
 *
 * - 同一 `time` → 用**新的**那根覆盖（正在走的那根 K 线会变）
 * - 更晚的 `time` → 追加（新一根）
 * - 更早的 `time` → 忽略（历史不回改）
 *
 * 这一步是「实时更新」的关键：后端每秒只推最后 1~2 根，
 * 前端必须合并进现有数组，而不是无脑拼接 ✗
 */
export function mergeBars(previous: ChartBar[], incoming: ChartBar[]): ChartBar[] {
    if (!incoming.length) return previous;
    const merged = previous.slice();
    for (const bar of incoming) {
        const last = merged[merged.length - 1];
        if (!last || bar.time > last.time) {
            merged.push(bar);
            continue;
        }
        if (bar.time === last.time) {
            merged[merged.length - 1] = bar;      // 正在走的那根 → 覆盖 ✓
            continue;
        }
        // 历史更早的：找一下有没有同一时间（回补）→ 覆盖，否则忽略
        const index = merged.findIndex((item) => item.time === bar.time);
        if (index >= 0) merged[index] = bar;
    }
    return merged;
}

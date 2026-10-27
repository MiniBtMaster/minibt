/**
 * LocalChartPage — 本地图表页（静态 CSV / 回放 / 本地模拟交易）。
 *
 * ⚠ 本文件是 `chart-page.ts` 的**副本**（用户要求：本地图表与实时看盘
 * 隔离，不共用同一份实现），只保留静态图表需要的功能：
 *   - 无二级报价、无实时推送、周期固定（由 CSV 的 duration 决定）；
 *   - 保留回放 / 指标 / 画线 / 预警 / 交易（本地模拟账户）。
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
import {
    DESK_LAYOUTS, layoutSpecByKey, layoutSpecForCount, layoutSpecOf,
    type DeskLayoutSpec,
} from './chart-page';
// 图例图标（齿轮 / 眼睛）和 miniqt 共用同一套 SVG ✓
import { EYE_CLOSED, EYE_OPEN, GEAR } from '../general/legend';
import { HorizontalLine } from '../horizontal-line/horizontal-line';
import { AccountDock, type AccountPayload } from './account-dock';
// 「编辑器」页签（本地图表也能写个人指标 / 策略 ✓）
import { EditorPanel } from './editor-panel';
import { buildReplayTicket, type ReplayTicket }
    from './replay-ticket';
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
// 工具栏图标：单色 SVG（`currentColor`）→ 深浅主题都对 ✓
import {
    ICON_BELL, ICON_CAMERA, ICON_ERASER, ICON_PAUSE, ICON_PENCIL,
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

interface LocalStrategySignal {
    id: string;
    time: number;
    side: 'buy' | 'sell';
    close?: boolean;
    price?: number;
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
    /** 本地 LSP（jedi）地址；`undefined` = 不可用 → 编辑器静默降级 ✓ */
    lsp?: () => { url: string; root: string } | undefined;
    /** ★ 收藏的指标（`{key,label,provider,params}`） */
    favorites?: Array<Record<string, unknown>>;
    /** ★ 收藏的策略 */
    strategyFavorites?: Array<Record<string, unknown>>;
    /** 主题（副图背景色要用 ✓） */
    theme?: 'light' | 'dark';
    /** 编辑器「策略回测 / 参数优化」→ App 打开独立策略 Tab ✓ */
    onStrategy?: (path: string, mode: 'backtest' | 'optimize') => void;
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

export class LocalChartPage {
    public readonly element: HTMLDivElement;
    public cycle: number;

    private readonly legend: HTMLDivElement;
    private readonly host: HTMLDivElement;
    private readonly cycleLabel: HTMLSpanElement;
    private handler: Handler | null = null;
    private readonly cells: Handler[] = [];
    private grid: HTMLDivElement | null = null;
    private layout: { cols: number; rows: number } = { cols: 1, rows: 1 };
    /** 布局规格（含**跨格**：上下左下右 / 上左上右下 ✓） */
    private spec: DeskLayoutSpec = layoutSpecByKey('single');
    private toolBoxOn = false;
    /** 「预警」对话框（Lib.AlertDialog，复刻 miniqt 的创建预警 ✓） */
    private alertDialog: AlertDialog | null = null;
    private tradeButton: HTMLButtonElement | null = null;
    /** 键盘精灵（空格键：搜指标 / 策略 / 合约 / 股票 ✓） */
    private sprite: KeyboardSprite | null = null;
    private spriteHotkey: ((event: KeyboardEvent) => void) | null = null;
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
    /** 回放 */
    private replay: Replay | null = null;
    private replayBar: HTMLDivElement | null = null;
    private replayLabel: HTMLSpanElement | null = null;
    private replaying = false;
    /** 已放到最后一根：暂停但**不退出**（等待用户平仓后手动退出 ✓） */
    private replayEnded = false;
    /** 正在恢复回放前数据：忽略 Replay.stop() 触发的空 onBars ✓ */
    private restoringReplay = false;
    /** 回放参数（「选择时间段 / 更换周期」改完就地重放 ✓） */
    private replaySeek = 0.3;
    private replayCycle = 0;
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
    private readonly cellLegendRows: HTMLDivElement[] = [];
    private readonly cellItems: IndicatorLine[][] = [];
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
    /** 本地模拟交易控件（共用组件 ✓） */
    private localTicket: ReplayTicket | null = null;
    /** 进回放前记住的可视范围（退出时恢复 ✓） */
    private savedRanges: Array<{ from: number; to: number } | null> = [];
    /** 「编辑器」面板（第一次切到该页签才建 ✓） */
    private editor: EditorPanel | null = null;
    private dockSplitter: HTMLDivElement | null = null;
    private dockHeight = 232;
    /** 底部面板占整个图表页的比例（窗口缩放时按它一起缩放 ✓） */
    private dockRatio = 1 / 4;
    private dockMaximized = false;
    /** 设置 → 编辑器「保存时自动格式化」✓ */
    private formatOnSaveSetting = false;
    private dockRestoreHeight = 0;
    private dockRestoreRatio = 1 / 4;
    private _dockSized = false;
    /** 高度来自设置（`dock_height`）→ 首次不再按 1/3 盖掉 ✓ */
    /** 兼容老逻辑的标记（现在初始化固定 3:1，不再读设置 ✓） */
    private _dockFromSettings = false;

    /** 只在调试面板用到：是否来自设置（保留 getter 避免未使用告警 ✓） */
    get dockFromSettings(): boolean {
        return this._dockFromSettings;
    }
    private bookVisible = false;
    private observer: ResizeObserver | null = null;
    private bars: ChartBar[] = [];
    private attached = false;
    private readonly book: QuotePanel;
    private readonly dock: AccountDock;
    /** ---- 本地图表状态（静态 CSV / 回放 / 本地模拟账户）---- */
    private localBars: ChartBar[] = [];
    /** 每格完整 CSV（回放切片后用它还原 ✓） */
    private localBarsByCell: ChartBar[][] = [];
    private localDecimals = 2;
    /** 本地数据的最小变动价位（CSV 的 `price_tick`；默认 0.01 ✓） */
    private localPriceTick = 0.01;
    private localPrice = 0;
    private localName = '';
    /** 鼠标最后点击的格子（0-based）✓ */
    private activeCell = 0;
    private localDataItems: Array<Record<string, unknown>> = [];
    /** 已添加的数据文件夹（数据菜单里列出来 ✓） */
    private localFolders: string[] = [];
    /** 每格完整指标数据（回放按时间切片 ✓） */
    private localIndicators: Array<IndicatorPayload | null> = [];
    private localAlerts: Array<Record<string, unknown>> = [];
    private localAlertSeq = 0;
    private localPrevPrice = 0;
    private localPriceInput: HTMLInputElement | null = null;
    private localQtyInput: HTMLInputElement | null = null;
    private localInfo: HTMLDivElement | null = null;
    /** 第 1 格的指标图层（兼容旧逻辑 ✓） */
    private readonly indicators: IndicatorLayer;
    private readonly subHost: HTMLDivElement;
    /** **每格**各一个指标图层（布局多图，各自副图 / 各自指标 ✓） */
    private readonly layers: IndicatorLayer[] = [];
    private crosshairStyle = 'classic';
    private customCrosshair = '';
    private customUp = '';
    private customDown = '';
    /** 回放时的指标（后端一次算好，按可见时间切片 ✓） */
    private replayIndicators: IndicatorLine[] = [];
    private replaySymbol = '';
    /** 进入回放 / seek 后的**第一次有效刷新** → 通知后端重置策略回放 ✓ */
    private replayResetPending = false;
    /**
     * 旧版按指标 B/S 信号成交（默认关闭 ✗）。
     *
     * 现在统一由后端 `StrategyRunner` 执行 —— 多合约 `set_target_size()` 也
     * 走同一条路；如果这里再按 marker 成交一次，同一根会**成交两遍** ✗
     */
    private legacySignalTrades = false;
    /** 策略信号自动交易：本轮回放是否要清空已执行信号 / 每格已同步到哪根 */
    private strategyTradeReset = true;
    private readonly strategyTradeSentUntil = new Map<number, number>();
    /** 多图回放：每格的 K 线 / 指标 ✓ */
    private replayCells: Array<{ cell: number; bars: ReplayBar[];
                                indicators: IndicatorLine[] }> = [];
    /** 多空可以同时持仓：每条腿各一条线 / 一个左侧标签 ✓ */
    /** 每格的持仓线（多布局各自独立，互不清除 ✓） */
    private positionLinesByCell = new Map<number,
        Array<{ side: string; line: HorizontalLine }>>();
    private positionBadges: HTMLDivElement[] = [];
    private positionKey = '';
    /** 挂单线（未成交委托）：价格 + 买/卖 + 手数，标签在左侧 ✓ */
    private orderLineVisible = true;
    /** 挂单（按格：多布局每格只画自己那个 CSV 的挂单 ✓） */
    private readonly orderItemsByCell =
        new Map<number, Array<Record<string, unknown>>>();
    private orderLines: Array<{ cell: number; line: HorizontalLine;
                                badge: HTMLDivElement;
                                price: number }> = [];
    /** 预警线（可多条；标签同样在图内左侧 ✓） */
    private alertLines: Array<{ line: HorizontalLine; badge: HTMLDivElement;
                                price: number }> = [];

    constructor(private readonly options: ChartPageOptions) {
        this.cycle = options.cycle || 60;

        this.element = document.createElement('div');
        this.element.className = 'desk-chart-page';

        // ---- toolbar -------------------------------------------------------
        const toolbar = document.createElement('div');
        toolbar.className = 'desk-chart-toolbar';

        const symbol = document.createElement('button');
        symbol.className = 'desk-symbol desk-symbol-btn';
        symbol.title = '选择本地数据（CSV；可添加文件夹）';
        symbol.textContent = `${options.symbol || '选择本地数据'} 🔍`;
        if (options.name) {
            const name = document.createElement('span');
            name.className = 'desk-muted';
            name.textContent = ` ${options.name}`;
            symbol.appendChild(name);
        }
        symbol.addEventListener('click', () => this.openLocalDataSearch());
        symbol.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            this.openLocalDataMenu();
        });
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
        // ★ 本地图表周期由 CSV 的 duration 决定，不允许切换 ✓
        cycleButton.disabled = true;
        cycleButton.title = '本地图表：周期由数据决定（不可切换）';
        cycleButton.classList.add('desk-tool-disabled');
        void this._openCycleMenu;        // 保留菜单实现（周期按钮禁用）

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
        const templateButton = this._toolButton('模板', () => {
            this.openTemplatePicker();
        }, '指标模板（保存 / 应用当前 CSV 的指标组合）');
        const alertButton = this._toolButton('', () => this._openAlertDialog(),
                                             '价格预警（到价提醒 / 可转下单）');
        alertButton.innerHTML = ICON_BELL;
        alertButton.title = '价格预警（本地数据 / 回放中也可用）';
        // ★ 回放按钮（复刻 miniqt：rewind 图标，选中时主题色底 ✓）
        const playButton = this._toolButton(
            '', () => this.toggleReplay(),
            '回放：进入后逐根播放历史 K 线（再点一次回到实时）');
        playButton.classList.add('desk-tool-replay');
        playButton.innerHTML = REWIND_SVG;
        this.playButton = playButton;
        // ★ 布局四合一（P27）：单图/左右/四图 + 已保存布局 + 保存 + 管理
        const layoutButton = this._toolButton('布局', (button) => {
            this.openLayoutMenu(button);
        }, '布局：预设 / 已保存布局 / 保存 / 管理 / 导入导出');
        layoutButton.classList.add('desk-tool-arrow');
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
        const tradeButton = this._toolButton('交易/编辑器', () => this.toggleDock(),
                                             '显示 / 隐藏下方「交易账户」面板');
        const bookButton = this._toolButton('二级报价', () => this.toggleBook(),
                                            '显示 / 隐藏右侧「二级报价」面板');
        this.tradeButton = tradeButton;
        this.bookButton = bookButton;
        // ---- 右侧工具组（按 miniqt 的顺序 ✓）---
        const deleteIndicator = this._toolButton(
            '', (button) => this.openRemoveMenu(button),
            '删除指标（按图表汇总，可删单个 / 全部）');
        deleteIndicator.innerHTML = ICON_TRASH;
        const clearDrawings = this._toolButton('', () => this.clearDrawings(),
                                               '清除全部画线');
        clearDrawings.innerHTML = ICON_ERASER;
        const linkButton = this._toolButton('联动', () => this.toggleLink(),
                                            '多图联动（时间轴 / 十字线同步）');
        const ticketButton = this._toolButton('买卖盘', () => this.toggleOrderTicket(),
                                              '图上买卖盘（买入 / 点差 / 卖出，有仓→平仓）');
        this.ticketButton = ticketButton;
        const shotButton = this._toolButton('', () => this.screenshot(),
                                            '截图（PNG）');
        shotButton.innerHTML = ICON_CAMERA;
        // ⚠ 「播放条」「导出历史」只对**行情报价页**有意义，看盘窗口不放
        //   （用户要求移除 ✓）——所以这里不再建这两个按钮。
        const spacer = document.createElement('span');
        spacer.className = 'desk-toolbar-spacer';

        this.linkButton = linkButton;

        // 左侧：周期 / 图表类型 / 指标 / 模板 ；右侧（miniqt 顺序）：
        // 删除指标 / 清空画线 / 持仓线 / 联动 / 买卖盘 / **布局 / 画线** / 交易 /
        // 二级报价 / 截图（布局与画线工具放在「交易」左边 ✓，用户要求）
        // 本地图表：无模板 / 布局 / 联动 / 二级报价 / 浮动买卖盘
        //（交易控件移到底部「交易账户」页，见 _buildLocalTicket ✓）
        toolbar.append(symbol, this._separator(), cycleButton, kindButton,
                       indicatorButton, templateButton,
                       this._separator(), alertButton, playButton,
                       spacer,
                       deleteIndicator, clearDrawings, lineButton,
                       linkButton, ticketButton, bookButton,
                       layoutButton, tradeButton, shotButton);
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
        // 图表右键菜单（本地图表也保留：指标 / 周期固定 / 画线 / 预警 / 截图）
        this.host.addEventListener('contextmenu', (event) => {
            const target = event.target as HTMLElement | null;
            if (target?.closest('input,textarea,select,.toolbox,.context-menu')) {
                return;
            }
            if (Drawing.hoveredObject) return;
            event.preventDefault();
            this._openChartContextMenu(event.clientX, event.clientY);
        });
        this.host.addEventListener('pointerdown', (event) => {
            const target = event.target as HTMLElement | null;
            const cell = target?.closest('.desk-chart-cell') as
                HTMLDivElement | null;
            const index = cell ? this.cellElements.indexOf(cell) : -1;
            if (index < 0) return;
            // ★ 同一个格子再点一次也要生效：用户可能先点了 A，又点回 A；
            //   而且「鼠标最后点击的合约」要成为交易面板的标的 ✓
            this.activeCell = index;
            this.options.symbol = this.symbolForCell(index);
            this._syncSymbolButton();
            this._syncActiveLocalPrice();
            // ★ 多布局：点哪一格 → 交易面板 / 商品搜索就切到**那一格的合约** ✓
            this.options.onCommand?.('local_active', {
                cell: index,
                symbol: this.symbolForCell(index),
                name: this.symbolForCell(index),
            });
        });

        this.subHost = document.createElement('div');
        this.subHost.className = 'desk-ind-host';
        const main = document.createElement('div');
        main.className = 'desk-chart-main';
        main.append(this.host, this.subHost);

        // 二级报价只负责看盘 / 点档填价（下单按钮统一到交易面板 ✓）
        this.book = new QuotePanel();
        // 二级报价点档位 → 只把价格填进下单框（买卖盘本身是市价调仓 ✓）
        this.book.onPricePick = (price) => this.setTicketPrice(price, true);
        this.book.onLevelClick = (_side, price) => this.setTicketPrice(price);
        const body = document.createElement('div');
        body.className = 'desk-chart-body';
        body.append(main, this.book.element);

        this.dock = new AccountDock((cmd, payload) => this.options.onCommand?.(
            cmd, payload));
        // ★ 编辑器页签 + 最大化（和看盘窗口同一套 ✓）
        this.dock.onEditorOpen = () => {
            this._ensureEditor().show();
            this.resize();
        };
        this.dock.onTabChange = (tab) => {
            if (tab === 'code') this._ensureEditor().show();
            else this.editor?.hide();
        };
        this.dock.onToggleMaximize = () => this.toggleDockMaximize();
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
        // ★ 本地图表：交易 / 编辑器面板**默认关闭**（用户要求 ✓）
        //   需要时点右上角「交易 / 编辑器」按钮打开（或 `toggleDock(true)`）✓
        this.dockVisible = false;
        this.bookVisible = false;
        this.dock.element.style.display = 'none';
        this.book.element.style.display = 'none';
        this._buildLocalTicket();
        // ★ 图表 / 底部面板之间放一条**可拖动**的分隔条（用户要求 ✓）
        this._ensureDockSplitter();
        // dock 默认关闭 → 分隔条也先藏起来（不然底下留一条空条 ✗）
        if (this.dockSplitter) this.dockSplitter.style.display = 'none';
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
        this.observer = new ResizeObserver(() => this.resize());
        this.observer.observe(this.host);
        this.resize();
        // ★ 首次显示：底部（模拟交易）面板占**页面高度的 1/3**（用户要求 ✓）
        const raf = (globalThis as unknown as {
            requestAnimationFrame?: (cb: () => void) => number;
        }).requestAnimationFrame;
        const fit = () => { this._sizeDockToPage(); this.resize(); };
        if (typeof raf === 'function') raf(fit); else fit();
        if (this.bars.length) {
            this.setBars(this.bars, true);
            this._fitLocalRange();
        }
        this._renderAlertLines();
    }

    /** 关掉某一格的图表（只剩一格时不允许；布局回到等分 ✓） */
    closeCell(index = -1): boolean {
        const count = this.cells.length;
        if (count <= 1) return false;
        const target = index < 0
            ? Math.max(0, this.cells.indexOf(this.handler as never))
            : Math.max(0, Math.min(index, count - 1));
        // 先把「剩下的格」数据搬到前面，再按新格数切布局
        const keepBars = this.localBarsByCell.filter((_, i) => i !== target);
        const keepIndicators = this.localIndicators.filter((_, i) => i !== target);
        const keepSymbols = this.cellSymbols.filter((_, i) => i !== target);
        this.localBarsByCell.length = 0;
        this.localBarsByCell.push(...(keepBars.length ? keepBars
                                                   : [this.localBars.slice()]));
        this.localIndicators.length = 0;
        this.localIndicators.push(...(keepIndicators.length ? keepIndicators
                                                          : [null]));
        this.cellSymbols.length = 0;
        this.cellSymbols.push(...(keepSymbols.length ? keepSymbols
                                                  : [this.localName]));
        const n = count - 1;
        const cols = n <= 1 ? 1 : (n <= 3 ? n : 2);
        const rows = n <= 3 ? 1 : 2;
        this.setLayout(cols, rows);
        this.activeCell = Math.min(target, this.cells.length - 1);
        this.handler = this.cells[this.activeCell] || this.cells[0] || null;
        this.resize();
        return true;
    }

    /**
     * 1×1 / 1×2 / 2×2 …：每格一个 LWC（同合约、同周期 ✓）
     *
     * `key` → 直接按预设（`v2` 上下 / `t1b2` 上1下2 / `h3` 横排三图 … ✓）
     */
    setLayout(cols: number, rows: number, key = ''): void {
        this.setLayoutSpec(key ? layoutSpecByKey(key) : layoutSpecOf(cols, rows));
    }

    /** 按预设切布局（跨格也能摆 ✓） */
    setLayoutSpec(spec: DeskLayoutSpec): void {
        if (this.replaying) this.exitReplay();
        this.spec = spec || layoutSpecByKey('single');
        const total = Math.max(1, this.spec.cells.length);
        const oldBars = this.localBarsByCell.slice();
        const oldIndicators = this.localIndicators.slice();
        const oldSymbols = this.cellSymbols.slice();
        this.layout = { cols: Math.max(1, this.spec.cols),
            rows: Math.max(1, this.spec.rows) };
        if (!this.attached) this.mount();
        else this._buildCells();
        this.activeCell = Math.min(this.activeCell, total - 1);
        // ★ 新格子初始 = 第一个图表的数据（用户要求）✓
        const firstBars = oldBars[0]?.length ? oldBars[0]
            : (this.localBars.length ? this.localBars : []);
        for (let index = 0; index < total; index += 1) {
            const bars = oldBars[index]?.length ? oldBars[index] : firstBars;
            const symbol = oldSymbols[index] || oldSymbols[0]
                || this.localName;
            this.cellBars[index] = bars.slice();
            this.localBarsByCell[index] = bars.slice();
            try {
                (this.layers[index] as unknown as {
                    setBars?: (rows: Array<{ time: number }>) => void;
                })?.setBars?.(bars);
            } catch { /* ignore */ }
            this.cellSymbols[index] = symbol;
            // 新格子只继承 K 线，不继承指标：避免多布局指标串格
            this.localIndicators[index] = oldIndicators[index] || null;
            this._applyCellBars(index);
        }
        this.bars = (this.cellBars[0] || []).slice();
        this._buildLegend();
        for (let index = 0; index < total; index += 1) {
            const payload = this.localIndicators[index];
            if (payload) this.setCellIndicators(index, payload);
        }
        this._applyChartType();
        this.resize();
        this._syncLayoutButton();
        this._syncSymbolButton();
        this._linkBound = false;
        this._bindLink();
        this._fitLocalRange(0);
    }

    private _buildCells(): void {
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
        const spec = this.spec || layoutSpecByKey('single');
        const total = spec.cells.length;
        this.cellSymbols.length = 0;
        this.cellBars.length = 0;
        this.layers.length = 0;
        this.cellElements.length = 0;
        for (let index = 0; index < total; index += 1) {
            const [col, row, colSpan, rowSpan] = spec.cells[index]
                || [index % this.layout.cols,
                    Math.floor(index / this.layout.cols), 1, 1];
            const cell = document.createElement('div');
            cell.className = 'desk-chart-cell';
            if (colSpan > 1 || rowSpan > 1) cell.classList.add('span');
            cell.style.gridColumn = `${col + 1} / span ${Math.max(1, colSpan)}`;
            cell.style.gridRow = `${row + 1} / span ${Math.max(1, rowSpan)}`;
            grid.appendChild(cell);
            this.cellElements.push(cell);
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
            this.cellSymbols.push(this.options.symbol);
            this.cellBars.push([]);
            const chart = () => (handler as unknown as { chart: never }).chart;
            const legend = (handler as unknown as {
                legend?: Record<string, unknown>;
            }).legend;
            if (legend) {
                // ★ 用 pylightcharts 原生图例（眼睛图标就是 minibt 那个 ✓）
                const div = legend.div as HTMLElement;
                div.style.display = 'flex';
                div.style.fontSize = '11.5px';
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
        this.toolBoxOn = false;
        this.lineButton?.classList.remove('on');
        this._applyChartType();
        this._bindLegendCrosshair();
        this._applyCrosshairStyle();
        if (this.orderTicketVisible) this._ensureOrderTicket();
    }

    /** 多格图例：每格一节（`#1 SHFE.rb2610` + K 线信息 + 指标行 ✓） */
    private _buildLegend(): void {
        this.cellLegendOhlc.length = 0;
        this.cellLegendRows.length = 0;
        this.cellItems.length = 0;
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
            this.cellLegendOhlc.push(ohlc);
            this.cellLegendRows.push(rows);
            this.cellItems.push([]);
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

    /** 窗口缩放时让底部面板保持比例（不是固定高度）✓ */
    private _applyDockRatio(total?: number): void {
        if (!this.dockVisible || this.dockMaximized) return;
        const height = total || this.element.getBoundingClientRect().height
            || this.element.clientHeight;
        if (height <= 240) return;
        const ratio = Math.max(0.16, Math.min(0.72, this.dockRatio || 1 / 4));
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
        const handler = this.handler as unknown as {
            toolBox?: { div: HTMLElement };
            createToolBox?: () => void;
        } | null;
        if (!handler) return;
        if (!handler.toolBox) handler.createToolBox?.();
        if (!handler.toolBox) return;
        this.toolBoxOn = !this.toolBoxOn;
        handler.toolBox.div.style.display = this.toolBoxOn ? 'flex' : 'none';
        this.lineButton?.classList.toggle('on', this.toolBoxOn);
    }

    /** 图表右键菜单（本地图表版：周期固定 / 无布局）✓ */
    private _openChartContextMenu(x: number, y: number): void {
        const anchor = document.createElement('div');
        anchor.style.cssText = `position:fixed;left:${x}px;top:${y}px;`
            + 'width:1px;height:1px;pointer-events:none;';
        document.body.appendChild(anchor);
        showChartContextMenu({
            favorites: this.options.favorites || [],
            strategies: this.options.strategyFavorites || [],
            layouts: [],
            cycle: this.cycle,
            cycleGroups: CYCLE_GROUPS,
            local: true,
            layoutItems: this._layoutPresetItems(),
            hasAlerts: this.localAlerts.length > 0,
            onIndicatorPicker: () => this.options.onCommand?.(
                'indicator_picker', {
                    symbol: this.symbolForCell(this.activeCell), local: true,
                    cell: this.activeCell,
                }),
            onAddFavorite: (key) => this.options.onAddIndicator?.(key, {}),
            onAddStrategy: (path) => this.options.onCommand?.(
                'editor_add_indicator', {
                    path, local: true,
                    symbol: this.symbolForCell(this.activeCell),
                    cell: this.activeCell,
                }),
            // 右键「删除指标策略」= 删除全部指标 + 策略（工具栏 🗑 里那条只删指标）
            onRemove: () => {
                this.clearIndicatorsAndStrategy();
                this.cellItems.forEach((_list, index) => {
                    this.cellItems[index] = [];
                });
                this.legendItems = [];
                this._renderLegendRows(0);
                window.setTimeout(() => anchor.remove(), 0);
            },
            onCycle: () => undefined,
            onLayoutPreset: () => undefined,
            onLayoutApply: () => undefined,
            onToggleToolBox: () => this.toggleToolBox(),
            onClearDrawings: () => this.clearDrawings(),
            onAlert: () => this._openAlertDialog(),
            onClearAlerts: () => {
                this.localAlerts = [];
                this.alertDialog?.setItems([]);
                this._renderAlertLines();
            },
            onScreenshot: () => this.screenshot(),
            onFitAll: () => this.fitAllBars(
                Math.max(0, this.cells.indexOf(this.handler as never))),
            onLastBars: () => this.showLastBars(
                300, Math.max(0, this.cells.indexOf(this.handler as never))),
            canCloseChart: this.cells.length > 1,
            onCloseChart: () => {
                const index = Math.max(0,
                    this.cells.indexOf(this.handler as never));
                this.closeCell(index);
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
                price: this.localPrice || null,
                decimals: this.localDecimals,
                theme: this.options.theme === 'light' ? 'light' : 'dark',
            });
            // ⚠ 不要设 callbackName：0.1.5 的 emit_callback 碰到未注册的名字
            //   会 TypeError: 'NoneType' object is not callable（用户实测 ✗）
            //    这里用**直接回调**（同页应用，不需要过 bridge ✓）
            this._bindAlertCallbacks(this.alertDialog);
        }
        this.alertDialog.setSymbol(this.options.symbol);
        this.alertDialog.setDecimals(this.localDecimals);
        this.alertDialog.setPrice(this.localPrice || null);
        this.alertDialog.setItems(this.localAlerts as never);
        this.alertDialog.open();
    }

    private _bindAlertCallbacks(dialog: AlertDialog): void {
        dialog.onCreateCallback = (payload: Record<string, unknown>) => {
            this.localAlertSeq += 1;
            this.localAlerts.push({
                id: this.localAlertSeq,
                symbol: this.options.symbol,
                price: payload.price,
                cross: payload.cross,
                action: payload.action,
                qty: payload.qty,
                message: payload.message,
                line: payload.line !== false,
                fired: false,
            });
            dialog.setItems(this.localAlerts as never);
            this._renderAlertLines();
            this.toast('预警已创建');
        };
        dialog.onDeleteCallback = (id: unknown) => {
            this.localAlerts = this.localAlerts.filter(
                (item) => item.id !== id);
            dialog.setItems(this.localAlerts as never);
            this._renderAlertLines();
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
        // ★ 实时推送按**时间合并**（同一根替换、新的追加）——
        //   以前直接 `concat` 会出现重复时间戳，LWC 的 `setData` 要求时间严格递增，
        //   一重复就抛错 → 图表从此不再更新（用户实测 ✗）
        const before = this.bars.length;
        this.bars = replace ? bars.slice() : mergeBars(this.bars, bars);
        this.cellBars[0] = this.bars;
        this.vpOverlays[0]?.setBars(this.bars as never);
        if (!this.handler) return;

        // ★ 增量：`replace=false` 时只 `series.update()` 变化的那几根
        //   （同 miniqt 的 `series.update(row)` —— 不再整表 setData，省一次全量 ✓）
        if (!replace) {
            const tail = this.bars.slice(-Math.max(1, bars.length));
            if (this._updateTail(tail, bars.length)) {
                this._setSeriesData();
                this._updateLegend(this.bars[this.bars.length - 1]);
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
                    local: true,
                    symbol: this.symbolForCell(this.activeCell),
                    cell: this.activeCell,
                }),
            })) : [{ label: '（暂无）', disabled: true }]),
            { label: '＋ 更多指标和策略…', separator: true,
              run: () => this.options.onCommand?.('indicator_picker', {
                  symbol: this.options.symbol }) },
            { label: '添加个人指标…',
              run: () => this.options.onCommand?.('pick_personal', {
                  kind: 'indicator' }) },
            { label: '添加个人策略…',
              run: () => this.options.onCommand?.('pick_personal', {
                  kind: 'strategy' }) },
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
                    symbol: this.symbolForCell(this.activeCell), name,
                    local: true, cell: this.activeCell,
                });
            };
        }
        this.templatePicker.open();
        this.options.onCommand?.('templates', {});
    }

    /** 模板列表 / 应用（后端 `templates` 补丁 ✓） */
    setTemplates(items: Array<Record<string, unknown>>): void {
        this.templatePicker?.setTemplates(items as never);
    }

    /** 应用模板（可带参数覆盖 ✓） */
    applyTemplate(key: string, params?: Record<string, Record<string, unknown>>): void {
        this.options.onCommand?.('apply_template', {
            symbol: this.symbolForCell(this.activeCell), key,
            params: params || {}, local: true, cell: this.activeCell,
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

    /** 当前加载的本地数据名（App 用来把补丁路由到对应 tab ✓） */
    get localDataName(): string {
        return this._activeLocalName();
    }

    /** 当前格子（键盘精灵 / 商品搜索加载到它 ✓） */
    get activeCellIndex(): number {
        return this.activeCell;
    }

    /** 第 N 格当前数据名（多布局指标 / 下单必须用它） */
    symbolForCell(index = this.activeCell): string {
        return String(this.cellSymbols[index] || this.options.symbol
            || this.localName || '');
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

    /** 关闭键盘精灵，并清掉可能残留的遮罩 / 面板 ✓ */
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
                        text: value, limit: 12, local: true,
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

    /** 选中一行：本地数据 → 加载到当前格；指标 → 加到当前格 ✓ */
    pickSprite(item: SpriteItem): void {
        if (!item) return;
        if (item.kind === 'symbol') {
            // 键盘精灵里的「合约」在本地图表里就是一条本地 CSV ✓
            this.loadLocal(String(item.symbol || item.key || ''));
            return;
        }
        if (item.kind === 'strategy') {
            this.options.onToast?.(
                'warning', '策略不能画在图上（请用 Bt 运行）');
            return;
        }
        this.options.onAddIndicator?.(item.key, {});
    }

    /** 打开「商品搜索」（pylightcharts `SymbolSearch` ✓） */
    openSymbolSearch(): void {
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
                if (!item.symbol || item.symbol === this.options.symbol) return;
                this.options.onCommand?.('switch_symbol', {
                    from: this.options.symbol, to: item.symbol,
                    name: item.name || '',
                });
            };
        }
        this.symbolSearch.setTheme(
            this.options.theme === 'light' ? 'light' : 'dark');
        this.symbolSearch.setMarkets(this.searchMarkets, this.searchMarket);
        this.symbolSearch.open(this.options.symbol);
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

    /** 切换合约（后端 `switch_symbol` 补丁 → 这里只改标题 ✓） */
    setSymbol(symbol: string, name = ''): void {
        this.options.symbol = symbol;
        this.options.name = name;
        if (this.symbolButton) {
            this.symbolButton.textContent = `${symbol} 🔍`;
            if (name) {
                const span = document.createElement('span');
                span.className = 'desk-muted';
                span.textContent = ` ${name}`;
                this.symbolButton.appendChild(span);
            }
        }
        this.book.setSymbol(symbol);
    }

    // ------------------------------------------------------------ 本地数据
    /** 后端 `{type:'local_data'}`：可选数据列表 + 已添加文件夹 ✓ */
    setLocalData(items: Array<Record<string, unknown>>,
                 folders: string[] = []): void {
        this.localDataItems = items || [];
        this.localFolders = folders || [];
    }

    /** 已添加的数据文件夹（数据菜单 / 调试用 ✓） */
    get dataFolders(): string[] {
        return this.localFolders.slice();
    }

    /** 左键「数据名 🔍」→ 本地数据搜索（可搜索 / 添加文件夹 ✓） */
    openLocalDataSearch(): void {
        if (!this.symbolSearch) {
            this.symbolSearch = new SymbolSearch({
                placeholder: '搜索本地数据（名称 / 来源）…',
                remote: false,
                addLabel: '＋ 数据文件夹',
                theme: this.options.theme === 'light' ? 'light' : 'dark',
            });
            this.symbolSearch.onPickCallback = (item) => {
                const name = String(item.symbol || '');
                if (!name) return;
                // ★ 交易面板的 🔍 → 只换**交易标的**（图表不动 ✓）
                if (this._pickingTrade) {
                    this._pickingTrade = false;
                    if (this.tradeLocked) return;
                    this.tradeSymbol = name;
                    this.localTicket?.setSymbol(name);
                    this.localTicket?.setInfo(`交易标的 → ${name}`);
                    return;
                }
                this.loadLocal(name);
            };
            this.symbolSearch.onAddCallback = () => this._addLocalFolder();
        }
        this.symbolSearch.setTheme(
            this.options.theme === 'light' ? 'light' : 'dark');
        this.symbolSearch.setItems(this.localDataItems.map((row) => ({
            symbol: String(row.name || ''),
            name: [String(row.source || ''),
                   Number(row.rows) ? `${Number(row.rows)} 根`
                       : String(row.size_text || '')]
                .filter(Boolean).join(' · '),
            exchange: String(row.source || ''),
            type: 'CSV',
            type_label: 'CSV',
            market: String(row.source || ''),
        })));
        this.symbolSearch.setHint(
            `共 ${this.localDataItems.length} 个本地 CSV · `
            + '↑↓ 选择 · Enter 加载 · Esc 关闭');
        this.symbolSearch.open();
    }

    /**
     * 添加数据文件夹（左键搜索面板 / 右键菜单共用 ✓）
     *
     * ★ 直接弹**系统**文件夹选择框（后端 `choose_directory`：Qt 原生 /
     *   tkinter 兜底），用户不用手输路径（用户要求 ✓）
     */
    private _addLocalFolder(): void {
        this.options.onCommand?.('local_add_folder', {});
    }

    /** 顶栏「数据名 🔍」→ 内置 / 用户 / 文件夹 + 添加文件夹 ✓ */
    openLocalDataMenu(): void {
        const button = this.symbolButton;
        if (!button) return;
        const items: MenuItem[] = [];
        let source = '';
        for (const row of this.localDataItems) {
            const name = String(row.name || '');
            const kind = String(row.source || '');
            if (kind !== source) {
                source = kind;
                items.push({ label: kind || '数据', disabled: true,
                             separator: items.length > 0 });
            }
            const rows = Number(row.rows) || 0;
            const size = String(row.size_text || '');
            const detail = [rows ? `${rows} 根` : size, kind]
                .filter(Boolean).join(' · ');
            items.push({
                label: `${name}${detail ? `  （${detail}）` : ''}`,
                run: () => this.loadLocal(name),
            });
        }
        if (!this.localDataItems.length) {
            items.push({ label: '（还没有数据）', disabled: true });
        }
        items.push({
            label: '＋ 添加数据文件夹…', separator: true,
            run: () => this._addLocalFolder(),
        });
        items.push({
            label: '刷新数据列表',
            run: () => this.options.onCommand?.('local_list', {}),
        });
        items.push({
            label: '重置本地模拟账户', separator: true,
            run: () => {
                if (window.confirm('清空本地模拟账户的持仓 / 委托 / 成交？')) {
                    this.options.onCommand?.('local_reset', {});
                }
            },
        });
        showMenuBelow(button, items);
    }

    /** 当前鼠标最后点击的格子里的数据名 ✓ */
    private _activeLocalName(): string {
        return this.cellSymbols[this.activeCell] || this.localName;
    }

    private _syncSymbolButton(): void {
        if (!this.symbolButton) return;
        const name = this._activeLocalName() || '选择本地数据';
        this.symbolButton.textContent = `${name} 🔍`;
    }

    /** 切到别的格子后，交易价格跟着那一格的最新收盘价 ✓ */
    private _syncActiveLocalPrice(): void {
        const bars = this.cellBars[this.activeCell] || [];
        const last = bars[bars.length - 1];
        if (last) this._syncLocalPrice(Number(last.close) || 0);
    }

    /** 选中一条本地数据 → 后端读 CSV 后回 `{type:'local_kline'}` ✓ */
    loadLocal(name: string): void {
        if (!name) return;
        this.options.onCommand?.('local_load',
                                 { name, cell: this.activeCell });
    }

    /** 后端 `{type:'local_kline'}`：静态 K 线（不参与实时更新 ✓） */
    setLocalBars(payload: {
        name?: string; symbol?: string; duration?: number; decimals?: number;
        price_tick?: number; bars?: ChartBar[]; cell?: number;
    }): void {
        const bars = payload.bars || [];
        if (!bars.length) return;
        if (this.replaying) this.exitReplay();
        const cell = Math.max(0, Math.min(Number(payload.cell) || 0,
                                         this.cells.length - 1));
        const name = String(payload.name || payload.symbol || '');
        const digits = Number(payload.decimals);
        // ⚠ `0` 是合法小数位（rb / PVC 都是 0 位）→ 不能用 `|| 2` ✗
        this.localDecimals = Number.isFinite(digits) ? Math.max(0, digits) : 2;
        // ★ 价格步进：CSV 自带 `price_tick` 就用它（股票默认 0.01 ✓），
        //   没有才按小数位推（1 位 → 0.1）✓
        const tick = Number(payload.price_tick);
        this.localPriceTick = (Number.isFinite(tick) && tick > 0)
            ? tick : Math.pow(10, -this.localDecimals);
        this.localTicket?.setStep(this.localPriceTick);
        this.cycle = Number(payload.duration) || this.cycle || 60;
        this.cycleLabel.textContent = this._cycleText(this.cycle);
        this.cellSymbols[cell] = name;
        this.cellBars[cell] = bars.slice();
        this.localBarsByCell[cell] = bars.slice();
        if (cell === 0) this.localBars = bars.slice();
        if (cell === this.activeCell) {
            this.localName = name;
            this.options.symbol = name;
            this.options.name = String(payload.symbol || '');
        }
        this._syncSymbolButton();
        if (this.attached) {
            this._applyCellBars(cell);
            this._applyChartType();
            this._updateLegend(bars[bars.length - 1], cell);
            this._fitLocalRange(cell);
        }
        if (cell === this.activeCell) {
            this._syncLocalPrice(Number(bars[bars.length - 1].close) || 0);
            this._checkLocalAlerts(this.localPrice);
        }
        // ★ 未锁定 → 交易标的跟着**当前格**的数据走（不是加载哪个就切哪个）✓
        if (cell === this.activeCell && !this.tradeLocked) {
            this.tradeSymbol = name;
            this.localTicket?.setSymbol(name);
        }
        this.toast(`已加载本地数据：${name}`);
    }

    /** 本地账户补丁 → 底部「交易账户」页（持仓/委托 + 右侧交易控件 ✓） */
    setLocalAccount(payload: Record<string, unknown>): void {
        // ★ 只有显式的 `active`（鼠标点格子）才切交易标的；
        //   回放 / 成交推来的普通账户补丁**不能**轮流改搜索框和价格框 ✗
        const named = String(payload.symbol || '');
        const active = payload.active === true;
        if (active && named && !this.tradeLocked) {
            this.tradeSymbol = named;
            this.localTicket?.setSymbol(named);
        }
        this.dock.setAccount(payload as never);
        const tables = (payload.tables || {}) as Record<string, {
            rows?: string[][] }>;
        // ★ 净仓 / 价格只算**交易面板当前标的**（多合约时不能把两个合约
        //   的手数加在一起，否则「平仓」会平错 ✗）
        const focus = this.tradeSymbol || named || this._activeLocalName();
        let net = 0;
        for (const row of tables.positions?.rows || []) {
            if (focus && String(row[0] || '') !== focus) continue;
            const qty = Number(row[2]) || 0;
            net += String(row[1]) === '空' ? -qty : qty;
        }
        this.localNet = net;
        // ★ 价格框只跟**当前交易标的**走（`named` 是这份账户补丁的合约）
        const owned = !!focus && (!named || named === focus);
        const last = Number(payload.last_price);
        if (owned && Number.isFinite(last) && last > 0) {
            this._syncLocalPrice(last);
            this.localTicket?.setPrice(last);
        }
        this.localTicket?.setNet(net);
        // ★ 价格步进 = 最小变动价位（按小数位推：1 位 → 0.1 ✓）
        this.localTicket?.setStep(this.localPriceTick
            || Math.pow(10, -this.localDecimals));
        this._syncLocalTicketInfo();
    }

    private localNet = 0;
    /** 交易面板标的（本地模拟：默认当前 CSV；🔍 可换其它本地数据 ✓） */
    private tradeSymbol = '';
    private tradeLocked = false;
    /** 🔍 是「换交易标的」还是「换图表数据」✓ */
    private _pickingTrade = false;

    /** 交易控件：价格 / 手数 / 买 / 卖 / 平（放在交易页右侧 ✓） */
    private _buildLocalTicket(): void {
        this.tradeSymbol = this.localName || this.options.symbol;
        const ticket = buildReplayTicket({
            title: '本地模拟交易',
            symbol: this.tradeSymbol,
            searchable: true,
            onSearch: () => {
                this._pickingTrade = true;
                this.openLocalDataSearch();
            },
            onLockChange: (locked) => {
                this.tradeLocked = locked;
                this.localTicket?.setInfo(locked
                    ? '已锁定：只在当前标的交易'
                    : '未锁定：可在本地数据里切换标的');
            },
            onOrder: (side, close) => this._localOrder(side, close),
            onAction: (action) => this.options.onCommand?.(
                'local_account_action', {
                    action, symbol: this.tradeSymbol || this.localName,
                }),
            info: '点二级报价档位可填价格 · 平仓=按价格；市价平仓=市价',
        });
        this.localTicket = ticket;
        const inputs = ticket.element.querySelectorAll('input[type=number]');
        this.localPriceInput = (inputs[0] || null) as HTMLInputElement | null;
        this.localQtyInput = (inputs[1] || null) as HTMLInputElement | null;
        this.localInfo = ticket.element.querySelector(
            '.desk-local-ticket-info') as HTMLDivElement | null;
        this.dock.setTicket(ticket.element);
    }

    private _localOrder(side: string, close: boolean): void {
        const symbol = this.tradeSymbol || this.localName;
        if (!symbol) {
            this.toast('请先选择本地数据');
            return;
        }
        const price = this.localTicket?.priceValue()
            || Number(this.localPriceInput?.value) || this.localPrice;
        // ★ 手数：共用控件兜底 1（以前读到 null → 0 → 误报「手数要大于 0」✗）
        const qty = this.localTicket?.qtyValue()
            || Number(this.localQtyInput?.value) || 1;
        if (!(price > 0) || !(qty > 0)) {
            this.toast('价格 / 手数要大于 0');
            return;
        }
        if (close && this.localNet === 0) {
            this.toast('当前没有持仓可平');
            return;
        }
        this.options.onCommand?.('local_order', {
            symbol, side, qty, price, close,
        });
    }

    private _syncLocalPrice(price: number): void {
        const value = Number(price);
        if (Number.isFinite(value) && value > 0) {
            this.localPrice = value;
        }
        if (this.localPriceInput
            && document.activeElement !== this.localPriceInput) {
            this.localPriceInput.value = this.localPrice
                ? this.localPrice.toFixed(this.localDecimals) : '';
        }
        // ★ 图上买卖盘：回放时买一/卖一都指向最新 K 线收盘价 ✓
        this.ticketBid = this.localPrice || null;
        this.ticketAsk = this.localPrice || null;
        this.ticketDecimals = this.localDecimals;
        this.ticketNet = this.localNet;
        this._renderTicket();
        this._syncLocalTicketInfo();
    }

    private _syncLocalTicketInfo(): void {
        if (!this.localInfo) return;
        const net = this.localNet > 0 ? `多 ${this.localNet} 手`
            : (this.localNet < 0 ? `空 ${-this.localNet} 手` : '无持仓');
        const symbol = this.tradeSymbol || this._activeLocalName() || '--';
        this.localInfo.textContent =
            `数据：${symbol}\n`
            + `现价：${this.localPrice
                ? this.localPrice.toFixed(this.localDecimals) : '--'}\n`
            + `持仓：${net}`;
    }

    /** 记住每格当前可视范围 ✓ */
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

    /** 恢复可视范围（等数据重画完再套 ✓） */
    private _restoreViewRangesSoon(): void {
        const apply = () => this._restoreViewRanges();
        const raf = (globalThis as unknown as {
            requestAnimationFrame?: (cb: () => void) => number;
        }).requestAnimationFrame;
        if (typeof raf === 'function') raf(() => raf(apply));
        else window.setTimeout(apply, 120);
        window.setTimeout(apply, 400);
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

    /** 右键「全部K线」：可视范围刚好显示全部 ✓ */
    fitAllBars(cell = 0): void {
        const scale = (this.cells[cell] as unknown as {
            chart?: { timeScale?: () => { fitContent?: () => void } };
        } | undefined)?.chart?.timeScale?.();
        try {
            scale?.fitContent?.();
        } catch {
            /* ignore */
        }
    }

    /** 右键「最新K线」：最近 300 根 ✓ */
    showLastBars(count = 300, cell = 0): void {
        const total = (this.cellBars[cell] || []).length;
        if (!total) return;
        const visible = Math.max(2, Math.min(Number(count) || 300, total));
        const scale = (this.cells[cell] as unknown as {
            chart?: { timeScale?: () => {
                setVisibleLogicalRange?: (
                    r: { from: number; to: number }) => void;
            } };
        } | undefined)?.chart?.timeScale?.();
        try {
            scale?.setVisibleLogicalRange?.({ from: total - visible,
                                             to: total + 2 });
        } catch {
            /* ignore */
        }
    }

    private _fitLocalRange(cell = 0): void {
        const handler = this.cells[cell] || this.handler;
        const chart = (handler as unknown as {
            chart?: { timeScale?: () => {
                setVisibleLogicalRange?: (range: { from: number; to: number })
                    => void } } })?.chart;
        const scale = chart?.timeScale?.();
        if (!scale?.setVisibleLogicalRange) return;
        const total = (this.cellBars[cell] || []).length;
        if (!total) return;
        const from = Math.max(0, total - 300);
        try {
            scale.setVisibleLogicalRange({ from: from - 0.5, to: total - 0.5 });
        } catch {
            /* ignore */
        }
    }

    /** 布局多图：后端 `{type:'layout'}` 补丁 → 网格 + 每格合约 ✓ */
    applyLayout(payload: {
        cols?: number; rows?: number; symbols?: string[];
        count?: number; key?: string; local?: boolean;
    }): void {
        const symbols = (payload.symbols || []).map(String);
        // ★ 自动加载策略合约：2 个合约 → 左右两图（和实时图表同一套
        //   `layoutSpecForCount`）；关键是 `setLayoutSpec` 会真的重建格子 ✗
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
        // ★ 布局和合约都已经一样 → 不重建（保留现有指标 / 视窗）✓
        const same = String(this.spec?.key || '') === String(spec.key || '')
            && this.cells.length === count
            && symbols.every((symbol, index) =>
                this.cellSymbols[index] === symbol);
        if (!same) this.setLayoutSpec(spec);
        symbols.forEach((symbol, index) => {
            if (index < this.cellSymbols.length) this.cellSymbols[index] = symbol;
        });
        this._buildLegend();          // 标题用新的合约 ✓
        this._syncSymbolButton();
        this.resize();
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
        this._updateLegend(this.cellBars[cell][this.cellBars[cell].length - 1],
                           cell);
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
        this.replaySeek = options.seek !== undefined
            ? options.seek : this.replaySeek;
        if (options.cycle) this.replayCycle = options.cycle;
        const cells = this.cellBars.map((bars, index) => ({
            cell: index,
            bars: bars.slice(),
            indicators: ((this.localIndicators[index]?.items || []) as
                IndicatorLine[]),
        }));
        const first = cells.find((cell) => cell.bars.length) || cells[0];
        if (!first || !first.bars.length) {
            this.toast('请先选择本地数据');
            return;
        }
        this._saveViewRanges();       // ★ 记住进回放前的可视范围 ✓
        // 本地回放：不请求后端，直接用已加载的 CSV 数据逐根播放 ✓
        this.setReplay({
            bars: first.bars,
            speed: this.replaySpeed,
            symbol: this.localName,
            indicators: first.indicators,
            cells,
        });
    }

    /** 进入回放（后端 `{type:'replay'}`；带 `indicators` 就一起回放 ✓） */
    setReplay(payload: {
        bars?: ReplayBar[]; speed?: number;
        indicators?: IndicatorLine[]; symbol?: string;
        cells?: Array<{ cell?: number; bars?: ReplayBar[];
                        indicators?: IndicatorLine[]; symbol?: string }>;
    }): void {
        const bars = payload.bars || [];
        if (!bars.length) return;
        this.replayIndicators = payload.indicators || [];
        this.replaySymbol = String(payload.symbol || this.options.symbol);
        this.replayEnded = false;
        this.restoringReplay = false;
        // 新一轮回放：策略信号按时间重新执行（后端按 id 去重）
        this.strategyTradeReset = true;
        this.strategyTradeSentUntil.clear();
        // ★ 多图回放：每格自己的 bars / 指标（后端已对齐长度 ✓）
        this.replayCells = (payload.cells || []).map((item, index) => ({
            cell: Number(item.cell ?? index),
            bars: item.bars || [],
            indicators: item.indicators || [],
        }));
        if (!this.replay) {
            this.replay = new Replay({
                onBars: (visible, finished, advance = false) => {
                    if (this.restoringReplay) return;
                    // 只有引擎真的装着数据才算「回放中」——否则 `stop()`
                    // 的那次空回调会把「已退出」又翻回「回放中」✗
                    this.replaying = !!this.replay?.active;
                    // ★ `stop()` / `load()` 里的空回调：不碰图表，也不消耗 reset ✓
                    if (!visible.length) return;
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
                    // ★ 表格（`tablestyle`）跟着回放走：按回放最后一根重算 ✓
                    this._syncTableIndex(Math.max(0, visible.length - 1));
                    this._syncReplayViewport(visible.length);
                    // ★ **每一格**都报自己的当前收盘价：后端据此把两个合约的
                    //   现价 / 浮盈都对齐到回放进度（以前只报当前格 → 另一
                    //   个合约的现价永远停在旧值 ✗）
                    const tails = this.cells.map((_item, index) => {
                        const data = this.cellBars[index] || [];
                        const tail = data[data.length - 1];
                        const symbol = this.symbolForCell(index);
                        if (!tail || !symbol) return null;
                        return {
                            symbol,
                            price: Number(tail.close) || 0,
                            time: tail.time,
                            index: data.length - 1,
                        };
                    }).filter((item): item is {
                        symbol: string; price: number; time: number;
                        index: number } => item !== null);
                    // ★ 交易面板只跟**鼠标最后点的格子**（不是轮流跟两个合约）✓
                    const activeName = this._activeLocalName()
                        || this.localName || this.options.symbol;
                    const active = tails.find((item) =>
                        item.symbol === activeName) || tails[0];
                    const last = active;
                    if (last) {
                        this._syncLocalPrice(last.price);
                        this._checkLocalAlerts(this.localPrice);
                    }
                    if (last) {
                        const reset = this.replayResetPending;
                        this.replayResetPending = false;
                        // ★ 现价 / 浮盈 / 策略成交都跟着回放走。
                        //   `advance=false`（进入 / 暂停 / seek）→ 后端只对齐
                        //   价格，**不跑 next、不成交**（用户要求 ✓）
                        this.options.onCommand?.('replay_price', {
                            symbol: last.symbol,
                            price: last.price,
                            time: last.time,
                            index: last.index,
                            cells: tails,
                            playing: advance
                                && !!(this.replay && this.replay.isPlaying),
                            advance,
                            reset,
                        });
                        // ★ 策略成交由后端 runner 统一执行（多合约 / 目标手数）；
                        //   旧的 marker 信号路径默认关闭，避免重复成交 ✓
                        if (advance && this.legacySignalTrades) {
                            this._syncStrategyTrades();
                        }
                    }
                    if (finished) {
                        // ★ 放到最后一根：只暂停，**不自动退出**。
                        //   回放中本地模拟账户可能还有仓位，用户需要先平仓；
                        //   退出由用户再点工具栏回放按钮完成（恢复原数据）。
                        this.replayEnded = true;
                        if (this.replayLabel) {
                            this.replayLabel.textContent =
                                `回放结束（${visible.length} 根）`;
                        }
                        this.replayBar?.classList.remove('on');
                        this.toast('回放结束：可先平仓，再点工具栏回放按钮退出');
                        this._syncReplayButton();
                    }
                },
                onState: (state) => this._syncReplayBar(state),
            });
            this._ensureReplayBar();
        }
        this.replaying = true;
        this.replayViewLengths = [];
        this.replaySpeed = Number(payload.speed) || this.replaySpeed || 5;
        this.replayResetPending = true;
        this.replay.load(bars, this.replaySpeed, this.replaySeek);
        // ★ 进入回放 = **暂停在 seek 位置**：点回放不交易；按 ▶ / 前进一根
        //   才开始跑策略（用户要求：「开始回放时本地模拟账户才开始交易」✓）
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
        play.className = 'desk-tool desk-replay-play';
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
        step.textContent = '↦';
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
        // 本地图表周期固定（CSV 的 duration）✓
        cycle.disabled = true;
        cycle.title = '本地图表：周期由数据决定（不可切换）';
        cycle.classList.add('desk-tool-disabled');
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
        if (this.replayEnded) {
            this.replayBar.classList.remove('on');
            this._syncReplayButton();
            return;
        }
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
     * 回放视窗：**可视根数不变、最新一根到右边的空隙不变** ✓
     *
     * 和 `chart-page.ts` 同一套算法（P59 统一）：LWC 在 `setData` 之后会
     * 自己把视窗锚在右边，再手动 +1 会「整体左滑 + 右边越来越空」✗
     */
    /**
     * 回放视窗：和**实时图表**同一套（P68）✓
     *
     * 播放阶段**完全不碰视窗** —— LWC 自己按 `rightOffset` 跟随：最新一根到
     * 右边的距离、可视根数都不变；用户拖动 / 缩放也不会被拉回 ✓
     * 只在「首次 / seek」摆一次：整段 + 右侧留白。
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
            if (reset || prev === 0 || Math.abs(current - prev) > 1) {
                const apply = () => {
                    try {
                        setRange.call(scale, {
                            from: Math.max(-0.5, current - 200),
                            to: current - 1 + 3,
                        });
                    } catch {
                        /* ignore */
                    }
                };
                apply();
                const raf = (globalThis as unknown as {
                    requestAnimationFrame?: (cb: () => void) => number;
                }).requestAnimationFrame;
                if (typeof raf === 'function') raf(() => apply());
            }
            next[index] = current;
        });
        this.replayViewLengths = next;
    }

    /** 从某格的**策略 marker** 生成自动交易信号（普通指标不参与 ✓） */
    private _strategySignals(cell: number, floor: number,
                             until: number): LocalStrategySignal[] {
        const payload = this.localIndicators[cell] as
            (IndicatorPayload & { strategy?: unknown }) | null;
        if (!payload || !payload.strategy) return [];
        const source = (this.localBarsByCell[cell]?.length
            ? this.localBarsByCell[cell] : this.cellBars[cell]) || [];
        const prices = new Map<number, number>();
        for (const bar of source) {
            prices.set(Number(bar.time), Number(bar.close));
        }
        const out: LocalStrategySignal[] = [];
        for (const item of payload.items || []) {
            if (item.kind !== 'marker') continue;
            const markers = (item as unknown as {
                markers?: Array<{ time?: number; up?: boolean;
                                  shape?: string; text?: string }>;
            }).markers || [];
            const label = String(item.label || item.key || '').toLowerCase();
            markers.forEach((marker, index) => {
                const time = Number(marker.time);
                if (!Number.isFinite(time) || time > until || time <= floor) {
                    return;
                }
                const text = String(marker.text || '').toUpperCase();
                const shape = String(marker.shape || '');
                const buy = marker.up === true
                    || (marker.up === undefined
                        && (shape === 'arrowUp' || text === 'B'));
                out.push({
                    id: `${item.key}:${time}:${index}`,
                    time,
                    side: buy ? 'buy' : 'sell',
                    close: label.includes('exit') || text === 'X',
                    price: prices.get(time),
                });
            });
        }
        return out.sort((a, b) => a.time - b.time);
    }

    /**
     * 回放每拍：把**策略信号**按当前已放出的时间发送给后端，落到本地模拟账户。
     *
     * 只发送新增的信号；`reset` 时发送当前时间之前的全部信号，这样从 30%
     * 开始回放也能先建立策略已有持仓。后端按信号 id 去重，重复发送安全 ✓。
     */
    private _syncStrategyTrades(): void {
        const reset = this.strategyTradeReset;
        const resetSymbols = new Set<string>();
        for (let index = 0; index < this.cells.length; index += 1) {
            const payload = this.localIndicators[index] as
                (IndicatorPayload & { strategy?: unknown }) | null;
            if (!payload || !payload.strategy) continue;
            const bars = this.cellBars[index] || [];
            const last = bars[bars.length - 1];
            if (!last) continue;
            const until = Number(last.time);
            const symbol = this.symbolForCell(index);
            if (!symbol || !Number.isFinite(until)) continue;
            const previous = this.strategyTradeSentUntil.get(index)
                ?? -Infinity;
            const floor = reset ? -Infinity : previous;
            // 倒退回放（seek 到更早）时重新完整同步一次
            if (!reset && until < previous) {
                this.strategyTradeSentUntil.set(index, -Infinity);
                continue;
            }
            const signals = this._strategySignals(index, floor, until);
            const resetCell = reset && !resetSymbols.has(symbol);
            if (resetCell) resetSymbols.add(symbol);
            if (signals.length || resetCell) {
                this.options.onCommand?.('local_strategy_trade', {
                    symbol, reset: resetCell, until, signals,
                });
            }
            this.strategyTradeSentUntil.set(index, until);
        }
        this.strategyTradeReset = false;
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
                        data: (item.data || []).filter(([time]) =>
                            Number(time) >= first && Number(time) <= last),
                        // ★ 自定义序列 / 原生 marker 都要按当前切片过滤。
                        //   只切 data 不够：未来信号会被 LWC 钉在当前最新一根，
                        //   看起来像“后面的 B/S 全挤在最后一根”（用户实测 ✗）
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
        const fullCells = this.replayCells.slice();
        this.restoringReplay = true;
        this.replaying = false;
        // ★ 表格回到实时（最后一根 ✓）
        this.tableMouseAt.clear();
        this._syncTableIndex(null);
        this.replayEnded = false;
        this.replayViewLengths = [];
        // stop() 会触发一次空 onBars；用 restoringReplay 忽略，避免把
        // 下面恢复好的 K 线又清空（用户实测：退出后只剩指标 ✗）
        this.replay?.stop();
        this.replayCells = [];
        this.replayResetPending = false;
        this.strategyTradeReset = true;
        this.strategyTradeSentUntil.clear();
        // 回到每格完整的静态 CSV（回放只切了可见切片 ✓）
        for (const cell of fullCells) {
            const index = Math.max(0, Number(cell.cell) || 0);
            const bars = this.localBarsByCell[index] || cell.bars;
            this.cellBars[index] = bars.slice();
            if (this.attached) this._applyCellBars(index);
            const payload = this.localIndicators[index];
            if (payload) this.setCellIndicators(index, payload);
        }
        this.bars = (this.cellBars[0] || []).slice();
        if (this.attached) {
            this._applyChartType();
            // ★ 恢复进回放前的可视范围（以前 `_fitLocalRange` 会缩到
            //   最近 300 根 → 看起来「只剩最后几根」✗）
            this._restoreViewRangesSoon();
        }
        this.replayBar?.classList.remove('on');
        this.restoringReplay = false;
        this._syncReplayButton();
        this._syncActiveLocalPrice();
    }

    // ------------------------------------------------------------- 删除 / 联动 / 持仓线
    /** 「🗑」删除菜单 —— 复刻 miniqt「删除指标策略」菜单 ✓
     *
     * 菜单按**格（多布局）**分组列出每个指标（一个指标可能有多条线，按
     * `source` 归组 ✓），点一下删这一个；最后一行「删除全部指标」清空整页。
     */
    openRemoveMenu(anchor: HTMLElement): void {
        const items: MenuItem[] = [];
        let total = 0;
        this.cellItems.forEach((list, cell) => {
            // 一个**指标**一条：`editor:CMO`（策略线）/ `pi:xxx` / `tv:MACD`
            const seen = new Map<string, string>();
            for (const item of list || []) {
                const key = String(item.key || '');
                // ⚠ key 是 `editor:<线名>:line:N`（第二段是线名，不是指标名）→
                //   分组必须用**后端打的 `source`**（`editor:CMO`），
                //   否则 5 条线会分成 5 组（用户实测 ✗）
                const source = String(item.source || key.split(':')[0]);
                if (seen.has(source)) continue;
                const label = source.startsWith('editor:')
                    ? `editor.${source.split(':')[1] || ''}`
                    : this._sourceLabel(source, item.label);
                seen.set(source, label);
            }
            if (!seen.size) return;
            total += seen.size;
            items.push({
                label: this._cellTitle(cell),
                disabled: true,
                separator: items.length > 0,
            });
            let index = 0;
            for (const [source, label] of seen) {
                index += 1;
                items.push({
                    label: `${index}  ${label}`,
                    // ★ 删的是**整个指标**（后端按 key 前缀匹配 → 所有线一起删 ✓）
                    run: () => this.removeIndicator(source, cell),
                });
            }
        });
        if (!total) {
            items.push({ label: '（本页还没有指标）', disabled: true });
        } else {
            items.push({ label: '删除全部指标', separator: true,
                run: () => this.clearIndicators() });
        }
        showMenuBelow(anchor, items);
    }

    /** 指标 key → 菜单上的一行文字（`pta_macd` → `pta.macd` ✓） */
    private _sourceLabel(source: string, fallback?: string): string {
        const text = String(source || '');
        if (text.startsWith('tv:')) return text.slice(3);
        if (text.startsWith('pi:')) return text.slice(3);
        // 「加到图表」的**策略/指标线** → `editor.<指标名>`
        // （以前 `st:line:cmo:1` 被截成 "st"，菜单上就是 `1 st` ✗）
        if (text === 'st' || text === 'editor') {
            return `editor.${String(fallback || '').trim() || text}`;
        }
        if (text.startsWith('editor:')) {
            const name = text.split(':')[1] || fallback || '';
            return `editor.${name}`;
        }
        if (text.startsWith('st:')) {
            const name = text.split(':')[2] || fallback || '';
            return `editor.${name}`;
        }
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
        this.options.onCommand?.('remove_indicator', {
            symbol: this.symbolForCell(cell),
            key: source, cell,
        });
        // 本格立即先撤掉（后端补丁回来后再对齐 ✓）
        const layer = this.layers[cell] || this.indicators;
        try {
            layer.removeSource?.(source);
        } catch { /* ignore */ }
        // 图例 / 隐藏状态用的 `cellItems` 也要同步，否则菜单还列着它 ✗
        const keep = (this.cellItems[cell] || []).filter((item) => {
            const key = String(item.key || '');
            return !(key === source || key.startsWith(source + ':'));
        });
        this.cellItems[cell] = keep;
        if (cell === 0) this.legendItems = keep;
        this._renderLegendRows(cell);
    }

    /** 「🗑」删除本图**全部指标**（不动「加到图表」的策略 ✓） */
    clearIndicators(): void {
        const cell = this.activeCell;
        this.options.onCommand?.('remove_indicator', {
            symbol: this.symbolForCell(cell), key: '*', strategy: false,
            cell,
        });
    }

    /** 右键「删除指标策略」= 删除全部指标 **+** 策略（和工具栏那条不同 ✓） */
    clearIndicatorsAndStrategy(): void {
        const cell = this.activeCell;
        this.options.onCommand?.('remove_indicator', {
            symbol: this.symbolForCell(cell), key: '*', strategy: true,
            cell,
        });
    }

    /** 「🧹」清除全部画线（含副图）✓ */
    clearDrawings(): void {
        for (const handler of this.cells) {
            const box = (handler as unknown as {
                toolBox?: { clearDrawings?: Function } }).toolBox;
            try {
                box?.clearDrawings?.();
            } catch {
                /* ignore */
            }
        }
        this.options.onCommand?.('clear_drawings', {
            symbol: this.options.symbol,
        });
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
        // ★ 点档位 → 填「本地模拟交易」面板的价格（强制覆盖手输 ✓）
        this.localTicket?.setPriceForce(this.orderPrice);
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
        // 本地图表：买 / 卖都按**最新收盘价**成交；有反向持仓时自动平仓 ✓
        const qty = Math.max(1, Number(this.orderQty) || 1);
        const close = (this.localNet > 0 && side === 'sell')
            || (this.localNet < 0 && side === 'buy');
        this.options.onCommand?.('local_order', {
            symbol: this._activeLocalName(),
            side, qty, price: this.localPrice, close,
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
    toast(text: string, placement: 'bottom' | 'top' = 'bottom'): void {
        const tip = document.createElement('div');
        // `top` = 顶部中间（编辑器体检提示 ✓）
        tip.className = `desk-toast on${placement === 'top' ? ' top' : ''}`;
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
            chart.timeScale().setVisibleRange({
                from: from as never, to: to as never,
            });
        } catch {
            /* 数据还没到，忽略 ✓ */
        } finally {
        }
    }


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
            // ② 十字线同步：本地图表按**索引**对齐（各 CSV 时间范围不同 ✓）
            chart.subscribeCrosshairMove((param: Record<string, unknown>) => {
                if (!this.linked || this._linkGuard || !param) return;
                const logical = Number(param.logical);
                this._linkGuard = true;
                try {
                    charts.forEach((other, otherIndex) => {
                        if (otherIndex === index) return;
                        const bars = this.cellBars[otherIndex] || [];
                        if (!Number.isFinite(logical) || !bars.length) {
                            other.clearCrosshairPosition?.();
                            return;
                        }
                        const at = Math.max(0, Math.min(bars.length - 1,
                                                        Math.round(logical)));
                        const bar = bars[at];
                        other.setCrosshairPosition(
                            Number(bar.close), bar.time as never,
                            series[otherIndex]);
                    });
                } catch {
                    /* ignore */
                } finally {
                    this._linkGuard = false;
                }
            });
        });
    }

    /** 设置 → 图表配置（持仓线 / 挂单线 / 字体大小 ✓） */
    setChartConfig(values: Record<string, unknown>): void {
        if (!values) return;
        if ('chart_color_up' in values) {
            this.customUp = String(values.chart_color_up || '');
        }
        if ('chart_color_down' in values) {
            this.customDown = String(values.chart_color_down || '');
        }
        if ('chart_color_up' in values || 'chart_color_down' in values) {
            this._applyChartType();
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
        if ('chart_font_size' in values) {
            const size = Math.max(9, Math.min(28,
                Number(values.chart_font_size) || 13));
            for (const div of Array.from(
                this.element.querySelectorAll<HTMLElement>('.desk-legend'))) {
                div.style.fontSize = `${size}px`;
            }
        }
        if ('editor_format_on_save' in values) {
            this.formatOnSaveSetting = !!values.editor_format_on_save;
            this.editor?.setFormatOnSave(this.formatOnSaveSetting);
        }
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

    /** 「持仓线」开关 ✓ */
    togglePositionLine(visible?: boolean): boolean {
        this.positionLineVisible =
            visible === undefined ? !this.positionLineVisible : !!visible;
        if (!this.positionLineVisible) {
            this.hidePositionLine();
        } else if (this.lastPosition) {
            // 多布局：恢复时每格的持仓线都要画回来（不能只画最后一条 ✓）
            if (this.lastPositions.size) {
                for (const [cell, payload] of this.lastPositions) {
                    this.setPosition(payload, cell);
                }
            } else {
                this.setPosition(this.lastPosition);
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
                    const rows = (this.localIndicators[index]?.items
                        || this.cellItems[index]
                        || []) as unknown as Array<Record<string, unknown>>;
                    return {
                        symbol,
                        indicators: rows.map((item) => {
                            const key = String(item.key || '');
                            const style = (layer?.styleOf?.(key) || {}) as
                                Record<string, unknown>;
                            return {
                                ...item,
                                ...style,
                                // 眼睛 / 设置里隐藏过的指标也要写进布局 ✓
                                visible: style.visible !== undefined
                                    ? style.visible
                                    : (hidden.has(key) ? false
                                        : item.visible !== false),
                            };
                        }),
                    };
                });
                this.options.onCommand?.('layout_save', {
                    symbol: this.symbolForCell(0), name, local: true,
                    cols: this.layout.cols, rows: this.layout.rows,
                    cycle: this.cycle, cells,
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
                    symbol: this.symbolForCell(0), key, local: true,
                });
            };
            this.layoutManager.onDeleteCallback = (key) => {
                this.options.onCommand?.('layout_delete', { key });
            };
            this.layoutManager.onFavoriteCallback = (key, on) => {
                this.options.onCommand?.('layout_favorite', { key, on });
            };
            this.layoutManager.onEditCallback = (row) => {
                this.openLayoutParams(row as unknown as
                    Record<string, unknown>);
            };
            this.layoutManager.onExportCallback = () => {
                this.options.onCommand?.('layouts_export', {});
            };
            this.layoutManager.onImportCallback = (text) => {
                this.options.onCommand?.('layouts_import', { text });
            };
        }
        this.layoutManager.open();
        this.options.onCommand?.('layouts', {});
    }

    /** 编辑某个布局的指标参数（✎）✓ */
    openLayoutParams(row: Record<string, unknown>): void {
        if (!this.layoutParams) {
            this.layoutParams = new LayoutParamsDialog();
            this.layoutParams.setTheme(
                this.options.theme === 'light' ? 'light' : 'dark');
            this.layoutParams.onSaveCallback = (cells) => {
                this.options.onCommand?.('layout_update', {
                    key: row.key, cells, local: true,
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
        const cols = this.layout.cols;
        const rows = this.layout.rows;
        const short: Record<string, string> = {
            v2: '上下', t1b2: '上1下2', t2b1: '上2下1',
            h3: '横三', v3: '竖三',
        };
        const text = short[this.spec?.key || ''];
        label.textContent = text ? `布局 ${text}`
            : (cols * rows > 1 ? `布局 ${cols}×${rows}` : '布局');
    }

    /** 布局预设（和看盘窗口同一批：单图 / 上下 / 上1下2 / 上2下1 / 横三 / 竖三 / 四图 ✓） */
    private _layoutPresetItems(): MenuItem[] {
        const current = this.spec?.key || '';
        return DESK_LAYOUTS.map((item) => ({
            label: `${item.label}${item.key === current ? '  ✓' : ''}`,
            run: () => this.setLayoutSpec(item),
        }));
    }

    /** 本地图表布局菜单（预设 + 已保存布局 ✓） */
    openLocalLayoutMenu(anchor: HTMLElement): void {
        showMenuBelow(anchor, this._layoutPresetItems());
    }

    openLayoutMenu(anchor: HTMLElement): void {
        const presets: MenuItem[] = this._layoutPresetItems();
        const saved = this.layouts.map((row) => {
            // 缩略信息：`4格 · 1分`（`shape` 后端已经算好，直接用 ✓）
            const count = Number(row.count || (Number(row.cols || 1)
                * Number(row.rows || 1)));
            const cycle = Number(row.cycle || 60);
            const indicators = Number(row.indicators || 0);
            const bits = [`${count}格`, cycleLabel(cycle)];
            if (indicators) bits.push(`${indicators}指标`);
            const desc = String(row.desc || '').split(' · ').slice(2).join(' · ');
            return {
                label: `${row.name || row.key}`
                    + (row.favorite ? '  ★' : '')
                    + `   ${bits.join(' · ')}`
                    + (desc ? `   ${desc.slice(0, 24)}` : ''),
                run: () => this.options.onCommand?.('layout_apply', {
                    symbol: this.symbolForCell(0), key: row.key, local: true,
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
        this.editor?.setTheme(theme);
        this.indicators?.applyTheme(theme);
        for (const layer of this.layers) layer.applyTheme(theme);
        this.alertDialog?.setTheme(theme);
        this.symbolSearch?.setTheme(theme);
        this.indicatorPicker?.setTheme(theme);
        this.templatePicker?.setTheme(theme);
        this._applyChartType();          // 换主题后重建非蜡烛序列（颜色）✓
        this._applyCrosshairStyle();      // 十字线样式跟主题 ✓
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

    /** 「交易」按钮：显示/隐藏底部账户面板（显示时按钮高亮 ✓） */
    toggleDock(visible?: boolean): boolean {
        const show = visible === undefined ? !this.dockVisible : !!visible;
        this.dockVisible = show;
        this.dock.element.style.display = show ? '' : 'none';
        if (this.dockSplitter) {
            this.dockSplitter.style.display = show ? '' : 'none';
        }
        if (show) {
            this._ensureDockSplitter();
            const total = this.element.getBoundingClientRect().height
                || this.element.clientHeight;
            if (!this._dockSized && total > 240) {
                this.dockRatio = 1 / 4;
                this.dockHeight = Math.round(total * this.dockRatio);
                this._dockSized = true;
            }
            this._applyDockRatio(total);
            this.dock.element.style.height = `${this.dockHeight}px`;
        }
        this._syncToggles();
        this.resize();
        return this.dockVisible;
    }

    /** 打开底部「代码」页签（策略回测页写回参数 / 用户点工具栏 ✓） */
    openEditor(): void {
        this._ensureEditor();
        if (!this.dockVisible) this.toggleDock(true);
        this.dock.setTab('code');
        this.resize();
    }

    /** 「代码」页签的编辑器（惰性创建 ✓） */
    private _ensureEditor(): EditorPanel {
        if (!this.editor) {
            this.editor = new EditorPanel({
                theme: this.options.theme === 'light' ? 'light' : 'dark',
                // 本地图表：加到图表走 `local_add_indicator`（带 CSV 名 + 格号 ✓）
                local: true,
                symbol: () => this.symbolForCell(this.activeCell),
                cell: () => this.activeCell,
                onCommand: (cmd: string, payload?: unknown) =>
                    this.options.onCommand?.(cmd, payload),
                lsp: () => this.options.lsp?.(),
                formatOnSave: this.formatOnSaveSetting,
                onToast: (level: string, text: string, _actions?: unknown[],
                          _detail?: string,
                          placement?: 'bottom' | 'top') => {
                    void level;
                    // `top` = 顶部中间（编辑器体检提示 ✓）
                    this.toast(text, placement === 'top' ? 'top' : 'bottom');
                },
                allowLive: false,          // 本地图表不显示「策略实盘」✓
                onBacktest: (path: string) =>
                    this.options.onStrategy?.(path, 'backtest'),
                onOptimize: (path: string) =>
                    this.options.onStrategy?.(path, 'optimize'),
            });
            this.dock.editorPane.appendChild(this.editor.element);
        }
        return this.editor;
    }

    /** app.ts 的编辑器补丁分发要用 ✓ */
    get editorPanel(): EditorPanel | null {
        return this.editor;
    }

    /** 后端「回测 / 参数优化」体检结果 → 转给编辑器 ✓ */
    setStrategyCheck(patch: Record<string, any>): void {
        this.editor?.setStrategyCheck?.(patch);
    }

    /** 底部面板「最大化 / 恢复」✓ */
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

    /**
     * 首次布局：**图表 : 编辑器 = 3 : 1**（底部面板 = 页面高度的 1/4）✓
     *
     * 以前这里按 0.34 算、`toggleDock()` 里按 1/3 算、还会从设置里恢复上次
     * 的 `dock_height_local` → **每次初始化比例都不一样**（用户反馈 ✗）。
     * 现在初始化**一律** 1/4，用户拖动后才按拖动的值（本会话内）✓
     */
    private _sizeDockToPage(): void {
        if (this._dockSized) return;
        const total = this.element.getBoundingClientRect().height
            || this.element.clientHeight;
        if (total <= 240) return;            // 还没挂载 / 高度为 0 → 下次再试
        this.dockRatio = 1 / 4;
        this.dockHeight = Math.max(140, Math.min(
            Math.round(total * this.dockRatio), Math.round(total * 0.72)));
        this.dock.element.style.height = `${this.dockHeight}px`;
        this._dockSized = true;
    }

    /** 图表 / 底部面板之间的可拖动分隔条 ✓ */
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
                this._dockSized = true;
                this.options.onCommand?.('set_setting', {
                    key: 'dock_height_local', value: this.dockHeight,
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
                || this.element.clientHeight || 720;
            this.dockRatio = 1 / 4;
            this.dockHeight = Math.round(Math.max(140, total * this.dockRatio));
            this.dock.element.style.height = `${this.dockHeight}px`;
            this.options.onCommand?.('set_setting', {
                key: 'dock_height_local', value: this.dockHeight,
            });
            this.resize();
        });
        this.dockSplitter = bar;
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
        this.linkButton?.classList.toggle('on', this.linked);
        this.ticketButton?.classList.toggle('on', this.orderTicketVisible);
    }

    /** 预警列表（后端 `{type:'alerts'}` 补丁 → 对话框列表 ✓） */
    setAlerts(items: Array<Record<string, unknown>>): void {
        this.localAlerts = items || [];
        this.alertDialog?.setItems(items as never);
        this._renderAlertLines();
    }

    /** 本地预警：每根回放 K 线 / 加载数据时检查一次 ✓ */
    private _checkLocalAlerts(price: number): void {
        if (!Number.isFinite(price) || price <= 0) return;
        const previous = this.localPrevPrice;
        this.localPrevPrice = price;
        for (const alert of this.localAlerts) {
            if (alert.fired) continue;
            const target = Number(alert.price);
            if (!Number.isFinite(target)) continue;
            const cross = String(alert.cross || '穿过');
            const hit = cross === '上穿'
                ? price >= target && (!previous || previous < target)
                : cross === '下穿'
                    ? price <= target && (!previous || previous > target)
                    : (!previous ? Math.abs(price - target) < 1e-9
                        : (previous - target) * (price - target) <= 0);
            if (!hit) continue;
            alert.fired = true;
            this.toast(`预警触发：${alert.message || this.options.symbol}`
                + ` @ ${price}`);
        }
        this.alertDialog?.setItems(this.localAlerts as never);
        this._renderAlertLines();
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

    /** 指标线（MA/BOLL 叠主图；MACD/KDJ/RSI 各开一个副图 ✓） */
    setIndicators(payload: IndicatorPayload): void {
        this.setCellLocalIndicators(0, payload);
    }

    /** 某格的指标（多布局每格独立 ✓）；回放中只更新切片数据 */
    setCellLocalIndicators(cell: number, payload: IndicatorPayload): void {
        const index = Math.max(0, Math.min(Number(cell) || 0,
                                         Math.max(0, this.cells.length - 1)));
        this.localIndicators[index] = payload;
        if (this.replaying) {
            const items = payload.items || [];
            if (index === 0) this.replayIndicators = items;
            const cell = this.replayCells.find((item) => item.cell === index);
            if (cell) cell.indicators = items;
            this._applyReplayIndicators();
            return;
        }
        this.setCellIndicators(index, payload);
    }

    /** 第 N 格的指标（后端 `{type:'indicator', cell:n}` ✓） */
    setCellIndicators(index: number, payload: IndicatorPayload): void {
        const cell = Math.max(0, Math.min(Number(index) || 0,
                                         Math.max(0, this.layers.length - 1)));
        const layer = this.layers[cell] || this.indicators;
        const items = (payload.items || []) as IndicatorLine[];
        this.cellItems[cell] = items;
        if (cell === 0) this.legendItems = items;
        // ★ 隐藏的指标不从 items 里删（删了指标标签也会消失 ✗）
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        this._ensureCrosshair();          // ★ 表格跟随鼠标依赖它（无 VP 也要装）
        layer.apply({ ...payload, items: this._drawItems(cell, items) });
        // 新 pane 会使用 LWC 默认分隔线颜色 -> 重新套主题
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
            gear.addEventListener('click', () =>
                this.editIndicator(item, gear, cell));
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
     * ⚠ **只隐藏指标线**：图例行 / 指标标签永远都在（用户要求 ✓）。
     */
    toggleIndicator(key: string, visible?: boolean, cell = 0): void {
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        const show = visible === undefined ? hidden.has(key) : !!visible;
        if (show) hidden.delete(key);
        else hidden.add(key);
        const layer = this.layers[cell] || this.indicators;
        // 眼睛与设置菜单的「显示该指标」共用同一份样式状态 ✓
        layer.setVisible(key, show);
        // ★ VP 是 canvas 覆盖层：只算“该画哪些”，**不**去删 items ✓
        this._syncVpOverlay(cell, (this.cellItems[cell] || [])
            .filter((item) => !hidden.has(item.key)));
        this._renderLegendRows(cell);
    }

    /** 指标（一个 source 的所有线）是否**主图 + 副图混在一起** ✓ */
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
        const symbol = this.symbolForCell(cell);
        const hidden = this.cellHidden[cell] || this.hiddenIndicators;
        const saved = layer.styleOf(item.key);
        const overlayLocked = this._overlayLocked(item, cell);
        // ★ 当前样式（选颜色「立即预览」与「应用」共用同一套默认值 ✓）
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
                        // ★ 与图例眼睛走**同一条路径**：只隐藏线，不删指标标签 ✓
                        this.toggleIndicator(item.key, !!state.visible, cell);
                    } else {
                        this._renderLegendRows(cell);
                    }
                    // 显示区域变了 → 重新加一次（主图 ↔ 副图）
                    if (!overlayLocked && !!state.overlay !== !!item.overlay) {
                        this.options.onCommand?.('add_indicator', {
                            symbol,
                            key: (item as unknown as { source?: string }).source
                                || String(item.key).split(':')[0],
                            params: state.params,
                            overlay: state.overlay, cell,
                        });
                        return;
                    }
                    // 参数变了 → 让后端重算
                    const before = JSON.stringify(item.params || {});
                    if (JSON.stringify(state.params) !== before) {
                        this.options.onCommand?.('add_indicator', {
                            symbol,
                            key: (item as unknown as { source?: string }).source
                                || String(item.key).split(':')[0],
                            params: state.params, cell,
                        });
                    }
                },
                onDelete: () => {
                    this.options.onCommand?.('remove_indicator', {
                        symbol,
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
        const symbol = this.symbolForCell(cell);
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
                    symbol,
                    key: (item as unknown as { source?: string }).source
                        || String(item.key).split(':')[0],
                    params: values, cell,
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

    /** 偏好设置（`ticket_click_orders` / 底部面板高度 `dock_height` ✓） */
    setSettings(settings: Record<string, unknown>): void {
        const ticker = settings?.ticker_only_quoted;
        this.tickerOnlyQuoted = ticker === true || ticker === 1
            || ticker === 'true';
        this._syncTickerButton();
        // ★ 本地图表自己的高度键（**不**继承看盘窗口的 `dock_height` ✗）
        // ⚠ `dock_height_local` **不再**在初始化时套用：用户要求每次
        //   初始化都是 图表:编辑器 = 3:1（老值会让比例每次都不一样 ✗）
        void settings?.dock_height_local;
        const filter = String(settings?.indicator_overlay_filter || 'all');
        this.indicatorFilter = filter === 'main' || filter === 'sub'
            ? filter : 'all';
        this.indicatorPicker?.setOverlayFilter(this.indicatorFilter);
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
        this.book.setBook(data);
        this.setTicketBook({ bids: data.bids || [], asks: data.asks || [] });
        // 买卖盘价格跟买一/卖一走，不填最新价 ✓
    }

    /**
     * 持仓线：**多头 / 空头分别画**（期货锁仓时两条腿同时存在 ✓）。
     * 没有持仓 → 全部移除；开关由「设置 → 图表配置 → 持仓线」控制。
     */
    private lastPosition: { long?: PosSide | null; short?: PosSide | null } | null = null;
    /** 每格最近一次的持仓（切换持仓线开关时逐格重画 ✓） */
    private readonly lastPositions = new Map<number, {
        long?: PosSide | null; short?: PosSide | null }>();

    setPosition(payload: { long?: PosSide | null; short?: PosSide | null },
                cell?: number): void {
        this.lastPosition = payload;
        this.lastPositions.set(typeof cell === 'number' ? cell : 0, payload);
        this._setTicketPosition(payload);
        // ★ 多布局：指定格子时临时切到那一格的 handler，画完再切回 ✓
        const saved = this.handler;
        const target = (typeof cell === 'number')
            ? (this.cells[cell] || null) : null;
        if (target) this.handler = target;
        try {
            this._applyPositionLine(payload, typeof cell === 'number' ? cell : 0);
        } finally {
            if (target) this.handler = saved;
        }
    }

    /** 真正画持仓线（`setPosition` 内部用 ✓） */
    private _applyPositionLine(payload: {
        long?: PosSide | null; short?: PosSide | null }, cell = 0): void {
        this.hidePositionLine(cell);
        if (!this.positionLineVisible || !this.handler) return;
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
                    lineStyle: 2 as never,          // dashed
                    width: 1,
                    text,
                    // 标签用图内左侧色块（不画在价格轴里 ✓）
                    axisLabelVisible: false,
                    labelVisible: false,
                },
                null,
            );
            try {
                const series = this.handler.series as unknown as
                    { attachPrimitive: Function };
                series.attachPrimitive(line);
                const bucket = this.positionLinesByCell.get(cell) || [];
                bucket.push({ side: short ? 'short' : 'long', line });
                this.positionLinesByCell.set(cell, bucket);
                keys.push(`${side.side}${side.volume}${avg}`);
                // ★ 标签绑在**持仓所在那一格**（cell），不再放到整页左侧 ✗
                this._addPositionBadge(avg, text, color, cell);
            } catch {
                try { line.detach(); } catch { /* ignore */ }
            }
        }
        this.positionKey = keys.join('|');
        this._placePositionBadge();
    }

    /** 当前持仓线标识（多空两条时用 `|` 连接）—— 便于调试/去重 ✓ */
    get positionLineKey(): string {
        return this.positionKey;
    }

    /** 新增一个**图内**持仓标签（带所属格子 / 原始文字 ✓） */
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
     * 把持仓色块放到**对应格子**的左侧（跟着均线高度 ✓）
     *
     * 关键修复：
     * * 每格用自己的 `pane` / `priceToCoordinate`（以前全用 `cells[0]`，
     *   第二格的持仓线/标签会跑到整页左下角 ✗）；
     * * 均价在可视区间外（持仓很久 / 回放价格跑远）→ 标签**贴到该格上沿 /
     *   下沿**并带 ↑/↓，用户始终能看到「多/空几手」；线本身仍在均价处。
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
                    // 均价在可视区间**上方** → 贴上沿 + ↑
                    badge.textContent = `↑ ${text}`;
                    badge.style.top = `${paneRect.top - hostRect.top
                        + 4 + topOffset}px`;
                    topOffset += 20;
                } else if (y > paneRect.height) {
                    // 均价在可视区间**下方** → 贴下沿 + ↓
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

    private hidePositionLine(cell = 0): void {
        // ★ 只删**这一格**的标签；另一格的持仓线/标签不能被顺带清掉 ✗
        this.positionBadges = this.positionBadges.filter((badge) => {
            if (Number(badge.dataset.cell) !== cell) return true;
            badge.remove();
            return false;
        });
        for (const item of (this.positionLinesByCell.get(cell) || [])) {
            try {
                item.line.detach();
            } catch {
                /* ignore */
            }
        }
        this.positionLinesByCell.delete(cell);
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
     * ``cell`` = 多布局格号（每格只画自己那个数据的挂单 ✓）
     */
    setOrders(items: Array<Record<string, unknown>>, cell = 0): void {
        this.orderItemsByCell.set(Math.max(0, Number(cell) || 0),
                                  Array.isArray(items) ? items : []);
        this._renderOrderLines();
    }

    private _renderOrderLines(): void {
        this._clearOrderLines();
        if (!this.orderLineVisible) return;
        for (const [cell, items] of this.orderItemsByCell) {
            const handler = this.cells[cell];
            if (!handler) continue;
            for (const item of items) {
                const price = Number(item.price);
                if (!Number.isFinite(price) || price <= 0) continue;
                const side = String(item.side || '买');
                const color = side === '卖' ? '#ef5350' : '#26a69a';
                const line = new HorizontalLine(
                    { time: null, logical: 0 as never, price },
                    {
                        lineColor: color,
                        lineStyle: 2 as never,      // dashed（同持仓线 ✓）
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
                    + price.toFixed(this.localDecimals);
                badge.textContent = text;
                badge.title = `${side}${String(item.offset || '开')} ${qty} 手`
                    + ` @ ${price}（未成交）`;
                badge.style.borderColor = color;
                badge.style.color = color;
                badge.dataset.price = String(price);
                badge.dataset.cell = String(cell);
                this.element.appendChild(badge);
                this.orderLines.push({ cell, line, badge, price });
            }
        }
        this._placeOrderBadges();
    }

    private _placeOrderBadges(): void {
        if (!this.orderLines.length) return;
        const hostRect = this.element.getBoundingClientRect();
        for (const item of this.orderLines) {
            const cell = this.cells[item.cell] as unknown as {
                series?: { priceToCoordinate?: (p: number) => number | null };
                chart?: { panes?: () => Array<{ getHTMLElement?: Function }> };
            } | undefined;
            const pane = cell?.chart?.panes?.()?.[0]?.getHTMLElement?.();
            const paneRect = pane?.getBoundingClientRect();
            const y = cell?.series?.priceToCoordinate?.(item.price);
            if (y === null || y === undefined || !paneRect) {
                item.badge.style.display = 'none';
                continue;
            }
            item.badge.style.left = `${paneRect.left - hostRect.left + 8}px`;
            item.badge.style.top = `${paneRect.top - hostRect.top + y - 9}px`;
            item.badge.style.display = '';
        }
        this._stackLineBadges();
    }

    private _clearOrderLines(): void {
        for (const item of this.orderLines) {
            try {
                item.line.detach();
            } catch {
                /* ignore */
            }
            item.badge.remove();
        }
        this.orderLines = [];
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
    private _renderAlertLines(): void {
        this._clearAlertLines();
        if (!this.handler) return;
        for (const item of this.localAlerts) {
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
                this.localDecimals)}`;
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

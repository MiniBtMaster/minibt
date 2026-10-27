/**
 * StrategyLabPage — 策略回测 / 参数优化（P118+）。
 *
 * 入口在本地图表编辑器的「策略回测 / 参数优化」按钮；本页是**独立 tab**，
 * 原来的本地图表保持不变。退出时由 App 关闭本 tab，回到 source tab。
 *
 * 布局（二级 Tab）：
 *   图表 / 回测结果 / 交易记录 / 参数优化
 * 图表直接用 MiniQT 的原代码生成自包含 HTML，iframe 装载；desk 只负责
 * 二级 Tab、指标卡片、交易记录和参数优化表。
 */

export interface StrategyLabOptions {
    id: string;
    file: string;
    mode: 'backtest' | 'optimize';
    theme: 'light' | 'dark';
    sourceId?: string;
    onCommand: (cmd: string, payload?: Record<string, unknown>) => void;
    onExit: () => void;
    onToast: (level: string, text: string) => void;
    onWriteParams?: (params: Record<string, unknown>) => void;
    /** 图表字体大小（设置 → 图表配置 → `chart_font_size` ✓） */
    fontSize?: number;
    /** 鼠标十字线标签颜色（设置 → 图表颜色 → `chart_color_crosshair` ✓） */
    crosshairColor?: string;
}

interface StrategyRow {
    name: string;
    contracts: string[];
    metrics?: Record<string, number>;
}

interface ResultPayload {
    strategy?: string;
    metrics?: Record<string, number>;
    equity?: { times?: number[]; values?: number[]; drawdown?: number[] };
    pnl?: Array<[number, number]>;
    trade_style?: { show?: boolean; color?: string; width?: number;
                    dash?: string };
    contracts?: Array<{ symbol: string; trade_count?: number; bars?: number }>;
}

interface TradeRow {
    time?: number;
    direction?: string;
    symbol?: string;
    price?: number;
    qty?: number;
    fee?: number;
    equity?: number;
    pnl?: number;
}

const METRIC_GROUPS: Array<[string, Array<[string, string, string]>]> = [
    ['收益指标', [
        ['profit', '最终收益', 'money'], ['return_pct', '累计收益率', 'pct'],
        ['total_fee', '总手续费', 'money'], ['payoff_ratio', '盈亏比', 'num'],
        ['avg_return', '平均收益', 'num'], ['avg_win', '平均盈利', 'num'],
    ]],
    ['风险指标', [
        ['sharpe', '夏普比率', 'num'], ['drawdown', '最大回撤', 'pct'],
        ['var', '风险价值(VaR)', 'num'], ['risk_return', '风险收益比', 'num'],
    ]],
    ['交易指标', [
        ['winrate', '胜率', 'pct'], ['wins', '盈利次数', 'int'],
        ['losses', '亏损次数', 'int'], ['profit_ratio', '收益比率', 'num'],
        ['trades', '交易次数', 'int'], ['avg_loss', '平均亏损', 'num'],
    ]],
];

function esc(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch] || ch));
}

function num(value: unknown, digits = 2): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '--';
    return parsed.toLocaleString('zh-CN', {
        minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
}

function fmt(value: unknown, kind: string): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '--';
    if (kind === 'money') return num(parsed, 2);
    if (kind === 'pct') return `${(parsed * 100).toFixed(2)}%`;
    if (kind === 'int') return String(Math.round(parsed));
    return num(parsed, 4);
}

function timeText(value: unknown): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return '--';
    return new Date(parsed * 1000).toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
    });
}

function equitySvg(equity: ResultPayload['equity']): string {
    const values = (equity?.values || []).map(Number);
    const drawdowns = (equity?.drawdown || []).map(Number);
    const count = Math.min(values.length, drawdowns.length);
    const pairs: Array<[number, number]> = [];
    for (let index = 0; index < count; index += 1) {
        const value = values[index];
        const drawdown = drawdowns[index];
        if (Number.isFinite(value) && Number.isFinite(drawdown)) {
            pairs.push([value, drawdown]);
        }
    }
    if (pairs.length < 2) {
        return '<div class="desk-strategy-empty">权益 / 回撤曲线暂不可用</div>';
    }

    const width = 1000;
    const height = 260;
    const left = 66;
    const right = 66;
    const top = 25;
    const bottom = 24;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    const xAt = (index: number) => left + index * plotWidth / (pairs.length - 1);

    const equityValues = pairs.map(([value]) => value);
    const drawdownValues = pairs.map(([, value]) => value * 100);
    let equityMin = Math.min(...equityValues);
    let equityMax = Math.max(...equityValues);
    if (equityMax === equityMin) {
        equityMax += 1;
        equityMin -= 1;
    }
    let drawdownMin = Math.min(...drawdownValues, 0);
    let drawdownMax = Math.max(...drawdownValues, 0);
    if (drawdownMax === drawdownMin) {
        // 全 0 回撤：0% 放在顶部，避免整条线贴底
        if (drawdownMax === 0) drawdownMin = -1;
        else drawdownMax = drawdownMin + 1;
    }

    const yEquity = (value: number) =>
        top + (equityMax - value) / (equityMax - equityMin) * plotHeight;
    const yDrawdown = (value: number) =>
        top + (drawdownMax - value) / (drawdownMax - drawdownMin) * plotHeight;

    const pathFor = (series: number[], yAt: (value: number) => number) => {
        const points = series.map((value, index) => ({
            x: xAt(index), y: yAt(value),
        }));
        let line = `M${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
        for (let index = 1; index < points.length; index += 1) {
            const previous = points[index - 1];
            const point = points[index];
            const mid = (previous.x + point.x) / 2;
            line += ` C${mid.toFixed(1)} ${previous.y.toFixed(1)},`
                + `${mid.toFixed(1)} ${point.y.toFixed(1)},`
                + `${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
        }
        return line;
    };

    const equityLine = pathFor(equityValues, yEquity);
    const drawdownLine = pathFor(drawdownValues, yDrawdown);
    const area = `${equityLine} L${xAt(pairs.length - 1).toFixed(1)}`
        + ` ${height - bottom} L${left} ${height - bottom} Z`;
    const ticks = [0, 1, 2, 3, 4];
    const grid = ticks.map((tick) => {
        const y = top + plotHeight * tick / 4;
        const equityValue = equityMax - (equityMax - equityMin) * tick / 4;
        const drawdownValue = drawdownMax
            - (drawdownMax - drawdownMin) * tick / 4;
        return `<line x1="${left}" y1="${y.toFixed(1)}" x2="${width - right}"
                y2="${y.toFixed(1)}" stroke="rgba(255,255,255,.07)" stroke-width="1"/>
            <text x="${left - 8}" y="${(y + 3).toFixed(1)}" text-anchor="end"
                class="desk-eq-tick">${num(equityValue, 0)}</text>
            <text x="${width - right + 8}" y="${(y + 3).toFixed(1)}"
                text-anchor="start" class="desk-eq-tick">
                ${drawdownValue.toFixed(2)}%</text>`;
    }).join('');
    return `<svg class="desk-strategy-equity" viewBox="0 0 ${width} ${height}"
        preserveAspectRatio="none" aria-label="权益与回撤曲线">
        <defs><linearGradient id="desk-strategy-eq" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#38bdf8" stop-opacity=".25"/>
            <stop offset="1" stop-color="#38bdf8" stop-opacity="0"/>
        </linearGradient></defs>
        <g>${grid}</g>
        <line x1="${left}" y1="${height - bottom}" x2="${width - right}"
            y2="${height - bottom}" stroke="rgba(255,255,255,.14)" stroke-width="1"/>
        <path d="${area}" fill="url(#desk-strategy-eq)" stroke="none"/>
        <path d="${equityLine}" fill="none" stroke="#38bdf8" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round"
            vector-effect="non-scaling-stroke"/>
        <path d="${drawdownLine}" fill="none" stroke="#ef5350" stroke-width="1.6"
            stroke-linecap="round" stroke-linejoin="round"
            vector-effect="non-scaling-stroke"/>
        <text x="${left}" y="14" class="desk-eq-label"
            style="fill:#38bdf8">● 权益（左轴）</text>
        <text x="${width - right}" y="14" text-anchor="end"
            class="desk-eq-label" style="fill:#ef5350">● 回撤（右轴）</text>
    </svg>`;
}

import { showMenuBelow } from './menu';
import { REPLAY_SEEKS } from './replay';
import { openParamPopover } from './param-popover';

/** 图表类型（和看盘工具栏一致：蜡烛 / 收盘线 / 面积 / 柱 ✓） */
const CHART_KINDS: Array<{ key: string; label: string }> = [
    { key: 'candle', label: '蜡烛' },
    { key: 'line', label: '收盘线' },
    { key: 'area', label: '面积' },
    { key: 'bar', label: '柱（OHLC）' },
];

/** 回放速度档位（和 MiniQT `ReplayWindow` 一致 ✓） */
const REPLAY_SPEEDS = [1, 2, 5, 10];

/** 优化目标下拉的兜底列表（完整 73 个由后端 `strategy_state` 下发 ✓） */
const DEFAULT_OPT_TARGETS = [
    'profit_ratio', 'sharpe', 'sortino', 'calmar', 'omega',
    'max_drawdown', 'volatility', 'win_rate', 'profit_factor',
];

// ---- 回放图标（SVG，和看盘工具栏同一套观感 ✓）----
/** 回放开关：**和看盘窗口工具栏（预警后面）同一个 rewind 图标** ✓ */
const REPLAY_ICON = `<svg width="14" height="14" viewBox="0 0 16 16"
    aria-hidden="true"><g fill="currentColor" stroke="none">
    <path d="M1.5 3 L1.5 13 L7.5 8 Z"/><path d="M8 3 L8 13 L14 8 Z"/>
    </g></svg>`;
const REPLAY_PLAY_ICON = `<svg width="13" height="13" viewBox="0 0 24 24"
    fill="currentColor"><path d="M7 4l13 8-13 8z"/></svg>`;
const REPLAY_PAUSE_ICON = `<svg width="13" height="13" viewBox="0 0 24 24"
    fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect
    x="14" y="4" width="4" height="16"/></svg>`;
const REPLAY_STEP_ICON = `<svg width="13" height="13" viewBox="0 0 24 24"
    fill="currentColor"><path d="M5 4l10 8-10 8z"/><rect x="16" y="4"
    width="3" height="16"/></svg>`;
const REPLAY_EXIT_ICON = `<svg width="13" height="13" viewBox="0 0 24 24"
    fill="currentColor"><path d="M2 4l8 8-8 8z"/><path d="M11 4l8 8-8 8z"/></svg>`;

export class StrategyLabPage {
    public readonly element: HTMLDivElement;
    public readonly id: string;
    public readonly file: string;
    public readonly mode: 'backtest' | 'optimize';
    public readonly sourceId: string;

    private readonly options: StrategyLabOptions;
    private readonly chartFrame: HTMLIFrameElement;
    private readonly resultFrame: HTMLIFrameElement;
    private readonly body: HTMLDivElement;
    private readonly tabs: HTMLDivElement;
    private readonly panels: Record<string, HTMLDivElement> = {};
    private readonly status: HTMLSpanElement;
    private strategies: StrategyRow[] = [];
    private contractTabs: Array<{ key: string; strategy: string;
                                  contract: string; label: string }> = [];
    private active = 'chart';
    private currentResult: ResultPayload = {};
    private frameKey = '';
    private resultKey = '';
    private readonly fileMode = window.location.protocol === 'file:';
    private readonly chartFiles = new Map<string, string>();
    private trades: TradeRow[] = [];
    private optRows: Array<Record<string, any>> = [];
    private optSelected = 0;
    private optFilter = '';
    private optSortKey = '';
    private optSortDir = 1;
    private optChartMode: 'pareto' | 'rank' | 'importance' = 'pareto';
    /** 当前优化目标 / 权重 / 可选目标（由 `strategy_state` 下发 ✓） */
    private optTargets: string[] = [];
    private optWeights: number[] = [];
    private targetOptions: string[] = [];
    private running = false;
    private initialReady = false;
    /** 图表工具栏状态（由 iframe 里的驱动回传 ✓） */
    private chartTools: HTMLDivElement | null = null;
    /** 左上角标签字号（跟设置里的 `chart_font_size` 走 ✓） */
    private fontSize = 13;
    /** 鼠标十字线 X/Y 轴标签颜色（跟 `chart_color_crosshair` 走 ✓） */
    private crosshairColor = '';
    /** 图表设置状态：`replay / playing / kind / toolbox` 由**本页**决定，
     *  `bars / total` 由 iframe 回报（两个图表要一起播放 / 一起暂停 ✓） */
    private toolState = {
        kind: 'candle', toolbox: false, replay: false, playing: false,
        bars: 0, total: 0, speed: 1,
    };
    /** 回放时钟**由本页统一驱动**（两个图表永远同一根，不会各跑各的 ✓） */
    private replayTimer: number | undefined;
    /** 底部回放条（整个图表下方 ✓） */
    private replayBar: HTMLDivElement | null = null;
    private replayPlayButton: HTMLButtonElement | null = null;
    private replayLabel: HTMLSpanElement | null = null;
    private readonly onFrameMessage = (event: MessageEvent) => {
        const data = (event.data || {}) as Record<string, unknown>;
        if (data && data.__deskSL === 'indicatorMenu') {
            this._onIndicatorMenu(data.data as {
                series?: string; kind?: string; payload?: Record<string, any>;
            });
            return;
        }
        if (!data || data.__deskSL !== 'state') return;
        const source = event.source as Window | null;
        const fromChart = source === this.chartFrame.contentWindow;
        const fromResult = source === this.resultFrame.contentWindow;
        if (!fromChart && !fromResult) return;
        const bars = Number(data.bars) || 0;
        const total = Number(data.total) || 0;
        if (total) this.toolState.total = total;
        // 图表驱动回报的开关状态 → 工具栏按钮的高亮 / 再点隐藏都靠它 ✓
        if (typeof data.toolbox === 'boolean') {
            this.toolState.toolbox = data.toolbox;
        }
        if (typeof data.kind === 'string' && data.kind) {
            this.toolState.kind = data.kind;
        }
        if (bars > this.toolState.bars) this.toolState.bars = bars;
        if (this.toolState.total && this.toolState.bars >= this.toolState.total) {
            // 放到最后一根 → 自动停（两个图表都是）✓
            this.toolState.playing = false;
            this._stopReplayClock();
        }
        const frame = fromResult ? this.resultFrame : this.chartFrame;
        // 两个图表「同进同退」：哪个掉队就把它拉回来 ✓
        if (this.toolState.replay && !data.replay) {
            this._post(frame, 'replayStart', { bars: this.toolState.bars });
        } else if (!this.toolState.replay && data.replay) {
            this._post(frame, 'replayExit', {});
        }
        this._renderChartTools();
        this._renderReplayBar();
    };

    constructor(options: StrategyLabOptions) {
        this.options = options;
        this.crosshairColor = String(options.crosshairColor || '');
        this.id = options.id;
        this.file = options.file;
        this.mode = options.mode;
        this.sourceId = options.sourceId || '';

        this.element = document.createElement('div');
        this.element.className = 'desk-strategy-lab';
        this.element.innerHTML = `
            <div class="desk-strategy-head">
                <div class="desk-strategy-title">
                    <span class="eyebrow">STRATEGY LAB</span>
                    <b>${options.mode === 'optimize' ? '参数优化' : '策略回测'}</b>
                    <span class="file">${esc(options.file.split(/[\\/]/).pop() || '')}</span>
                </div>
                <div class="desk-strategy-head-right">
                    <span class="desk-strategy-progress" data-progress>
                        <i></i><em></em>
                    </span>
                    <span class="status" data-status>准备中…</span>
                    <button class="desk-strategy-exit" data-exit>退出${options.mode === 'optimize' ? '参数优化' : '回测'}</button>
                </div>
            </div>
            <div class="desk-strategy-tabs" data-tabs></div>
            <div class="desk-strategy-body" data-body></div>`;
        this.body = this.element.querySelector('[data-body]') as HTMLDivElement;
        this.tabs = this.element.querySelector('[data-tabs]') as HTMLDivElement;
        this.status = this.element.querySelector('[data-status]') as HTMLSpanElement;

        this.chartFrame = document.createElement('iframe');
        this.chartFrame.className = 'desk-strategy-iframe desk-strategy-chart';
        this.chartFrame.title = '合约图表';
        this.chartFrame.style.display = 'none';
        this.body.appendChild(this.chartFrame);

        this.resultFrame = document.createElement('iframe');
        this.resultFrame.className = 'desk-strategy-iframe desk-strategy-result-chart';
        this.resultFrame.title = '回测结果图表';
        this.resultFrame.style.display = 'none';

        this.fontSize = Math.max(9, Math.min(28,
            Number(options.fontSize) || 13));
        this._buildPanels();
        this._bind();
        window.addEventListener('message', this.onFrameMessage);
        this._buildTabs();
        this._showTab('chart');
    }

    // ------------------------------------------------------------- lifecycle
    show(): void {
        this.element.style.display = 'flex';
        this._showTab(this.active);
    }

    hide(): void {
        this.element.style.display = 'none';
    }

    /** 设置 → 图表配置「图表字体大小」/「鼠标标签颜色」同步到两个图表 ✓ */
    setChartConfig(values: Record<string, unknown>): void {
        if (!values) return;
        if ('chart_font_size' in values) {
            const size = Math.max(9, Math.min(28,
                Number(values.chart_font_size) || 13));
            if (size !== this.fontSize) {
                this.fontSize = size;
                this._postFrames('font', { size });
            }
        }
        if ('chart_color_crosshair' in values) {
            this.crosshairColor = String(values.chart_color_crosshair || '');
            this._postFrames('crosshair', { color: this.crosshairColor });
        }
    }

    applyTheme(theme: 'light' | 'dark'): void {
        if (theme === this.options.theme) return;
        this.options.theme = theme;
        this.frameKey = '';
        this.resultKey = '';
        this.chartFiles.clear();
        this._loadChartFrame(this.active === 'result' ? 'result' : this.active);
    }

    destroy(): void {
        this._stopReplayClock();
        window.removeEventListener('message', this.onFrameMessage);
        this.element.remove();
    }

    get sourceTabId(): string { return this.sourceId; }

    private _buildTabs(): void {
        const contracts = this.contractTabs.length ? this.contractTabs
            : [{ key: 'chart', label: '图表', strategy: '', contract: '' }];
        const items: Array<[string, string]> = contracts.map((item) =>
            [item.key, item.label]);
        items.push(['result', '回测结果'], ['record', '指标/记录']);
        if (this.mode === 'optimize') items.push(['optimize', '参数优化']);
        // ★ 回放按钮放进**页签行末尾**（看盘窗口工具栏同款图标）：
        //   回测页在「指标/记录」之后，优化页在「参数优化」之后 ✓
        const replay = `<button class="desk-tool desk-tool-replay${
            this.toolState.replay ? ' on' : ''}" data-sl="replay"
                title="${this.toolState.replay
                    ? '退出回放（恢复全部数据）'
                    : '回放：逐根放出策略信号'}">${REPLAY_ICON}</button>`;
        this.tabs.innerHTML = '<div class="desk-strategy-tablist">'
            + items.map(([key, label]) =>
                `<button class="desk-strategy-tab${key === this.active ? ' on' : ''}"
                    data-tab="${esc(key)}">${esc(label)}</button>`).join('')
            + replay
            + '</div><div class="desk-strategy-charttools" data-charttools></div>';
        this.chartTools = this.tabs.querySelector(
            '[data-charttools]') as HTMLDivElement | null;
        this._renderChartTools();
    }

    /**
     * 右侧图表设置：`回放 / 图表类型 / 画线工具 / 删除画线工具`
     *
     * 这些动作都发给 iframe 里的 `__deskSL` 驱动（图表是 MiniQT 生成的 HTML，
     * 由 `miniqt_backtest_chart.DESK_DRIVER_JS` 提供 API ✓）
     */
    private _renderChartTools(): void {
        const host = this.chartTools;
        if (host) this._syncReplayTabButton();
        if (!host) return;
        const state = this.toolState;
        const kindLabel = CHART_KINDS.find((item) => item.key === state.kind)
            ?.label || '蜡烛';
        const bar = (key: string, text: string, title: string,
                     on = false) => `<button class="desk-sl-btn${on ? ' on' : ''}"
                data-sl="${key}" title="${esc(title)}">${text}</button>`;
        // 回放按钮在**页签行**上（见 `_buildTabs`）→ 这里只放图表设置 ✓
        host.innerHTML = `<button class="desk-sl-btn" data-sl="kind"
                    title="图表类型">${esc(kindLabel)} ▾</button>`
            + bar('toolbox', '画线工具', '显示 / 隐藏画线工具', state.toolbox)
            + bar('clear', '删除画线工具', '清空图上所有画线');
    }

    /** 进回放时要放出的根数（默认**末尾 30%**，`total` 未知时给 0 ✓） */
    private _initialSeekBars(fraction = 0.3): number {
        const total = Number(this.toolState.total) || 0;
        if (!total) return 0;
        return Math.max(1, Math.round(total * fraction));
    }

    /** 页签行上的回放按钮：回放中高亮 ✓ */
    private _syncReplayTabButton(): void {
        const button = this.tabs.querySelector<HTMLElement>(
            '.desk-strategy-tablist [data-sl="replay"]');
        if (!button) return;
        button.classList.toggle('on', this.toolState.replay);
        button.title = this.toolState.replay
            ? '退出回放（恢复全部数据）' : '回放：逐根放出策略信号';
    }

    /** 右侧图表设置的动作（回放 / 图表类型 / 画线工具 / 删除画线 ✓） */
    private _onChartTool(action: string, anchor: HTMLElement): void {
        switch (action) {
            case 'replay':
                this.toolState.replay = !this.toolState.replay;
                this.toolState.playing = false;
                // ★ 默认截到 **末尾 30%**（和看盘窗口 `seek: 0.3` 一致）：
                //   以前传空 payload → 驱动给 0 根 = 全部数据 → 点播放看不
                //   出变化（用户实测"点播放不动"✗）
                const seek = this._initialSeekBars();
                this.toolState.bars = this.toolState.replay ? seek : 0;
                this._stopReplayClock();
                this._postFrames(this.toolState.replay
                    ? 'replayStart' : 'replayExit',
                    this.toolState.replay ? { bars: seek } : {});
                // ★ 页签行上的按钮 / 底部回放条都要跟着变（优化页也要 ✓）
                this._buildTabs();
                this._syncReplayTabButton();
                this._renderReplayBar();
                break;
            case 'play':
                this.toolState.replay = true;
                this.toolState.playing = true;
                this._startReplayClock();
                break;
            case 'pause':
                this.toolState.playing = false;
                this._stopReplayClock();
                break;
            case 'step':
                this.toolState.playing = false;
                this._stopReplayClock();
                this._postFrames('replayStep', {});
                break;
            case 'replayExit':
                this.toolState.replay = false;
                this.toolState.playing = false;
                this._stopReplayClock();
                this._postFrames('replayExit', {});
                break;
            case 'toolbox':
                // ★ 先更新本地状态再发；否则第二次点击仍看到 `false` → 又发
                //   `show: true`，工具箱永远藏不起来（用户实测 ✗）
                this.toolState.toolbox = !this.toolState.toolbox;
                this._postFrames('toolbox', { show: this.toolState.toolbox });
                this._renderChartTools();
                break;
            case 'clear':
                this._postFrames('clearDrawings', {});
                this.options.onToast('info', '已删除图上所有画线');
                break;
            case 'kind':
                showMenuBelow(anchor, CHART_KINDS.map((item) => ({
                    label: `${item.label}${item.key === this.toolState.kind
                        ? '  ✓' : ''}`,
                    run: () => this._postFrames('type', { kind: item.key }),
                })));
                break;
            default:
                break;
        }
        void anchor;
    }

    /**
     * 回放条（**整个图表的下方**，复刻看盘窗口的底部工具条 ✓）
     *
     * 从左到右：``[选择策略 ▾] [▶] [↦] [1x ▾] 已暂停 · 3051/10000（31%） [▶▶]``
     *
     * 和看盘窗口的区别（用户要求 ✓）：
     * * 「选择K线」→ **选择策略**（这里的标的本来就是策略，不是合约）；
     * * 二级菜单「选择合约」→ **选择策略**（按策略名切）；
     * * 「选择时间段」保留；**周期按钮删除**（回测结果固定周期 ✓）。
     */
    private _ensureReplayBar(): void {
        if (this.replayBar) return;
        const bar = document.createElement('div');
        bar.className = 'desk-replay-bar';

        // ① 选择策略 ▾（策略 / 时间段）
        const select = document.createElement('button');
        select.className = 'desk-tool desk-tool-arrow';
        select.title = '选择策略（策略 / 时间段）';
        const selectLabel = document.createElement('span');
        selectLabel.className = 'desk-tool-label';
        selectLabel.textContent = '选择策略';
        const selectCaret = document.createElement('span');
        selectCaret.className = 'desk-tool-caret';
        selectCaret.textContent = '▾';
        select.append(selectLabel, selectCaret);
        select.addEventListener('click', () => {
            const names: string[] = [];
            for (const item of this.contractTabs) {
                if (item.strategy && !names.includes(item.strategy)) {
                    names.push(item.strategy);
                }
            }
            showMenuBelow(select, [
                {
                    label: '选择策略',
                    submenu: names.length
                        ? names.map((name) => ({
                            label: `${name}${this._activeStrategy() === name
                                ? '  ✓' : ''}`,
                            run: () => this._pickStrategy(name),
                        }))
                        : [{ label: '只有一个策略', disabled: true }],
                },
                {
                    label: '选择时间段',
                    submenu: REPLAY_SEEKS.map((fraction) => ({
                        label: `从 ${Math.round(fraction * 100)}% 处开始`,
                        run: () => this._startReplayAt(fraction),
                    })),
                },
            ]);
        });

        // ② 播放 / 暂停
        const play = document.createElement('button');
        play.className = 'desk-tool desk-tool-replay desk-replay-play';
        play.innerHTML = REPLAY_PLAY_ICON;
        play.title = '播放 / 暂停';
        play.addEventListener('click', () => {
            if (this.toolState.playing) {
                this.toolState.playing = false;
                this._stopReplayClock();
            } else {
                this.toolState.replay = true;
                this.toolState.playing = true;
                this._startReplayClock();
            }
            this._renderReplayBar();
        });
        this.replayPlayButton = play;

        // ③ 前进一根
        const step = document.createElement('button');
        step.className = 'desk-tool';
        step.innerHTML = REPLAY_STEP_ICON;
        step.title = '前进一根';
        step.addEventListener('click', () => {
            this.toolState.playing = false;
            this._stopReplayClock();
            this._postFrames('replayStep', {});
            this._renderReplayBar();
        });

        // ④ 速度 ▾
        const speed = document.createElement('button');
        speed.className = 'desk-tool desk-tool-arrow';
        speed.title = '回放速度';
        const speedLabel = document.createElement('span');
        speedLabel.className = 'desk-tool-label';
        speedLabel.textContent = `${this.toolState.speed}x`;
        const speedCaret = document.createElement('span');
        speedCaret.className = 'desk-tool-caret';
        speedCaret.textContent = '▾';
        speed.append(speedLabel, speedCaret);
        speed.addEventListener('click', () => {
            showMenuBelow(speed, REPLAY_SPEEDS.map((value) => ({
                label: `${value}x${value === this.toolState.speed ? '  ✓' : ''}`,
                run: () => {
                    this.toolState.speed = value;
                    speedLabel.textContent = `${value}x`;
                    if (this.toolState.playing) this._startReplayClock();
                },
            })));
        });

        // ⑤ 进度（`已暂停 · 3051/10000（31%）` ✓）
        this.replayLabel = document.createElement('span');
        this.replayLabel.className = 'desk-muted desk-replay-progress';

        // ⑥ 退出回放（▶▶ 图标，和截图一致 ✓）
        const exit = document.createElement('button');
        exit.className = 'desk-tool desk-tool-replay on';
        exit.title = '退出回放（恢复全部数据）';
        exit.innerHTML = REPLAY_EXIT_ICON;
        exit.addEventListener('click', () => {
            this.toolState.replay = false;
            this.toolState.playing = false;
            this._stopReplayClock();
            this._postFrames('replayExit', {});
            this._renderChartTools();
            this._renderReplayBar();
        });

        bar.append(select, play, step, speed, this.replayLabel, exit);
        this.element.appendChild(bar);          // 整页最下方 = 整个图表下方 ✓
        this.replayBar = bar;
    }

    /** 回放条状态同步（进度 / 播放图标 / 显示与否 ✓） */
    private _renderReplayBar(): void {
        this._ensureReplayBar();
        const state = this.toolState;
        this.replayBar?.classList.toggle('on', state.replay);
        if (this.replayPlayButton) {
            this.replayPlayButton.innerHTML = state.playing
                ? REPLAY_PAUSE_ICON : REPLAY_PLAY_ICON;
            this.replayPlayButton.classList.toggle('on', state.playing);
        }
        if (this.replayLabel) {
            const total = state.total;
            const percent = total
                ? Math.round((state.bars / total) * 100) : 0;
            this.replayLabel.textContent = `${state.playing
                ? '回放中' : '已暂停'} · ${state.bars}/${total || '--'}`
                + `（${percent}%）`;
        }
    }

    /** 当前选中的策略名（回放条「选择策略」打 ✓ 用 ✓） */
    private _activeStrategy(): string {
        const found = this.contractTabs.find((item) => item.key === this.active);
        return found?.strategy || this.strategies[0]?.name || '';
    }

    /** 回放条「选择策略」→ 切到该策略的第一张合约图并继续回放 ✓ */
    private _pickStrategy(name: string): void {
        const target = this.contractTabs.find((item) => item.strategy === name);
        if (target) this._showTab(target.key);
        if (this.toolState.replay) {
            this.toolState.bars = 0;
            this._postFrames('replayStart', {});
        }
        this._renderReplayBar();
        this.options.onToast('info', `回放策略：${name}`);
    }

    /** 回放条「选择时间段」→ 从该位置重新开始 ✓ */
    private _startReplayAt(fraction: number): void {
        this.toolState.replay = true;
        this.toolState.playing = false;
        this._stopReplayClock();
        const bars = this._initialSeekBars(fraction);
        this._postFrames('replayStart', { bars: Math.max(1, bars) });
        // ★ 驱动里的字段名是 `frac`（不是 seek）✓
        this._postFrames('replaySeek', { frac: fraction });
        this.toolState.bars = bars;
        const percent = Math.round(fraction * 100);
        this.options.onToast('info', `回放从 ${percent}% 处开始`);
        this._renderChartTools();
        this._renderReplayBar();
    }

    /**
     * 图例齿轮菜单回调（`kind`：`params` / `style` / `width` / `color` / …）
     *
     * * `params` → 弹参数框，确认后让后端**按新参数重算指标并重建图表** ✓
     * * 其余样式项 → 图表里已经即时生效，这里只提示一下（不重算 ✓）
     */
    private _onIndicatorMenu(data: {
        series?: string; kind?: string; payload?: Record<string, any>;
    }): void {
        const payload0 = data?.payload || {};
        const series = String(payload0.source || data?.series || '');
        const kind = String(data?.kind || '');
        const payload = data?.payload || {};
        if (kind !== 'params') {
            const label: Record<string, string> = {
                style: '线型', width: '线宽', color: '线颜色',
                priceLine: '价格线', priceLabel: '价格标签',
            };
            this.options.onToast('info',
                `${series}：已更新${label[kind] || '样式'}`);
            return;
        }
        const values = (payload.values || {}) as Record<string, number>;
        if (!Object.keys(values).length) return;
        openParamPopover(
            null,
            `${series} 参数`,
            values,
            (next) => {
                this.options.onCommand('strategy_indicator_params', {
                    id: this.id, series, values: next,
                });
                this.options.onToast('info', `${series}：正在按新参数重算…`);
            },
            this.options.theme === 'light' ? 'light' : 'dark',
        );
    }

    /** 回放时钟：1x ≈ 400ms 放一根，倍速只改间隔（两个图表同时单步 ✓） */
    private _startReplayClock(): void {
        this._stopReplayClock();
        const interval = Math.max(30, Math.round(400 / Math.max(1,
            this.toolState.speed)));
        this.replayTimer = window.setInterval(() => {
            if (!this.toolState.replay) {
                this._stopReplayClock();
                return;
            }
            this._postFrames('replayStep', {});
            this._renderChartTools();
        }, interval);
        this._renderChartTools();
    }

    private _stopReplayClock(): void {
        if (this.replayTimer === undefined) return;
        window.clearInterval(this.replayTimer);
        this.replayTimer = undefined;
    }

    /** 把命令发给两个 iframe（图表 / 回测结果都保持同样的类型与画线状态 ✓） */
    private _postFrames(cmd: string, payload: Record<string, unknown>): void {
        this._post(this.chartFrame, cmd, payload);
        if (this.resultFrame.contentWindow) {
            this._post(this.resultFrame, cmd, payload);
        }
    }

    private _post(frame: HTMLIFrameElement, cmd: string,
                  payload: Record<string, unknown>): void {
        const win = frame.contentWindow;
        if (!win) return;
        try {
            win.postMessage({ __deskSL: cmd, ...payload }, '*');
        } catch {
            /* 老 HTML 没有驱动 → 忽略 ✓ */
        }
    }

    private _buildPanels(): void {
        for (const key of ['result', 'record', 'optimize']) {
            const panel = document.createElement('div');
            panel.className = `desk-strategy-panel desk-strategy-${key}`;
            panel.dataset.panel = key;
            panel.style.display = 'none';
            this.panels[key] = panel;
            this.body.appendChild(panel);
        }
        this.panels.result.appendChild(this.resultFrame);
        this.panels.record.innerHTML = '<div class="desk-strategy-empty">回测中…</div>';
        if (this.panels.optimize) {
            this.panels.optimize.innerHTML = '<div class="desk-strategy-empty">参数优化中…</div>';
        }
    }

    private _bind(): void {
        this.element.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            if (target.closest('[data-exit]')) {
                this.options.onExit();
                return;
            }
            if (target.closest('[data-opt-restart]')) {
                this._restartOptimize();
                return;
            }
            if (target.closest('[data-opt-target-reset]')) {
                if (this.running) return;
                this.optRows = [];
                this.optTargets = [];
                this._renderOptimization();
                this.options.onCommand('strategy_start', {
                    file: this.file, mode: 'optimize', metrics: [],
                });
                return;
            }
            const tool = target.closest<HTMLElement>('[data-sl]');
            if (tool) {
                this._onChartTool(tool.dataset.sl || '', tool);
                return;
            }
            const tab = target.closest<HTMLElement>('[data-tab]');
            if (tab) {
                const key = tab.dataset.tab || 'chart';
                if (key.startsWith('c:')) {
                    const [, strategy, contract] = key.split(':');
                    this.options.onCommand('strategy_select', {
                        id: this.id, strategy, contract,
                    });
                }
                this._showTab(key);
            }
            const sort = target.closest<HTMLElement>('[data-opt-sort]');
            if (sort) {
                const key = sort.dataset.optSort || '';
                if (this.optSortKey === key) this.optSortDir *= -1;
                else { this.optSortKey = key; this.optSortDir = 1; }
                this._renderOptimization();
                return;
            }
            const row = target.closest<HTMLElement>('[data-opt-row]');
            if (row) {
                this.optSelected = Number(row.dataset.optRow || 0);
                this._highlightOptRow();
            }
            if (target.closest('[data-opt-use]')) this._useOptTrial();
            if (target.closest('[data-opt-write]')) this._writeOpt();
            if (target.closest('[data-opt-export]')) this._exportOpt();
            if (target.closest('[data-opt-chart]')) this._showOptChart();
            if (target.closest('[data-opt-table]')) this.setOptimization({ rows: this.optRows });
            const chartTab = target.closest<HTMLElement>('[data-opt-mode]');
            if (chartTab) {
                this.optChartMode = (chartTab.dataset.optMode || 'pareto') as ('pareto' | 'rank' | 'importance');
                this._renderOptChart();
            }
        });
        this.element.addEventListener('input', (event) => {
            const input = (event.target as HTMLElement)
                .closest<HTMLInputElement>('[data-opt-filter]');
            if (!input) return;
            this.optFilter = input.value;
            this._renderOptimization();
        });
        this.element.addEventListener('change', (event) => {
            const select = (event.target as HTMLElement)
                .closest<HTMLSelectElement>('[data-sl-speed]');
            if (!select) return;
            this._postFrames('replaySpeed', { speed: Number(select.value) || 1 });
        });
    }

    private _showTab(key: string): void {
        if (key === 'chart' && this.contractTabs.length) {
            key = this.contractTabs[0].key;
        }
        this.active = key;
        const contractTab = key.startsWith('c:') || key === 'chart';
        if (contractTab) {
            this.resultKey = '';
            this.chartFiles.delete('result');
        }
        this.chartFrame.style.display = contractTab ? 'block' : 'none';
        this.resultFrame.style.display = key === 'result' ? 'block' : 'none';
        for (const [name, panel] of Object.entries(this.panels)) {
            panel.style.display = name === key ? 'block' : 'none';
        }
        this.tabs.querySelectorAll<HTMLElement>('[data-tab]').forEach((node) => {
            node.classList.toggle('on', node.dataset.tab === key);
        });
        // 回放中切页签 → 让刚显示出来的图表对齐位置（还在播就继续播 ✓）
        if (this.toolState.replay) {
            this._resyncFrame(key === 'result' ? this.resultFrame
                : this.chartFrame);
        }
        this._loadChartFrame(key);
    }

    // ------------------------------------------------------------- data
    setState(patch: Record<string, any>): void {
        this.strategies = (patch.strategies || []) as StrategyRow[];
        const status = String(patch.status || '');
        this.running = status === 'running';
        if (Array.isArray(patch.target_options)) {
            this.targetOptions = patch.target_options.map(String);
        }
        if (Array.isArray(patch.targets)) {
            this.optTargets = patch.targets.map(String);
        }
        if (Array.isArray(patch.weights)) {
            this.optWeights = patch.weights.map(Number);
        }
        if (status === 'running') {
            this.frameKey = '';
            this.resultKey = '';
            this.chartFiles.clear();
            if (this.mode === 'optimize') this.optRows = [];
        }
        const labels: Record<string, string> = {
            running: '回测中…', ready: '已完成', error: '失败',
            cancelled: '已取消', idle: '准备中…',
        };
        this.status.textContent = labels[status] || status;
        this.status.className = `status ${status}`;
        const progress = this.element.querySelector('[data-progress]') as HTMLElement;
        if (progress) {
            progress.style.display = status === 'running' ? 'inline-flex' : 'none';
        }
        const selected = (patch.selected || {}) as Record<string, string>;
        this._syncContractTabs(selected);
        if (patch.error) {
            this._showError(String(patch.error));
        } else if (status === 'ready') {
            if (!this.initialReady) {
                this.initialReady = true;
                this.active = this.mode === 'optimize'
                    ? 'optimize' : (this.contractTabs[0]?.key || 'chart');
                this._buildTabs();
                this._showTab(this.active);
            } else {
                this._buildTabs();
                this._showTab(this.active);
            }
        }
        if (this.mode === 'optimize') this._renderOptimization();
    }

    private _syncContractTabs(selected: Record<string, string>): void {
        this.contractTabs = [];
        const multiStrategy = this.strategies.length > 1;
        for (const strategy of this.strategies) {
            for (const contract of strategy.contracts || []) {
                const key = `c:${strategy.name}:${contract}`;
                this.contractTabs.push({
                    key, strategy: strategy.name, contract,
                    label: multiStrategy
                        ? `${strategy.name} · ${contract}` : contract,
                });
            }
        }
        const preferred = selected.strategy && selected.contract
            ? `c:${selected.strategy}:${selected.contract}` : '';
        if (preferred && this.contractTabs.some((item) => item.key === preferred)
            && !this.initialReady) {
            this.active = preferred;
        }
        if (this.contractTabs.length
            && !this.contractTabs.some((item) => item.key === this.active)
            && !['result', 'record', 'optimize'].includes(this.active)) {
            this.active = this.contractTabs[0].key;
        }
    }

    setChart(_patch: Record<string, any>): void {
        // 图表现在由后端 MiniQT 代码生成，前端只负责切 iframe；保留接口兼容。
    }

    /** 图表 HTML 被后端重建了 → 清掉前端缓存并重新装载当前页签 ✓ */
    reloadCharts(): void {
        this.chartFiles.clear();
        this.resultKey = '';
        this._loadChartFrame(this.active === 'result' ? 'result' : this.active);
    }

    private _loadChartFrame(key: string): void {
        if (!this.initialReady) return;
        if (key === 'result') {
            const wanted = 'result';
            if (this.resultKey === wanted) return;
            this.resultKey = wanted;
            this._loadFrame(this.resultFrame, wanted);
            return;
        }
        if (!key.startsWith('c:') && key !== 'chart') return;
        const contract = this.contractTabs.find((item) => item.key === key)
            || this.contractTabs[0];
        if (!contract) return;
        if (this.frameKey === contract.key) return;
        this.frameKey = contract.key;
        this._loadFrame(this.chartFrame, contract.key);
    }

    /** Qt 壳是 file://，没有 HTTP 服务 → 用后端写好的本地 HTML 文件。 */
    private _loadFrame(frame: HTMLIFrameElement, key: string): void {
        if (!this.fileMode) {
            this._setFrameUrl(frame, this._chartUrl(key));
            return;
        }
        const cached = this.chartFiles.get(key);
        if (cached) {
            this._setFrameUrl(frame, cached);
            return;
        }
        frame.removeAttribute('src');
        frame.srcdoc = '<!doctype html><meta charset="utf-8"><body style="'
            + 'background:#111;color:#9aa4b2;font:13px sans-serif;'
            + 'display:flex;align-items:center;justify-content:center;'
            + 'height:100vh;margin:0">正在生成 MiniQT 图表…</body>';
        this.options.onCommand('strategy_chart_file', {
            id: this.id, key, theme: this.options.theme,
        });
    }

    /** 后端（Qt/file://）返回图表文件地址后装载 ✓ */
    setChartFile(patch: Record<string, any>): void {
        const key = String(patch.key || '');
        const url = String(patch.url || '');
        if (!key || !url) return;
        this.chartFiles.set(key, url);
        if (key === 'result') {
            if (this.active === 'result') this._setFrameUrl(this.resultFrame, url);
        } else if (this.active === key || this.frameKey === key) {
            this._setFrameUrl(this.chartFrame, url);
        }
    }

    private _setFrameUrl(frame: HTMLIFrameElement, url: string): void {
        // srcdoc 的优先级高于 src：不清掉就会一直停在“正在生成…”页面
        frame.removeAttribute('srcdoc');
        frame.onload = () => this._syncFrameState(frame);
        frame.src = url;
    }

    /**
     * iframe 重载（换合约 / 换主题）后把当前设置再套一次 ✓
     *
     * 回放中重载时**直接恢复播放状态**（以前只恢复位置 → 切到回测结果图
     * 就变成暂停，还得再点一次播放 ✗）
     */
    private _syncFrameState(frame: HTMLIFrameElement): void {
        const { kind, toolbox, replay, playing, bars } = this.toolState;
        this._post(frame, 'font', { size: this.fontSize });
        this._post(frame, 'crosshair', { color: this.crosshairColor });
        if (kind !== 'candle') this._post(frame, 'type', { kind });
        if (toolbox) this._post(frame, 'toolbox', { show: true });
        if (!replay) return;
        this._post(frame, 'replayStart', { bars });
        void playing;
    }

    /** 切页签：让刚显示出来的图表跟上回放位置 / 播放状态 ✓ */
    private _resyncFrame(frame: HTMLIFrameElement): void {
        if (!this.toolState.replay) return;
        this._post(frame, 'replayStart', { bars: this.toolState.bars });
        // 播放状态交给本页的时钟驱动（`replayPlay` 只用于瞬时推进）✓
        if (this.toolState.playing) {
            this._post(frame, 'replayPlay', {});
            this._startReplayClock();
        }
    }

    private _chartUrl(key: string): string {
        const query = new URLSearchParams({
            id: this.id, key, theme: this.options.theme,
        });
        const base = window.location.pathname.replace(/[^/]*$/, '');
        return `${base}strategy_chart?${query.toString()}`;
    }

    setResult(patch: ResultPayload): void {
        this.currentResult = patch || {};
        this._renderRecord();
        if (this.active === 'result') this._loadChartFrame('result');
    }

    setTrades(rows: TradeRow[]): void {
        this.trades = rows || [];
        this._renderRecord();
    }

    setError(message: string): void {
        this._showError(message);
    }

    setProgress(current: number, total: number, text = ''): void {
        const host = this.element.querySelector('[data-progress]') as HTMLElement;
        if (!host) return;
        const bar = host.querySelector('i') as HTMLElement;
        const label = host.querySelector('em') as HTMLElement;
        const percent = total > 0
            ? Math.max(0, Math.min(100, current / total * 100)) : 0;
        host.classList.toggle('indeterminate', total <= 0);
        if (bar) bar.style.width = total > 0 ? `${percent}%` : '';
        if (label) {
            label.textContent = total > 0 ? `${current}/${total}` : '';
        }
        if (text && total > 0) {
            this.status.textContent = `${text} ${current}/${total}`;
        }
    }

    private _renderRecord(): void {
        const metrics = this.currentResult.metrics || {};
        const cards = METRIC_GROUPS.flatMap(([, items]) => items).map(
            ([key, title, kind]) => `
            <div class="desk-strategy-metric-card">
                <span>${title}</span><b>${fmt(metrics[key], kind)}</b>
            </div>`).join('');
        const contracts = (this.currentResult.contracts || []).map((item) => `
            <tr><td>${esc(item.symbol)}</td><td>${item.trade_count ?? 0}</td>
                <td>${item.bars ?? 0}</td></tr>`).join('');
        const tradeRows = this.trades.map((row) => {
            const pnl = Number(row.pnl);
            const cls = !Number.isFinite(pnl) ? '' : (pnl >= 0 ? 'up' : 'down');
            return `<tr>
                <td>${timeText(row.time)}</td>
                <td>${esc(row.direction || '')}</td>
                <td>${esc(row.symbol || '')}</td>
                <td>${Number.isFinite(Number(row.price)) ? num(row.price, 3) : '--'}</td>
                <td>${Number.isFinite(Number(row.qty)) ? Math.round(Number(row.qty)) : '--'}</td>
                <td>${Number.isFinite(Number(row.fee)) ? num(row.fee, 2) : '--'}</td>
                <td class="${cls}">${Number.isFinite(pnl) ? num(pnl, 2) : '--'}</td>
            </tr>`;
        }).join('');
        this.panels.record.innerHTML = `
            <div class="desk-strategy-panel-title">回测结果
                <span>${esc(this.currentResult.strategy || '')}</span></div>
            <div class="desk-strategy-metric-cards">${cards}</div>
            <div class="desk-strategy-equity-title">权益 / 回撤
                <span>${this.currentResult.equity?.values?.length || 0} 点</span></div>
            <div class="desk-strategy-equity-wrap">${equitySvg(this.currentResult.equity)}</div>
            <div class="desk-strategy-panel-title small">分合约结果</div>
            <div class="desk-strategy-table-wrap"><table class="desk-strategy-table">
                <thead><tr><th>合约</th><th>交易记录数</th><th>K线根数</th></tr></thead>
                <tbody>${contracts || '<tr><td colspan="3">--</td></tr>'}</tbody>
            </table></div>
            <div class="desk-strategy-panel-title small">交易记录
                <span>${this.trades.length} 行</span></div>
            <div class="desk-strategy-table-wrap"><table class="desk-strategy-table">
                <thead><tr><th>时间</th><th>方向</th><th>合约</th>
                    <th>成交价</th><th>数量</th><th>手续费</th><th>盈亏</th></tr></thead>
                <tbody>${tradeRows || '<tr><td colspan="7">暂无交易</td></tr>'}</tbody>
            </table></div>`;
    }

    setOptimization(patch: Record<string, any>): void {
        const panel = this.panels.optimize;
        if (!panel) return;
        const rows = (patch.rows || []) as Array<Record<string, any>>;
        this.optRows = rows;
        this.optSelected = 0;
        this.optFilter = '';
        this.optSortKey = '';
        this.optSortDir = 1;
        this._renderOptimization();
    }

    /** 优化目标设置：最多 3 个 `OPTTargetType`（空 = 策略 op_config 默认）✓ */
    private _optSettingsHtml(): string {
        const options = this.targetOptions.length
            ? this.targetOptions : DEFAULT_OPT_TARGETS;
        const selects = [0, 1, 2].map((index) => {
            const chosen = this.optTargets[index] || '';
            const blank = index === 0 ? '' : '<option value="">（不使用）</option>';
            return `<label>目标 ${index + 1}<select data-opt-target="${index}">
                ${blank}${options.map((item) =>
                    `<option value="${esc(item)}"${
                        item === chosen ? ' selected' : ''}>${esc(item)}</option>`).join('')}
            </select></label>`;
        }).join('');
        const weights = this.optTargets.map((name, index) => {
            const weight = Number(this.optWeights[index]);
            const arrow = Number.isFinite(weight) && weight < 0 ? '↓ 最小' : '↑ 最大';
            return `<span>${esc(name)} ${arrow}</span>`;
        }).join('');
        return `<div class="desk-strategy-opt-targets">
            <div class="desk-strategy-opt-targets-title">
                <b>优化目标</b>
                <span class="desk-muted">最多 3 个 · 选项来自 OPTTargetType</span>
                ${weights ? `<span class="desk-muted">${weights}</span>` : ''}
            </div>
            <div class="desk-strategy-opt-targets-form">${selects}
                <button class="desk-strategy-exit" data-opt-restart
                    ${this.running ? 'disabled' : ''}>按当前目标重新优化</button>
                <button class="desk-strategy-exit" data-opt-target-reset
                    ${this.running ? 'disabled' : ''}>恢复策略默认</button>
            </div>
        </div>`;
    }

    private _restartOptimize(): void {
        if (this.running) return;
        const metrics = [0, 1, 2]
            .map((index) => this.panels.optimize?.querySelector<HTMLSelectElement>(
                `[data-opt-target="${index}"]`)?.value || '')
            .filter((value, index, all) => !!value && all.indexOf(value) === index)
            .slice(0, 3);
        if (!metrics.length) {
            this.options.onToast('warning', '至少选 1 个优化目标');
            return;
        }
        this.optRows = [];
        this.optTargets = metrics;
        this._renderOptimization();
        this.options.onCommand('strategy_start', {
            file: this.file, mode: 'optimize', metrics,
        });
    }

    /** 参数优化表：筛选 + 点击表头排序（文档里的「可筛选 / 排序」✓） */
    private _renderOptimization(): void {
        const panel = this.panels.optimize;
        if (!panel) return;
        const settings = this._optSettingsHtml();
        const rows = this.optRows;
        if (!rows.length) {
            panel.innerHTML = settings
                + '<div class="desk-strategy-empty">暂无参数优化结果</div>';
            return;
        }
        const columns = Object.keys(rows[0]);
        const needle = this.optFilter.trim().toLowerCase();
        let view = rows.map((row, index) => ({ row, index }));
        if (needle) {
            view = view.filter(({ row }) => columns.some((key) =>
                String(row[key] ?? '').toLowerCase().includes(needle)));
        }
        if (this.optSortKey) {
            const key = this.optSortKey;
            view = view.slice().sort((a, b) => {
                const av = a.row[key];
                const bv = b.row[key];
                const an = Number(av);
                const bn = Number(bv);
                let cmp: number;
                if (String(av ?? '').trim() !== ''
                    && String(bv ?? '').trim() !== ''
                    && Number.isFinite(an) && Number.isFinite(bn)) {
                    cmp = an - bn;
                } else {
                    cmp = String(av ?? '').localeCompare(
                        String(bv ?? ''), 'zh-CN', { numeric: true });
                }
                return cmp * this.optSortDir;
            });
        }
        const arrow = (key: string) => this.optSortKey === key
            ? (this.optSortDir > 0 ? ' ▲' : ' ▼') : '';
        panel.innerHTML = `${settings}<div class="desk-strategy-panel-title">参数优化结果
            <span>${view.length}/${rows.length} 个 trial</span></div>
            <div class="desk-strategy-opt-actions">
                <button class="desk-strategy-exit" data-opt-use>用选中回测</button>
                <button class="desk-strategy-exit" data-opt-write>写回最优参数</button>
                <button class="desk-strategy-exit" data-opt-chart>优化图表</button>
                <button class="desk-strategy-exit" data-opt-export>导出 CSV</button>
                <input class="desk-strategy-opt-filter" data-opt-filter
                    placeholder="筛选参数 / 目标…" value="${esc(this.optFilter)}">
            </div>
            <div class="desk-strategy-table-wrap"><table class="desk-strategy-table">
            <thead><tr>${columns.map((key) =>
                `<th data-opt-sort="${esc(key)}" class="sortable">${esc(key)}${arrow(key)}</th>`).join('')}</tr></thead>
            <tbody>${view.map(({ row, index }) => `<tr data-opt-row="${index}"
                class="${index === this.optSelected ? 'on' : ''}">${columns.map((key) =>
                `<td>${esc(row[key])}</td>`).join('')}</tr>`).join('')}</tbody>
            </table></div>`;
    }

    private _highlightOptRow(): void {
        this.panels.optimize?.querySelectorAll<HTMLElement>('[data-opt-row]')
            .forEach((node) => {
                node.classList.toggle('on',
                    Number(node.dataset.optRow) === this.optSelected);
            });
    }

    private _optParams(row: Record<string, any>): Record<string, any> {
        const params: Record<string, any> = {};
        for (const [key, value] of Object.entries(row || {})) {
            if (!key.startsWith('params_')) continue;
            const name = key.slice('params_'.length);
            const number = Number(value);
            params[name] = Number.isFinite(number) && String(value).trim() !== ''
                ? number : value;
        }
        return params;
    }

    private _useOptTrial(): void {
        const row = this.optRows[this.optSelected];
        if (!row) return;
        this.options.onCommand('strategy_trial_run', {
            id: this.id, params: this._optParams(row),
        });
        this._showTab('chart');
    }

    private _writeOpt(): void {
        const row = this.optRows[this.optSelected];
        if (!row) return;
        this.options.onWriteParams?.(this._optParams(row));
    }

    private _showOptChart(): void {
        if (!this.optRows.length) return;
        const panel = this.panels.optimize;
        if (!panel) return;
        panel.innerHTML = `<div class="desk-strategy-panel-title">参数优化图表
            <span>${this.optRows.length} 个 trial</span></div>
            <div class="desk-strategy-opt-actions">
                <button class="desk-strategy-exit" data-opt-table>返回表格</button>
                <button class="desk-strategy-exit" data-opt-mode="pareto">帕累托前沿</button>
                <button class="desk-strategy-exit" data-opt-mode="rank">参数排名</button>
                <button class="desk-strategy-exit" data-opt-mode="importance">参数重要性</button>
            </div>
            <div class="desk-strategy-opt-chart" data-opt-chart-host></div>`;
        this._renderOptChart();
    }

    private _renderOptChart(): void {
        const host = this.panels.optimize?.querySelector(
            '[data-opt-chart-host]') as HTMLElement;
        if (!host) return;
        this.panels.optimize?.querySelectorAll<HTMLElement>('[data-opt-mode]')
            .forEach((node) => node.classList.toggle('on',
                node.dataset.optMode === this.optChartMode));
        const rows = this.optRows;
        const valueKeys = Object.keys(rows[0] || {})
            .filter((key) => /^values_/.test(key) || key === 'value');
        if (this.optChartMode === 'pareto') {
            host.innerHTML = this._paretoSvg(rows, valueKeys);
            return;
        }
        const params = Object.keys(rows[0] || {})
            .filter((key) => /^params_/.test(key));
        // ★ 参数排名 / 参数重要性都按**参数名**展示（以前 rank 错用了
        //   `values_0` / `values_1` → 单目标时 0 个参数 ✗）
        const targetKey = valueKeys[0] || 'value';
        const target = rows.map((row) => Number(row[targetKey]));
        const finite = target.filter((value) => Number.isFinite(value));
        const mean = finite.length
            ? finite.reduce((a, b) => a + b, 0) / finite.length : 0;
        const variance = finite.length
            ? finite.reduce((a, b) => a + (b - mean) ** 2, 0) / finite.length
            : 0;
        const importance = (key: string): number => {
            const list = rows.map((row) => Number(row[key]));
            const valid = list.map((value, index) => [value, target[index]])
                .filter(([value, goal]) => Number.isFinite(value)
                    && Number.isFinite(goal));
            if (!valid.length && !variance) return 0;
            const avg = valid.length
                ? valid.reduce((a, [value]) => a + value, 0) / valid.length : 0;
            let cov = 0;
            valid.forEach(([value, goal]) => {
                cov += (value - avg) * (goal - mean);
            });
            return variance
                ? Math.abs(cov / (valid.length || 1) / Math.sqrt(variance)) : 0;
        };
        let values = params.map((key) =>
            [key, importance(key)] as [string, number]);
        if (this.optChartMode === 'rank') {
            values.sort((a, b) => b[1] - a[1]);
        }
        const max = Math.max(...values.map(([, value]) => value), 1);
        host.innerHTML = `<div class="desk-strategy-opt-chart-title">${this.optChartMode === 'rank' ? '参数排名' : '参数重要性'}
            <span>${values.length} 个参数</span></div>
            <div class="desk-strategy-opt-bars">${values.map(([key, value]) =>
                `<div class="row"><span>${esc(key)}</span>
                 <i><b style="width:${Math.max(2, Math.abs(value) / max * 100)}%"></b></i>
                 <em>${value.toFixed(4)}</em></div>`).join('')}</div>`;
    }

    /**
     * 帕累托前沿图（SVG）：**自适应宽度** + 坐标轴标签 / 刻度 + 网格虚线 ✓
     *
     * 以前固定 `width=920` 还带 `Math.min(..., 0)` → 图只占左边一块、右边一大片空白，
     * x 轴还从 0 起（数值都在 5000+ 时点全挤到右边）✗
     */
    private _paretoSvg(rows: Array<Record<string, any>>,
                       valueKeys: string[]): string {
        // ★ 单目标 CSV 只有 `value`：用 trial number → value 画优化历史；
        //   多目标才用 values_0 / values_1 画帕累托前沿 ✓
        const single = valueKeys.length < 2;
        const xKey = single ? 'number' : valueKeys[0];
        const yKey = single ? (valueKeys[0] || 'value')
            : (valueKeys[1] || valueKeys[0]);
        const points: Array<{ x: number; y: number; index: number }> = [];
        rows.forEach((row, index) => {
            let x = Number(row[xKey]);
            if (single && !Number.isFinite(x)) x = index + 1;
            const y = Number(row[yKey]);
            if (Number.isFinite(x) && Number.isFinite(y)) {
                points.push({ x, y, index });
            }
        });
        if (!points.length) {
            return '<div class="desk-strategy-empty">没有可画的 trial</div>';
        }
        const xs = points.map((point) => point.x);
        const ys = points.map((point) => point.y);
        const span = (values: number[]) => {
            const min = Math.min(...values);
            const max = Math.max(...values);
            const pad = (max - min || Math.abs(max) || 1) * 0.12;
            return [min - pad, max + pad];
        };
        const [xMin, xMax] = span(xs);
        const [yMin, yMax] = span(ys);
        // 自适应：跟随容器宽度（最大 1600），高度按比例 ✓
        const hostWidth = this.panels.optimize?.clientWidth || 1200;
        const width = Math.max(420, Math.min(1600, hostWidth - 60));
        const height = Math.max(240, Math.min(420, Math.round(width * 0.34)));
        const left = 74;
        const right = 22;
        const top = 18;
        const bottom = 46;
        const plotW = width - left - right;
        const plotH = height - top - bottom;
        const xAt = (value: number) =>
            left + (value - xMin) / (xMax - xMin || 1) * plotW;
        const yAt = (value: number) =>
            top + (yMax - value) / (yMax - yMin || 1) * plotH;
        const tick = (value: number) => {
            const abs = Math.abs(value);
            if (abs >= 10000) return value.toFixed(0);
            if (abs >= 100) return value.toFixed(1);
            if (abs >= 1) return value.toFixed(2);
            return value.toFixed(4);
        };
        const ticks = [0, 1, 2, 3, 4];
        const grid = ticks.map((index) => {
            const ratio = index / 4;
            const y = top + plotH * ratio;
            const x = left + plotW * ratio;
            return `<line x1="${left}" y1="${y.toFixed(1)}"
                    x2="${(width - right).toFixed(1)}" y2="${y.toFixed(1)}"
                    stroke="var(--desk-border)" stroke-dasharray="4 4"
                    stroke-width="1" opacity=".75"/>
                <text x="${(left - 8).toFixed(1)}" y="${(y + 3.5).toFixed(1)}"
                    text-anchor="end" class="desk-opt-tick"
                >${tick(yMax - (yMax - yMin) * ratio)}</text>
                <line x1="${x.toFixed(1)}" y1="${top}"
                    x2="${x.toFixed(1)}" y2="${(top + plotH).toFixed(1)}"
                    stroke="var(--desk-border)" stroke-dasharray="4 4"
                    stroke-width="1" opacity=".55"/>
                <text x="${x.toFixed(1)}" y="${(top + plotH + 16).toFixed(1)}"
                    text-anchor="middle" class="desk-opt-tick"
                >${tick(xMin + (xMax - xMin) * ratio)}</text>`;
        }).join('');
        // 帕累托前沿：按 x 升序把「不被支配」的点连起来 ✓
        const sorted = [...points].sort((a, b) => a.x - b.x);
        const front: typeof sorted = [];
        let best = -Infinity;
        for (const point of sorted) {
            if (point.y > best) {
                front.push(point);
                best = point.y;
            }
        }
        const frontPoints = front.map((point) =>
            `${xAt(point.x).toFixed(1)},${yAt(point.y).toFixed(1)}`).join(' ');
        const frontLine = front.length > 1
            ? `<polyline fill="none" stroke="#ef5350" stroke-width="1.6"`
                + ` opacity=".85" points="${frontPoints}"/>`
            : '';
        const bestPoint = points.reduce(
            (a, b) => (b.y > a.y ? b : a), points[0]);
        const dots = points.map((point) => {
            const best = point === bestPoint;
            return `<circle cx="${xAt(point.x).toFixed(1)}"
                cy="${yAt(point.y).toFixed(1)}" r="${best ? 5 : 3.4}"
                fill="${best ? '#ef5350' : '#2196f3'}"
                opacity="${best ? 1 : .8}">
                <title>Trial ${point.index + 1} · ${esc(rows[point.index][xKey])} / ${esc(rows[point.index][yKey])}</title>
            </circle>`;
        }).join('');
        return `<div class="desk-strategy-opt-chart-title">Pareto-front Plot
            <span>${esc(xKey)}（X） × ${esc(yKey)}（Y）· ${points.length} trials</span></div>
            <svg class="desk-strategy-opt-svg" viewBox="0 0 ${width} ${height}"
                preserveAspectRatio="xMidYMid meet">
            ${grid}
            <line x1="${left}" y1="${(top + plotH).toFixed(1)}"
                x2="${(width - right).toFixed(1)}" y2="${(top + plotH).toFixed(1)}"
                stroke="var(--desk-muted)" stroke-width="1"/>
            <line x1="${left}" y1="${top}" x2="${left}"
                y2="${(top + plotH).toFixed(1)}"
                stroke="var(--desk-muted)" stroke-width="1"/>
            ${frontLine}${dots}
            <text x="${(left + plotW / 2).toFixed(1)}"
                y="${(height - 8).toFixed(1)}" text-anchor="middle"
                class="desk-opt-label">${esc(xKey)}</text>
            <text x="14" y="${(top + plotH / 2).toFixed(1)}" text-anchor="middle"
                class="desk-opt-label"
                transform="rotate(-90 14 ${(top + plotH / 2).toFixed(1)})"
            >${esc(yKey)}</text>
            </svg>`;
    }

    private _exportOpt(): void {
        if (!this.optRows.length) return;
        const columns = Object.keys(this.optRows[0]);
        const lines = [columns.join(',')].concat(this.optRows.map((row) =>
            columns.map((key) => `"${String(row[key] ?? '').replace(/"/g, '""')}"`).join(',')));
        const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'optimization_trials.csv';
        link.click();
        URL.revokeObjectURL(link.href);
    }

    private _showError(message: string): void {
        const html = `<div class="desk-strategy-error"><b>回测失败</b><p>${esc(message)}</p></div>`;
        this.panels.record.innerHTML = html;
        if (this.panels.optimize) this.panels.optimize.innerHTML = html;
        this._showTab('record');
    }


}

/**
 * IndicatorLayer — 7 个常用指标（MA/EMA/BOLL/MACD/KDJ/RSI）。
 *
 * 主图指标（overlay）→ 直接往蜡烛图上加 Line 序列；
 * 副图指标（MACD/KDJ/RSI）→ 图下方**各开一个小 LWC 图**（简单可靠，不依赖
 * lightweight-charts 的 pane API）。
 */
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
// 图例图标（齿轮 / 眼睛）和 miniqt 共用同一套 SVG ✓
import { GEAR } from '../general/legend';
// `bandstyle`（两条线之间填充）用 pylightcharts 自己的 LineFill 原语 ✓
import { LineFill } from '../line-fill/line-fill';
import type { IndicatorStyleState } from './indicator-settings';

export interface IndicatorLine {
    key: string;
    label: string;
    overlay: boolean;
    /** `candles` = 蜡烛型指标（OHLC 四列，`candlestyle` 配色 ✓） */
    kind: 'line' | 'hist' | 'candles' | 'marker' | 'vp'
        | 'band' | 'table' | 'span'
        | 'watermark';
    color: string;
    /** 来自 `PlotInfo.linestyle[name]`（线宽 / 线型 ✓） */
    lineWidth?: number;
    /** Lightweight Charts 的 `LineStyle`：0 实线 / 1 点 / 2 虚 / 3 长虚 */
    lineStyle?: number;
    /** `line_dash='vbar'` 的柱状：基准价 + 涨跌配色 ✓ */
    base?: number;
    upColor?: string;
    downColor?: string;
    /** `bandstyle`：填充的两条线（item.key ✓） */
    lowerKey?: string;
    upperKey?: string;
    /** `LineStyle.price_line` / `price_label`：右侧价格线 / 价格标签 ✓ */
    priceLine?: boolean;
    priceLabel?: boolean;
    /** 十字线标记（设置菜单「坐标轴」✓） */
    crosshairMarker?: boolean;
    /**
     * ★ 指标线是否可见（`false` = 被图例眼睛 / 设置里的「显示该指标」
     *   隐藏）——**只影响指标线**，指标标签/图例行一直在 ✓
     */
    visible?: boolean;
    /** `PlotInfo.legend=False`：不显示图例行（线照画 ✓） */
    legend?: boolean;
    /** `spanstyle`：水平参考线（数值 + 颜色 + 线型 ✓） */
    spans?: Array<{
        price: number;
        color?: string;
        lineStyle?: number;
        lineWidth?: number;
    }>;
    /** `watermark`：图表大水印（`fontSize` 来自 `WaterMark.font_size` ✓） */
    fontSize?: number;
    /** `tablestyle`：表格内容 / 位置（top-right …）✓ */
    position?: string;
    headings?: string[];
    rows?: string[][];
    /** `PlotInfo` 里的线名（色带按名字找线 ✓） */
    seriesName?: string;
    /** 信号箭头（`kind: 'marker'` 时用 ✓） */
    markers?: Array<{
        time: number;
        position?: 'aboveBar' | 'belowBar' | 'inBar';
        shape?: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
        color?: string;
        text?: string;
        price?: number;
    }>;
    pane?: string;
    data: Array<[number, number | null]>;
    /** 该指标的可调参数（图例 ⚙ 编辑用 ✓） */
    params?: Record<string, unknown>;
    /** 目录里的原始 key（编辑后用 `add_indicator` 重新加 ✓） */
    source?: string;
}

export interface IndicatorPayload {
    type: 'indicator';
    symbol: string;
    items?: IndicatorLine[];
    /** 完整库指标还在后台算（只为 builtin）→ 前端**只加不删** ✓ */
    pending?: boolean;
    /** `last` = 只更新每个指标最后一个点（同根 K 线增量）✓ */
    mode?: 'last';
    /** 第几格（多布局；0 = 主图 ✓） */
    cell?: number;
    /** 只替换策略线（保留该格原有指标）✓ */
    strategyOnly?: boolean;
    /** 策略名（图例显示 ✓） */
    strategy?: string;
}

/** 缺口色：透明（LWC 按**线段起点**的颜色决定这段画不画 ✓） */
export const GAP_COLOR = 'rgba(0,0,0,0)';

/**
 * 指标行 `[time, value]` → LWC 折线数据：**裁首尾空点 + 中间缺口补透明点**。
 *
 * LWC v5 的 whitespace 只延长时间轴、并不会断开折线；所以用「缺口点补前值 +
 * 该点颜色透明」让引擎在缺口起点就不画线段，视觉上等价于断线，但始终只有一条
 * 序列（不会复制指标线 / 增加价格标签）✓。
 *
 * * **首尾空点必须裁掉**：策略只回放了一段时，前面成千上万个 NaN 会变成同样
 *   多的透明点，整条线会画不出来（副图 / 图例都在，就是没线 ✗）；
 * * **中间缺口一个都不能丢**：以前空点比例 > 20% 就“整段丢掉空点、用普通数据
 *   画”，于是 `Chandelier_Exit` / `SuperTrend_STRATEGY` 这类「一半 up 一半 dn」
 *   的线（缺口在中间、占一半）会被一条直线从缺口上连过去（用户实测 ✗）。
 */
export function gapLineData(
    rows: Array<[number, number | null | undefined]>,
    color?: string,
): Array<{ time: never; value: number; color?: string }> {
    const finite = (value: number | null | undefined): boolean =>
        value !== null && value !== undefined && Number.isFinite(Number(value));
    let start = 0;
    let end = rows.length;
    while (start < end && !finite(rows[start]?.[1])) start += 1;
    while (end > start && !finite(rows[end - 1]?.[1])) end -= 1;
    if (start >= end) return [];
    let last = Number(rows[start]?.[1]);
    const out: Array<{ time: never; value: number; color?: string }> = [];
    for (let index = start; index < end; index += 1) {
        const row = rows[index];
        const time = Number(row?.[0]) as never;
        if (!finite(row?.[1])) {
            out.push({ time, value: last, color: GAP_COLOR });
            continue;
        }
        last = Number(row?.[1]);
        // ⚠ **有效点不要逐点设色**：LWC 会拿逐点颜色覆盖序列的 `color`，
        //   于是设置卡里改的颜色永远不生效（用户实测：选颜色没反应 ✗）。
        //   缺口点仍然用透明色（引擎按**线段起点颜色**决定画不画）✓
        void color;
        out.push({ time, value: last });
    }
    return out;
}

interface PaneHandle {
    /** 在 `chart.panes()` 里的下标（0 = 主图 ✓） */
    index: number;
    series: Map<string, ISeriesApi<'Line' | 'Histogram'>>;
    height?: number;
}

export class IndicatorLayer {
    private readonly panes = new Map<string, PaneHandle>();
    /** 当前这一份 items 里**还有可见线**的副图（paneKey）✓ */
    private paneVisible = new Set<string>();
    private readonly overlaySeries = new Map<string, ISeriesApi<'Line'>>();
    private lastItems: IndicatorLine[] = [];
    /** 每个线条上一次的「显示区域」（主图 true / 副图 false ✓） */
    private readonly overlayState = new Map<string, boolean>();
    /** 信号箭头的载体序列 / markers 原语 ✓ */
    private readonly markerSeries = new Map<string, ISeriesApi<'Line'>>();
    private readonly markerPrimitive = new Map<string, { setMarkers: (m: unknown[]) => void }>();
    /** 交易信号的自定义序列（`kind: 'shapes'`）✓ */
    private readonly shapeSeries = new Map<string, unknown>();
    /** 当前格的 K 线（由页面 `setBars()` 同步；保留给其它指标 ✓） */
    private bars: Array<{ time: number }> = [];
    protected readonly barsRef = () => this.bars;
    /** 蜡烛型指标的序列（**主图/副图**都可能；删除走 `chart.removeSeries` ✓） */
    private readonly candleSeries = new Map<string, {
        series: ISeriesApi<'Line'>; pane: number;
    }>();

    /** `bandstyle` 填充：key → 挂在上面那条线上的原语 ✓ */
    private readonly bands = new Map<string, { upper: unknown;
        fill: unknown }>();
    /** 拖动过的表格位置（key → 相对图表左上角的像素 ✓） */
    private readonly tableOffsets = new Map<string, { x: number; y: number }>();
    /** `watermark` 水印节点：key → 元素 ✓ */
    private readonly watermarks = new Map<string, HTMLDivElement>();
    /** `spanstyle` 水平参考线：key → 已画的线（重画前先删 ✓） */
    private readonly spans = new Map<string, Array<{
        series: { removePriceLine?: (line: unknown) => void };
        handle: unknown;
    }>>();
    /** `tablestyle`：key → 覆盖在图上的小表格 ✓ */
    private readonly tables = new Map<string, HTMLDivElement>();

    /** 图例行（pylightcharts `Legend`，自带眼睛 SVG ✓） */
    private readonly legendRows = new Map<string, {
        row: HTMLDivElement; gear: HTMLButtonElement; series: unknown;
    }>();

    /** ⚙ 打开设置菜单（由 ChartPage 提供 ✓） */
    onSettings: ((item: IndicatorLine, anchor: HTMLElement) => void) | null
        = null;
    /** 原生图例眼睛 → 页面的 toggleIndicator（VP 画布也要跟着隐藏 ✓） */
    onToggle: ((item: IndicatorLine) => void) | null = null;

    /** ★ 图例设置里改过的样式（后端每次全量推送时重新套上去 ✓） */
    private readonly styleOverrides = new Map<string, Partial<IndicatorStyleState>>();

    constructor(
        private readonly hostElement: HTMLDivElement,
        private readonly getMainChart: () => IChartApi | null,
        private readonly theme: () => {
            background: string; text: string; up?: string; down?: string;
        },
        /** 该格主图的 `handler.legend`（pylightcharts 原生图例 ✓） */
        private readonly getLegend: () => {
            makeSeriesRow?: Function;
            _lines?: Array<{ row?: HTMLDivElement; series?: unknown }>;
        } | null = () => null,
        /** pylightcharts `Handler`（自定义序列：交易信号箭头 ✓） */
        private readonly getHandler: () => {
            createCustomSeries?: Function;
        } | null = () => null,
    ) {
        // 副图不再需要自己的 DOM 容器（pane 在主图里 ✓），这里只留个引用
        this.element = this.hostElement;
    }

    /** 面板宿主（旧副图容器；现在只做调试引用 ✓） */
    private readonly element: HTMLDivElement;

    /** 每条线的**最后一个有效值**：增量推空点时用它补「前值 + 透明色」✓ */
    private readonly lastValues = new Map<string, number>();

    /** 线 / 柱的 `setData` 数据（统一处理 NaN 缺口，见 {@link gapLineData} ✓） */
    private _lineDataFor(item: IndicatorLine, color?: string):
        Array<{ time: never; value: number; color?: string }> {
        return gapLineData(item.data || [], color);
    }

    /** 增量更新：同一根 K 线内后端只推最后一个点 ✓ */
    applyLast(payload: IndicatorPayload): void {
        for (const item of payload.items || []) {
            const rows = item.data || [];
            const known = this.lastItems.find((entry) => entry.key === item.key);
            if (known && rows.length) {
                const data = known.data || (known.data = []);
                // 新 K 线 / 断线补齐时 rows 可能 >1，必须全部合并 ✓
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
            if (!rows.length) continue;
            for (const last of rows as unknown as Array<
                [number, number | number[]]>) {
                const time = Number(last?.[0]);
                if (!Number.isFinite(time)) continue;
                if (item.kind === 'candles') {
                    const ohlc = (last[1] as number[]) || [];
                    if (ohlc.length < 4 || !Number.isFinite(Number(ohlc[3]))) {
                        continue;
                    }
                    const entry = this.candleSeries.get(item.key);
                    const series = entry?.series as unknown as {
                        update?: (row: unknown) => void;
                    } | undefined;
                    series?.update?.({
                        time: time as never,
                        open: Number(ohlc[0]),
                        high: Number(ohlc[1]),
                        low: Number(ohlc[2]),
                        close: Number(ohlc[3]),
                    });
                    continue;
                }
                // 线 / 柱：逐根 update（同根 1 根；新 K 线至少 2 根）
                const raw = last[1];
                const series = this._seriesOf(item.key) as unknown as {
                    update?: (row: unknown) => void;
                } | null;
                if (!series?.update) continue;
                const value = Number(raw);
                if (raw === null || raw === undefined
                    || !Number.isFinite(value)) {
                    // ★ 空点也要 update：补一个「前值 + 透明色」的缺口点。
                    //   以前这里直接 `continue`，下一根有效点会从**上一个有效点**
                    //   直接连过来（缺口两侧被一条直线连上 ✗，Chandelier_Exit 实测）：
                    //   LWC 的 `update()` 同样按**线段起点颜色**决定画不画，所以缺口点
                    //   必须是透明的，且必须真的写进序列数据里 ✓
                    const previous = this.lastValues.get(item.key);
                    if (previous !== undefined) {
                        series.update({
                            time: time as never, value: previous,
                            color: GAP_COLOR,
                        });
                    }
                    continue;
                }
                this.lastValues.set(item.key, value);
                const point: Record<string, unknown> = {
                    time: time as never, value,
                };
                if (item.kind === 'hist') {
                    point.color = value >= (Number(item.base) || 0)
                        ? (item.upColor || this.theme().up || item.color)
                        : (item.downColor || this.theme().down || item.color);
                }
                series.update(point);
            }
        }
    }

    /**
     * 全量数据只在**历史没变**时改成 `update(last)`。
     *
     * 后端每秒会重推整套线；如果每次都 `setData`，挂在序列上的 `LineFill`
     * 色带会跟着整段重绘，实时图上看起来一闪一闪。比较前面的点，只有最后
     * 一根变化时走 `update()`，色带保持连续 ✓
     */
    private _setSeriesData(series: {
        data?: () => unknown[];
        setData?: (rows: unknown[]) => void;
        update?: (row: unknown) => void;
    }, data: unknown[]): void {
        const current = (typeof series.data === 'function'
            ? series.data() : []) as Array<Record<string, unknown>>;
        if (current.length && current.length === data.length
            && typeof series.update === 'function') {
            let samePrefix = true;
            for (let index = 0; index < data.length - 1; index += 1) {
                const oldPoint = current[index] || {};
                const newPoint = (data[index] || {}) as Record<string, unknown>;
                if (oldPoint.time !== newPoint.time
                    || oldPoint.value !== newPoint.value) {
                    samePrefix = false;
                    break;
                }
            }
            if (samePrefix) {
                const oldLast = current[current.length - 1] || {};
                const newLast = (data[data.length - 1] || {}) as
                    Record<string, unknown>;
                const sameLast = oldLast.time === newLast.time
                    && oldLast.value === newLast.value
                    && oldLast.color === newLast.color;
                if (!sameLast) series.update(newLast);
                return;
            }
        }
        series.setData?.(data);
    }

    /** 全量替换（后端每次推整套线 ✓） */
    apply(payload: IndicatorPayload): void {
        const items = payload.items || [];
        // ★ 先把用户隐藏 / 颜色等覆盖套上，再判断副图是否有可见线
        //   （后端每秒全量推送的 item 默认 visible=true，不能提前判断 ✗）
        for (const item of items) this._applyStyleOverride(item);
        // ★ 副图显示条件：该 pane 里至少有一条**可见**的指标线
        this.paneVisible = new Set();
        for (const item of items) {
            if (item.overlay) continue;
            if (item.visible === false) continue;
            this.paneVisible.add(item.pane || item.key);
        }
        // 后台还在算（custom 指标）→ 这一拍**不要删**已有的副图/序列，
        // 否则“删了又加”会让副图无限增长（用户实测 ✗）
        const keepMissing = !!payload.pending;
        this.lastItems = items;
        void this.element;                 // 保留宿主引用（调试用 ✓）
        const overlayKeys = new Set(items.filter((item) => item.overlay)
            .map((item) => item.key));
        // ★ 显示区域变了（主图 ↔ 副图）→ 先把旧序列拆掉，下面重建 ✓
        for (const item of items) {
            const before = this.overlayState.get(item.key);
            if (before !== undefined && before !== item.overlay) {
                if (before) {
                    const series = this.overlaySeries.get(item.key);
                    if (series) {
                        try {
                            this.getMainChart()?.removeSeries(series);
                        } catch { /* ignore */ }
                        this.overlaySeries.delete(item.key);
                    }
                } else {
                    const paneKey = item.pane || item.key;
                    const handle = this.panes.get(paneKey);
                    const series = handle?.series.get(item.key);
                    if (series && handle) {
                        try {
                            this.getMainChart()?.removeSeries(series as never);
                        } catch { /* ignore */ }
                        handle.series.delete(item.key);
                    }
                }
                this._dropLegendRow(item.key);
            }
            this.overlayState.set(item.key, !!item.overlay);
        }
        const paneKeys = new Set(items.filter((item) => !item.overlay)
            .map((item) => item.pane || item.key));

        // ★ `pending`（完整库还在后台算）→ 跳过下面所有“删除”逻辑，
        //   只把已有的线更新一遍，避免每秒“删了又加”导致副图疯长 ✗
        if (!keepMissing) {
        // 删掉不再需要的（主图 + 副图）
        for (const [key, series] of this.overlaySeries) {
            if (!overlayKeys.has(key)) {
                try {
                    this.getMainChart()?.removeSeries(series);
                } catch { /* ignore */ }
                this.overlaySeries.delete(key);
                this._dropLegendRow(key);
            }
        }
        const aliveKeys = new Set(items.map((item) => item.key));
        for (const key of [...this.legendRows.keys()]) {
            if (!aliveKeys.has(key)) this._dropLegendRow(key);
        }
        for (const [key, entry] of [...this.candleSeries]) {
            if (aliveKeys.has(key)) continue;
            try {
                this.getMainChart()?.removeSeries(entry.series as never);
            } catch { /* ignore */ }
            this.candleSeries.delete(key);
        }
        for (const [key, entry] of [...this.shapeSeries]) {
            if (aliveKeys.has(key)) continue;
            try {
                const handler = this.getHandler?.() as unknown as {
                    removeSeries?: Function } | null;
                if (handler?.removeSeries) {
                    handler.removeSeries(entry as never);
                } else {
                    const series = (entry as { series?: unknown }).series
                        || entry;
                    this.getMainChart()?.removeSeries(series as never);
                }
            } catch { /* ignore */ }
            this.shapeSeries.delete(key);
        }
        for (const [key, series] of [...this.markerSeries]) {
            if (aliveKeys.has(key)) continue;
            try {
                this.getMainChart()?.removeSeries(series);
            } catch { /* ignore */ }
            this.markerSeries.delete(key);
            this.markerPrimitive.delete(key);
        }
        // 删掉不再需要的副图：先删序列，再 `removePane(index)`（从大到小，
        // 否则下标会串位 ✓），最后修正剩下的 handle.index
        const dropped: Array<{ pane: string; index: number }> = [];
        for (const [pane, handle] of this.panes) {
            if (paneKeys.has(pane)) continue;
            for (const series of handle.series.values()) {
                try {
                    this.getMainChart()?.removeSeries(series);
                } catch { /* ignore */ }
            }
            handle.series.clear();
            dropped.push({ pane, index: handle.index });
            this.panes.delete(pane);
        }
        dropped.sort((a, b) => b.index - a.index);
        for (const { index } of dropped) {
            try {
                (this.getMainChart() as unknown as {
                    removePane?: (i: number) => void;
                })?.removePane?.(index);
            } catch { /* ignore */ }
            // 被删 pane 之后的副图整体上移一位 ✓
            for (const handle of this.panes.values()) {
                if (handle.index > index) handle.index -= 1;
            }
        }
        }   // ← end of `if (!keepMissing)`

        void this.theme;
        // ★ 色带必须等**两条线都建好**后再挂 LineFill：
        //   以前在循环前调用 `_applyBands()`，此时 `_seriesOf(lowerKey)`
        //   还是 null → ScalpingPullBackTool 的 pacU/pacL 灰色带永远不显示 ✗。
        for (const item of items) {
            if (item.kind === 'band' || item.kind === 'table'
                || item.kind === 'span' || item.kind === 'watermark') continue;
            const lineData = this._lineDataFor(item, item.color);
            // 记住最后一个有效值：实时增量推空点时用它补缺口点 ✓
            const tail = lineData[lineData.length - 1];
            if (tail && Number.isFinite(tail.value)) {
                this.lastValues.set(item.key, tail.value);
            } else {
                this.lastValues.delete(item.key);
            }
            // ★ 信号箭头：不需要线条数据，只要一个「载体序列」挂 markers ✓
            // ★ 信号箭头：有 `rows` 且拿到 Handler → 用**自定义序列**
            //   （原生 marker 不计入缩放、回放截不掉 ✗）
            const rows = (item as unknown as { shapeRows?: unknown[] }).shapeRows || [];
            if (item.kind === 'marker' && rows.length
                && this._applyShapeRows(item, rows)) {
                continue;
            }
            if (item.kind === 'marker') {
                if (!item.overlay && !this.paneVisible.has(
                        item.pane || item.key)) continue;
                this._applyMarkers(item);
                continue;
            }
            // ★ 蜡烛型指标**自己管理序列**（主图叠加 / 副图都支持）：
            //   以前的 overlay 分支固定建 LineSeries → 蜡烛叠主图什么也看不到 ✗
            if (item.kind === 'candles') {
                if (!item.overlay && !this.paneVisible.has(
                        item.pane || item.key)) continue;
                this._applyCandleSeries(item);
                continue;
            }
            // ★ 成交量分布：**改由 `vp-overlay.ts` 的 canvas 层绘制** ✓
            //   （custom series 的锚点只能挂在真实 K 线上 → 永远贴最后一根 ✗）
            if (item.kind === 'vp') {
                // ★ canvas 层绘制；但**图例行**仍要建（左上角要有指标名 ✓）
                this._syncLegendRow(item, this._vpAnchorSeries());
                continue;
            }
            if (!lineData.length) continue;
            if (item.overlay) {
                let series = this.overlaySeries.get(item.key);
                const chart = this.getMainChart();
                if (!chart) continue;
                if (!series) {
                    series = chart.addSeries(
                        (window as never as {
                            LightweightCharts: { LineSeries: never },
                        }).LightweightCharts.LineSeries as never,
                        {
                            color: item.color,
                            // ★ 线宽 / 线型来自 `PlotInfo.linestyle`（副图早就用了，
                            //   主图以前写死 1 + 实线 → 虚线和线宽全丢 ✗）
                            lineWidth: Math.min(4, Math.max(1,
                                Number(item.lineWidth) || 1)),
                            lineStyle: Number(item.lineStyle) || 0,
                            // `LineStyle.price_line/price_label`（minibt 默认开 ✓）
                            priceLineVisible: item.priceLine !== false,
                            lastValueVisible: item.priceLabel !== false,
                            crosshairMarkerVisible: item.crosshairMarker !== false,
                            // ★ 被「显示该指标 / 眼睛」隐藏过的线：重建后仍是隐藏 ✓
                            visible: item.visible !== false,
                        } as never,
                    ) as unknown as ISeriesApi<'Line'>;
                    this.overlaySeries.set(item.key, series);
                }
                // 同一指标重加（换参数 / 主题）时线宽线型也要刷新 ✓
                (series as unknown as { applyOptions?: Function })
                    .applyOptions?.({
                        color: item.color,
                        lineWidth: Math.min(4, Math.max(1,
                            Number(item.lineWidth) || 1)),
                        lineStyle: Number(item.lineStyle) || 0,
                        visible: item.visible !== false,
                    });
                this._setSeriesData(series as never, lineData as never);
                this._syncLegendRow(item, series);
                continue;
            }
            // ★ 一个指标一个副图：`pane` 相同就复用（没有 pane 才退回 key ✓）
            const paneKey = item.pane || item.key;
            // 这个副图的线**全部隐藏** → 不建副图（标签 / 眼睛仍保留 ✓）
            if (!this.paneVisible.has(paneKey)) continue;
            let handle = this.panes.get(paneKey);
            if (!handle) {
                handle = this._addPane();
                this.panes.set(paneKey, handle);
            }
            let series = handle.series.get(item.key);
            if (!series) {
                series = this._addSeriesToPane(handle, item);
                handle.series.set(item.key, series);
            } else {
                // ★ 设置卡改过的样式（颜色 / 线宽 / 线型）在后端每次全量
                //   推送后都要重新套上：以前只有「建序列那一次」用 item.color，
                //   副图序列重建 / 改参数后就回到默认色（用户实测：颜色不生效 ✗）
                (series as unknown as { applyOptions?: Function })
                    .applyOptions?.({
                        color: item.color,
                        lineWidth: Math.min(4, Math.max(1,
                            Number(item.lineWidth) || 1)),
                        lineStyle: Number(item.lineStyle) || 0,
                        priceLineVisible: item.priceLine !== false,
                        lastValueVisible: item.priceLabel !== false,
                        crosshairMarkerVisible: item.crosshairMarker !== false,
                        // ★ 隐藏状态要跟着走，否则副图线“自己又出来” ✗
                        visible: item.visible !== false,
                    } as never);
            }
            // 柱状（`line_dash='vbar'`）：基准价上下颜色不同（MACD 柱 ✓）
            const histData = item.kind === 'hist'
                ? lineData.map((point) => (point.color
                    ? point          // 缺口点：保留透明色（否则缺口里冒出平值柱子 ✗）
                    : {
                        ...point,
                        // 涨/跌两色：指标自己配了就用它，否则跟主题 ✓
                        color: point.value >= (Number(item.base) || 0)
                            ? (item.upColor || this.theme().up || item.color)
                            : (item.downColor || this.theme().down || item.color),
                    }))
                : lineData;
            this._setSeriesData(
                series as never,
                (item.kind === 'hist' ? histData : lineData) as never);
            this._syncLegendRow(item, series);
        }
        // ★ 线都建好后再挂色带（此时 upper/lower series 才存在 ✓）
        this._applyBands(items);
        // ★ 表格 / 参考线最后画：
        //   * 表格要让开图例行 → 得等 `legendRows` 建好；
        //   * 参考线要挂到**对应 pane** 的序列上 → 得等副图序列建好 ✓
        this._applyTables(items);
        this._applySpans(items);
        this._applyWatermarks(items);
        // ★ 最后一个可见线被眼睛 / 设置关掉 → 立刻收起空副图
        //   （`pending` 时后端只是暂时没算完，不能误删副图 ✓）
        if (!keepMissing) this._syncPaneVisibility();
    }

    /** 副图里没有可见线了 → `removePane`（标签 / 眼睛状态仍保留 ✓） */
    private _syncPaneVisibility(): void {
        for (const [paneKey, handle] of [...this.panes]) {
            if (this.paneVisible.has(paneKey)) continue;
            this._removePane(paneKey, handle);
        }
    }

    private _removePane(paneKey: string, handle: PaneHandle): void {
        const chart = this.getMainChart();
        for (const series of handle.series.values()) {
            try {
                chart?.removeSeries(series);
            } catch { /* ignore */ }
        }
        handle.series.clear();
        try {
            (chart as unknown as {
                removePane?: (index: number) => void;
            })?.removePane?.(handle.index);
        } catch { /* ignore */ }
        this.panes.delete(paneKey);
        for (const other of this.panes.values()) {
            if (other.index > handle.index) other.index -= 1;
        }
    }

    /**
     * 交易信号 → **自定义序列**（`custom-series` 的 `marker` 图形 ✓）
     *
     * 返回 false 表示环境不支持（没有 handler）→ 调用方退回原生 marker。
     */
    private _applyShapeRows(item: IndicatorLine, rows: unknown[]): boolean {
        const handler = this.getHandler?.();
        if (!handler || typeof handler.createCustomSeries !== 'function') {
            return false;
        }
        let entry = this.shapeSeries.get(item.key);
        if (!entry) {
            const handle = `shape${Math.round(Math.random() * 1e9)}`;
            const paneIndex = item.overlay ? 0 : this._markerPaneIndex(item);
            try {
                // ⚠ `createCustomSeries()` 返回的是 **wrapper**
                //   `{name, series, priceScale, paneView}`，不是系列本身 →
                //   数据要 `wrapper.series.setData()`（以前直接 `setData` 失败，
                //   于是静默退回原生 marker ✗）
                entry = handler.createCustomSeries(
                    item.label || item.key, {}, handle, paneIndex) as never;
            } catch (error) {
                console.error('[desk] 信号自定义序列创建失败', error);
                return false;
            }
            if (!entry) return false;
            this.shapeSeries.set(item.key, entry);
        }
        try {
            const wrapper = entry as unknown as {
                series?: { setData?: (rows: unknown[]) => void;
                           applyOptions?: Function };
                setData?: (rows: unknown[]) => void;
            };
            const series = wrapper.series || wrapper;
            const setter = (series as { setData?: (rows: unknown[]) => void })
                .setData || wrapper.setData;
            if (!setter) return false;
            setter.call(series, rows);
            (series as { applyOptions?: Function }).applyOptions?.({
                color: item.color || '#26a69a',
            });
        } catch (error) {
            console.error('[desk] 信号自定义序列写数据失败', error);
            return false;
        }
        return true;
    }

    /**
     * 成交量分布（`kind='vp'`）：横条贴**可视范围右边缘** ✓
     *
     * 自定义序列的数据点是按 `time` 定位的，所以每次可视范围变化都要把
     * `time` 改成"可视范围最后一根"再 `setData`（拖动/缩放/主题都跟着走）。
     */
    /**
     * 蜡烛型指标（`kind='candles'`）：**主图叠加 / 副图**都能画 ✓
     */
    private _applyCandleSeries(item: IndicatorLine): void {
        const chart = this.getMainChart();
        if (!chart) return;
        const rows = (item.data || []).map((row) => {
            const value = row as unknown as { 0?: number; 1?: number[] } |
                [number, number[]];
            const time = Number((value as unknown as { 0: number })[0]);
            const ohlc = (value as unknown as { 1: number[] })[1] || [];
            return {
                time: time as never,
                open: Number(ohlc[0]),
                high: Number(ohlc[1]),
                low: Number(ohlc[2]),
                close: Number(ohlc[3]),
            };
        }).filter((row) => Number.isFinite(row.open));
        if (!rows.length) return;
        const lwc = (window as unknown as {
            LightweightCharts?: { CandlestickSeries?: never };
        }).LightweightCharts;
        const options = {
            upColor: item.upColor || this.theme().up || '#26a69a',
            downColor: item.downColor || this.theme().down || '#ef5350',
            borderVisible: false,
            wickUpColor: item.upColor || this.theme().up || '#26a69a',
            wickDownColor: item.downColor || this.theme().down || '#ef5350',
            priceLineVisible: false,
            lastValueVisible: item.priceLabel === true,
            // ★ 眼睛 / 「显示该指标」隐藏后重建也要保持隐藏 ✓
            visible: item.visible !== false,
        } as never;
        const paneIndex = item.overlay ? 0 : this._markerPaneIndex(item);
        let entry = this.candleSeries.get(item.key);
        let series = entry?.series as unknown as {
            setData?: (rows: unknown[]) => void;
            applyOptions?: Function;
        } | undefined;
        if (!entry || entry.pane !== paneIndex) {
            if (entry) {
                try { chart.removeSeries(entry.series as never); } catch { /* ignore */ }
                this.candleSeries.delete(item.key);
            }
            let created: ISeriesApi<'Line'> | null = null;
            try {
                created = (chart.addSeries as unknown as (
                    d: never, o: never, p?: number) => ISeriesApi<'Line'>)(
                    lwc?.CandlestickSeries as never, options, paneIndex);
            } catch {
                return;
            }
            if (!created) return;
            entry = { series: created, pane: paneIndex };
            this.candleSeries.set(item.key, entry);
            series = created as unknown as typeof series;
        } else if (series) {
            const colors = options as unknown as Record<string, unknown>;
            series.applyOptions?.({
                upColor: colors.upColor, downColor: colors.downColor,
                wickUpColor: colors.wickUpColor,
                wickDownColor: colors.wickDownColor,
                visible: item.visible !== false,
            } as never);
        }
        try {
            series?.setData?.(rows as never);
        } catch { /* ignore */ }
        this._syncLegendRow(item, (series || entry?.series) as never);
    }

    /** 页面把 K 线交给图层（保留给其它指标用 ✓；VP 由 canvas 层负责） */
    setBars(bars: Array<{ time: number }>): void {
        this.bars = Array.isArray(bars) ? bars : [];
    }

    /** 按 key 找序列（主图叠加 + 各副图都查 ✓） */
    private _seriesOf(key: string): unknown {
        const overlay = this.overlaySeries.get(key);
        if (overlay) return overlay;
        for (const handle of this.panes.values()) {
            const series = handle.series.get(key);
            if (series) return series;
        }
        return null;
    }

    /**
     * `PlotInfo.spanstyle`：水平参考线（0 / 30 / 70 这种 ✓）
     *
     * 用 LWC 的 `createPriceLine` 挂在**同一个 pane 的线**上；
     * 该 pane 一根线都没有时，先建一条隐形载体序列 ✓
     */
    private _applySpans(items: IndicatorLine[]): void {
        const alive = new Set(items.map((item) => item.key));
        for (const [key, drawn] of [...this.spans]) {
            if (alive.has(key)) continue;
            for (const line of drawn) {
                try {
                    line.series.removePriceLine?.(line.handle);
                } catch { /* ignore */ }
            }
            this.spans.delete(key);
        }
        for (const item of items) {
            if (item.kind !== 'span') continue;
            const spans = item.spans || [];
            if (!spans.length || this.spans.has(item.key)) continue;
            const carrier = this._paneCarrier();
            if (!carrier) continue;
            const drawn: Array<{
                series: { removePriceLine?: (line: unknown) => void };
                handle: unknown;
            }> = [];
            for (const span of spans) {
                const price = Number(span.price);
                if (!Number.isFinite(price)) continue;
                try {
                    const handle = carrier.createPriceLine({
                        price,
                        color: span.color || '#666666',
                        lineWidth: (Number(span.lineWidth) || 1) as never,
                        lineStyle: (Number(span.lineStyle) || 0) as never,
                        axisLabelVisible: false,
                        title: '',
                    });
                    drawn.push({ series: carrier, handle });
                } catch { /* ignore */ }
            }
            if (drawn.length) this.spans.set(item.key, drawn);
        }
    }

    /** 参考线的落点：副图第一条线 → 主图叠加线 → 新建一条隐形载体 ✓ */
    private _paneCarrier(): {
        createPriceLine: (options: unknown) => unknown;
        removePriceLine?: (line: unknown) => void;
    } | null {
        for (const handle of this.panes.values()) {
            for (const series of handle.series.values()) {
                return series as never;
            }
        }
        for (const series of this.overlaySeries.values()) {
            return series as never;
        }
        const chart = this.getMainChart();
        const lwc = (window as unknown as {
            LightweightCharts?: { LineSeries?: never };
        }).LightweightCharts;
        if (!chart || !lwc?.LineSeries) return null;
        return (chart.addSeries as unknown as
            (d: never, o: never) => unknown)(lwc.LineSeries as never, {
            color: 'rgba(0,0,0,0)',
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
        } as never) as never;
    }

    /** `PlotInfo.watermark`：图表中央的大水印（半透明，不挡操作 ✓） */
    private _applyWatermarks(items: IndicatorLine[]): void {
        const alive = new Set(items.map((item) => item.key));
        for (const [key, node] of [...this.watermarks]) {
            if (alive.has(key)) continue;
            node.remove();
            this.watermarks.delete(key);
        }
        const cell = this.element.parentElement;
        if (!cell) return;
        for (const item of items) {
            if (item.kind !== 'watermark') continue;
            let node = this.watermarks.get(item.key);
            if (!node) {
                node = document.createElement('div');
                node.className = 'desk-ind-watermark';
                cell.appendChild(node);
                this.watermarks.set(item.key, node);
            }
            node.textContent = item.label || '';
            node.style.fontSize = `${Math.max(12, Number(item.fontSize) || 44)}px`;
        }
    }

    /** `PlotInfo.bandstyle`：两条线之间填充（上沿线挂 LineFill 原语 ✓） */
    private _applyBands(items: IndicatorLine[]): void {
        const alive = new Set(items.map((item) => item.key));
        for (const [key, entry] of [...this.bands]) {
            if (alive.has(key)) continue;
            try {
                (entry.upper as unknown as {
                    detachPrimitive?: (p: unknown) => void;
                }).detachPrimitive?.(entry.fill);
            } catch { /* ignore */ }
            this.bands.delete(key);
        }
        for (const item of items) {
            if (item.kind !== 'band' || !item.lowerKey || !item.upperKey) {
                continue;
            }
            if (this.bands.has(item.key)) continue;
            const upper = this._seriesOf(item.upperKey) as unknown as {
                attachPrimitive?: (p: unknown) => void;
            } | null;
            const lower = this._seriesOf(item.lowerKey);
            if (!upper || !lower || typeof upper.attachPrimitive !== 'function') {
                continue;
            }
            try {
                const fill = new LineFill(lower as never, {
                    fillColor: item.color,
                    opacity: null,
                });
                upper.attachPrimitive(fill);
                this.bands.set(item.key, { upper, fill });
            } catch { /* 原语不可用 → 少一层填充，不影响线 ✓ */ }
        }
    }

    /** `PlotInfo.tablestyle`：在图上盖一个小表格（pos 决定角 ✓） */
    private _applyTables(items: IndicatorLine[]): void {
        const alive = new Set(items.map((item) => item.key));
        for (const [key, node] of [...this.tables]) {
            if (alive.has(key)) continue;
            node.remove();
            this.tables.delete(key);
        }
        const cell = this.element.parentElement;
        if (!cell) return;
        for (const item of items) {
            if (item.kind !== 'table') continue;
            let node = this.tables.get(item.key);
            if (!node) {
                node = document.createElement('div');
                node.className = 'desk-ind-table';
                node.style.position = 'absolute';
                node.style.zIndex = '6';
                node.style.pointerEvents = 'auto';
                node.style.cursor = 'move';
                node.title = '拖动可以移动这张表';
                this._makeTableDraggable(node, item.key);
                const pos = String(item.position || 'top-right');
                if (pos.includes('left')) node.style.left = '8px';
                else node.style.right = '76px';
                if (pos.includes('bottom')) node.style.bottom = '26px';
                else node.style.top = '8px';
                cell.appendChild(node);
                this.tables.set(item.key, node);
            }
            // ★ 拖动过就用用户拖的位置（`TableStyle.draggable` 默认 True ✓）
            const moved = this.tableOffsets.get(item.key);
            if (moved) {
                node.style.left = `${moved.x}px`;
                node.style.top = `${moved.y}px`;
                node.style.right = 'auto';
                node.style.bottom = 'auto';
            }
            // ★ 顶部表格要让开**指标图例行**（原生图例占着左上角，否则叠一起 ✗）
            const legendRows = this.legendRows.size;
            if (moved) {
                /* 已经拖过了 → 不再按 position 重置 ✓ */
            } else if (String(item.position || 'top-right').includes('bottom')) {
                node.style.top = '';
                node.style.bottom = '26px';
            } else {
                node.style.bottom = '';
                node.style.top = `${12 + Math.max(0, legendRows) * 19}px`;
            }
            const rows = item.rows || [];
            const headings = item.headings || [];
            node.innerHTML = [
                item.label ? `<div class="desk-ind-table-title">${item.label}</div>` : '',
                '<table>',
                headings.length
                    ? `<thead><tr>${headings.map((text) =>
                        `<th>${text}</th>`).join('')}</tr></thead>` : '',
                '<tbody>',
                rows.map((row) => `<tr>${row.map((text) =>
                    `<td>${text}</td>`).join('')}</tr>`).join(''),
                '</tbody></table>',
            ].join('');
        }
    }

    /** 只刷新表格的 tbody（表格跟随鼠标时每帧都调 ✓） */
    updateTableRows(key: string, rows: string[][]): void {
        const node = this.tables.get(key);
        if (!node) return;
        const body = node.querySelector('tbody');
        if (!body) return;
        body.innerHTML = (rows || []).map((row) => `<tr>${row.map((text) =>
            `<td>${text}</td>`).join('')}</tr>`).join('');
        node.dataset.mouseRow = '1';
    }

    /** 恢复实时（鼠标离开 → 让页面重新推最后一根 ✓） */
    clearTableMouseRow(key: string): void {
        const node = this.tables.get(key);
        if (node) delete node.dataset.mouseRow;
    }

    /** 让指标表格可以**拖动**（`TableStyle.draggable=True` 默认就是可拖 ✓） */
    private _makeTableDraggable(node: HTMLDivElement, key: string): void {
        node.addEventListener('mousedown', (event: MouseEvent) => {
            if (event.button !== 0) return;
            if ((event.target as HTMLElement)
                .closest('input,button,a,select,textarea')) {
                return;                      // 表里的控件不吃拖动 ✓
            }
            event.preventDefault();
            event.stopPropagation();
            const rect = node.getBoundingClientRect();
            const host = this.element.parentElement?.getBoundingClientRect();
            const startX = event.clientX;
            const startY = event.clientY;
            const baseX = rect.left - (host?.left || 0);
            const baseY = rect.top - (host?.top || 0);
            const move = (moveEvent: MouseEvent) => {
                const x = Math.max(0, baseX + moveEvent.clientX - startX);
                const y = Math.max(0, baseY + moveEvent.clientY - startY);
                node.style.left = `${x}px`;
                node.style.top = `${y}px`;
                node.style.right = 'auto';
                node.style.bottom = 'auto';
                this.tableOffsets.set(key, { x, y });
            };
            const up = () => {
                document.removeEventListener('mousemove', move);
                document.removeEventListener('mouseup', up);
            };
            document.addEventListener('mousemove', move);
            document.addEventListener('mouseup', up);
        });
    }

    /** 信号箭头（买卖点）：挂在一条**隐形 LineSeries** 上 ✓ */
    private _applyMarkers(item: IndicatorLine): void {
        const chart = item.overlay ? this.getMainChart() : null;
        let host = this.markerSeries.get(item.key);
        // ★ 箭头要挂在**同一 pane 里已经有数据的序列**上：
        //   新建一条没有任何数据的空序列时，LWC 不会把 markers 画出来 ✗
        if (!host) {
            host = this._paneSeries(item) as never;
            if (host) this.markerSeries.set(item.key, host);
        }
        const lwc = (window as unknown as {
            LightweightCharts?: {
                LineSeries?: never;
                createSeriesMarkers?: (series: unknown, markers: unknown[]) =>
                    { setMarkers: (markers: unknown[]) => void };
            };
        }).LightweightCharts;
        if (!host) {
            if (!chart || !lwc?.LineSeries) return;
            const paneIndex = this._markerPaneIndex(item);
            const addMarker = chart.addSeries.bind(chart) as unknown as (
                d: never, o: never, p?: number) => ISeriesApi<'Line'>;
            host = addMarker(lwc.LineSeries as never, {
                color: 'rgba(0,0,0,0)',
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
                // 载体序列本身不画线，只用来放箭头 ✓
                lineVisible: false,
            } as never, paneIndex);
            this.markerSeries.set(item.key, host);
            this._syncLegendRow(item, host);
        }
        const markers = (item.markers || []).map((marker) => ({
            time: marker.time as never,
            position: marker.position || 'belowBar',
            shape: marker.shape || 'circle',
            color: marker.color || item.color,
            text: marker.text || '',
        }));
        try {
            if (lwc?.createSeriesMarkers) {
                const cached = this.markerPrimitive.get(item.key);
                if (cached) cached.setMarkers(markers as never);
                else {
                    this.markerPrimitive.set(
                        item.key,
                        lwc.createSeriesMarkers(host, markers as never));
                }
            } else {
                (host as unknown as {
                    setMarkers?: (markers: unknown[]) => void;
                }).setMarkers?.(markers as never);
            }
        } catch { /* 箭头失败不影响主图 */ }
    }

    /** 箭头落点：同 pane 的第一条线 → 主图叠加线 → 主图 K 线 ✓ */
    private _paneSeries(item: IndicatorLine): unknown {
        // ★ 信号箭头要挂**主图**（`overlay`）—— 以前先找 `item.pane` 的副图，
        //   于是交易信号画在 CMO 副图里（用户实测 ✗）
        if (item.overlay) {
            for (const series of this.overlaySeries.values()) return series;
            const mainLegend = this.getLegend?.() as unknown as {
                _lines?: Array<{ series?: unknown }>;
            } | undefined;
            for (const row of mainLegend?._lines || []) {
                if (row.series) return row.series;
            }
        }
        const paneKey = item.pane || item.key;
        const handle = this.panes.get(paneKey);
        if (handle) {
            for (const series of handle.series.values()) return series;
        }
        for (const series of this.overlaySeries.values()) return series;
        const legend = this.getLegend?.() as unknown as {
            _lines?: Array<{ series?: unknown }>;
        } | undefined;
        for (const row of legend?._lines || []) {
            if (row.series) return row.series;
        }
        void item;
        return null;
    }

    /** 箭头缺落点时才建副图（普通情况都复用已有序列 ✓） */
    private _markerPaneIndex(item: IndicatorLine): number {
        if (item.overlay) return 0;
        const paneKey = item.pane || item.key;
        let handle = this.panes.get(paneKey);
        if (!handle) {
            handle = this._addPane();
            this.panes.set(paneKey, handle);
        }
        return handle.index;
    }

    /** VP 的图例**锚定序列**（隐形折线，只为了让 `makeSeriesRow` 有东西可挂 ✓） */
    private vpAnchor: unknown = null;

    private _vpAnchorSeries(): unknown {
        if (this.vpAnchor) return this.vpAnchor;
        try {
            const chart = this.getMainChart();
            const lwc = (window as unknown as {
                LightweightCharts?: { LineSeries?: never };
            }).LightweightCharts;
            if (!chart || !lwc?.LineSeries) return null;
            this.vpAnchor = chart.addSeries(lwc.LineSeries as never, {
                color: 'transparent',
                lineVisible: false,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
            } as never);
        } catch { /* ignore */ }
        return this.vpAnchor;
    }

    /**
     * 图例行：用 pylightcharts 的 `Legend.makeSeriesRow`（**真·眼睛图标** ✓），
     * 再在后面加一个更大的 ⚙ 打开设置菜单。
     */
    private _syncLegendRow(item: IndicatorLine, series: unknown): void {
        const existing = this.legendRows.get(item.key);
        if (existing) {
            // ★ 副图被收起后重新显示时会新建 series：图例行不能还绑着
            //   已经 removeSeries 掉的旧对象，否则眼睛 / 齿轮作用不到线上 ✗
            if (existing.series !== series) {
                existing.series = series;
                const legend = this.getLegend?.();
                const line = (legend?._lines || []).find(
                    (row) => row.row === existing.row);
                if (line) line.series = series;
                try {
                    (legend as unknown as {
                        setSeriesVisible?: (s: unknown, v: boolean) => unknown;
                    } | null)?.setSeriesVisible?.(
                        series, item.visible !== false);
                } catch { /* ignore */ }
            }
            return;
        }
        // `PlotInfo.legend=False` → 只画线、不显示标签（minibt 同款语义 ✓）
        if (item.legend === false) return;
        const legend = this.getLegend?.();
        if (!legend || typeof legend.makeSeriesRow !== 'function') return;
        try {
            legend.makeSeriesRow!(item.label || item.key,
                                  series as never, true, true);
            const lines = legend._lines || [];
            const last = lines[lines.length - 1] as {
                row?: HTMLDivElement } | undefined;
            const row = last?.row;
            if (!row) return;
            row.classList.add('desk-legend-native-row');
            const gear = document.createElement('button');
            gear.className = 'desk-legend-gear';
            gear.title = '指标设置（参数 / 线型 / 颜色 / 删除）';
            // 和 miniqt 看盘窗口**完全同一个**齿轮（原生 Legend 的 GEAR ✓）
            // 和 MiniQT 的 `legend-settings-switch` 一样 16×16（以前 13×13
            // 放在 16px 容器里 → 视觉上明显小一圈 ✗）
            gear.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24"
                aria-hidden="true">${GEAR}</svg>`;
            gear.addEventListener('click', (event) => {
                event.stopPropagation();
                this.onSettings?.(item, gear);
            });
            row.appendChild(gear);
            // ★ pylightcharts 原生眼睛只隐藏 series；VP 是 canvas 覆盖层，
            //   不经过 series → 还要通知页面 toggleIndicator 清 VP ✓。
            const nativeEye = row.querySelector<HTMLElement>(
                '.legend-toggle-switch');
            if (nativeEye) {
                nativeEye.addEventListener('click', () => this.onToggle?.(item));
            }
            this.legendRows.set(item.key, {
                row, gear, series,
            });
            // ★ 这一行是隐藏的（眼睛 / 设置里关掉的）→ 建行时就把眼睛切成闭眼，
            //   否则图标看着是“显示”，线却不在，用户要双击两下才回来 ✗
            if (item.visible === false) {
                const sync = (legend as unknown as {
                    setSeriesVisible?: (s: unknown, v: boolean) => unknown;
                }).setSeriesVisible;
                try {
                    sync?.call(legend, series, false);
                } catch { /* ignore */ }
            }
        } catch {
            /* 图例不可用也不影响画线 ✓ */
        }
    }

    /** 删除某个指标的图例行（👁 眼睛由 pylightcharts 自己管 ✓） */
    private _dropLegendRow(key: string): void {
        const entry = this.legendRows.get(key);
        if (!entry) return;
        entry.row.remove();
        const legend = this.getLegend?.();
        if (legend && Array.isArray(legend._lines)) {
            legend._lines = legend._lines.filter(
                (row) => row.series !== entry.series);
        }
        this.legendRows.delete(key);
    }

    /** 取某个线条保存过的样式（设置菜单重新打开时用 ✓） */
    styleOf(key: string): Partial<IndicatorStyleState> {
        return { ...(this.styleOverrides.get(key) || {}) };
    }

    /** 把保存过的样式套到后端新推来的 item 上（重连 / 新 K 线 / 参数重算 ✓） */
    private _applyStyleOverride(item: IndicatorLine): void {
        const saved = this.styleOverrides.get(item.key);
        if (!saved) return;
        if (saved.color !== undefined) item.color = saved.color;
        if (saved.lineWidth !== undefined) item.lineWidth = saved.lineWidth;
        if (saved.lineStyle !== undefined) item.lineStyle = saved.lineStyle;
        if (saved.priceLine !== undefined) item.priceLine = saved.priceLine;
        if (saved.priceLabel !== undefined) item.priceLabel = saved.priceLabel;
        if (saved.crosshairMarker !== undefined) {
            item.crosshairMarker = saved.crosshairMarker;
        }
        // ★ 隐藏状态也要记住：后端每秒全量推送时 item 是新的（visible 默认
        //   true）→ 不补这一行的话隐藏的指标线会“自己又出来”（用户实测 ✗）
        if (saved.visible !== undefined) item.visible = saved.visible;
    }

    /** 眼睛：与设置菜单的「显示该指标」共用同一份状态 ✓
     *
     * ⚠ **只改指标线的可见性**（`applyOptions({visible})`）：
     * 图例行 / 指标标签 / 齿轮都不动（用户反复强调的要求 ✓）。
     */
    setVisible(key: string, visible: boolean): void {
        const saved = { ...(this.styleOverrides.get(key) || {}), visible };
        this.styleOverrides.set(key, saved);
        const item = this.lastItems.find((row) => row.key === key);
        if (item) item.visible = visible;
        const entry = this.legendRows.get(key);
        const series = (entry?.series || this._seriesOf(key)) as
            unknown as { applyOptions?: Function } | undefined;
        // ★ 默认图例（pylightcharts `Legend`）负责把**眼睛图标**也切成
        //   开 / 闭眼；找不到就算了（不影响指标线）✓
        const legend = this.getLegend?.() as unknown as {
            setSeriesVisible?: (series: unknown, visible: boolean) => unknown;
        } | null;
        if (series) {
            try {
                series.applyOptions?.({ visible });
            } catch { /* ignore */ }
            try {
                legend?.setSeriesVisible?.(series, visible);
            } catch { /* ignore */ }
        }
        // ★ 副图：最后一条线隐藏 → 收起 pane；重新显示 → 重建 pane ✓
        try {
            this.apply({ type: 'indicator', symbol: '', items: this.lastItems });
        } catch { /* ignore */ }
    }

    /** 设置菜单「应用」：样式 / 可见性直接作用到序列 + 记住 ✓ */
    applyStyle(key: string, state: IndicatorStyleState): void {
        const before = this.lastItems.find((row) => row.key === key)?.visible;
        const saved: Partial<IndicatorStyleState> = {
            lineStyle: state.lineStyle,
            lineWidth: state.lineWidth,
            color: state.color,
            priceLine: state.priceLine,
            priceLabel: state.priceLabel,
            visible: state.visible,
            crosshairMarker: state.crosshairMarker,
        };
        this.styleOverrides.set(key, saved);
        const entry = this.legendRows.get(key);
        const series = (entry?.series || this._seriesOf(key)) as
            unknown as { applyOptions?: Function } | undefined;
        if (!series?.applyOptions) {
            // ★ 蜡烛 / 信号这类序列不在 `_seriesOf` 里 → 至少把颜色刷到
            //   图例色点上，否则用户会以为“选了颜色没反应”（用户实测 ✗）
            this._paintLegend(key, state.color);
            return;
        }
        try {
            series.applyOptions({
                color: state.color,
                lineColor: state.color,
                lineWidth: state.lineWidth,
                lineStyle: state.lineStyle,
                priceLineVisible: state.priceLine,
                lastValueVisible: state.priceLabel,
                crosshairMarkerVisible: state.crosshairMarker,
                visible: state.visible,
            });
        } catch {
            /* ignore */
        }
        if (state.visible !== undefined && state.visible !== before) {
            try {
                this.apply({ type: 'indicator', symbol: '',
                             items: this.lastItems });
            } catch { /* ignore */ }
        }
        // ★ 折线的每个点可能带着**旧的逐点颜色**（`_lineDataFor` 只在缺口点
        //   设透明色了，但已经画上去的数据还是老颜色）→ 这里用新颜色重设一遍，
        //   否则在「本地图表」这种没有后续推送的页面上选了颜色也不变 ✗
        try {
            const item = this.lastItems.find((row) => row.key === key);
            if (item && item.kind !== 'candles' && item.kind !== 'hist'
                    && (item.kind === 'line' || !item.kind)) {
                const target = series as unknown as {
                    setData?: (rows: unknown[]) => void };
                if (target.setData && Array.isArray(item.data)) {
                    target.setData(this._lineDataFor(item, state.color) as never);
                }
            }
        } catch {
            /* ignore */
        }
        // ★ 左上角图例的色点也是“跟随颜色”的一部分（以前永远停在旧色 ✗）
        this._paintLegend(key, state.color);
    }

    /** 把某个指标在图例里的色点改成新颜色（原生图例 + 页面自定义图例 ✓） */
    private _paintLegend(key: string, color?: string): void {
        if (!color) return;
        const entry = this.legendRows.get(key);
        const row = entry?.row as HTMLElement | undefined;
        try {
            row?.querySelectorAll?.('.legend-swatch')
                .forEach((node) => {
                    const swatch = node as HTMLElement;
                    swatch.style.background = color;
                    swatch.dataset.color = color;
                });
        } catch {
            /* ignore */
        }
    }

    /** 跟随主题：副图现在是主图的 pane，**主图 applyOptions 就够了** ✓ */
    applyTheme(_theme: 'light' | 'dark'): void {
        // 副图 = 主图的 pane（同一个 chart）→ 主题由主图统一应用 ✓
    }

    /** 主图 resize 时副图自动跟着变（同一个 chart ✓） */
    resize(_width: number): void {
        // 无需处理：pane 跟 chart 同宽
    }

    get keys(): string[] {
        return this.lastItems.map((item) => item.key);
    }

    /** 图例里的指标标签 key（测试用：验证隐藏时标签不会消失 ✓） */
    get legendKeys(): string[] {
        return [...this.legendRows.keys()];
    }

    /** 删掉某个**指标**的全部线（`source` = 目录 key；不等后端补丁也行 ✓） */
    removeSource(source: string): void {
        const keep = this.lastItems.filter((item) =>
            (item.source || String(item.key).split(':')[0]) !== source);
        if (keep.length === this.lastItems.length) return;
        this.apply({ type: 'indicator', symbol: '', items: keep });
    }

    clear(): void {
        this.apply({ type: 'indicator', symbol: '', items: [] });
    }

    /** 在主图 chart 里**新增一个 pane**（不是新建 chart ✓） */
    private _addPane(): PaneHandle {
        const chart = this.getMainChart();
        if (!chart) return { index: 0, series: new Map() };
        const add = (chart as unknown as { addPane?: Function }).addPane;
        let index = Math.max(1, chart.panes().length);
        if (typeof add === 'function') {
            // `preserveEmpty=false`：删光序列的 pane 会自动消失（配合 removePane ✓）
            add.call(chart, false);
            index = Math.max(1, chart.panes().length - 1);
        }
        const handle: PaneHandle = { index, series: new Map(), height: 96 };
        this._setPaneHeight(handle, 96);
        return handle;
    }

    /** 往指定 pane 加序列（`addSeries(type, opts, paneIndex)` ✓） */
    private _addSeriesToPane(handle: PaneHandle, item: IndicatorLine):
        ISeriesApi<'Line' | 'Histogram'> {
        const chart = this.getMainChart();
        const lwc = (window as unknown as {
            LightweightCharts?: { LineSeries?: never; HistogramSeries?: never;
                                  CandlestickSeries?: never };
        }).LightweightCharts;
        // ★ `candles` = 蜡烛型指标（`candlestyle` 的 bull/bear 配色 ✓）
        const definition = (item.kind === 'candles'
            ? lwc?.CandlestickSeries
            : (item.kind === 'hist'
                ? lwc?.HistogramSeries : lwc?.LineSeries)) as never;
        if (item.kind === 'candles') {
            const options = {
                upColor: item.upColor || '#26a69a',
                downColor: item.downColor || '#ef5350',
                borderVisible: false,
                wickUpColor: item.upColor || '#26a69a',
                wickDownColor: item.downColor || '#ef5350',
                priceLineVisible: false,
                lastValueVisible: false,
            } as never;
            const addCandle = chart?.addSeries.bind(chart) as unknown as (
                d: never, o: never, p?: number) => ISeriesApi<'Line'>;
            if (!chart) return null as never;
            return addCandle(definition, options, handle.index);
        }
        // 线宽 / 线型都来自 `PlotInfo.linestyle`（和 miniqt 显示一致 ✓）
        const options = {
            color: item.color,
            lineWidth: Math.min(4, Math.max(1, Number(item.lineWidth) || 1)),
            lineStyle: Number(item.lineStyle) || 0,
            priceLineVisible: item.priceLine !== false,
            lastValueVisible: item.priceLabel !== false,
            crosshairMarkerVisible: item.crosshairMarker !== false,
            // ★ 隐藏的指标线（眼睛 / 设置里的「显示该指标」）重建后仍隐藏 ✓
            visible: item.visible !== false,
        } as never;
        if (!chart) return null as never;
        const add = chart.addSeries.bind(chart) as unknown as (
            d: never, o: never, p?: number) =>
            ISeriesApi<'Line' | 'Histogram'>;
        return add(definition, options, handle.index);
    }

    /** 副图高度（`pane.setHeight`；拖分隔条时 LWC 自己会改 ✓） */
    private _setPaneHeight(handle: PaneHandle, height: number): void {
        const chart = this.getMainChart();
        if (!chart || handle.height === height) return;
        handle.height = height;
        try {
            const pane = chart.panes()[handle.index] as unknown as {
                setHeight?: (value: number) => void;
            } | undefined;
            pane?.setHeight?.(height);
        } catch { /* 老版本 LWC 没有 setHeight → 平均拉伸 ✓ */ }
    }
}

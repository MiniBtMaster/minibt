import { ISeriesApi, LineData, Logical, MouseEventParams, PriceFormatBuiltIn, SeriesType } from "lightweight-charts";
import { Handler } from "./handler";
import { GlobalParams } from "./global-params";
import { seriesColor } from "./series-color";
import { LegendMenu, LegendMenuConfig } from "./legend-menu";

declare const window: GlobalParams;


interface LineElement {
    name: string;
    div: HTMLDivElement;
    row: HTMLDivElement;
    toggle?: HTMLDivElement;
    settings?: HTMLDivElement;
    /** keep the row visible (name only) even without a crosshair */
    pinned?: boolean;
    series: ISeriesApi<SeriesType>,
    solid: string;
}

/** A small gear, the entry point of the indicator settings card.
 *
 * desk 也用它（`desk-legend-gear`）→ 和 miniqt 看盘窗口的指标设置图标**同一个** ✓
 */
export const GEAR = `
    <path style="fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke:currentColor;stroke-opacity:1;stroke-miterlimit:4;" d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"/>
    <path style="fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke:currentColor;stroke-opacity:1;stroke-miterlimit:4;" d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>`;

// The eye is drawn by this bundle (upstream Lightweight Charts has no such
// control). `stroke: currentColor` (not a hard-coded white) makes the icon
// follow the legend's text colour, which python sets with `legend(color=...)`
// and a theme re-applies - on a light background a white eye is invisible.
export const EYE_OPEN = `
    <path style="fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke:currentColor;stroke-opacity:1;stroke-miterlimit:4;" d="M 21.998437 12 C 21.998437 12 18.998437 18 12 18 C 5.001562 18 2.001562 12 2.001562 12 C 2.001562 12 5.001562 6 12 6 C 18.998437 6 21.998437 12 21.998437 12 Z M 21.998437 12 " transform="matrix(0.833333,0,0,0.833333,0,0)"/>
    <path style="fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke:currentColor;stroke-opacity:1;stroke-miterlimit:4;" d="M 15 12 C 15 13.654687 13.654687 15 12 15 C 10.345312 15 9 13.654687 9 12 C 9 10.345312 10.345312 9 12 9 C 13.654687 9 15 10.345312 15 12 Z M 15 12 " transform="matrix(0.833333,0,0,0.833333,0,0)"/>
`;
export const EYE_CLOSED = `
    <path style="fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke:currentColor;stroke-opacity:1;stroke-miterlimit:4;" d="M 20.001562 9 C 20.001562 9 19.678125 9.665625 18.998437 10.514062 M 12 14.001562 C 10.392187 14.001562 9.046875 13.589062 7.95 12.998437 M 12 14.001562 C 13.607812 14.001562 14.953125 13.589062 16.05 12.998437 M 12 14.001562 L 12 17.498437 M 3.998437 9 C 3.998437 9 4.354687 9.735937 5.104687 10.645312 M 7.95 12.998437 L 5.001562 15.998437 M 7.95 12.998437 C 6.689062 12.328125 5.751562 11.423437 5.104687 10.645312 M 16.05 12.998437 L 18.501562 15.998437 M 16.05 12.998437 C 17.38125 12.290625 18.351562 11.320312 18.998437 10.514062 M 5.104687 10.645312 L 2.001562 12 M 18.998437 10.514062 L 21.998437 12 " transform="matrix(0.833333,0,0,0.833333,0,0)"/>
`;

/** 图例前面的**纯色圆点**（以前是 `▨` 方块＋斜线，用户要求改圆点 ✓） */
function swatch(solid: string): string {
    // 纯色小圆点：颜色 = 这条线自己的颜色（`seriesColor` → `options().color` ✓）
    // ⚠ 别加 `box-shadow: inset`：9~10px 下那圈内阴影会被看成"小方框"（用户实测 ✗）
    return `<span class="legend-swatch" data-color="${solid}" style=`
        + `"display:inline-block;width:10px;height:10px;min-width:10px;`
        + `min-height:10px;border-radius:50%;background:${solid};`
        + `background-image:none;border:0;margin-right:6px;`
        + `vertical-align:middle;flex:none;box-shadow:none;"`
        + `></span>`;
}


export class Legend {
    private handler: Handler;
    public div: HTMLDivElement;
    public seriesContainer: HTMLDivElement

    private ohlcEnabled: boolean = false;
    private percentEnabled: boolean = false;
    private linesEnabled: boolean = false;
    private colorBasedOnCandle: boolean = false;

    private text: HTMLSpanElement;
    private candle: HTMLDivElement;
    public _lines: LineElement[] = [];
    /** pane the legend is anchored to, and the observer watching it */
    private _observedPane: HTMLElement | null = null;
    private _paneObserver: ResizeObserver | null = null;
    private _containerObserver: MutationObserver | null = null;
    private _scheduled = false;


    constructor(handler: Handler) {
        this.legendHandler = this.legendHandler.bind(this)

        this.handler = handler;
        this.ohlcEnabled = false;
        this.percentEnabled = false
        this.linesEnabled = false
        this.colorBasedOnCandle = false

        this.div = document.createElement('div');
        this.div.classList.add("legend")
        this.div.style.maxWidth = `${(handler.scale.width * 100) - 8}vw`
        this.div.style.display = 'none';
        
        const seriesWrapper = document.createElement('div');
        seriesWrapper.style.display = 'flex';
        seriesWrapper.style.flexDirection = 'row';
        this.seriesContainer = document.createElement("div");
        this.seriesContainer.classList.add("series-container");

        this.text = document.createElement('span')
        this.text.style.lineHeight = '1.8'
        this.candle = document.createElement('div')
        
        seriesWrapper.appendChild(this.seriesContainer);
        this.div.appendChild(this.text)
        this.div.appendChild(this.candle)
        this.div.appendChild(seriesWrapper)
        handler.div.appendChild(this.div)

        // this.makeSeriesRows(handler);

        handler.addCrosshairListener(this.legendHandler)
        this.updatePosition()
    }

    /**
     * Keep the legend clear of the left price scale.
     *
     * The legend is anchored 10px from the container's left edge, which is
     * exactly where a visible left price scale draws its labels (e.g. after
     * `chart.add_symbol(..., scale='left')`), so the two overlapped. Anchoring it
     * to the pane instead fixes that; the pane's rectangle is re-read on every
     * crosshair move and whenever the pane is resized, so a scale that appears,
     * disappears or gets wider is followed.
     */
    updatePosition() {
        const container = this.handler.div.getBoundingClientRect();
        const pane = this.handler.chart.panes()[0]?.getHTMLElement?.();
        if (pane) this._watch(pane);
        // the pane follows the container's top-left corner, but a chart-layout
        // change (a scale appearing / disappearing / growing) can move it
        // without resizing it, so the container's own subtree is watched too
        this._watchContainer();
        if (!pane) return;
        // `getHTMLElement()` is the pane *widget*, which spans the price scales:
        // the drawing area starts after the left one (that is where the legend's
        // text used to land)
        const widget = pane.getBoundingClientRect().left - container.left;
        const left = widget + this.handler.chart.priceScale('left').width();
        const value = `${Math.max(0, Math.round(left)) + 10}px`;
        // assigning the same value must not wake the observer up again
        if (this.div.style.left !== value) this.div.style.left = value;
    }

    private _watch(pane: HTMLElement) {
        if (this._observedPane === pane) return;
        this._paneObserver?.disconnect();
        if (typeof ResizeObserver !== 'undefined') {
            this._paneObserver = new ResizeObserver(() => this.updatePosition());
            this._paneObserver.observe(pane);
        }
        this._observedPane = pane;
    }

    private _watchContainer() {
        if (this._containerObserver || typeof MutationObserver === 'undefined') {
            return;
        }
        this._containerObserver = new MutationObserver(() => {
            if (this._scheduled) return;
            // coalesce the burst of mutations a single layout change produces
            this._scheduled = true;
            requestAnimationFrame(() => {
                this._scheduled = false;
                this.updatePosition();
            });
        });
        this._containerObserver.observe(this.handler.div,
            { childList: true, subtree: true, attributes: true });
    }

    toJSON() {
        // Exclude the chart attribute from serialization
        const {_lines, handler, ...serialized} = this;
        return serialized;
    }

    // makeSeriesRows(handler: Handler) {
    //     if (this.linesEnabled) handler._seriesList.forEach(s => this.makeSeriesRow(s))
    // }


    makeSeriesRow(name: string, series: ISeriesApi<SeriesType>, showToggle: boolean = true, pinned: boolean = false) {
        let row = document.createElement('div')
        row.style.display = 'flex'
        row.style.alignItems = 'center'
        let div = document.createElement('div')

        // shared with the tooltips: which option carries a series' colour
        // depends on the series type (`color` / `lineColor` / `topColor`)
        const { solid } = seriesColor(series);

        // show the name right away; `legendHandler` appends the value while the
        // crosshair is over a bar (a pinned indicator row keeps just the name)
        div.innerHTML = `${swatch(solid)}<span>${name}</span>`

        // The eye is the in-chart entry point for hiding/showing the series.
        // `showToggle` lets a caller turn it off per series (python
        // `legend_toggle=False`) when visibility is handled elsewhere, e.g. by an
        // indicator settings window that calls Line.hide_data()/show_data().
        let toggle: HTMLDivElement | undefined
        if (showToggle) {
            toggle = document.createElement('div')
            toggle.classList.add('legend-toggle-switch')

            let svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("width", "22");
            svg.setAttribute("height", "16");

            let group = document.createElementNS("http://www.w3.org/2000/svg", "g");
            group.innerHTML = EYE_OPEN

            // ★ 眼睛**只**控制指标线的显示 / 隐藏（图例行不隐藏）。
            //   图标状态以 `series.options().visible` 为准（不再用闭包变量）——
            //   否则设置里的「显示该指标」改了可见性后，点一下眼睛会反着来 ✗。
            const setEye = (visible: boolean) => {
                group.innerHTML = visible ? EYE_OPEN : EYE_CLOSED
                toggle!.classList.toggle('off', !visible)
                toggle!.title = visible ? '隐藏指标线' : '显示指标线'
                ;(toggle as unknown as { __plcSetEye?: Function })
                    .__plcSetEye = setEye
            }
            ;(toggle as unknown as { __plcSetEye?: Function })
                .__plcSetEye = setEye
            toggle.title = '隐藏指标线'
            toggle.addEventListener('click', () => {
                const current = (series as unknown as {
                    options?: () => { visible?: boolean } })?.options?.()
                const on = !(current?.visible !== false)
                setEye(on)
                series.applyOptions({ visible: on })
                // NaN 断点分出来的"分段序列"是独立对象，必须跟着一起隐藏/显示，
                // 否则点了眼睛主线还是一段一段留在图上（python 侧在
                // `_sync_gap_segments` 里把它们挂在 `__gapSegments`）。
                const gaps = (series as unknown as {
                    __gapSegments?: ISeriesApi<SeriesType>[]
                }).__gapSegments
                if (Array.isArray(gaps)) {
                    for (const piece of gaps) {
                        try {
                            piece.applyOptions({ visible: on })
                        } catch (e) { /* 分段已被删除 */ }
                    }
                }
            })

            svg.appendChild(group)
            toggle.appendChild(svg)
        }

        row.appendChild(div)
        if (toggle) row.appendChild(toggle)
        this.seriesContainer.appendChild(row)

        this._lines.push({
            name: name,
            div: div,
            row: row,
            toggle: toggle,
            series: series,
            solid: solid,
            pinned: pinned,
        });
    }

    /** 只切换**指标线**的可见性（指标标签 / 眼睛图标保持在位 ✓）
     *
     * desk 的「设置 → 显示该指标」和眼睛共用它 → 两边状态永远一致。
     *
     * @returns 切换后的可见性（找不到序列 → ``undefined``）
     */
    setSeriesVisible(series: ISeriesApi<SeriesType>,
                     visible: boolean): boolean | undefined {
        const line = this._lines.find((item) => item.series === series)
        if (!line) return undefined
        try {
            series.applyOptions({ visible })
        } catch (e) { /* 序列已被删除 */ }
        const setEye = (line.toggle as unknown as {
            __plcSetEye?: (value: boolean) => void } | undefined)?.__plcSetEye
        if (typeof setEye === 'function') setEye(visible)
        const gaps = (series as unknown as {
            __gapSegments?: ISeriesApi<SeriesType>[]
        }).__gapSegments
        if (Array.isArray(gaps)) {
            for (const piece of gaps) {
                try {
                    piece.applyOptions({ visible })
                } catch (e) { /* 分段已被删除 */ }
            }
        }
        return visible
    }

    /** Add the settings (gear) button to a series' legend row.
     *
     * Called from python (`SeriesCommon.enable_legend_settings`): the gear is the
     * in-chart entry point for the indicator settings card (line style / colour /
     * price line / price label). Unlike the old implementation - which watched
     * every mouse move over the legend and called back to python - a click is the
     * only round trip, and python can pop the card right where the user clicked.
     */
    addSettingsToggle(series: ISeriesApi<SeriesType>, seriesId: string, callbackName: string) {
        const line = this._lines.find((item) => item.series === series)
        if (!line || !line.row) return
        if (line.settings) return
        const settings = document.createElement('div')
        settings.classList.add('legend-settings-switch')
        settings.title = '指标设置'
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svg.setAttribute('width', '16')
        svg.setAttribute('height', '16')
        svg.setAttribute('viewBox', '0 0 24 24')
        svg.innerHTML = GEAR
        settings.appendChild(svg)
        settings.addEventListener('click', (event: MouseEvent) => {
            event.stopPropagation()
            const rect = this.handler.div.getBoundingClientRect()
            const x = Math.round(event.clientX - rect.left)
            const y = Math.round(event.clientY - rect.top)
            window.callbackFunction(
                `${callbackName}_~_${seriesId};;;${x};;;${y}`)
        })
        line.row.appendChild(settings)
        line.settings = settings
    }

    /** Pin a series' legend row so its name/eye/settings stay visible without a
     *  crosshair (called from python for indicator lines). */
    pinSeriesRow(series: ISeriesApi<SeriesType>, pinned: boolean) {
        const line = this._lines.find((item) => item.series === series)
        if (!line) return
        line.pinned = pinned
        if (pinned) line.row.style.display = 'flex'
    }

    /** Add the settings (gear) button that opens the **JavaScript** indicator
     *  menu (line style/width/colour/price line + params).
     *
     * Counterpart of ``addSettingsToggle`` (which round-trips to a PyQt card):
     * this one builds a two-level menu inside the page, so a host without Qt
     * (minibt / btplot) gets the same settings surface. Applied changes are
     * still reported to python through ``callbackName`` for persistence.
     */
    addSettingsMenu(series: ISeriesApi<SeriesType>, seriesId: string,
                    config: LegendMenuConfig, callbackName: string) {
        const line = this._lines.find((item) => item.series === series)
        if (!line || !line.row || line.settings) return
        const settings = document.createElement('div')
        settings.classList.add('legend-settings-switch')
        settings.title = '指标设置'
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svg.setAttribute('width', '16')
        svg.setAttribute('height', '16')
        svg.setAttribute('viewBox', '0 0 24 24')
        svg.innerHTML = GEAR
        settings.appendChild(svg)
        let menu: LegendMenu | null = null
        settings.addEventListener('click', (event: MouseEvent) => {
            event.stopPropagation()
            if (!menu) {
                menu = new LegendMenu(series, seriesId, config || {}, callbackName)
            }
            menu.toggle(settings)
        })
        line.row.appendChild(settings)
        line.settings = settings
    }

    /** Add the TradingView-style collapse/expand button for the indicator rows.
     *
     * Ported from miniqt's ``_install_legend_collapse``: the button lives in
     * ``legend.div`` (vertical stack) so it always sits **below** the indicator
     * rows; it hides itself while there are none, shows ``∧`` when expanded and
     * ``∨ N`` when collapsed. Clicking must not fall through to the canvas, so
     * the row keeps ``pointer-events:auto`` (see ``.legend-collapse``).
     */
    enableCollapse() {
        const container = this.seriesContainer
        if (!container || (container as unknown as { __plcCollapse?: boolean }).__plcCollapse) {
            return
        }
        (container as unknown as { __plcCollapse?: boolean }).__plcCollapse = true
        const button = document.createElement('div')
        button.classList.add('legend-collapse')
        button.style.display = 'none'
        this.div.appendChild(button)
        let collapsed = false
        const refresh = () => {
            const count = container.children.length
            button.style.display = count ? 'block' : 'none'
            button.textContent = collapsed ? `\u2228 ${count}` : '\u2227'
            container.style.display = collapsed ? 'none' : ''
        }
        button.addEventListener('click', (event: MouseEvent) => {
            event.stopPropagation()
            collapsed = !collapsed
            refresh()
        })
        if (typeof MutationObserver !== 'undefined') {
            new MutationObserver(refresh).observe(container, { childList: true })
        }
        refresh()
    }

    legendItemFormat(num: number, decimal: number) { return num.toFixed(decimal).toString().padStart(8, ' ') }

    /** Crosshair time -> `YYYY-MM-DD` (adds `HH:mm` only for intraday bars).
     *
     * TradingView/LWC times are UTC; a daily bar lands on 00:00 UTC, so a
     * zero clock means "date only" and we do not print a misleading `00:00`.
     */
    legendTimeFormat(time: any): string {
        if (time === undefined || time === null) return ''
        const pad = (n: number) => (n < 10 ? '0' : '') + n
        if (typeof time === 'object') {
            const { year, month, day } = time
            if (year === undefined) return ''
            return `${year}-${pad(month)}-${pad(day)}`
        }
        if (typeof time === 'number') {
            const d = new Date(time * 1000)
            if (isNaN(d.getTime())) return ''
            let out = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
            if (d.getUTCHours() || d.getUTCMinutes()) {
                out += ` ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
            }
            return out
        }
        return String(time)
    }

    shorthandFormat(num: number) {
        const absNum = Math.abs(num)
        if (absNum >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (absNum >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString().padStart(8, ' ');
    }

    legendHandler(param: MouseEventParams, usingPoint= false) {
        this.updatePosition()
        if (!this.ohlcEnabled && !this.linesEnabled && !this.percentEnabled) return;
        const options: any = this.handler.series.options()

        if (!param.time) {
            if (this.div.matches(':hover')) {
                // The pointer is on a legend row, which takes the events away from the
                // chart: keep the last values instead of "leaving", otherwise moving
                // across the rows (which steal the pointer) makes the labels flash.
                return
            }
            this.candle.style.color = 'transparent'
            this.candle.innerHTML = this.candle.innerHTML.replace(options['upColor'], '').replace(options['downColor'], '')
            // the value labels are only shown while the crosshair is over a bar,
            // but a pinned indicator row keeps its name (+ eye/settings)
            this._lines.forEach((e) => {
                if (e.pinned && this.linesEnabled) {
                    e.row.style.display = 'flex'
                    e.div.innerHTML = `${swatch(e.solid)}<span>${e.name}</span>`
                } else {
                    e.row.style.display = 'none'
                }
            })
            return
        }

        let data: any;
        let logical: Logical | null = null;

        if (usingPoint) {
            const timeScale = this.handler.chart.timeScale();
            let coordinate = timeScale.timeToCoordinate(param.time)
            if (coordinate)
            logical = timeScale.coordinateToLogical(coordinate.valueOf())
            if (logical)
            data = this.handler.series.dataByIndex(logical.valueOf())
        }
        else {
            data = param.seriesData.get(this.handler.series);
        }

        this.candle.style.color = ''
        let str = '<span style="line-height: 1.8;">'
        if (data) {
            // One single line for the whole bar readout:
            //   D | O .. | H .. | L .. | C .. | V .. | +pct%
            // (previously the OHLC+percent row and a separate `<br>` volume row;
            // minibt's charts showed two rows — now one ✓).
            if (this.ohlcEnabled) {
                const when = this.legendTimeFormat(param.time)
                if (when) str += `${when} | `
                str += `O ${this.legendItemFormat(data.open, this.handler.precision)} | `
                str += `H ${this.legendItemFormat(data.high, this.handler.precision)} | `
                str += `L ${this.legendItemFormat(data.low, this.handler.precision)} | `
                str += `C ${this.legendItemFormat(data.close, this.handler.precision)}`
                if (this.handler.volumeSeries) {
                    let volumeData: any;
                    if (logical) {
                        volumeData = this.handler.volumeSeries.dataByIndex(logical)
                    }
                    else {
                        volumeData = param.seriesData.get(this.handler.volumeSeries)
                    }
                    if (volumeData && typeof volumeData.value === 'number') {
                        str += ` | V ${Math.round(volumeData.value)}`
                    }
                }
            }

            if (this.percentEnabled) {
                let percentMove = ((data.close - data.open) / data.open) * 100
                let color = percentMove > 0 ? options['upColor'] : options['downColor']
                let percentStr = `${percentMove >= 0 ? '+' : ''}${percentMove.toFixed(2)}%`

                if (this.colorBasedOnCandle) {
                    str += ` | <span style="color: ${color};">${percentStr}</span>`
                } else {
                    str += ' | ' + percentStr
                }
            }
        }
        this.candle.innerHTML = str + '</span>'

        this._lines.forEach((e) => {
            if (!this.linesEnabled) {
                e.row.style.display = 'none'
                return
            }
            e.row.style.display = 'flex'

            let data
            if (usingPoint && logical) {
                data = e.series.dataByIndex(logical) as LineData
            }
            else {
                data = param.seriesData.get(e.series) as LineData
            }
            const value = this.rowValue(e, data)
            // The swatch and the name identify the row, so they are always
            // drawn; the value is appended when this point has one. A series
            // without a value used to `return`, which left that row - and every
            // row after it - with nothing but the eye icon.
            const label = `${swatch(e.solid)}<span>${e.name}</span>`
            e.div.innerHTML = value === null ? label : `${label} : ${value}`
        })
    }

    /** The text one legend row shows for a data point (`null` = no value).
     *
     * ★ **蜡烛**行与主图顶部那一行**完全同款**：
     * ``D | O .. | H .. | L .. | C .. | V .. | +pct%`` ✓
     * （以前蜡烛走到下面的 `low – high` 分支，副图只显示“5111.00 – 5118.00” ✗
     * —— 用户反馈“回测结果页副图 K 线的标签过于简陋”✗）。
     *
     * Custom series built from range shapes carry `low`/`high` instead of
     * `value` (`priceValueBuilder` derives the price scale from them), so they
     * are shown as a range.
     */
    rowValue(row: LineElement, data: any): string | null {
        if (!data) return null
        const format = row.series.options().priceFormat as PriceFormatBuiltIn
        const precision = format?.precision ?? this.handler.precision
        if (row.series.seriesType() === 'Candlestick'
            && typeof data.open === 'number' && isFinite(data.open)
            && typeof data.close === 'number' && isFinite(data.close)) {
            return this.candleReadout(row, data, precision)
        }
        if (typeof data.value === 'number' && isFinite(data.value)) {
            return row.series.seriesType() == 'Histogram'
                ? this.shorthandFormat(data.value)
                : this.legendItemFormat(data.value, precision)
        }
        const { low, high } = data
        if (typeof low === 'number' && typeof high === 'number'
            && isFinite(low) && isFinite(high)) {
            return `${this.legendItemFormat(low, precision)} – `
                + this.legendItemFormat(high, precision)
        }
        if (typeof data.close === 'number' && isFinite(data.close)) {
            return this.legendItemFormat(data.close, precision)
        }
        return null
    }

    /** 一根蜡烛的完整读数：`D | O | H | L | C | V | +pct%` ✓（主图/副图同款）。
     *
     * ``V`` 仅在该点带 ``customValues.volume``（minibt 给副图合约塞的 ✓）或
     * ``volume`` 时显示 —— 引擎的蜡烛数据本身不含成交量 ✗。
     */
    candleReadout(row: LineElement, data: any,
                  precision?: number): string {
        const options: any = row.series.options() || {}
        const p = precision ?? this.handler.precision
        let str = ''
        const when = this.legendTimeFormat(data.time)
        if (when) str += `${when} | `
        str += `O ${this.legendItemFormat(data.open, p)} | `
        str += `H ${this.legendItemFormat(data.high, p)} | `
        str += `L ${this.legendItemFormat(data.low, p)} | `
        str += `C ${this.legendItemFormat(data.close, p)}`
        const volume = data.customValues?.volume ?? data.volume
        if (typeof volume === 'number' && isFinite(volume)) {
            str += ` | V ${Math.round(volume)}`
        }
        if (data.open !== 0) {
            const move = ((data.close - data.open) / data.open) * 100
            const color = move > 0 ? options.upColor : options.downColor
            const text = `${move >= 0 ? '+' : ''}${move.toFixed(2)}%`
            str += (this.colorBasedOnCandle && color)
                ? ` | <span style="color: ${color};">${text}</span>`
                : ` | ${text}`
        }
        return str
    }
}

import { ISeriesApi, SeriesType } from "lightweight-charts";
import { GlobalParams } from "./global-params";

declare const window: GlobalParams;

/** One editable indicator parameter (the 参数 tab of the settings menu). */
export interface LegendMenuParam {
    name: string;
    value: any;
    /** ``int`` / ``float`` / ``bool`` / ``str`` — drives value coercion. */
    type?: string;
    /** Display only — the value is a ``KLine`` / ``DataFrame`` etc. and cannot be
     *  typed in a text box. Rendered disabled and **excluded from the callback**
     *  so ``str(kline)`` can never overwrite the real object. */
    readonly?: boolean;
}

/** Everything the JS settings menu needs to render + apply one indicator line.
 *
 * Built on the python side (``pylightcharts.abstract.SeriesCommon``) and passed
 * to ``Legend.addSettingsMenu`` as JSON. Localised labels let the callback stay
 * generic.
 */
export interface LegendMenuConfig {
    title?: string;
    params?: LegendMenuParam[];
    lineStyle?: string;
    lineWidth?: number;
    lineColor?: string;
    priceLine?: boolean;
    priceLabel?: boolean;
    /** Area series colour through ``lineColor``/``topColor``/``bottomColor``. */
    isArea?: boolean;
    /** Hide the 线型 group (histogram / column lines have no line style). */
    showStyle?: boolean;
    styles?: string[];
    widths?: number[];
    colors?: string[];
    labels?: { [key: string]: string };
}

const STYLE_VALUE: { [key: string]: number } = {
    solid: 0,
    dotted: 1,
    dashed: 2,
    large_dashed: 3,
    sparse_dotted: 4,
};

const STYLE_LABEL: { [key: string]: string } = {
    solid: '实线',
    dotted: '点线',
    dashed: '虚线',
    large_dashed: '长虚线',
    sparse_dotted: '疏点线',
};

const DEFAULT_STYLES = ['solid', 'dotted', 'dashed', 'large_dashed', 'sparse_dotted'];
const DEFAULT_WIDTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const DEFAULT_COLORS = [
    '#ffffff', '#f23645', '#ff9800', '#ffeb3b', '#4caf50',
    '#00bcd4', '#2196f3', '#9c27b0', '#e91e63', '#9e9e9e',
];

/** Chinese labels (match miniqt's indicator card); a config may override them. */
const DEFAULT_LABELS: { [key: string]: string } = {
    title: '指标设置', params: '参数', style: '线型', width: '线宽',
    color: '线颜色', other: '其它设置', confirm: '确认',
    priceLine: '价格线', priceLabel: '价格标签',
};

/**
 * A small two-level menu that mimics miniqt's indicator settings card
 * (参数 / 线型 / 线宽 / 线颜色 / 其它设置) **in JavaScript**.
 *
 * The top level lists the groups; hovering/clicking one opens a flyout submenu
 * (二级菜单) to its right. Style/width/colour/price-line changes are applied to
 * the series immediately *and* reported to python through
 * ``window.callbackFunction`` so the host can persist them; the 参数 group
 * collects inputs and reports them on 确认 (python recomputes the indicator).
 */
export class LegendMenu {
    private panel: HTMLDivElement;
    private sub: HTMLDivElement;
    private isOpen = false;
    private _hideTimer: any = null;

    constructor(
        private series: ISeriesApi<SeriesType>,
        private seriesId: string,
        private config: LegendMenuConfig,
        private callbackName: string,
    ) {
        this.panel = document.createElement('div');
        this.panel.classList.add('legend-menu');
        this.panel.style.display = 'none';
        this.sub = document.createElement('div');
        this.sub.classList.add('legend-menu', 'legend-menu-sub');
        this.sub.style.display = 'none';
        document.body.appendChild(this.panel);
        document.body.appendChild(this.sub);

        this.build();
        document.addEventListener('mousedown', (event: MouseEvent) => {
            if (!this.isOpen) return;
            const target = event.target as Node;
            if (this.panel.contains(target) || this.sub.contains(target)) return;
            this.hide();
        });
        this.panel.addEventListener('mouseleave', () => this.scheduleHideSub());
        this.sub.addEventListener('mouseenter', () => this.cancelHideSub());
        this.sub.addEventListener('mouseleave', () => this.scheduleHideSub());
    }

    /** Open the menu below ``anchor`` (toggling it closed on a second click). */
    toggle(anchor: HTMLElement) {
        if (this.isOpen) {
            this.hide();
            return;
        }
        this.isOpen = true;
        this.panel.style.display = 'flex';
        const rect = anchor.getBoundingClientRect();
        const view = document.documentElement;
        const width = this.panel.offsetWidth || 132;
        let left = rect.right + 4;
        if (left + width > view.clientWidth - 4) {
            left = Math.max(4, rect.left - width - 4);
        }
        this.panel.style.left = left + 'px';
        const height = this.panel.offsetHeight || 0;
        const top = Math.min(rect.top, Math.max(4, view.clientHeight - height - 4));
        this.panel.style.top = top + 'px';
    }

    private hide() {
        this.isOpen = false;
        this.panel.style.display = 'none';
        this.hideSub();
    }

    private hideSub() {
        this.cancelHideSub();
        this.sub.style.display = 'none';
    }

    /** Close the flyout shortly after the pointer leaves the menu / flyout.
     *
     * A plain ``mouseleave`` on the panel hid the flyout the moment the pointer
     * travelled from an item onto the flyout (a sibling element), so the
     * submenu could not be clicked. The short delay, cancelled by the flyout's
     * ``mouseenter``, keeps it open while the pointer moves across.
     */
    private scheduleHideSub() {
        this.cancelHideSub();
        this._hideTimer = setTimeout(() => {
            this._hideTimer = null;
            this.sub.style.display = 'none';
        }, 300);
    }

    private cancelHideSub() {
        if (this._hideTimer !== null) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
    }

    private label(key: string, fallback: string): string {
        const labels = this.config.labels || {};
        return labels[key] || DEFAULT_LABELS[key] || fallback;
    }

    private build() {
        // No title row: the indicator name is already on the legend row, and a
        // title made the first menu slot look like an (empty) "参数" entry when
        // params were disabled. Items only, like the topbar menu.
        const items: Array<[string, (parent: HTMLElement) => void]> = [];
        if (this.config.params && this.config.params.length) {
            items.push(['params', (parent) => this.buildParams(parent)]);
        }
        if (this.config.showStyle !== false) {
            items.push(['style', (parent) => this.buildStyles(parent)]);
        }
        items.push(['width', (parent) => this.buildWidths(parent)]);
        items.push(['color', (parent) => this.buildColors(parent)]);
        items.push(['other', (parent) => this.buildOther(parent)]);

        for (const [key, buildSub] of items) {
            const item = document.createElement('div');
            item.classList.add('legend-menu-item');
            const text = document.createElement('span');
            text.textContent = this.label(key, key);
            const arrow = document.createElement('span');
            arrow.classList.add('legend-menu-arrow');
            arrow.textContent = '›';
            item.appendChild(text);
            item.appendChild(arrow);
            const openSub = () => {
                this.sub.innerHTML = '';
                buildSub(this.sub);
                this.showSub(item);
            };
            item.addEventListener('mouseenter', openSub);
            item.addEventListener('click', (event: MouseEvent) => {
                event.stopPropagation();
                openSub();
            });
            this.panel.appendChild(item);
        }
    }

    private showSub(anchor: HTMLElement) {
        this.cancelHideSub();
        this.sub.style.display = 'flex';
        const rect = anchor.getBoundingClientRect();
        const panelRect = this.panel.getBoundingClientRect();
        const view = document.documentElement;
        const width = this.sub.offsetWidth || 140;
        let left = panelRect.right - 2;
        if (left + width > view.clientWidth - 4) {
            left = Math.max(4, panelRect.left - width + 2);
        }
        this.sub.style.left = left + 'px';
        const height = this.sub.offsetHeight || 0;
        const top = Math.min(rect.top, Math.max(4, view.clientHeight - height - 4));
        this.sub.style.top = top + 'px';
    }

    private choice(text: string, active: boolean, onPick: () => void): HTMLDivElement {
        const div = document.createElement('div');
        div.classList.add('legend-menu-choice');
        if (active) div.classList.add('active');
        div.textContent = text;
        div.addEventListener('click', (event: MouseEvent) => {
            event.stopPropagation();
            onPick();
        });
        return div;
    }

    private buildStyles(parent: HTMLElement) {
        let styles = this.config.styles || DEFAULT_STYLES;
        // ★ 当前线型不在列表里（如 minibt 的 `dashdot` 别名）→ 插到最前面，
        //   保证“菜单里勾中的”就是图上真正画的那种 ✓（否则会落到实线上 ✗）
        const currentStyle = this.config.lineStyle;
        if (currentStyle && !styles.includes(currentStyle)) {
            styles = [currentStyle, ...styles];
        }
        for (const style of styles) {
            parent.appendChild(this.choice(
                STYLE_LABEL[style] || style, this.config.lineStyle === style,
                () => {
                    this.config.lineStyle = style;
                    this.apply('style', { value: style });
                    this.hide();
                }));
        }
    }

    private buildWidths(parent: HTMLElement) {
        let widths = this.config.widths || DEFAULT_WIDTHS;
        // ★ 当前线宽不在列表里 → 插到最前面（否则一项都不会被勾中 ✗）
        const currentWidth = Number(this.config.lineWidth);
        if (this.config.lineWidth !== undefined && this.config.lineWidth !== null
            && !widths.some((w) => Number(w) === currentWidth)) {
            widths = [currentWidth, ...widths];
        }
        for (const width of widths) {
            parent.appendChild(this.choice(
                String(width), Number(this.config.lineWidth) === Number(width),
                () => {
                    this.config.lineWidth = Number(width);
                    this.apply('width', { value: Number(width) });
                    this.hide();
                }));
        }
    }

    private buildColors(parent: HTMLElement) {
        const colors = this.config.colors || DEFAULT_COLORS;
        // 颜色不做“归一化后比对”也不强插当前色 —— 指标常用 CSS 色名
        // （`blue`/`tomato`），与 hex 色板对不上时**不勾选**也是可接受的 ✓
        for (const color of colors) {
            const div = document.createElement('div');
            div.classList.add('legend-menu-choice', 'legend-menu-swatch');
            if ((this.config.lineColor || '').toLowerCase() === color.toLowerCase()) {
                div.classList.add('active');
            }
            const chip = document.createElement('span');
            chip.classList.add('legend-menu-chip');
            chip.style.backgroundColor = color;
            const text = document.createElement('span');
            text.textContent = color;
            div.appendChild(chip);
            div.appendChild(text);
            div.addEventListener('click', (event: MouseEvent) => {
                event.stopPropagation();
                this.config.lineColor = color;
                this.apply('color', { value: color });
                this.hide();
            });
            parent.appendChild(div);
        }
        const custom = document.createElement('input');
        custom.type = 'color';
        custom.classList.add('legend-menu-color-input');
        custom.value = this.normalizeHex(this.config.lineColor) || '#ffffff';
        custom.addEventListener('input', () => {
            this.config.lineColor = custom.value;
            this.apply('color', { value: custom.value }, false);
        });
        custom.addEventListener('change', () => {
            this.apply('color', { value: custom.value });
        });
        parent.appendChild(custom);
    }

    private normalizeHex(color?: string): string {
        if (!color) return '';
        if (/^#[0-9a-fA-F]{6}$/.test(color)) return color;
        const short = /^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$/.exec(color);
        if (short) return `#${short[1]}${short[1]}${short[2]}${short[2]}${short[3]}${short[3]}`;
        const rgb = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(color);
        if (rgb) {
            const hex = (n: string) => Number(n).toString(16).padStart(2, '0');
            return `#${hex(rgb[1])}${hex(rgb[2])}${hex(rgb[3])}`;
        }
        return '';
    }

    private buildOther(parent: HTMLElement) {
        parent.appendChild(this.toggleRow(
            this.label('priceLine', '价格线'), !!this.config.priceLine, (on) => {
                this.config.priceLine = on;
                this.apply('price', {
                    priceLine: this.config.priceLine,
                    priceLabel: this.config.priceLabel,
                });
            }));
        parent.appendChild(this.toggleRow(
            this.label('priceLabel', '价格标签'), !!this.config.priceLabel, (on) => {
                this.config.priceLabel = on;
                this.apply('price', {
                    priceLine: this.config.priceLine,
                    priceLabel: this.config.priceLabel,
                });
            }));
    }

    private toggleRow(text: string, on: boolean, onToggle: (on: boolean) => void): HTMLDivElement {
        const row = document.createElement('div');
        row.classList.add('legend-menu-choice', 'legend-menu-toggle');
        if (on) row.classList.add('on');
        const label = document.createElement('span');
        label.textContent = text;
        const state = document.createElement('span');
        state.textContent = on ? '开' : '关';
        if (on) state.classList.add('on');
        row.appendChild(label);
        row.appendChild(state);
        // ``on`` 必须记在 row 上（不能只看 state 的 class）——原来只在 state
        // span 上加了 'on'，row 永远没有 'on' → next 恒为 true，只能开不能关 ✗
        let value = on;
        row.addEventListener('click', (event: MouseEvent) => {
            event.stopPropagation();
            value = !value;
            row.classList.toggle('on', value);
            state.textContent = value ? '开' : '关';
            state.classList.toggle('on', value);
            onToggle(value);
        });
        return row;
    }

    private buildParams(parent: HTMLElement) {
        const fields: Array<{ name: string; type: string; input: HTMLInputElement }> = [];
        for (const param of this.config.params || []) {
            const row = document.createElement('div');
            row.classList.add('legend-menu-param-row');
            const flag = document.createElement('span');
            flag.classList.add('legend-menu-flag');
            flag.textContent = '⚑';
            const name = document.createElement('span');
            name.classList.add('legend-menu-param-name');
            name.textContent = param.name;
            const input = document.createElement('input');
            input.classList.add('legend-menu-param-input');
            input.value = (param.value === undefined || param.value === null)
                ? '' : String(param.value);
            row.appendChild(flag);
            row.appendChild(name);
            row.appendChild(input);
            parent.appendChild(row);
            if (param.readonly) {
                // 对比合约（KLine）/ DataFrame 这类参数**只能看不能改**：
                // 菜单回传的是字符串，写回去会把原对象弄丢 ✗
                input.readOnly = true;
                input.disabled = true;
                row.classList.add('is-readonly');
                row.title = '对象参数（不可编辑）';
                continue;
            }
            fields.push({ name: param.name, type: param.type || '', input });
        }
        const confirm = () => {
            const values: { [key: string]: any } = {};
            for (const field of fields) {
                values[field.name] = this.coerce(field.input.value, field.type);
            }
            this.apply('params', { values });
            this.hide();
        };
        for (const field of fields) {
            field.input.addEventListener('keydown', (event: KeyboardEvent) => {
                if (event.key === 'Enter') confirm();
            });
        }
        const button = document.createElement('div');
        button.classList.add('legend-menu-confirm');
        button.textContent = '▶ ' + this.label('confirm', '确认');
        button.addEventListener('click', (event: MouseEvent) => {
            event.stopPropagation();
            confirm();
        });
        parent.appendChild(button);
    }

    private coerce(raw: string, type: string): any {
        const kind = (type || '').toLowerCase();
        const text = (raw || '').trim();
        if (kind.includes('bool')) {
            return ['1', 'true', 'yes', 'on', 't', '是'].includes(text.toLowerCase());
        }
        if (kind.includes('int')) {
            const value = parseInt(text, 10);
            return isNaN(value) ? text : value;
        }
        if (kind.includes('float') || kind.includes('num')) {
            const value = parseFloat(text);
            return isNaN(value) ? text : value;
        }
        if (text !== '' && !isNaN(Number(text))) return Number(text);
        return raw;
    }

    private apply(kind: string, payload: any, hide = true) {
        if (hide) this.hide();
        try {
            this.applySeries(kind, payload);
        } catch (error) { /* keep the menu usable even if the series is gone */ }
        try {
            const info = { ...(payload || {}),
                source: (this.config as { source?: string }).source || '' };
            window.callbackFunction(
                `${this.callbackName}_~_${this.seriesId};;;${kind};;;${JSON.stringify(info)}`);
        } catch (error) { /* no python bridge (static export) */ }
    }

    private applySeries(kind: string, payload: any) {
        const series: any = this.series;
        if (kind === 'style') {
            const value = STYLE_VALUE[payload.value];
            series.applyOptions({ lineStyle: value === undefined ? 0 : value });
        } else if (kind === 'width') {
            series.applyOptions({ lineWidth: Number(payload.value) });
        } else if (kind === 'color') {
            const color = payload.value;
            if (this.config.isArea) {
                series.applyOptions({
                    lineColor: color,
                    topColor: color + '55',
                    bottomColor: color + '00',
                });
            } else {
                series.applyOptions({ color });
            }
        } else if (kind === 'price') {
            series.applyOptions({
                priceLineVisible: !!payload.priceLine,
                lastValueVisible: !!payload.priceLabel,
            });
        }
    }
}

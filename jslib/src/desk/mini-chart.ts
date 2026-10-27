/**
 * MiniChart —— 设置页里的小折线图（纯 SVG，无依赖 ✓）
 *
 * 用于「模拟账户」的分析区：
 * * 账户权益曲线（一条线）；
 * * 各品种累计平仓盈亏（每条线一个品种）；
 * * 自动画坐标轴 / 网格 / 图例 / 悬浮提示。
 *
 * 数据格式：`points` 是 `[label, value]` 数组（label 是时间字符串 ✓）。
 */
export interface MiniSeries {
    name: string;
    color?: string;
    points: Array<[string, number]>;
}

export interface MiniChartOptions {
    height?: number;
    /** Y 轴数值格式化（默认保留 2 位） */
    format?: (value: number) => string;
    /** 曲线下方的填充（权益曲线用 ✓） */
    area?: boolean;
    /** 零轴（盈亏图用 ✓） */
    zeroLine?: boolean;
    empty?: string;
}

/** 默认配色（和指标配色同一套 ✓） */
const PALETTE = ['#2962ff', '#f23645', '#089981', '#ff9800', '#9c27b0',
                 '#00bcd4', '#e91e63', '#7c4dff', '#8d6e63', '#607d8b'];

const SVG_NS = 'http://www.w3.org/2000/svg';

/** 每张图的参数 / ResizeObserver：页面从隐藏变可见时按**真实宽度**重画 ✓ */
const chartState = new WeakMap<HTMLElement, {
    series: MiniSeries[]; options: MiniChartOptions;
}>();
const chartObserver = new WeakMap<HTMLElement, ResizeObserver>();

function escapeText(text: string): string {
    return String(text).replace(/[&<>"]/g, (char) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char] || char));
}

/**
 * 画一张小折线图（返回值 = 配色表，方便外面画图例 ✓）
 */
export function renderMiniChart(host: HTMLElement,
                                series: MiniSeries[],
                                options: MiniChartOptions = {}): void {
    // 保存最新参数：宿主宽度变化（设置页从隐藏 tab 切回来）时重画。
    chartState.set(host, { series, options });
    if (typeof ResizeObserver !== 'undefined' && !chartObserver.has(host)) {
        const observer = new ResizeObserver(() => {
            const state = chartState.get(host);
            if (!state) return;
            const width = Math.max(240, host.clientWidth || 0);
            const drawn = Number(host.dataset.miniWidth || 0);
            if (width > 0 && Math.abs(width - drawn) > 2) {
                renderMiniChart(host, state.series, state.options);
            }
        });
        observer.observe(host);
        chartObserver.set(host, observer);
    }
    host.textContent = '';
    host.classList.add('desk-mini-chart');
    const height = Number(options.height) || 160;
    const format = options.format || ((value: number) => value.toFixed(2));
    const valid = series
        .map((item, index) => ({
            name: String(item.name || `曲线 ${index + 1}`),
            color: item.color || PALETTE[index % PALETTE.length],
            points: (item.points || [])
                .map((point) => {
                    const value = Number(Array.isArray(point) ? point[1]
                        : point);
                    const label = Array.isArray(point) ? String(point[0]) : '';
                    return { label, value };
                })
                .filter((point) => Number.isFinite(point.value)),
        }))
        .filter((item) => item.points.length > 0);
    if (!valid.length) {
        const empty = document.createElement('div');
        empty.className = 'desk-mini-chart-empty';
        empty.textContent = options.empty || '暂无数据';
        host.appendChild(empty);
        return;
    }
    const values: number[] = [];
    let first = '';
    let last = '';
    for (const item of valid) {
        for (const point of item.points) values.push(point.value);
        const head = item.points[0].label;
        const tail = item.points[item.points.length - 1].label;
        if (!first && head) first = head;
        if (tail) last = tail;
    }
    if (options.zeroLine) {
        values.push(0);
    }
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
        min = 0;
        max = 1;
    }
    if (Math.abs(max - min) < 1e-9) {
        const pad = Math.abs(max) > 0 ? Math.abs(max) * 0.05 : 1;
        min -= pad;
        max += pad;
    }
    const pad = (max - min) * 0.12;
    min -= pad;
    max += pad;

    // ★ 用宿主的**真实宽度**做 viewBox；宽度为 0（隐藏页）时先给 600，
    //   ResizeObserver 在可见后会按真实宽度重画。以前固定 600 直接铺满
    //   宽容器 → SVG 里的字号 / 线宽被整体放大（用户实测 ✗）。
    const width = Math.max(240, host.clientWidth || 0) || 600;
    host.dataset.miniWidth = String(width);
    const left = 76;
    const right = 10;
    const top = 8;
    const bottom = 20;
    const innerW = Math.max(10, width - left - right);
    const innerH = Math.max(20, height - top - bottom);
    const count = Math.max(1, Math.max(...valid.map((item) => item.points.length)) - 1);
    const scaleX = (index: number) => left + (index / count) * innerW;
    const scaleY = (value: number) => top + (1 - (value - min) / (max - min)) * innerH;

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'desk-mini-chart-svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', String(height));
    svg.setAttribute('preserveAspectRatio', 'none');

    // 网格 + Y 轴刻度（4 档 ✓）
    for (let step = 0; step <= 3; step += 1) {
        const value = min + ((max - min) * step) / 3;
        const y = scaleY(value);
        const line = document.createElementNS(SVG_NS, 'line');
        line.setAttribute('x1', String(left));
        line.setAttribute('x2', String(left + innerW));
        line.setAttribute('y1', String(y));
        line.setAttribute('y2', String(y));
        line.setAttribute('class', 'desk-mini-chart-grid');
        svg.appendChild(line);
        const text = document.createElementNS(SVG_NS, 'text');
        text.setAttribute('x', String(left - 6));
        text.setAttribute('y', String(y + 3));
        text.setAttribute('text-anchor', 'end');
        text.setAttribute('class', 'desk-mini-chart-axis');
        text.textContent = format(value);
        svg.appendChild(text);
    }
    // 零轴
    if (options.zeroLine && min < 0 && max > 0) {
        const y = scaleY(0);
        const line = document.createElementNS(SVG_NS, 'line');
        line.setAttribute('x1', String(left));
        line.setAttribute('x2', String(left + innerW));
        line.setAttribute('y1', String(y));
        line.setAttribute('y2', String(y));
        line.setAttribute('class', 'desk-mini-chart-zero');
        svg.appendChild(line);
    }
    // 曲线
    for (const item of valid) {
        // 只有一个点（初始权益 / 刚重置账户）时画一条水平线，
        // 不要只留一个看不见的点（用户反馈“曲线有问题” ✗）。
        const points = item.points.length === 1
            ? `${left},${scaleY(item.points[0].value)} `
                + `${left + innerW},${scaleY(item.points[0].value)}`
            : item.points
                .map((point, index) => `${scaleX(index)},${scaleY(point.value)}`)
                .join(' ');
        if (options.area && item.points.length > 1) {
            const area = document.createElementNS(SVG_NS, 'polygon');
            area.setAttribute('points',
                `${left},${scaleY(min)} ${points} `
                + `${scaleX(item.points.length - 1)},${scaleY(min)}`);
            area.setAttribute('fill', item.color);
            area.setAttribute('opacity', '0.12');
            area.setAttribute('stroke', 'none');
            svg.appendChild(area);
        }
        const path = document.createElementNS(SVG_NS, 'polyline');
        path.setAttribute('points', points);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', item.color);
        path.setAttribute('stroke-width', '1.6');
        path.setAttribute('stroke-linejoin', 'round');
        path.setAttribute('stroke-linecap', 'round');
        svg.appendChild(path);
        // 末端小圆点
        const tail = item.points[item.points.length - 1];
        const dot = document.createElementNS(SVG_NS, 'circle');
        dot.setAttribute('cx', String(item.points.length === 1
            ? left + innerW : scaleX(item.points.length - 1)));
        dot.setAttribute('cy', String(scaleY(tail.value)));
        dot.setAttribute('r', '2.6');
        dot.setAttribute('fill', item.color);
        svg.appendChild(dot);
    }
    // X 轴：首 / 尾时间
    for (const [anchor, text, x] of [
            ['start', first, left],
            ['end', last, left + innerW]] as const) {
        if (!text) continue;
        const node = document.createElementNS(SVG_NS, 'text');
        node.setAttribute('x', String(x));
        node.setAttribute('y', String(height - 5));
        node.setAttribute('text-anchor', anchor);
        node.setAttribute('class', 'desk-mini-chart-axis');
        node.textContent = text;
        svg.appendChild(node);
    }
    host.appendChild(svg);

    // 多条线 → 画图例 ✓
    if (valid.length > 1) {
        const legend = document.createElement('div');
        legend.className = 'desk-mini-chart-legend';
        for (const item of valid) {
            const chip = document.createElement('span');
            chip.className = 'desk-mini-chart-chip';
            const dot = document.createElement('i');
            dot.style.background = item.color;
            const label = document.createElement('span');
            label.textContent = item.name;
            chip.append(dot, label);
            legend.appendChild(chip);
        }
        host.appendChild(legend);
    }
    void escapeText;
}

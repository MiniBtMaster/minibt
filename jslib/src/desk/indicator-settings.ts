/**
 * IndicatorSettings — 指标「设置」菜单（复刻 minibt 实时图的指标菜单）。
 *
 * ```
 * ┌ MA20 指标参数 ─────────┐
 * │ 参数                    │
 * │  length   [ 20 ]        │
 * │ 样式                    │
 * │  线型 [实线 ▾]  线宽 [2 ▾] │
 * │  颜色 ●●●●●●●●●●●●●     │
 * │ 显示                    │
 * │  ☑ 价格线   ☑ 价格标签   │
 * │  ☑ 显示该指标            │
 * │ [删除指标]              │
 * └────────────────────────┘
 * ```
 *
 * 由 :class:`~jslib/src/desk/indicator.ts` 的 👁 行旁边的 ⚙ 打开。
 */
import { ensureStyle } from '../panels/emit';

export const LINE_STYLES: Array<[string, number]> = [
    ['实线', 0], ['点线', 1], ['虚线', 2], ['大虚线', 3], ['稀疏点线', 4],
];

export const LINE_WIDTHS = [1, 2, 3, 4];

export const LINE_COLORS = [
    '#f6c343', '#2196f3', '#e91e63', '#26a69a', '#9c27b0', '#ff9800',
    '#00bcd4', '#8bc34a', '#ef5350', '#90a4ae',
];

const STYLE_ID = 'desk-indicator-settings-style';

const CSS = `
.desk-is {
    position: fixed;
    z-index: 13200;
    width: 232px;
    padding: 8px 10px 10px;
    border-radius: 8px;
    border: 1px solid var(--is-border);
    background: var(--is-bg);
    color: var(--is-text);
    box-shadow: 0 14px 36px rgba(0, 0, 0, .45);
    font-size: 11.5px;
}

.desk-is-title {
    font-weight: 600;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.desk-is-close { border: none; background: transparent; color: var(--is-muted);
    cursor: pointer; font-size: 12px; }

.desk-is-group { color: var(--is-muted); margin: 6px 0 3px; font-size: 10.5px; }

.desk-is-row { display: flex; align-items: center; justify-content: space-between;
    gap: 8px; margin-bottom: 4px; }

.desk-is-label { color: var(--is-muted); }

.desk-is-input, .desk-is-select {
    width: 88px; height: 22px; padding: 0 6px; text-align: right;
    border-radius: 4px; border: 1px solid var(--is-border);
    background: var(--is-input); color: var(--is-text); font-size: 11.5px;
    outline: none;
}

.desk-is-select { text-align: left; }

.desk-is-colors { display: flex; flex-wrap: wrap; gap: 4px; margin: 2px 0 4px; }

.desk-is-color {
    width: 14px; height: 14px; border-radius: 3px; cursor: pointer;
    border: 1px solid transparent;
}

.desk-is-color.on { border-color: var(--is-text); }
/* 颜色行末尾的调色板按钮（＋ = 打开取色窗口 ✓） */
.desk-is-color-custom {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: var(--is-input);
    border-style: dashed;
}
.desk-is-color-custom.on { border-style: solid; }
.desk-is-color-plus {
    font-size: 12px;
    line-height: 1;
    color: var(--is-muted);
    pointer-events: none;
}
.desk-is-color-input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    border: 0;
    padding: 0;
    cursor: pointer;
}

.desk-is-actions { display: flex; justify-content: space-between; gap: 6px;
    margin-top: 8px; }

.desk-is-btn { height: 24px; padding: 0 10px; border-radius: 4px; cursor: pointer;
    border: 1px solid var(--is-border); background: transparent;
    color: var(--is-text); font-size: 11.5px; }

.desk-is-btn.danger { color: #ef5350; border-color: #ef5350; }

.desk-is-btn.primary { background: var(--is-accent); border-color: var(--is-accent);
    color: #fff; }
`;

const PALS = {
    dark: {
        bg: '#161a20', text: '#d8d9db', muted: '#8b93a1', border: '#262c36',
        input: '#0f1115', accent: '#2962ff',
    },
    light: {
        bg: '#ffffff', text: '#1f2329', muted: '#6b7280', border: '#e3e6ea',
        input: '#f6f7f9', accent: '#1a73e8',
    },
};

export interface IndicatorStyleState {
    params: Record<string, unknown>;
    lineStyle: number;
    lineWidth: number;
    color: string;
    priceLine: boolean;
    priceLabel: boolean;
    visible: boolean;
    /** 坐标轴：十字线标记（TradingView「坐标轴」页 ✓） */
    crosshairMarker: boolean;
    /** 显示区域：true = 主图叠加，false = 独立副图 ✓ */
    overlay: boolean;
    /**
     * ★ 该指标**主图 + 副图都有线**（`overlap` 是 True/False 混合的字典）
     *   → 「位置」显示「主副图」且不可改（用户要求 ✓）。
     */
    overlayLocked?: boolean;
}

export interface ParamMeta {
    type?: string;
    min?: number;
    max?: number;
    step?: number;
}

export interface IndicatorSettingsHooks {
    onApply: (state: IndicatorStyleState) => void;
    onDelete: () => void;
    /** 选颜色时**立即预览**（不用等「应用」；用户要求 ✓） */
    onColorPreview?: (color: string) => void;
}

let current: HTMLDivElement | null = null;

export function closeIndicatorSettings(): void {
    current?.remove();
    current = null;
}

export function openIndicatorSettings(
    anchor: HTMLElement | null,
    title: string,
    state: IndicatorStyleState,
    hooks: IndicatorSettingsHooks,
    theme: 'light' | 'dark' = 'dark',
    paramMeta: Record<string, ParamMeta> = {},
): void {
    ensureStyle(STYLE_ID, CSS);
    closeIndicatorSettings();

    const box = document.createElement('div');
    box.className = 'desk-is';
    const pal = PALS[theme === 'light' ? 'light' : 'dark'];
    for (const [key, value] of Object.entries(pal)) {
        box.style.setProperty(`--is-${key}`, value);
    }

    const titleRow = document.createElement('div');
    titleRow.className = 'desk-is-title';
    titleRow.innerHTML = `<span>${title} 指标参数</span>`;
    const close = document.createElement('button');
    close.className = 'desk-is-close';
    close.textContent = '✕';
    close.title = '关闭';
    close.addEventListener('click', () => closeIndicatorSettings());
    titleRow.appendChild(close);
    box.appendChild(titleRow);

    // ---- 参数 ----
    const inputs = new Map<string, HTMLInputElement>();
    const kinds = new Map<string, string>();
    const paramNames = Object.keys(state.params || {});
    if (paramNames.length) {
        const group = document.createElement('div');
        group.className = 'desk-is-group';
        group.textContent = '参数';
        box.appendChild(group);
        for (const name of paramNames) {
            const value = state.params[name];
            const row = document.createElement('label');
            row.className = 'desk-is-row';
            const label = document.createElement('span');
            label.className = 'desk-is-label';
            label.textContent = name;
            const input = document.createElement('input');
            input.className = 'desk-is-input';
            input.value = String(value ?? '');
            const meta = paramMeta[name] || {};
            const isNumber = typeof value === 'number';
            if (isNumber) {
                // ★ 参数区间（模板 / 优化入口也用它 ✓）
                input.type = 'number';
                if (meta.min !== undefined) input.min = String(meta.min);
                if (meta.max !== undefined) input.max = String(meta.max);
                input.step = String(meta.step ?? 1);
            }
            input.title = meta.min !== undefined
                ? `${title}.${name}（${meta.min} ~ ${meta.max}，步长 ${meta.step}）`
                : `${title}.${name}`;
            kinds.set(name, typeof value === 'number' ? 'number'
                : (typeof value === 'boolean' ? 'bool' : 'str'));
            inputs.set(name, input);
            row.append(label, input);
            box.appendChild(row);
        }
    }

    // ---- 样式 ----
    const styleGroup = document.createElement('div');
    styleGroup.className = 'desk-is-group';
    styleGroup.textContent = '样式';
    box.appendChild(styleGroup);

    const styleRow = document.createElement('div');
    styleRow.className = 'desk-is-row';
    const styleLabel = document.createElement('span');
    styleLabel.className = 'desk-is-label';
    styleLabel.textContent = '线型 / 线宽';
    const styleSelect = document.createElement('select');
    styleSelect.className = 'desk-is-select';
    styleSelect.style.width = '66px';
    for (const [label, value] of LINE_STYLES) {
        const option = document.createElement('option');
        option.value = String(value);
        option.textContent = label;
        if (Number(state.lineStyle) === value) option.selected = true;
        styleSelect.appendChild(option);
    }
    const widthSelect = document.createElement('select');
    widthSelect.className = 'desk-is-select';
    widthSelect.style.width = '42px';
    for (const width of LINE_WIDTHS) {
        const option = document.createElement('option');
        option.value = String(width);
        option.textContent = String(width);
        if (Number(state.lineWidth) === width) option.selected = true;
        widthSelect.appendChild(option);
    }
    styleRow.append(styleLabel, styleSelect, widthSelect);
    box.appendChild(styleRow);

    const colors = document.createElement('div');
    colors.className = 'desk-is-colors';
    let chosen = state.color || LINE_COLORS[0];
    // ★ 选颜色就**立即上看**（不用等「应用」）—— 以前只在点「应用」时
    //   才写进序列，用户以为“选了颜色没反应”（用户实测 ✗）。
    const preview = () => {
        try {
            hooks.onColorPreview?.(chosen);
        } catch {
            /* ignore */
        }
    };
    for (const color of LINE_COLORS) {
        const chip = document.createElement('span');
        chip.className = 'desk-is-color'
            + (color.toLowerCase() === chosen.toLowerCase() ? ' on' : '');
        chip.style.background = color;
        chip.title = color;
        chip.addEventListener('click', () => {
            chosen = color;
            colors.querySelectorAll('.desk-is-color')
                .forEach((node) => node.classList.remove('on'));
            chip.classList.add('on');
            preview();
        });
        colors.appendChild(chip);
    }
    // ★ 颜色行末尾的「调色板」按钮：点开系统的三色（RGB）取色窗口，
    //   可以挑列表里没有的颜色（用户要求 ✓）
    const custom = document.createElement('label');
    custom.className = 'desk-is-color desk-is-color-custom';
    custom.title = '其它颜色（打开调色板）';
    custom.innerHTML = '<span class="desk-is-color-plus">＋</span>';
    const picker = document.createElement('input');
    picker.type = 'color';
    picker.className = 'desk-is-color-input';
    picker.value = chosen;
    picker.addEventListener('input', () => {
        chosen = picker.value;
        colors.querySelectorAll('.desk-is-color')
            .forEach((node) => node.classList.remove('on'));
        custom.classList.add('on');
        custom.style.background = chosen;
        if (plus) plus.style.opacity = '0.9';
        preview();
    });
    custom.addEventListener('click', (event) => {
        // 点哪个位置都打开取色器（有些浏览器只认 input 本体 ✓）
        if (event.target !== picker) {
            event.preventDefault();
            picker.click();
        }
    });
    const plus = custom.querySelector('.desk-is-color-plus') as
        HTMLElement | null;
    // 已经是自定义色 → 直接把按钮显示成那个颜色 ✓
    if (!LINE_COLORS.some((color) =>
            color.toLowerCase() === String(chosen).toLowerCase())) {
        custom.classList.add('on');
        custom.style.background = chosen;
        if (plus) plus.style.opacity = '0.9';
    }
    custom.appendChild(picker);
    colors.appendChild(custom);
    box.appendChild(colors);

    // ---- 显示开关 ----
    const showGroup = document.createElement('div');
    showGroup.className = 'desk-is-group';
    showGroup.textContent = '显示';
    box.appendChild(showGroup);
    const toggles = new Map<string, HTMLInputElement>();
    for (const [key, label, value] of [
            ['visible', '显示该指标', state.visible]] as const) {
        const row = document.createElement('label');
        row.className = 'desk-is-row';
        const text = document.createElement('span');
        text.className = 'desk-is-label';
        text.textContent = label;
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = !!value;
        toggles.set(key, input);
        row.append(text, input);
        box.appendChild(row);
    }

    // ---- 坐标轴 ----
    const axisGroup = document.createElement('div');
    axisGroup.className = 'desk-is-group';
    axisGroup.textContent = '坐标轴';
    box.appendChild(axisGroup);
    for (const [key, label, value] of [
            ['priceLabel', '价格标签', state.priceLabel],
            ['priceLine', '价格线', state.priceLine],
            ['crosshairMarker', '十字线标记',
             state.crosshairMarker !== false]] as const) {
        const row = document.createElement('label');
        row.className = 'desk-is-row';
        const text = document.createElement('span');
        text.className = 'desk-is-label';
        text.textContent = label;
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = !!value;
        toggles.set(key, input);
        row.append(text, input);
        box.appendChild(row);
    }

    // ---- 显示区域（主图 / 副图）----
    const areaGroup = document.createElement('div');
    areaGroup.className = 'desk-is-group';
    areaGroup.textContent = '显示区域';
    box.appendChild(areaGroup);
    const areaRow = document.createElement('div');
    areaRow.className = 'desk-is-row';
    const areaLabel = document.createElement('span');
    areaLabel.className = 'desk-is-label';
    areaLabel.textContent = '位置';
    const areaSelect = document.createElement('select');
    areaSelect.className = 'desk-is-select';
    // ★ 三条线**主副图都有**（`overlap` 是混合字典）→ 显示「主副图」且
    //   不可改；只有全部在主图 / 全部在副图时才能切（用户要求 ✓）。
    const locked = !!state.overlayLocked;
    const areaChoice = locked ? 'mixed' : (state.overlay ? '1' : '0');
    for (const [value, label] of [
            ['1', '主图叠加'], ['0', '独立副图'], ['mixed', '主副图']]) {
        const option = document.createElement('option');
        option.value = String(value);
        option.textContent = String(label);
        if (value === areaChoice) option.selected = true;
        areaSelect.appendChild(option);
    }
    areaSelect.disabled = locked;
    areaSelect.title = locked
        ? '这个指标的主图和副图都有线，位置不能单独改'
        : '主图叠加 / 独立副图（切换后会重新加这个指标）';
    areaRow.append(areaLabel, areaSelect);
    box.appendChild(areaRow);

    // ---- 按钮 ----
    const actions = document.createElement('div');
    actions.className = 'desk-is-actions';
    const drop = document.createElement('button');
    drop.className = 'desk-is-btn danger';
    drop.textContent = '删除指标';
    drop.title = '把这个指标从图上删掉';
    drop.addEventListener('click', () => {
        closeIndicatorSettings();
        hooks.onDelete();
    });
    const ok = document.createElement('button');
    ok.className = 'desk-is-btn primary';
    ok.textContent = '应用';
    ok.title = '应用这些设置';
    ok.addEventListener('click', () => {
        const params: Record<string, unknown> = {};
        for (const [name, input] of inputs) {
            const kind = kinds.get(name);
            const raw = input.value.trim();
            if (kind === 'number') {
                const number = Number(raw);
                if (!Number.isFinite(number)) {
                    input.focus();
                    return;
                }
                params[name] = number;
            } else if (kind === 'bool') {
                params[name] = raw === 'true' || raw === '1';
            } else {
                params[name] = raw;
            }
        }
        closeIndicatorSettings();
        hooks.onApply({
            params,
            lineStyle: Number(styleSelect.value),
            lineWidth: Number(widthSelect.value),
            color: chosen,
            priceLine: !!toggles.get('priceLine')?.checked,
            priceLabel: !!toggles.get('priceLabel')?.checked,
            visible: !!toggles.get('visible')?.checked,
            crosshairMarker: !!toggles.get('crosshairMarker')?.checked,
            // 固定时（主副图都有线）不把 'mixed' 当成“改成副图”✓
            overlay: locked ? state.overlay
                : Number(areaSelect.value) === 1,
            overlayLocked: locked,
        });
    });
    actions.append(drop, ok);
    box.appendChild(actions);

    document.body.appendChild(box);
    current = box;

    const rect = anchor?.getBoundingClientRect();
    const boxRect = box.getBoundingClientRect();
    const left = rect
        ? Math.min(rect.right + 6, window.innerWidth - boxRect.width - 8)
        : 120;
    const top = rect
        ? Math.min(rect.top, window.innerHeight - boxRect.height - 8)
        : 120;
    box.style.left = `${Math.max(8, left)}px`;
    box.style.top = `${Math.max(8, top)}px`;

    const dismiss = (event: MouseEvent) => {
        if (current && !current.contains(event.target as Node)
            && !anchor?.contains(event.target as Node)) {
            closeIndicatorSettings();
            document.removeEventListener('mousedown', dismiss);
        }
    };
    document.addEventListener('mousedown', dismiss);
}

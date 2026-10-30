/**
 * ParamPopover — 指标参数**就地编辑**（替代 `window.prompt`，复刻 TradingView 的
 * 「指标设置」小面板 ✓）。
 *
 * ```
 *        ⚙ ← 点这里
 *   ┌───────────────────────┐
 *   │ MA20 参数           ✕ │
 *   │ length  [ 20 ]        │
 *   │            [取消][确定]│
 *   └───────────────────────┘
 * ```
 */
import { ensureStyle } from '../panels/emit';

const STYLE_ID = 'desk-param-popover-style';

const CSS = `
.desk-pp {
    position: fixed;
    z-index: 13000;
    min-width: 190px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--pp-border);
    background: var(--pp-bg);
    color: var(--pp-text);
    box-shadow: 0 12px 32px rgba(0, 0, 0, .4);
    font-size: 11.5px;
}

.desk-pp-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
    font-weight: 600;
}

.desk-pp-close {
    border: none;
    background: transparent;
    color: var(--pp-muted);
    cursor: pointer;
    font-size: 12px;
}

.desk-pp-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 5px;
}

.desk-pp-row .k { color: var(--pp-muted); }

.desk-pp-input {
    width: 84px;
    height: 22px;
    padding: 0 6px;
    text-align: right;
    border-radius: 4px;
    border: 1px solid var(--pp-border);
    background: var(--pp-input);
    color: var(--pp-text);
    font-size: 11.5px;
    outline: none;
}

.desk-pp-input:focus { border-color: var(--pp-accent); }

.desk-pp-actions {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    margin-top: 8px;
}

.desk-pp-btn {
    height: 24px;
    padding: 0 10px;
    border-radius: 4px;
    cursor: pointer;
    border: 1px solid var(--pp-border);
    background: transparent;
    color: var(--pp-text);
    font-size: 11.5px;
}

.desk-pp-btn.primary {
    background: var(--pp-accent);
    border-color: var(--pp-accent);
    color: #fff;
}
`;

const PALS = {
    dark: {
        bg: '#161a20', text: '#d8d9db', muted: '#8b93a1',
        border: '#262c36', input: '#0f1115', accent: '#2962ff',
    },
    light: {
        bg: '#ffffff', text: '#1f2329', muted: '#6b7280',
        border: '#e3e6ea', input: '#f6f7f9', accent: '#1a73e8',
    },
};

let current: HTMLDivElement | null = null;
let dismissHandler: ((event: MouseEvent) => void) | null = null;

export function closeParamPopover(): void {
    if (dismissHandler) {
        document.removeEventListener('mousedown', dismissHandler);
        dismissHandler = null;
    }
    current?.remove();
    current = null;
}

/**
 * 打开参数编辑浮层。
 *
 * @param anchor    ⚙ 按钮（浮层贴着它显示）
 * @param title     标题（如 `MA20 参数`）
 * @param params    当前参数（数字/布尔/文本都支持）
 * @param onSave    确定 → 回传新参数（取消不回调）
 */
export function openParamPopover(
    anchor: HTMLElement | null,
    title: string,
    params: Record<string, unknown>,
    onSave: (values: Record<string, unknown>) => void,
    theme: 'light' | 'dark' = 'dark',
): void {
    ensureStyle(STYLE_ID, CSS);
    closeParamPopover();

    const box = document.createElement('div');
    box.className = 'desk-pp';
    const pal = PALS[theme === 'light' ? 'light' : 'dark'];
    for (const [key, value] of Object.entries(pal)) {
        box.style.setProperty(`--pp-${key}`, value);
    }

    const head = document.createElement('div');
    head.className = 'desk-pp-head';
    const label = document.createElement('span');
    label.textContent = `${title} 参数`;
    const close = document.createElement('button');
    close.className = 'desk-pp-close';
    close.textContent = '✕';
    close.title = '关闭（不保存）';
    close.addEventListener('click', () => closeParamPopover());
    head.append(label, close);

    const inputs = new Map<string, HTMLInputElement>();
    const kinds = new Map<string, string>();
    for (const [name, value] of Object.entries(params)) {
        const row = document.createElement('label');
        row.className = 'desk-pp-row';
        const text = document.createElement('span');
        text.className = 'k';
        text.textContent = name;
        const input = document.createElement('input');
        input.className = 'desk-pp-input';
        input.value = String(value ?? '');
        input.title = `${title}.${name}`;
        kinds.set(name, typeof value === 'number' ? 'number'
            : (typeof value === 'boolean' ? 'bool' : 'str'));
        inputs.set(name, input);
        row.append(text, input);
        box.appendChild(row);
    }
    box.insertBefore(head, box.firstChild);

    const actions = document.createElement('div');
    actions.className = 'desk-pp-actions';
    const cancel = document.createElement('button');
    cancel.className = 'desk-pp-btn';
    cancel.textContent = '取消';
    cancel.addEventListener('click', () => closeParamPopover());
    const ok = document.createElement('button');
    ok.className = 'desk-pp-btn primary';
    ok.textContent = '确定';
    ok.title = '应用新参数（会重新计算指标）';
    ok.addEventListener('click', () => {
        const values: Record<string, unknown> = {};
        for (const [name, input] of inputs) {
            const kind = kinds.get(name);
            const raw = input.value.trim();
            if (kind === 'number') {
                const number = Number(raw);
                if (!Number.isFinite(number)) {
                    input.focus();
                    return;                        // 非法数字不关框 ✓
                }
                values[name] = number;
            } else if (kind === 'bool') {
                values[name] = raw === 'true' || raw === '1';
            } else {
                values[name] = raw;
            }
        }
        closeParamPopover();
        onSave(values);
    });
    actions.append(cancel, ok);
    box.appendChild(actions);

    document.body.appendChild(box);
    current = box;

    // 贴着 ⚙ 显示，并夹在视口里 ✓
    const rect = anchor?.getBoundingClientRect();
    const boxRect = box.getBoundingClientRect();
    const left = rect
        ? Math.min(rect.left, window.innerWidth - boxRect.width - 8)
        : window.innerWidth / 2 - boxRect.width / 2;
    const top = rect
        ? Math.min(rect.bottom + 6, window.innerHeight - boxRect.height - 8)
        : 120;
    box.style.left = `${Math.max(8, left)}px`;
    box.style.top = `${Math.max(8, top)}px`;

    const first = inputs.values().next().value as HTMLInputElement | undefined;
    first?.focus();
    first?.select();

    const dismiss = (event: MouseEvent) => {
        if (current && !current.contains(event.target as Node)
            && !anchor?.contains(event.target as Node)) {
            closeParamPopover();
        }
    };
    dismissHandler = dismiss;
    document.addEventListener('mousedown', dismiss);
}

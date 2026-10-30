/**
 * IndicatorMenu — 完整指标库（459 个）的搜索式菜单 + 参数表单。
 *
 * 目录由后端反射 `minibt.indicators` 生成（`indicator_menu` 补丁），
 * 这里只负责：搜索 / 分组 / 点选 / 参数输入（默认值来自后端签名）。
 */
export interface CatalogParam {
    name: string;
    label?: string;
    default: unknown;
    type?: 'int' | 'float' | 'bool' | 'str';
}

export interface CatalogItem {
    key: string;
    label: string;
    group?: string;
    overlap?: boolean;
    params?: CatalogParam[];
}

let panel: HTMLDivElement | null = null;
let dismissHandler: ((event: MouseEvent) => void) | null = null;

export function closeIndicatorMenu(): void {
    if (dismissHandler) {
        document.removeEventListener('mousedown', dismissHandler);
        dismissHandler = null;
    }
    panel?.remove();
    panel = null;
}

/** 打开指标菜单（`anchor` 为空 → 屏幕左上角附近 ✓） */
export interface PersonalHooks {
    onImport?: (kind: 'indicator' | 'strategy') => void;
    onManage?: () => void;
    onClear?: () => void;
}

export function openIndicatorMenu(
    anchor: HTMLElement | null,
    items: CatalogItem[],
    onPick: (key: string, params: Record<string, unknown>) => void,
    hooks: PersonalHooks = {},
): void {
    closeIndicatorMenu();
    const box = document.createElement('div');
    box.className = 'desk-ind-menu';

    const search = document.createElement('input');
    search.className = 'desk-input desk-ind-search';
    search.placeholder = `搜索指标（${items.length} 个）…`;
    search.addEventListener('input', () => render(search.value));

    const list = document.createElement('div');
    list.className = 'desk-ind-list';

    box.appendChild(search);
    box.appendChild(list);
    const footer = document.createElement('div');
    footer.className = 'desk-ind-footer';
    const addButton = (label: string, title: string, run: () => void) => {
        const button = document.createElement('button');
        button.className = 'desk-tool';
        button.textContent = label;
        button.title = title;
        button.addEventListener('click', () => {
            closeIndicatorMenu();
            run();
        });
        footer.appendChild(button);
    };
    if (hooks.onImport) {
        addButton('添加个人指标', '收录个人指标目录（持久化，下次自动加载）',
            () => hooks.onImport?.('indicator'));
        addButton('添加个人策略', '收录个人策略目录（持久化，下次自动加载）',
            () => hooks.onImport?.('strategy'));
    }
    if (hooks.onManage) {
        addButton('个人指标策略管理', '查看 / 删除已收录的目录（默认目录不显示）',
            hooks.onManage);
    }
    if (hooks.onClear) addButton('清空', '清空本图指标', hooks.onClear);
    if (footer.childElementCount) box.appendChild(footer);
    document.body.appendChild(box);
    panel = box;

    const at = anchor?.getBoundingClientRect();
    const width = 300;
    const height = Math.min(420, window.innerHeight - 80);
    box.style.width = `${width}px`;
    box.style.height = `${height}px`;
    box.style.left = `${Math.max(8, Math.min(
        at ? at.left : 80, window.innerWidth - width - 8))}px`;
    box.style.top = `${Math.max(8, Math.min(
        at ? at.bottom + 4 : 80, window.innerHeight - height - 8))}px`;

    const dismiss = (event: MouseEvent) => {
        if (panel && !panel.contains(event.target as Node)) {
            closeIndicatorMenu();
        }
    };
    dismissHandler = dismiss;
    document.addEventListener('mousedown', dismiss);

    function render(keyword: string): void {
        const needle = keyword.trim().toLowerCase();
        list.textContent = '';
        let lastGroup = '';
        const matched = items.filter((item) => !needle
            || item.key.toLowerCase().includes(needle)
            || item.label.toLowerCase().includes(needle));
        for (const item of matched) {
            const group = item.group || '其他';
            if (group !== lastGroup) {
                const header = document.createElement('div');
                header.className = 'desk-ind-group';
                header.textContent = group;
                list.appendChild(header);
                lastGroup = group;
            }
            const row = document.createElement('div');
            row.className = 'desk-ind-item';
            row.title = item.key;
            row.textContent = item.label;
            if (item.overlap) {
                const tag = document.createElement('span');
                tag.className = 'desk-ind-tag';
                tag.textContent = '主图';
                row.appendChild(tag);
            }
            row.addEventListener('click', async () => {
                const params = await askParams(item);
                if (params === null) return;          // 取消
                closeIndicatorMenu();
                onPick(item.key, params);
            });
            list.appendChild(row);
        }
        if (!matched.length) {
            const empty = document.createElement('div');
            empty.className = 'desk-ind-empty';
            empty.textContent = '没有匹配的指标';
            list.appendChild(empty);
        }
    }

    render('');
    search.focus();
}

/** 参数表单（默认值来自后端签名；取消 → null ✓） */
export function askParams(
    item: CatalogItem,
): Promise<Record<string, unknown> | null> {
    const params = item.params || [];
    if (!params.length) return Promise.resolve({});
    return new Promise((resolve) => {
        const mask = document.createElement('div');
        mask.className = 'desk-mask';
        const dialog = document.createElement('div');
        dialog.className = 'desk-dialog';
        const title = document.createElement('div');
        title.className = 'desk-dialog-title';
        title.textContent = `${item.label} · 参数`;
        dialog.appendChild(title);

        const inputs = new Map<string, HTMLInputElement>();
        for (const param of params) {
            const row = document.createElement('label');
            row.className = 'desk-dialog-row';
            const name = document.createElement('span');
            name.textContent = param.label || param.name;
            const input = document.createElement('input');
            input.className = 'desk-input';
            input.value = String(param.default ?? '');
            input.dataset.type = param.type || 'float';
            row.append(name, input);
            dialog.appendChild(row);
            inputs.set(param.name, input);
        }

        const actions = document.createElement('div');
        actions.className = 'desk-dialog-actions';
        const cancel = document.createElement('button');
        cancel.className = 'desk-tool';
        cancel.textContent = '取消';
        const ok = document.createElement('button');
        ok.className = 'desk-tool on';
        ok.textContent = '确定';
        actions.append(cancel, ok);
        dialog.appendChild(actions);

        const close = (value: Record<string, unknown> | null) => {
            mask.remove();
            resolve(value);
        };
        cancel.addEventListener('click', () => close(null));
        ok.addEventListener('click', () => {
            const values: Record<string, unknown> = {};
            for (const [name, input] of inputs) {
                const type = input.dataset.type;
                const raw = input.value.trim();
                values[name] = type === 'int' ? parseInt(raw, 10)
                    : (type === 'float' ? parseFloat(raw)
                        : (type === 'bool' ? raw === 'true' : raw));
                if ((type === 'int' || type === 'float')
                    && !Number.isFinite(values[name] as number)) {
                    input.focus();
                    return;                        // 非法数字 → 不关框 ✓
                }
            }
            close(values);
        });
        mask.addEventListener('mousedown', (event) => {
            if (event.target === mask) close(null);
        });
        mask.appendChild(dialog);
        document.body.appendChild(mask);
        (inputs.values().next().value as HTMLInputElement | undefined)?.focus();
    });
}


/** 个人脚本管理器（列出已导入目录，可逐个移除 ✓） */
export function showPersonalManager(
    items: Array<{ category: string; path: string; kind: string;
                   default?: boolean }>,
    onDrop: (category: string) => void,
): void {
    const mask = document.createElement('div');
    mask.className = 'desk-mask';
    const dialog = document.createElement('div');
    dialog.className = 'desk-dialog desk-dialog-wide';
    const title = document.createElement('div');
    title.className = 'desk-dialog-title';
    title.textContent = '个人指标策略管理';
    dialog.appendChild(title);

    const custom = items.filter((item) => !item.default);
    if (!custom.length) {
        const empty = document.createElement('div');
        empty.className = 'desk-muted';
        empty.textContent = '还没有收录其它目录（默认目录 personal/indicators、'
            + 'personal/strategies 不在这里显示）';
        dialog.appendChild(empty);
    }
    for (const item of custom) {
        const row = document.createElement('div');
        row.className = 'desk-dialog-row';
        const label = document.createElement('span');
        label.textContent = `${item.kind === 'strategy' ? '策略' : '指标'} · `
            + item.category;
        const path = document.createElement('span');
        path.className = 'desk-muted desk-personal-path';
        path.textContent = item.path;
        const drop = document.createElement('button');
        drop.className = 'desk-tool';
        drop.textContent = '移除';
        drop.addEventListener('click', () => {
            onDrop(item.category);
            row.remove();
        });
        row.append(label, path, drop);
        dialog.appendChild(row);
    }

    const actions = document.createElement('div');
    actions.className = 'desk-dialog-actions';
    const close = document.createElement('button');
    close.className = 'desk-tool on';
    close.textContent = '关闭';
    const dismiss = () => mask.remove();
    close.addEventListener('click', dismiss);
    actions.appendChild(close);
    dialog.appendChild(actions);

    mask.addEventListener('mousedown', (event) => {
        if (event.target === mask) dismiss();
    });
    mask.appendChild(dialog);
    document.body.appendChild(mask);
}

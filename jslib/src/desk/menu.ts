/** Floating menu shared by the quote page (right click) and the chart toolbar. */

export interface MenuItem {
    label: string;
    /** greyed-out + not clickable */
    disabled?: boolean;
    /** draw a divider above this item */
    separator?: boolean;
    run?: () => void;
    /** 行尾的 ✕（删除这条记录等，不会触发 `run` ✓） */
    onDelete?: () => void;
    /** **二级子菜单**（有它就渲染成 `标签 ›`，hover / 点击展开 ✓） */
    submenu?: MenuItem[];
}

let current: HTMLDivElement | null = null;
let currentSubs: HTMLDivElement[] = [];
let dismissHandler: ((event: MouseEvent) => void) | null = null;

export function closeMenu(): void {
    if (dismissHandler) {
        document.removeEventListener('mousedown', dismissHandler);
        dismissHandler = null;
    }
    currentSubs.forEach((node) => node.remove());
    currentSubs = [];
    current?.remove();
    current = null;
}

/**
 * 画一个菜单（`items` → DOM），返回容器 ✓
 *
 * 二级子菜单：`item.submenu` 存在时这一行右边画 `›`，hover / 点击展开一层
 * （周期菜单的 秒 / 分 / 时 / 天 就是这种结构 ✓）。
 */
function buildMenu(items: MenuItem[], className = 'desk-menu'): HTMLDivElement {
    const menu = document.createElement('div');
    menu.className = className;
    for (const item of items) {
        if (item.separator) {
            const line = document.createElement('div');
            line.className = 'desk-menu-sep';
            menu.appendChild(line);
        }
        const row = document.createElement('div');
        row.className = 'desk-menu-item';
        const text = document.createElement('span');
        text.className = 'desk-menu-label';
        text.textContent = item.label;
        row.appendChild(text);

        if (item.submenu && item.submenu.length) {
            row.classList.add('has-submenu');
            const arrow = document.createElement('span');
            arrow.className = 'desk-menu-arrow';
            arrow.textContent = '›';
            row.appendChild(arrow);
            if (item.disabled) row.classList.add('disabled');
            let sub: HTMLDivElement | null = null;
            const closeSub = () => {
                if (!sub) return;
                sub.remove();
                currentSubs = currentSubs.filter((node) => node !== sub);
                sub = null;
            };
            const openSub = () => {
                if (sub) return;
                sub = buildMenu(item.submenu!, 'desk-menu desk-menu-sub');
                document.body.appendChild(sub);
                currentSubs.push(sub);
                const box = row.getBoundingClientRect();
                const size = sub.getBoundingClientRect();
                const left = Math.min(box.right + 2,
                                      window.innerWidth - size.width - 6);
                const top = Math.min(box.top - 6,
                                     window.innerHeight - size.height - 6);
                sub.style.left = `${Math.max(6, left)}px`;
                sub.style.top = `${Math.max(6, top)}px`;
            };
            row.addEventListener('mouseenter', openSub);
            row.addEventListener('mouseleave', () => {
                window.setTimeout(() => {
                    if (sub && !sub.matches(':hover')) closeSub();
                }, 200);
            });
            row.addEventListener('click', (event) => {
                event.stopPropagation();
                if (sub) closeSub();
                else openSub();
            });
        } else if (item.disabled) {
            row.classList.add('disabled');
        } else {
            row.addEventListener('click', () => {
                closeMenu();
                item.run?.();
            });
        }

        if (item.onDelete) {
            const remove = document.createElement('button');
            remove.className = 'desk-menu-remove';
            remove.textContent = '✕';
            remove.title = '删除这条记录（文件不会删）';
            remove.addEventListener('click', (event) => {
                event.stopPropagation();       // 别触发 run ✓
                closeMenu();
                item.onDelete?.();
            });
            row.appendChild(remove);
        }
        menu.appendChild(row);
    }
    return menu;
}

/** Show `items` at viewport coordinates (keeps the menu inside the window). */
export function showMenu(x: number, y: number, items: MenuItem[]): void {
    closeMenu();
    const menu = buildMenu(items);
    document.body.appendChild(menu);
    current = menu;

    const box = menu.getBoundingClientRect();
    const left = Math.min(x, window.innerWidth - box.width - 6);
    const top = Math.min(y, window.innerHeight - box.height - 6);
    menu.style.left = `${Math.max(6, left)}px`;
    menu.style.top = `${Math.max(6, top)}px`;

    const dismiss = (event: MouseEvent) => {
        const node = event.target as Node;
        if (current && !current.contains(node)
            && !currentSubs.some((sub) => sub.contains(node))) {
            closeMenu();
            document.removeEventListener('mousedown', dismiss);
        }
    };
    dismissHandler = dismiss;
    document.addEventListener('mousedown', dismiss);
}

/** Same menu, anchored under a toolbar button. */
export function showMenuBelow(anchor: HTMLElement, items: MenuItem[]): void {
    const box = anchor.getBoundingClientRect();
    showMenu(box.left, box.bottom + 2, items);
}

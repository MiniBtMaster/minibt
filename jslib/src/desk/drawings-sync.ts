/**
 * 多布局画线：**共用一个画线工具** + 按「合约|周期」持久化 ✓
 *
 * 用户 2026-10-29 需求：
 *  1. 多图表布局里所有图共用一个画线工具，统一由工具栏「画线」按钮显隐；
 *  2. 画线本地持久化，键 = `合约|周期`（同一个品种不同周期各画各的，
 *     **不**把一个品种所有周期的画线混到一起 —— 之前验证过会乱 ✗）。
 *
 * 实现要点：
 *  * pylightcharts 的 `ToolBox.saveDrawings()` 会调用
 *    `window.callbackFunction('save_drawings<handlerId>_~_<json>')` →
 *    这里 hook 住这条消息，按 handlerId 找到「哪一格」，再把画线交给 desk
 *    后端存盘（Qt / 浏览器两种壳都走同一条 `callbackFunction` ✓）；
 *  * 每格的工具箱**都建出来但默认隐藏**（不建的话 `loadDrawings()` 无处可载），
 *    工具栏按钮只显示**当前格**那一个 → 视觉上就是“共用一个工具”；
 *  * 同键的多格（比如左右两图都是 ag2612|1分）拿到同一份画线 ✓。
 */

interface CellInfo {
    /** handler id（`Handler` 构造时给的那个，save_drawings 回调里带 ✓） */
    id: string;
    /** 持久化键：`<合约>|<周期秒>` ✓ */
    key: string;
    /** pylightcharts `Handler`（要 `.toolBox` / `.createToolBox()`） */
    handler: unknown;
}

interface BoxLike {
    div?: HTMLElement;
    loadDrawings?: (items: unknown[]) => void;
    clearDrawings?: () => void;
}

export interface DrawingsSyncOptions {
    /** 当前每格（每次调用都现算：换合约 / 换周期 / 换布局后 ✓） */
    cells: () => CellInfo[];
    /** 存一份画线（空数组 = 删除该键） */
    save: (key: string, items: unknown[]) => void;
    /** 请求某个键的画线（后端随后推 `{type:'drawings', key, items}` ✓） */
    request?: (key: string) => void;
}

/** handlerId → 保存回调（`save_drawings<id>_~_<json>` 用 ✓） */
const SAVERS = new Map<string, (json: string) => void>();
let hooked = false;

function installHook(): void {
    if (hooked) return;
    hooked = true;
    const host = window as unknown as { callbackFunction?: Function };
    const wrap = (): void => {
        const original = host.callbackFunction;
        if (typeof original !== 'function') return;
        if ((original as unknown as { __deskDrawings?: boolean }).__deskDrawings) {
            return;
        }
        const hookedFn = function (this: unknown, message: string) {
            const text = String(message ?? '');
            if (text.startsWith('save_drawings')) {
                const rest = text.slice('save_drawings'.length);
                const cut = rest.indexOf('_~_');
                if (cut > 0) {
                    const saver = SAVERS.get(rest.slice(0, cut));
                    if (saver) {
                        try {
                            saver(rest.slice(cut + 3));
                        } catch {
                            /* 解析失败不打断画线 ✓ */
                        }
                        return;
                    }
                }
            }
            return original.apply(this, arguments as never);
        };
        (hookedFn as unknown as { __deskDrawings?: boolean })
            .__deskDrawings = true;
        host.callbackFunction = hookedFn as unknown as Function;
    };
    wrap();
    // Qt 壳 / pylightcharts 可能在页面加载后才绑定 callbackFunction → 补装 ✓
    window.setTimeout(wrap, 800);
    window.setTimeout(wrap, 3000);
}

export class DrawingsSync {
    /** `key -> 画线列表`（后端推来 / 本地保存后都缓一份，换格不用再问 ✓） */
    private readonly cache = new Map<string, unknown[]>();
    private readonly ids = new Set<string>();

    constructor(private readonly options: DrawingsSyncOptions) {}

    /** 重建格子 / 换合约 / 换周期 / 换布局后调用 ✓ */
    refresh(): void {
        installHook();
        const cells = this.options.cells();
        const alive = new Set(cells.map((cell) => cell.id));
        for (const id of [...this.ids]) {
            if (!alive.has(id)) {
                SAVERS.delete(id);
                this.ids.delete(id);
            }
        }
        for (const cell of cells) {
            if (!cell.id) continue;
            this.ids.add(cell.id);
            SAVERS.set(cell.id, (json) => this._onSave(cell.key, json));
            this._applyTo(cell);
        }
    }

    /** 后端 `{type:'drawings', key, items}` ✓ */
    apply(payload: { key?: string; items?: unknown[] }): void {
        const key = String(payload.key || '');
        if (!key) return;
        const items = Array.isArray(payload.items) ? payload.items : [];
        this.cache.set(key, items);
        for (const cell of this.options.cells()) {
            if (cell.key === key) this._applyTo(cell);
        }
    }

    /** 清掉某个键（所有同键的格一起清，后端也删掉 ✓） */
    clear(key: string): void {
        if (!key) return;
        this.cache.set(key, []);
        for (const cell of this.options.cells()) {
            if (cell.key !== key) continue;
            this._box(cell)?.clearDrawings?.();
        }
        this.options.save(key, []);
    }

    /** 工具箱显隐：**只显示当前格**（多布局共用一个 ✓） */
    showToolBox(visible: boolean, activeId: string): void {
        for (const cell of this.options.cells()) {
            const box = this._box(cell);
            if (!box?.div) continue;
            box.div.style.display = visible && cell.id === activeId
                ? 'flex' : 'none';
        }
    }

    private _onSave(key: string, json: string): void {
        let items: unknown[] = [];
        try {
            const parsed = JSON.parse(json) as unknown;
            items = Array.isArray(parsed) ? parsed : [];
        } catch {
            return;                       // 坏数据不落盘 ✓
        }
        this.cache.set(key, items);
        this.options.save(key, items);
    }

    private _box(cell: CellInfo): BoxLike | null {
        const handler = cell.handler as unknown as {
            toolBox?: BoxLike;
            createToolBox?: () => void;
        } | null;
        if (!handler) return null;
        // 不建工具箱的话 `loadDrawings()` 无处可载（隐藏着也要建 ✓）
        if (!handler.toolBox) handler.createToolBox?.();
        return handler.toolBox || null;
    }

    private _applyTo(cell: CellInfo): void {
        const box = this._box(cell);
        if (!box) return;
        const items = this.cache.get(cell.key);
        box.clearDrawings?.();
        if (items === undefined) {
            this.options.request?.(cell.key);   // 没缓存过 → 问后端 ✓
            return;
        }
        if (items.length) box.loadDrawings?.(items);
    }
}

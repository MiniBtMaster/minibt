/**
 * 「自选 / 收藏 / 自选分组」的**共享存储**（首页 + 行情报价共用 ✓）
 *
 * 首页（P74）本来就把收藏 / 分组放在 `localStorage`：
 * ```
 * minibt.desk.home.favorites   ["SHFE.rb2601", …]      ★ 收藏
 * minibt.desk.home.groups      [{id,label,symbols}]    自建分组
 * ```
 * P80 起行情报价也要能收藏 / 加入自选 → 抽到这一份，两边读写同一份数据，
 * 变更时用 `CustomEvent` 广播（`minibt:watch`）让首页重画 ✓
 *
 * 内置分组：
 * | id | 标签 | 说明 |
 * |---|---|---|
 * | `all` | 自选 | 后端 `watchlist` + 本地加入的合约（`pins.all`）|
 * | `favorites` | 收藏 | ★ 收藏列表 |
 * | `black` / `metal` / `index` / `energy` | 黑色系等 | 按代码前缀 + 本地 pins |
 *
 * `pins`（`minibt.desk.home.pins`）记录「手动加入某个内置分组」的合约，
 * 这样右键「加入自选 → 黑色系」也能生效（前缀过滤之外再并上 pins ✓）。
 */
export type WatchKind = 'recent' | 'favorites' | 'all' | 'filter' | 'custom';

export interface WatchGroup {
    id: string;
    label: string;
    kind: WatchKind;
    prefixes?: string[];
    symbols?: string[];
}

const FAVORITES_KEY = 'minibt.desk.home.favorites';
const GROUPS_KEY = 'minibt.desk.home.groups';
const PINS_KEY = 'minibt.desk.home.pins';
/** 变更广播（首页监听 → 重画自选 / 收藏 ✓） */
export const WATCH_EVENT = 'minibt:watch-change';

export const FUTURES_PREFIXES = ['RB', 'I', 'JM', 'J', 'HC', 'SS', 'SF', 'SM'];
export const METAL_PREFIXES = ['CU', 'AL', 'ZN', 'NI', 'AU', 'AG', 'SN', 'PB'];
export const INDEX_PREFIXES = ['IF', 'IM', 'IH', 'IC', 'T', 'TF', 'TS'];
export const ENERGY_PREFIXES = ['SC', 'MA', 'TA', 'PP', 'L', 'V', 'EG', 'RU'];

/** 内置分组（首页侧栏 + 右键「加入自选」子菜单同一套 ✓） */
export const BUILTIN_GROUPS: WatchGroup[] = [
    { id: 'all', label: '自选', kind: 'all' },
    { id: 'black', label: '黑色系', kind: 'filter', prefixes: FUTURES_PREFIXES },
    { id: 'metal', label: '有色金属', kind: 'filter', prefixes: METAL_PREFIXES },
    { id: 'index', label: '股指期货', kind: 'filter', prefixes: INDEX_PREFIXES },
    { id: 'energy', label: '能源化工', kind: 'filter', prefixes: ENERGY_PREFIXES },
];

function read<T>(key: string, fallback: T): T {
    try {
        const text = window.localStorage.getItem(key);
        if (!text) return fallback;
        const value = JSON.parse(text);
        return value ?? fallback;
    } catch {
        return fallback;
    }
}

function write(key: string, value: unknown): void {
    try {
        window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
        /* 隐私模式 / 配额满 → 忽略 ✓ */
    }
}

/**
 * 落盘钩子：`app.ts` 注入 → 每次改动都把**整份**发给后端
 * （`~/.minibt/desk_user_prefs.json`，localStorage 在 Qt 里重启会丢 ✗）
 */
let persistHook: ((state: WatchState) => void) | null = null;

export interface WatchState {
    favorites: string[];
    groups: Array<{ id: string; label: string; symbols: string[] }>;
    pins: Record<string, string[]>;
}

export function setPersistHook(hook: ((state: WatchState) => void) | null): void {
    persistHook = hook;
}

/** 当前**整份**状态（发给后端 / 给首页渲染 ✓） */
export function snapshot(): WatchState {
    return {
        favorites: favorites(),
        groups: customGroups().map((group) => ({
            id: group.id,
            label: group.label,
            symbols: (group.symbols || []).slice(),
        })),
        pins: pins(),
    };
}

/** 后端（或别的地方）给了整份状态 → 写进 localStorage + 广播 ✓ */
export function applyState(state: WatchState | null | undefined): void {
    if (!state) return;
    if (Array.isArray(state.favorites)) {
        write(FAVORITES_KEY, state.favorites.map((item) => String(item)));
    }
    if (Array.isArray(state.groups)) {
        write(GROUPS_KEY, state.groups.map((group) => ({
            id: String(group.id),
            label: String(group.label),
            symbols: (group.symbols || []).map((item) => String(item)),
        })));
    }
    if (state.pins && typeof state.pins === 'object') {
        write(PINS_KEY, state.pins);
    }
    notify(false);
}

function notify(persist = true): void {
    try {
        if (persist && persistHook) persistHook(snapshot());
    } catch {
        /* ignore */
    }
    try {
        window.dispatchEvent(new CustomEvent(WATCH_EVENT));
    } catch {
        /* ignore */
    }
}

// ------------------------------------------------------------------ 收藏
export function favorites(): string[] {
    const list = read<unknown>(FAVORITES_KEY, []);
    return Array.isArray(list) ? list.map((item) => String(item)) : [];
}

export function isFavorite(symbol: string): boolean {
    return !!symbol && favorites().includes(symbol);
}

/** ★ 收藏 / 取消收藏（只影响「收藏」这一类 ✓） */
export function toggleFavorite(symbol: string): boolean {
    if (!symbol) return false;
    const list = favorites();
    const next = list.includes(symbol)
        ? list.filter((item) => item !== symbol)
        : [symbol, ...list].slice(0, 200);
    write(FAVORITES_KEY, next);
    notify();
    return next.includes(symbol);
}

// ------------------------------------------------------------------ 分组
export function customGroups(): WatchGroup[] {
    const raw = read<unknown>(GROUPS_KEY, []);
    if (!Array.isArray(raw)) return [];
    return raw.filter((item): item is WatchGroup =>
        !!item && typeof item === 'object' && !!(item as WatchGroup).id
        && !!(item as WatchGroup).label)
        .map((item) => ({
            id: String(item.id),
            label: String(item.label),
            kind: 'custom',
            symbols: Array.isArray(item.symbols)
                ? item.symbols.map((symbol) => String(symbol)) : [],
        }));
}

/** 全部可选分组（首页侧栏 / 右键子菜单）✓ */
export function allGroups(): WatchGroup[] {
    return [...BUILTIN_GROUPS, ...customGroups()];
}

/** 能「加入」的分组（排除最近打开 / 收藏）✓ */
export function writableGroups(): WatchGroup[] {
    return allGroups().filter((group) => group.kind !== 'recent'
        && group.kind !== 'favorites');
}

function pins(): Record<string, string[]> {
    const raw = read<unknown>(PINS_KEY, {});
    if (!raw || typeof raw !== 'object') return {};
    const out: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
        if (Array.isArray(value)) {
            out[key] = value.map((item) => String(item));
        }
    }
    return out;
}

/** 某个分组里手动加入的合约（内置分组靠 pins，自建分组在 symbols ✓） */
export function pinnedSymbols(groupId: string): string[] {
    return pins()[groupId] || [];
}

/** 把合约加入某个分组（自选 / 黑色系 / … / 自建分组 ✓） */
export function addToGroup(groupId: string, symbol: string): boolean {
    const id = String(groupId || '');
    if (!id || !symbol) return false;
    const group = allGroups().find((item) => item.id === id);
    if (!group) return false;
    if (group.kind === 'favorites') {
        if (isFavorite(symbol)) return false;
        write(FAVORITES_KEY, [symbol, ...favorites()].slice(0, 200));
        notify();
        return true;
    }
    if (group.kind === 'custom') {
        const list = customGroups();
        const target = list.find((item) => item.id === id);
        if (!target) return false;
        target.symbols = [symbol, ...(target.symbols || [])
            .filter((item) => item !== symbol)];
        write(GROUPS_KEY, list);
        notify();
        return true;
    }
    // 内置（自选 / 黑色系 / 有色金属 / 股指期货 / 能源化工）→ pins ✓
    const map = pins();
    const list = [symbol, ...(map[id] || []).filter((item) => item !== symbol)];
    map[id] = list.slice(0, 200);
    write(PINS_KEY, map);
    notify();
    return true;
}

/** 某个分组的全部标记合约（给后端 `home_symbols` 拉报价用 ✓） */
export function groupSymbols(groupId: string): string[] {
    const group = allGroups().find((item) => item.id === groupId);
    if (!group) return [];
    if (group.kind === 'custom') return group.symbols || [];
    return pinnedSymbols(groupId);
}

/** 自建分组：新建（首页「＋」按钮用 ✓） */
export function createGroup(label: string, symbols: string[] = []): WatchGroup | null {
    const text = String(label || '').trim();
    if (!text) return null;
    const list = customGroups();
    const group: WatchGroup = {
        id: `custom-${Date.now().toString(36)}`,
        label: text,
        kind: 'custom',
        symbols: symbols.slice(),
    };
    list.push(group);
    write(GROUPS_KEY, list);
    notify();
    return group;
}

export function saveGroupSymbols(groupId: string, symbols: string[]): void {
    const list = customGroups();
    const target = list.find((item) => item.id === groupId);
    if (!target) return;
    target.symbols = symbols;
    write(GROUPS_KEY, list);
    notify();
}

export function deleteGroup(groupId: string): void {
    write(GROUPS_KEY, customGroups().filter((item) => item.id !== groupId));
    const map = pins();
    delete map[groupId];
    write(PINS_KEY, map);
    notify();
}

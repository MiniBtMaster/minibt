/**
 * 本地模拟交易控件（P69 抽出共用 ✓）
 *
 * 本地图表（P49）和**看盘窗口回放**（P69）用的是同一个模拟账户
 * （`minibt/desk/local_data.py::LocalSim`），所以交易控件也复用这一份：
 *
 * ```
 * 交易
 * 价格 [13880]
 * 手数 [1]
 * [买入] [卖出]
 * [平仓] [主价平仓] [反手] [撤单]
 * ```
 *
 * **本地模拟 / 天勤模拟 / 实盘共用这一套按钮**（用户要求 ✓）：
 * 回放 → 走本地模拟账户；实时 → 走天勤（或实盘）账户。
 * 只发命令（`local_order` / `replay_order` / `place_order` / `…_action`），
 * 不碰账户逻辑 ✓
 */
export interface ReplayTicketOptions {
    title?: string;
    /** 当前交易标的（显示在标题行 ✓） */
    symbol?: string;
    /** 是否显示 🔍（本地模拟 / 天勤都开 ✓） */
    searchable?: boolean;
    /** 点 🔍 → 由宿主打开合约搜索（切换**交易标的** ✓） */
    onSearch?: () => void;
    /** 锁定：锁定后不能搜索 / 不跟随图表点击 ✓ */
    locked?: boolean;
    onLockChange?: (locked: boolean) => void;
    /** 点击 买入 / 卖出 / 平仓 */
    onOrder: (side: 'buy' | 'sell', close: boolean) => void;
    /** 点击 主价平仓 / 反手 / 撤单（按输入价的「平仓」走 `onOrder(…, true)`） */
    onAction: (action: 'close_main' | 'reverse' | 'cancel') => void;
    /** 初始价格 */
    price?: number;
    /** 按钮下方提示（可选） */
    info?: string;
    /** 数量单位：期货「手数」/ 股票「股数」✓ */
    qtyLabel?: string;
    /** 初始数量（股票默认 100 股 = 1 手） */
    qtyDefault?: number;
}

export interface ReplayTicket {
    element: HTMLDivElement;
    /** 跟随最新价刷新输入框（用户没手动改过才覆盖 ✓） */
    setPrice: (price: number | null) => void;
    /** 换标的：强制写价并恢复“跟随最新价” ✓ */
    resetPrice: (price: number | null) => void;
    /** 点二级报价 10 档 → **强制**填进价格框（覆盖用户输入 ✓） */
    setPriceForce: (price: number | null) => void;
    /** 标题（回放 → 「本地模拟交易（回放）」/ 实时 → 「交易」✓） */
    setTitle: (text: string) => void;
    /** 当前交易标的（`SHFE.rb2601` ✓） */
    setSymbol: (symbol: string) => void;
    /** 是否锁定（锁定后 🔍 禁用 ✓） */
    isLocked: () => boolean;
    setLocked: (locked: boolean) => void;
    /** 能不能交易（主连 / 指数只能看行情 → 按钮禁用 ✓） */
    setTradeable: (tradeable: boolean) => void;
    /** 价格步进 = 合约最小变动价位（`price_tick`：rb 1 / ag 1 / au 0.02… ✓） */
    setStep: (tick: number | null) => void;
    /** 净仓（正=多 / 负=空）→ 影响「平仓」按钮的方向提示 */
    setNet: (net: number) => void;
    setInfo: (text: string) => void;
    setQtyLabel: (text: string) => void;
    priceValue: () => number;
    qtyValue: () => number;
}

export function buildReplayTicket(options: ReplayTicketOptions): ReplayTicket {
    const ticket = document.createElement('div');
    ticket.className = 'desk-local-ticket';

    // ---- 标题行：合约 + 🔍 + 锁定 ✓ ----
    const head = document.createElement('div');
    head.className = 'desk-local-ticket-head';
    const title = document.createElement('span');
    title.className = 'desk-local-ticket-title';
    title.textContent = options.symbol || options.title || '交易';
    title.title = '当前交易标的（点 🔍 可切换）';
    const search = document.createElement('button');
    search.type = 'button';
    search.className = 'desk-local-ticket-search';
    search.textContent = '🔍';
    search.title = '搜索合约（只切换交易标的，不换图表）';
    search.addEventListener('click', () => {
        if (search.disabled) return;
        options.onSearch?.();
    });
    const lockLabel = document.createElement('label');
    lockLabel.className = 'desk-local-ticket-lock';
    lockLabel.title = '锁定后不跟随图表切换（🔍 也不可用）';
    const lockInput = document.createElement('input');
    lockInput.type = 'checkbox';
    lockInput.checked = !!options.locked;
    const lockText = document.createElement('span');
    lockText.textContent = '锁定';
    lockLabel.append(lockInput, lockText);
    lockInput.addEventListener('change', () => {
        search.disabled = lockInput.checked;
        search.classList.toggle('off', lockInput.checked);
        options.onLockChange?.(lockInput.checked);
    });
    head.append(title, search, lockLabel);
    if (options.searchable === false) search.style.display = 'none';

    const priceRow = document.createElement('div');
    priceRow.className = 'desk-local-ticket-row';
    const priceLabel = document.createElement('span');
    priceLabel.className = 'k';
    priceLabel.textContent = '价格';
    const price = document.createElement('input');
    price.type = 'number';
    // ★ 价格步进 = **合约最小变动价位**（后端 `book.price_tick` 推下来后覆盖 ✓）
    price.step = '0.01';
    price.placeholder = '现价';
    price.value = options.price ? String(options.price) : '';

    const qtyRow = document.createElement('div');
    qtyRow.className = 'desk-local-ticket-row';
    const qtyLabel = document.createElement('span');
    qtyLabel.className = 'k';
    qtyLabel.textContent = options.qtyLabel || '手数';
    const qty = document.createElement('input');
    qty.type = 'number';
    qty.step = '1';
    qty.min = '1';
    qty.value = String(options.qtyDefault || 1);
    priceRow.append(priceLabel, price);
    qtyRow.append(qtyLabel, qty);

    const buttons = document.createElement('div');
    buttons.className = 'desk-local-ticket-buttons';
    let net = 0;
    const actionButtons: HTMLButtonElement[] = [];
    const buy = document.createElement('button');
    buy.className = 'buy';
    buy.textContent = '买入';
    buy.title = '按上面的价格 / 手数买入开仓';
    const sell = document.createElement('button');
    sell.className = 'sell';
    sell.textContent = '卖出';
    sell.title = '按上面的价格 / 手数卖出开仓';
    // ★ 平仓：**按价格框 + 手数框**（限价平，走 insert_order ✓）
    const close = document.createElement('button');
    close.className = 'flat';
    close.textContent = '平仓';
    close.title = '按上面的价格 / 手数平掉持仓（限价）';
    buy.addEventListener('click', () => options.onOrder('buy', false));
    sell.addEventListener('click', () => options.onOrder('sell', false));
    close.addEventListener('click', () =>
        options.onOrder(net > 0 ? 'sell' : 'buy', true));

    const acts = document.createElement('div');
    acts.className = 'desk-local-ticket-buttons desk-local-ticket-acts';
    // ★ 第二排：市价平仓 / 反手 / 撤单（样式跟随二级报价 ✓）
    for (const [action, label, cls, tip] of [
            ['close_main', '市价平仓', 'flat', '按最新价市价平掉当前合约持仓'],
            ['reverse', '反手', 'plain', '反手（市价平掉后反向开相同手数）'],
            ['cancel', '撤单', 'plain', '撤掉当前合约未成交的挂单']] as const) {
        const button = document.createElement('button');
        button.className = `desk-book-btn ${cls}`;
        button.textContent = label;
        button.title = tip;
        button.addEventListener('click', () => options.onAction(action));
        actionButtons.push(button);
        acts.appendChild(button);
    }
    buttons.append(buy, sell, close);
    actionButtons.push(buy, sell, close);

    const info = document.createElement('div');
    info.className = 'desk-local-ticket-info';
    info.textContent = options.info || '回放中同样有效';
    ticket.append(head, priceRow, qtyRow, buttons, acts, info);

    let touched = false;
    let lastPrice: number | null = null;
    price.addEventListener('input', () => {
        touched = true;
    });
    const setPrice = (value: number | null) => {
        if (value === null || !Number.isFinite(value) || value <= 0) return;
        lastPrice = value;
        if (!touched) price.value = String(value);
    };
    setPrice(options.price ?? null);
    return {
        element: ticket,
        setPrice,
        setPriceForce: (value: number | null) => {
            const next = Number(value);
            if (!Number.isFinite(next) || next <= 0) return;
            lastPrice = next;
            price.value = String(next);
            touched = true;          // 用户选的价 → 不再被最新价覆盖 ✓
        },
        // ★ 换交易标的（点了另一张图 / 另一个合约）：强制换成新合约的最新价，
        //   并且**解除 touched**，让后面的实时行情继续更新价格框 ✓
        resetPrice: (value: number | null) => {
            const next = Number(value);
            if (!Number.isFinite(next) || next <= 0) return;
            lastPrice = next;
            price.value = String(next);
            touched = false;
        },
        setTitle: (text: string) => {
            title.textContent = text;
        },
        setSymbol: (symbol: string) => {
            if (!symbol) return;
            title.textContent = symbol;
            qtyLabel.textContent = /^(SH|SZ|HK|US|JP)\./i.test(symbol)
                ? '股数' : '手数';
        },
        setQtyLabel: (text: string) => {
            qtyLabel.textContent = text;
        },
        isLocked: () => !!lockInput.checked,
        setLocked: (locked: boolean) => {
            lockInput.checked = !!locked;
            search.disabled = !!locked;
            search.classList.toggle('off', !!locked);
        },
        setTradeable: (tradeable: boolean) => {
            const on = tradeable !== false;
            for (const button of actionButtons) {
                button.disabled = !on;
                button.style.opacity = on ? '' : '.45';
                button.style.cursor = on ? 'pointer' : 'not-allowed';
            }
        },
        setStep: (tick: number | null) => {
            const value = Number(tick);
            if (!Number.isFinite(value) || value <= 0) return;
            // 用定点字符串，避免 `0.020000000000000004` 这种浮点尾巴 ✓
            const text = value.toFixed(10).replace(/0+$/, '').replace(/\.$/, '');
            price.step = text || '0.01';
        },
        setNet: (value: number) => {
            net = Number(value) || 0;
        },
        setInfo: (text: string) => {
            info.textContent = text;
        },
        priceValue: () => {
            const raw = Number(price.value);
            if (Number.isFinite(raw) && raw > 0) return raw;
            return Number(lastPrice) || 0;
        },
        qtyValue: () => {
            const raw = Math.round(Number(qty.value));
            return Number.isFinite(raw) && raw > 0 ? raw : 1;
        },
    };
}

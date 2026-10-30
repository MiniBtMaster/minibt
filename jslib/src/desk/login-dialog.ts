/**
 * 登录框（期货天勤 / 股票 FutuOpenD）——参考 miniqt 的 `LoginWindow` ✓
 *
 * 用途：**离线启动**（天勤没账号 + FutuOpenD 没开）时也能接入服务：
 *   * `新建 ▾` → 「登录期货账户…」/「连接股票（富途 OpenD）…」
 *   * 首页左下角「数据源」两行一点就开（显示 已连接 / 未连接 ✓）
 *
 * 前端只管画 + 收值；真正连接由后端 `connect_futures` / `connect_stocks`
 * 在后台线程做，状态用 `login` 补丁回推（`pending` → `ok` / `error`）✓
 */
import type { DeskTheme } from './theme';

export type LoginKind = 'futures' | 'stocks';

export interface LoginDialogOptions {
    theme: DeskTheme;
    /** 提交登录 / 连接（`kind` 决定连哪一个 ✓） */
    onSubmit: (kind: LoginKind, values: Record<string, unknown>) => void;
    /** 股票：测试 FutuOpenD 网关（只探端口） */
    onTest: (values: { host: string; port: number }) => void;
    /** 「帮助」：打开下载 / 说明页 */
    onHelp: (which: 'futu' | 'real' | 'tqsdk') => void;
    /** 打开外链（股票登录「帮助」弹窗里的「打开下载页面」✓） */
    onOpenUrl?: (url: string) => void;
    /** 切到某个面板 → 让后端把记住的账号推过来（预填 ✓） */
    onCommand?: (kind: LoginKind) => void;
}

/** 天勤可登录的期货公司（和 miniqt 的 `FUTURES_BROKERS` 一致 ✓） */
const BROKERS: Array<[string, string]> = [
    ['H宏源期货', '宏源期货'],
    ['H徽商期货', '徽商期货'],
    ['Y银河期货', '银河期货'],
];

//: FutuOpenD 连接教程地址（复刻 miniqt `FUTU_SETUP_URL` ✓）
const FUTU_SETUP_URL = 'https://openapi.futunn.com/futu-api-doc/quick/'
    + 'opend-base.html';

const FUTU_DEFAULT_HOST = '127.0.0.1';
const FUTU_DEFAULT_PORT = '11111';

const STYLE_ID = 'desk-login-style';

const CSS = `
.desk-login-mask {
    position: fixed; inset: 0; z-index: 9000;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, .5); backdrop-filter: blur(1.5px);
}
.desk-login {
    width: 380px; border-radius: 10px; overflow: hidden;
    border: 1px solid var(--desk-border); background: var(--desk-panel);
    box-shadow: 0 24px 60px rgba(0, 0, 0, .55); color: var(--desk-text);
    font-size: 12px;
}
.desk-login-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 14px 6px;
}
.desk-login-logo { font-size: 14px; font-weight: 600; letter-spacing: .2px; }
.desk-login-close {
    border: 0; background: transparent; color: var(--desk-muted);
    font-size: 14px; cursor: pointer; padding: 2px 4px; border-radius: 4px;
}
.desk-login-close:hover { background: var(--desk-hover); color: var(--desk-text); }
.desk-login-tabs {
    display: flex; gap: 6px; padding: 0 14px 10px;
    border-bottom: 1px solid var(--desk-border);
}
.desk-login-tab {
    flex: 1 1 0; height: 26px; border-radius: 6px; cursor: pointer;
    border: 1px solid var(--desk-border); background: var(--desk-bg);
    color: var(--desk-muted); font-size: 12px;
}
.desk-login-tab.on {
    background: var(--desk-accent); border-color: var(--desk-accent);
    color: #fff;
}
.desk-login-body { padding: 12px 14px 4px; }
.desk-login-sub { text-align: center; color: var(--desk-muted); margin-bottom: 10px; }
.desk-login-pane[hidden] { display: none; }
.desk-login-tip {
    color: var(--desk-muted); line-height: 1.6; margin-bottom: 10px;
    padding: 6px 8px; border-radius: 6px; background: var(--desk-hover);
    font-size: 11px;
}
.desk-login-row {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.desk-login-row > span { flex: 0 0 64px; color: var(--desk-muted); }
.desk-login-row input, .desk-login-row select {
    flex: 1 1 auto; height: 26px; min-width: 0; padding: 0 8px;
    border: 1px solid var(--desk-border); border-radius: 5px;
    background: var(--desk-bg); color: var(--desk-text); font-size: 12px;
}
.desk-login-row input:focus, .desk-login-row select:focus {
    outline: none; border-color: var(--desk-accent);
}
.desk-login-eye {
    flex: 0 0 auto; width: 26px; height: 26px; border-radius: 5px;
    border: 1px solid var(--desk-border); background: var(--desk-bg);
    color: var(--desk-muted); cursor: pointer;
}
.desk-login-flags {
    display: flex; align-items: center; gap: 14px; margin: 2px 0 10px;
    color: var(--desk-muted);
}
.desk-login-flags label { display: inline-flex; align-items: center; gap: 5px; cursor: pointer; }
.desk-login-flags input { accent-color: var(--desk-accent); }
/* FutuOpenD 教程弹窗（复刻 miniqt 的 _FutuHelpDialog ✓） */
.desk-help-mask {
    position: fixed; inset: 0; z-index: 9500;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, .5); backdrop-filter: blur(1.5px);
}
.desk-help-box {
    width: 470px; max-width: 92vw; border-radius: 10px; overflow: hidden;
    border: 1px solid var(--desk-border); background: var(--desk-panel);
    box-shadow: 0 24px 60px rgba(0, 0, 0, .55); color: var(--desk-text);
    font-size: 12px;
}
.desk-help-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 13px 15px 8px; font-size: 13.5px; font-weight: 600;
}
.desk-help-close {
    border: 0; background: transparent; color: var(--desk-muted); font-size: 14px;
    cursor: pointer; padding: 2px 5px; border-radius: 4px;
}
.desk-help-close:hover { background: var(--desk-hover); color: var(--desk-text); }
.desk-help-body { padding: 0 15px 12px; line-height: 1.75; color: var(--desk-text); }
/* 编辑器「帮助」（Pi Agent Web 环境配置指引）：宽一点 + 等宽 ✓ */
.desk-help-wide { width: 720px; max-width: 94vw; }
.desk-help-pre {
    margin: 0; max-height: 58vh; overflow: auto;
    font-family: Consolas, "Cascadia Mono", Menlo, monospace;
    font-size: 11.5px; line-height: 1.6; white-space: pre-wrap;
    background: var(--desk-bg); border: 1px solid var(--desk-border);
    border-radius: 6px; padding: 10px 12px;
}
.desk-help-body a { color: var(--desk-accent); text-decoration: none; word-break: break-all; }
.desk-help-body a:hover { text-decoration: underline; }
.desk-help-steps { margin: 0; padding-left: 4px; }
.desk-help-foot {
    display: flex; gap: 10px; padding: 11px 15px;
    border-top: 1px solid var(--desk-border);
}
.desk-help-btn {
    flex: 1; height: 30px; border-radius: 6px; cursor: pointer; font-size: 12.5px;
    border: 1px solid var(--desk-border); background: transparent;
    color: var(--desk-text);
}
.desk-help-btn:hover { background: var(--desk-hover); }
.desk-help-btn.primary {
    background: var(--desk-accent); border-color: var(--desk-accent); color: #fff;
    font-weight: 600;
}
.desk-help-btn.primary:hover { filter: brightness(1.06); }

.desk-login-link {
    margin-left: auto; border: 0; background: transparent; cursor: pointer;
    color: var(--desk-accent); font-size: 12px; padding: 0;
}
.desk-login-real[hidden] { display: none; }
.desk-login-real {
    padding-top: 8px; border-top: 1px dashed var(--desk-border); margin-bottom: 4px;
}
.desk-login-actions { display: flex; gap: 8px; margin-bottom: 6px; }
.desk-login-actions button {
    height: 26px; padding: 0 12px; border-radius: 5px; cursor: pointer;
    border: 1px solid var(--desk-border); background: var(--desk-bg);
    color: var(--desk-text); font-size: 12px;
}
.desk-login-actions button:hover { background: var(--desk-hover); }
.desk-login-status {
    min-height: 18px; margin: 2px 0 8px; line-height: 1.5;
    white-space: pre-wrap; word-break: break-word;
}
.desk-login-status.ok { color: var(--desk-up); }
.desk-login-status.error { color: var(--desk-down); }
.desk-login-status.pending { color: var(--desk-accent); }
.desk-login-foot {
    display: flex; justify-content: flex-end; gap: 8px;
    padding: 10px 14px 14px; border-top: 1px solid var(--desk-border);
}
.desk-login-foot button {
    height: 28px; min-width: 76px; padding: 0 14px; border-radius: 6px;
    cursor: pointer; font-size: 12px; border: 1px solid var(--desk-border);
    background: var(--desk-bg); color: var(--desk-text);
}
.desk-login-foot button:hover { background: var(--desk-hover); }
.desk-login-foot button.primary {
    background: var(--desk-accent); border-color: var(--desk-accent);
    color: #fff; font-weight: 600;
}
.desk-login-foot button.primary[disabled] { opacity: .6; cursor: default; }
`;

/** 弹窗样式（帮助 / 提醒 / FutuOpenD 教程共用）—— 任何页面都能提前装上 ✓
 *
 * ⚠ 以前这套 CSS 只在 `LoginDialog` 打开时才注入 → 从没登录过的话，
 *   编辑器「帮助」按钮点了**什么都没出现**（元素有、样式没有）✗
 */
export function ensureDeskDialogStyle(): void {
    ensureStyle(STYLE_ID, CSS);
}

function ensureStyle(id: string, css: string): void {
    if (document.getElementById(id)) return;
    const node = document.createElement('style');
    node.id = id;
    node.textContent = css;
    document.head.appendChild(node);
}

export class LoginDialog {
    public readonly element: HTMLDivElement;
    private readonly options: LoginDialogOptions;
    private theme: DeskTheme;
    private kind: LoginKind = 'futures';
    private busy = false;

    private readonly tabs: Record<LoginKind, HTMLButtonElement>;
    private readonly panes: Record<LoginKind, HTMLDivElement>;
    private readonly status: HTMLDivElement;
    private readonly submitButton: HTMLButtonElement;
    private readonly realBlock: HTMLDivElement;

    constructor(options: LoginDialogOptions) {
        ensureStyle(STYLE_ID, CSS);
        this.options = options;
        this.theme = options.theme || 'dark';

        this.element = document.createElement('div');
        this.element.className = 'desk-login-mask';
        this.element.style.display = 'none';

        const box = document.createElement('div');
        box.className = 'desk-login';

        // ---- head -------------------------------------------------------
        const head = document.createElement('div');
        head.className = 'desk-login-head';
        head.innerHTML = '<span class="desk-login-logo">Mini Quant Trader</span>';
        const close = document.createElement('button');
        close.className = 'desk-login-close';
        close.textContent = '✕';
        close.title = '关闭（不登录也能继续用离线功能 ✓）';
        close.addEventListener('click', () => this.close());
        head.appendChild(close);

        // ---- tabs -------------------------------------------------------
        const tabBar = document.createElement('div');
        tabBar.className = 'desk-login-tabs';
        this.tabs = {
            futures: this._tab('期货登录', 'futures'),
            stocks: this._tab('股票登录', 'stocks'),
        };
        tabBar.append(this.tabs.futures, this.tabs.stocks);

        // ---- body -------------------------------------------------------
        const body = document.createElement('div');
        body.className = 'desk-login-body';
        this.panes = {
            futures: this._futuresPane(),
            stocks: this._stocksPane(),
        };
        this.realBlock = this.panes.futures.querySelector(
            '.desk-login-real') as HTMLDivElement;
        this.status = document.createElement('div');
        this.status.className = 'desk-login-status';
        body.append(this.panes.futures, this.panes.stocks, this.status);

        // ---- foot -------------------------------------------------------
        const foot = document.createElement('div');
        foot.className = 'desk-login-foot';
        this.submitButton = document.createElement('button');
        this.submitButton.className = 'primary';
        this.submitButton.textContent = '登录';
        this.submitButton.title = '连接行情（后台连接，成功后会提示 ✓）';
        this.submitButton.addEventListener('click', () => this._submit());
        const cancel = document.createElement('button');
        cancel.textContent = '取消';
        cancel.addEventListener('click', () => this.close());
        foot.append(this.submitButton, cancel);

        box.append(head, tabBar, body, foot);
        this.element.appendChild(box);
        this.element.addEventListener('mousedown', (event) => {
            if (event.target === this.element) this.close();
        });
        // 回车 = 提交（密码框里也生效 ✓）
        this.element.addEventListener('keydown', (event) => {
            if ((event as KeyboardEvent).key === 'Enter') this._submit();
            if ((event as KeyboardEvent).key === 'Escape') this.close();
        });
        document.body.appendChild(this.element);
        this.setTheme(this.theme);
        this.setKind('futures');
    }

    // ------------------------------------------------------------- 内部
    private _tab(label: string, kind: LoginKind): HTMLButtonElement {
        const button = document.createElement('button');
        button.className = 'desk-login-tab';
        button.textContent = label;
        button.title = `${label}（离线也能打开本框 ✓）`;
        button.addEventListener('click', () => this.setKind(kind));
        return button;
    }

    private _row(label: string, input: HTMLElement): HTMLLabelElement {
        const row = document.createElement('label');
        row.className = 'desk-login-row';
        const name = document.createElement('span');
        name.textContent = label;
        row.append(name, input);
        return row;
    }

    private _input(field: string, placeholder = '', type = 'text'): HTMLInputElement {
        const input = document.createElement('input');
        input.type = type;
        input.dataset.f = field;
        input.placeholder = placeholder;
        return input;
    }

    private _futuresPane(): HTMLDivElement {
        const pane = document.createElement('div');
        pane.className = 'desk-login-pane';
        pane.dataset.pane = 'futures';
        const sub = document.createElement('div');
        sub.className = 'desk-login-sub';
        sub.textContent = '请登录您的天勤期货账号（不登录也能用离线功能）';

        const password = this._input('password', '请输入密码', 'password');
        const passwordRow = this._row('密码', password);
        const eye = document.createElement('button');
        eye.className = 'desk-login-eye';
        eye.type = 'button';
        eye.textContent = '👁';
        eye.title = '显示 / 隐藏密码';
        eye.addEventListener('click', () => {
            password.type = password.type === 'password' ? 'text' : 'password';
        });
        passwordRow.appendChild(eye);

        const flags = document.createElement('div');
        flags.className = 'desk-login-flags';
        flags.innerHTML = `
            <label><input type="checkbox" data-f="remember">记住密码</label>
            <label><input type="checkbox" data-f="real">使用实盘账户</label>
            <button class="desk-login-link" data-help="real"
                title="实盘账户说明 / 免责声明">帮助</button>`;
        const remember = flags.querySelector(
            'input[data-f="remember"]') as HTMLInputElement;
        const real = flags.querySelector(
            'input[data-f="real"]') as HTMLInputElement;

        const realBlock = document.createElement('div');
        realBlock.className = 'desk-login-real';
        realBlock.hidden = true;
        const select = document.createElement('select');
        select.dataset.f = 'broker';
        for (const [value, label] of BROKERS) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            select.appendChild(option);
        }
        realBlock.append(
            this._row('期货公司', select),
            this._row('资金账号', this._input('account', '实盘资金账号')),
            this._row('交易密码', this._input('trade_password', '交易密码',
                                               'password')),
        );
        real.addEventListener('change', () => {
            realBlock.hidden = !real.checked;
            this.submitButton.textContent = real.checked ? '实盘登录' : '登录';
        });
        void remember;

        flags.querySelector('[data-help="real"]')?.addEventListener(
            'click', () => this.options.onHelp('real'));

        pane.append(
            sub,
            this._row('用户名', this._input('username', '手机号 / 邮箱')),
            passwordRow,
            flags,
            realBlock,
        );
        return pane;
    }

    private _stocksPane(): HTMLDivElement {
        const pane = document.createElement('div');
        pane.className = 'desk-login-pane';
        pane.dataset.pane = 'stocks';
        const tip = document.createElement('div');
        tip.className = 'desk-login-tip';
        tip.innerHTML = '请先启动并登录 <b>FutuOpenD</b>，再连接本机网关。'
            + '<br>A 股行情权限可在富途牛牛免费申请 ✓';
        const host = this._input('host', FUTU_DEFAULT_HOST);
        host.value = FUTU_DEFAULT_HOST;
        const port = this._input('port', FUTU_DEFAULT_PORT);
        port.value = FUTU_DEFAULT_PORT;

        // ★ 股票交易入口：默认只行情；勾选后连接 Futu 交易账户
        const flags = document.createElement('div');
        flags.className = 'desk-login-flags';
        flags.innerHTML = `
            <label><input type="checkbox" data-f="trade">启用交易（富途账户）</label>`;
        const env = document.createElement('select');
        env.dataset.f = 'trd_env';
        for (const [value, label] of [['SIMULATE', '模拟交易'],
                                      ['REAL', '真实交易']] as const) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            env.appendChild(option);
        }
        const market = document.createElement('select');
        market.dataset.f = 'trd_market';
        market.value = 'CN';
        for (const [value, label] of [['CN', '沪深市场'],
                                      ['HK', '香港市场'],
                                      ['US', '美国市场'],
                                      ['JP', '日本市场']] as const) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            market.appendChild(option);
        }
        market.value = 'CN';

        const actions = document.createElement('div');
        actions.className = 'desk-login-actions';
        const test = document.createElement('button');
        test.textContent = '测试连接';
        test.title = '只探端口（几毫秒），确认 OpenD 是否在跑';
        test.addEventListener('click', () => {
            this.options.onTest({
                host: host.value.trim() || FUTU_DEFAULT_HOST,
                port: Number(port.value) || Number(FUTU_DEFAULT_PORT),
            });
        });
        const help = document.createElement('button');
        help.textContent = '帮助';
        help.title = 'FutuOpenD 连接教程（下载 / 安装 / 登录三步）';
        // ★ 复刻 miniqt：点「帮助」先弹**教程窗**，再让用户点「打开下载页面」✓
        help.addEventListener('click', () => this._showFutuHelp());
        actions.append(test, help);

        pane.append(
            tip,
            this._row('网关地址', host),
            this._row('网关端口', port),
            flags,
            this._row('交易环境', env),
            this._row('交易市场', market),
            actions,
        );
        return pane;
    }

    /**
     * FutuOpenD 连接教程（**复刻 miniqt `_FutuHelpDialog`** ✓）
     *
     * 以前点「帮助」直接跳浏览器，用户看不到步骤 → 现在弹窗讲三步，底部
     * 「打开下载页面」再开外链，「关闭」只关窗 ✓
     */
    private _showFutuHelp(): void {
        ensureStyle(STYLE_ID, CSS);
        const mask = document.createElement('div');
        mask.className = 'desk-help-mask';
        const box = document.createElement('div');
        box.className = 'desk-help-box';

        const head = document.createElement('div');
        head.className = 'desk-help-head';
        head.innerHTML = '<span>FutuOpenD 股票行情连接教程</span>';
        const close = document.createElement('button');
        close.className = 'desk-help-close';
        close.textContent = '✕';
        close.title = '关闭';
        head.appendChild(close);

        const body = document.createElement('div');
        body.className = 'desk-help-body';
        body.innerHTML = `<div class="desk-help-steps">
            <p>1. 打开富途官网，下载并安装 <b>FutuOpenD</b> 客户端：<br>
                <a href="#" data-open-url>${FUTU_SETUP_URL}</a></p>
            <p>2. 注册 / 登录 FutuOpenD，并保持客户端处于登录状态（不要关闭）。</p>
            <p>3. 回到 minibt desk 股票登录窗口，点「测试连接」通过后，再点「登录」。</p>
        </div>`;

        const foot = document.createElement('div');
        foot.className = 'desk-help-foot';
        const open = document.createElement('button');
        open.className = 'desk-help-btn primary';
        open.textContent = '打开下载页面';
        open.title = FUTU_SETUP_URL;
        const cancel = document.createElement('button');
        cancel.className = 'desk-help-btn';
        cancel.textContent = '关闭';
        cancel.title = '不打开网页，直接关窗';
        foot.append(open, cancel);

        box.append(head, body, foot);
        mask.appendChild(box);

        const openUrl = () => this.options.onOpenUrl?.(FUTU_SETUP_URL);
        const dismiss = () => mask.remove();
        open.addEventListener('click', () => {
            openUrl();
            dismiss();
        });
        (body.querySelector('[data-open-url]') as HTMLElement | null)
            ?.addEventListener('click', (event) => {
                event.preventDefault();
                openUrl();
            });
        cancel.addEventListener('click', dismiss);
        close.addEventListener('click', dismiss);
        mask.addEventListener('mousedown', (event) => {
            if (event.target === mask) dismiss();
        });
        document.body.appendChild(mask);
    }

    private _checked(name: string): boolean {
        const node = this.panes[this.kind].querySelector(
            `[data-f="${name}"]`) as HTMLInputElement | null;
        return !!node?.checked;
    }

    private _submit(): void {
        if (this.busy) return;
        const values: Record<string, unknown> = {};
        for (const node of Array.from(
            this.panes[this.kind].querySelectorAll('[data-f]'))) {
            const input = node as HTMLInputElement | HTMLSelectElement;
            const name = input.dataset.f!;
            values[name] = input instanceof HTMLInputElement && input.type === 'checkbox'
                ? input.checked : input.value.trim();
        }
        if (this.kind === 'stocks') {
            values.port = Number(values.port) || Number(FUTU_DEFAULT_PORT);
            values.host = String(values.host || FUTU_DEFAULT_HOST);
            if (values.trade && String(values.trd_env) === 'REAL'
                && !window.confirm('将连接富途真实交易账户，确认继续？')) {
                return;
            }
        }
        this.options.onSubmit(this.kind, values);
    }

    // ------------------------------------------------------------- 公开
    get visible(): boolean {
        return this.element.style.display !== 'none';
    }

    open(kind: LoginKind = 'futures',
         saved: Record<string, any> | null = null): void {
        this.element.style.display = '';
        this.setKind(kind);
        this.setSaved(kind, saved || {});
        this.status.textContent = '';
        this.status.className = 'desk-login-status';
        this.busy = false;
        this.submitButton.disabled = false;
        this.submitButton.textContent = this._checked('real') ? '实盘登录' : '登录';
        const first = this.panes[this.kind].querySelector(
            '[data-f="username"], [data-f="host"]') as HTMLInputElement | null;
        window.setTimeout(() => first?.focus(), 30);
    }

    /** 后端记住的账号 → 预填（密码只在「记住密码」时才有 ✓） */
    setSaved(kind: LoginKind, saved: Record<string, any>): void {
        saved = saved || {};
        // ★ 没记住密码时清空上一次的密码，避免关闭“记住密码”后仍误提交旧密码
        if (!('password' in saved)) {
            const password = this.panes[kind].querySelector(
                '[data-f="password"]') as HTMLInputElement | null;
            if (password) password.value = '';
        }
        for (const [name, value] of Object.entries(saved)) {
            const node = this.panes[kind].querySelector(
                `[data-f="${name}"]`) as HTMLInputElement | null;
            if (!node) continue;
            if (node.type === 'checkbox') node.checked = !!value;
            else if (value !== null && value !== undefined) node.value = String(value);
        }
        if (kind === 'futures') {
            const real = this._checked('real');
            this.realBlock.hidden = !real;
            this.submitButton.textContent = real ? '实盘登录' : '登录';
        }
    }

    setKind(kind: LoginKind): void {
        this.kind = kind === 'stocks' ? 'stocks' : 'futures';
        for (const name of ['futures', 'stocks'] as LoginKind[]) {
            const on = name === this.kind;
            this.tabs[name].classList.toggle('on', on);
            this.panes[name].hidden = !on;
        }
        this.submitButton.textContent = this.kind === 'stocks'
            ? '连接' : (this._checked('real') ? '实盘登录' : '登录');
        this.submitButton.title = this.kind === 'stocks'
            ? '连接 FutuOpenD 网关（后台连接 ✓）'
            : '登录天勤（快期模拟 / 实盘 ✓）';
        this.status.textContent = '';
        this.status.className = 'desk-login-status';
        this.options.onCommand?.(this.kind);
    }

    /** 后端回推的登录状态（`pending` / `ok` / `error` / `test` ✓） */
    setState(patch: Record<string, any>): void {
        const kind = (patch.kind === 'stocks' ? 'stocks' : 'futures') as LoginKind;
        if (kind !== this.kind) {
            // 另一个市场的结果：只在成功时提示（别抢当前面板 ✓）
            if (!patch.ok) return;
            this.setKind(kind);
        }
        const state = String(patch.state || '');
        const text = String(patch.text || '');
        this.status.textContent = text;
        this.status.className = 'desk-login-status';
        if (state === 'pending' || state === 'test') {
            this.status.classList.add('pending');
        } else if (patch.ok === true || state === 'ok') {
            this.status.classList.add('ok');
        } else if (patch.ok === false || state === 'error') {
            this.status.classList.add('error');
        }
        this.busy = state === 'pending';
        this.submitButton.disabled = this.busy;
        if (state === 'ok') {
            window.setTimeout(() => this.close(), 900);
        }
    }

    setTheme(theme: DeskTheme): void {
        this.theme = theme === 'light' ? 'light' : 'dark';
        this.element.classList.toggle('theme-light', this.theme === 'light');
        this.element.classList.toggle('theme-dark', this.theme !== 'light');
    }

    close(): void {
        this.element.style.display = 'none';
        this.busy = false;
        this.submitButton.disabled = false;
    }
}

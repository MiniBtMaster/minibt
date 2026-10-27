// MiniBT 看盘终端（minibt desk）—— VS Code 侧的启动 / 体检 / 参数拼装。
//
// 思路和「在编辑器页运行策略图表」一致：**子进程 + 本地 HTTP 服务 + iframe**。
// desk 早就能脱离 Qt 跑：`minibt desk --browser` 起一个 127.0.0.1 服务（SSE 下发
// + POST 上报），所以这里只要拼参数、体检、起进程、等 `/healthz` 就绪 ✓。
//
// 本模块**只放纯逻辑**（不 require vscode），方便用 node 直接跑测试：
//   node -e "const d=require('./desk'); console.log(d.buildDeskArgs({...}))"
const net = require('net');

/** 输出面板名 / 状态栏文字 */
const DESK_NAME = 'MiniBT 看盘';

/** 默认值（用户没设置时用它；Futu 客户端默认 127.0.0.1:11111 ✓） */
const DEFAULTS = {
    account: '',
    password: '',
    futuHost: '127.0.0.1',
    futuPort: 11111,
    stocks: 'auto',       // auto | on | off
    offline: false,
    theme: 'auto',        // auto | dark | light
    autoStart: false,
    port: 0,              // 0 = 自动挑空闲端口
    pythonPath: 'python',
};

/** 体检结论的三种入口 */
const ACTIONS = {
    start: 'start',       // 直接起（有账号 / 有股票 / 明确离线）
    warn: 'warn',         // 什么都没配 → 弹提醒
};

/** 把 VS Code 的配置对象（或普通对象）规范成纯设置 ✓ */
function normalizeSettings(raw) {
    const get = (key) => {
        if (!raw) return undefined;
        if (typeof raw.get === 'function') return raw.get(key, undefined);
        return raw[key];
    };
    const pick = (key, fallback) => {
        const value = get(key);
        return value === undefined || value === null || value === ''
            ? fallback : value;
    };
    const port = Number(pick('futuPort', DEFAULTS.futuPort));
    return {
        account: String(pick('account', DEFAULTS.account)).trim(),
        password: String(pick('password', DEFAULTS.password) || ''),
        futuHost: String(pick('futuHost', DEFAULTS.futuHost)).trim()
            || DEFAULTS.futuHost,
        futuPort: Number.isFinite(port) && port > 0 ? port : DEFAULTS.futuPort,
        stocks: String(pick('stocks', DEFAULTS.stocks)).toLowerCase(),
        offline: !!pick('offline', DEFAULTS.offline),
        theme: String(pick('theme', DEFAULTS.theme)).toLowerCase(),
        autoStart: !!pick('autoStart', DEFAULTS.autoStart),
        port: Number(pick('port', DEFAULTS.port)) || 0,
        pythonPath: String(pick('pythonPath', DEFAULTS.pythonPath))
            || DEFAULTS.pythonPath,
    };
}

/**
 * 拼 `minibt desk` 的命令行参数 ✓
 *
 * **密码永远不进命令行**（走环境变量，见 `buildDeskEnv`），这样 `ps` /
 * 进程列表 / 崩溃日志里都不会出现明文 ✓
 */
function buildDeskArgs(settings, options) {
    const opts = options || {};
    const s = normalizeSettings(settings);
    // `--no-browser`：页面由 VS Code 的 iframe 托管，**不要**再弹系统浏览器 ✓
    const args = ['-m', 'minibt', 'desk', '--browser', '--no-browser',
        '--json'];
    if (s.offline || opts.offline) {
        args.push('--offline');
    } else {
        if (s.account) args.push('--user', s.account);
        args.push('--futu-host', s.futuHost);
        args.push('--futu-port', String(s.futuPort));
        if (s.stocks === 'off' || opts.noStocks) args.push('--no-stocks');
    }
    const port = Number(opts.port === undefined ? s.port : opts.port) || 0;
    args.push('--port', String(port));
    const theme = String(opts.theme || s.theme || 'auto').toLowerCase();
    if (theme === 'dark' || theme === 'light') args.push('--theme', theme);
    return args;
}

/** 子进程环境变量：密码 / 账号都走 env（`minibt/cli.py` 会读 ✓） */
function buildDeskEnv(baseEnv, settings) {
    const s = normalizeSettings(settings);
    const env = Object.assign({}, baseEnv || process.env, {
        PYTHONIOENCODING: 'utf-8',
        MINIBT_VSCODE: '1',
        MINIBT_DESK_BROWSER: '1',
        MINIBT_DESK_NO_BROWSER: '1',
        MINIBT_FUTU_HOST: s.futuHost,
        MINIBT_FUTU_PORT: String(s.futuPort),
    });
    if (s.account) env.MINIBT_TQ_USER = s.account;
    if (s.password) env.MINIBT_TQ_PASSWORD = s.password;
    if (s.offline) env.MINIBT_DESK_OFFLINE = '1';
    return env;
}

/**
 * 启动前体检 ✓
 *
 * | 情况 | 结论 |
 * |---|---|
 * | 明确离线 | 直接起（离线演示） |
 * | 有账号 + 密码 | 直接起（期货 + 股票） |
 * | 有账号、没密码 | warn（提示设置密码） |
 * | 没账号但 Futu OpenD 通 | 直接起（只股票） |
 * | 没账号、Futu 也不通 | **warn**（弹提醒让用户选） |
 *
 * @param {{account:string,password:string,offline:boolean,
 *          stocks:string,futuReachable:boolean}} state
 */
function decideStart(state) {
    const s = normalizeSettings(state);
    const futu = !!(state && state.futuReachable);
    if (s.offline) {
        return { action: ACTIONS.start, mode: 'offline', futures: false,
            stocks: false, reason: '离线演示（settings 里 offline=true）' };
    }
    if (s.account && s.password) {
        return { action: ACTIONS.start, mode: 'full', futures: true,
            stocks: s.stocks !== 'off',
            reason: `天勤账号 ${s.account}` };
    }
    if (s.account && !s.password) {
        return { action: ACTIONS.warn, mode: 'no-password', futures: false,
            stocks: false, reason: '设置了天勤账号，但没有密码' };
    }
    if (futu && s.stocks !== 'off') {
        return { action: ACTIONS.start, mode: 'stocks', futures: false,
            stocks: true,
            reason: `只连股票（FutuOpenD ${s.futuHost}:${s.futuPort}）` };
    }
    return { action: ACTIONS.warn, mode: 'nothing', futures: false,
        stocks: false,
        reason: `没设置天勤账号，也没检测到 Futu OpenD`
            + `（${s.futuHost}:${s.futuPort}）` };
}

/** TCP 探一下 FutuOpenD 通不通（1500ms 超时足够；连上就立刻断）✓ */
function probePort(host, port, timeoutMs) {
    return new Promise((resolve) => {
        const socket = new net.Socket();
        let done = false;
        const finish = (ok) => {
            if (done) return;
            done = true;
            try { socket.destroy(); } catch (error) { /* ignore */ }
            resolve(ok);
        };
        socket.setTimeout(Number(timeoutMs) || 1500);
        socket.once('connect', () => finish(true));
        socket.once('timeout', () => finish(false));
        socket.once('error', () => finish(false));
        try {
            socket.connect(Number(port) || DEFAULTS.futuPort, host);
        } catch (error) {
            finish(false);
        }
    });
}

/** 从 `minibt desk --json` 的那行读就绪信息（端口 / 状态）✓ */
function parseReadyLine(line) {
    const text = String(line || '').trim();
    if (!text.startsWith('{') || !text.endsWith('}')) return null;
    try {
        const info = JSON.parse(text);
        if (info && (info.ready || info.url)) return info;
    } catch (error) {
        /* 不是就绪行 */
    }
    return null;
}

/** 状态栏文字（`● 已连接 · 期货+股票` / `○ 未启动`）✓ */
function statusText(state) {
    const s = state || {};
    if (s.running) {
        const parts = [];
        if (s.futures) parts.push('期货');
        if (s.stocks) parts.push('股票');
        if (s.offline) parts.push('离线');
        const tail = parts.length ? ` · ${parts.join('+')}` : '';
        return `$(pulse) ${DESK_NAME}${tail}`;
    }
    return `$(graph) ${DESK_NAME}`;
}

module.exports = {
    DESK_NAME,
    DEFAULTS,
    ACTIONS,
    normalizeSettings,
    buildDeskArgs,
    buildDeskEnv,
    decideStart,
    probePort,
    parseReadyLine,
    statusText,
};

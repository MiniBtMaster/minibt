// MiniBT Charts —— 在 VS Code 编辑器页（WebviewPanel）里跑 minibt 策略图表。
//
// 做法：用子进程跑 `runner/vscode_runner.py`，它把策略里的图表强制切到可嵌入的
// 引擎（pylightcharts 网页版 / bokeh server），并把结果报回来：
//
//   MINIBT_URL=http://127.0.0.1:PORT/   → 本地服务，用 <iframe> 嵌进编辑器页签
//   MINIBT_HTML=/path/to/chart.html     → 自包含 HTML，直接当页签内容（静态快照）
//
// 页签先显示"正在启动图表服务…"，探测到端口后才把 iframe 换进来 —— 这样策略算
// 指标算得久也不会看到 ERR_CONNECTION_REFUSED；如果最后只等来 HTML，就自动变成
// 静态快照页签。
//
// 为什么不能嵌"纯 pylightcharts（原生窗口）"：原生窗口是 PyQt6 + WebView2 的
// 独立操作系统窗口，没法放进 VS Code 的 webview；而网页引擎用的是同一套
// lightweight-charts + pylightcharts bundle，画出来的图完全一样。
const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');

/** 本扩展版本（自查用：输出面板第一行会打印它）。 */
const VERSION = require('./package.json').version;

/** 看盘终端（minibt desk）的纯逻辑：参数 / 体检 / 状态文字 ✓ */
const desk = require('./desk');

/** 当前会话。 */
let session = null;

/** 看盘终端会话 `{process, panel, url, settings, stopping}` */
let deskSession = null;

/** 状态栏「MiniBT 看盘」 */
let deskStatus = null;

/** 共用的输出面板（VS Code 底部「输出」里的 MiniBT）。 */
let output = null;
function getOutput() {
    if (!output) output = vscode.window.createOutputChannel('MiniBT');
    return output;
}

// --------------------------------------------------------------- 解释器解析

/**
 * 找一个真能 `import minibt, pylightcharts` 的解释器。
 *
 * VS Code 里的 `python` 往往不是工作区配的那个（PATH 上可能是 3.14，而 minibt
 * 装在 3.12）—— 子进程会报 `ModuleNotFoundError: No module named 'rich'`
 * （rich 是 minibt 的依赖），看上去像扩展坏了。
 *
 * 顺序：显式配置的 minibt.pythonPath 优先（不再探测）→ VS Code/Python 扩展设的
 * `python.defaultInterpreterPath` → Windows `py -0p` 列出的全部 → `python`/
 * `python3`。选第一个依赖齐（rich / pylightcharts）的；都不行就退回 `python`，
 * 让 runner 报清楚的错。
 */
function resolvePython(config) {
    const configured =
        String(config.get('pythonPath', 'python') || '').trim() || 'python';
    if (configured !== 'python') return { cmd: configured, args: [] };
    const channel = getOutput();
    const candidates = [];
    const seen = new Set();
    const add = (cmd, args) => {
        args = args || [];
        const key = cmd + ' ' + args.join(' ');
        if (cmd && !seen.has(key)) {
            seen.add(key);
            candidates.push({ cmd, args });
        }
    };
    // 1) VS Code / Python 扩展设的解释器（存在才用）
    try {
        const setting = String(vscode.workspace.getConfiguration('python')
            .get('defaultInterpreterPath', '') || '').trim();
        if (setting && fs.existsSync(setting)) add(setting);
    } catch (error) { /* 设置读不到就跳过 */ }
    // 2) Windows 的 py 启动器：列出所有已装版本（`py -0p`）
    if (process.platform === 'win32') {
        try {
            const out = cp.execFileSync('py', ['-0p'], {
                encoding: 'utf8', timeout: 5000,
                stdio: ['ignore', 'pipe', 'ignore'],
            });
            for (const line of out.split(/\r?\n/)) {
                const match = /^\s*-V:\S+\s+\*?\s*(.+?)\s*$/.exec(line);
                if (match && fs.existsSync(match[1])) add(match[1]);
            }
        } catch (error) { /* 没装 py 就算了 */ }
    }
    // 3) PATH 上的名字
    add('python');
    if (process.platform !== 'win32') add('python3');
    for (const cand of candidates) {
        if (probeInterpreter(cand)) {
            const label = [cand.cmd].concat(cand.args).join(' ');
            if (label !== 'python') {
                channel.appendLine(
                    `[minibt] minibt.pythonPath 未配置，自动选了：${label}`);
            }
            return cand;
        }
    }
    return { cmd: 'python', args: [] };
}

/**
 * 探这个解释器能不能跑 minibt。
 *
 * 探的是**依赖**（rich / pylightcharts），不是 `import minibt` —— 后者一跑就是
 * ~10s（pandas / pandas_ta 一大堆），会把启动拖死；而真正会缺的就是这些依赖
 * （比如 PATH 上的 python 是另一个版本，没装 rich）。
 */
function probeInterpreter(cand) {
    try {
        cp.execFileSync(cand.cmd, cand.args.concat(
            ['-c', 'import rich, pylightcharts']), {
            cwd: os.tmpdir(),           // 别被工作区里的本地包“骗”到
            timeout: 30000,
            stdio: 'ignore',
            env: Object.assign({}, process.env, { PYTHONIOENCODING: 'utf-8' }),
        });
        return true;
    } catch (error) {
        return false;
    }
}

// --------------------------------------------------------------------- 工具

/** 只做 TCP 连接探测：不 GET，避免给 bokeh 造出一个"幽灵会话"。 */
function waitForPort(url, timeoutMs) {
    let host = '127.0.0.1';
    let port = 0;
    try {
        const parsed = new URL(url);
        host = parsed.hostname;
        port = Number(parsed.port);
    } catch (error) {
        return Promise.resolve(false);
    }
    const deadline = Date.now() + timeoutMs;
    return new Promise((resolve) => {
        const attempt = () => {
            const socket = net.connect({ host, port });
            socket.setTimeout(700);
            socket.once('connect', () => {
                socket.destroy();
                resolve(true);
            });
            const retry = () => {
                socket.destroy();
                if (Date.now() > deadline) resolve(false);
                else setTimeout(attempt, 350);
            };
            socket.once('error', retry);
            socket.once('timeout', retry);
        };
        attempt();
    });
}

/** 从策略输出里认进度：`进度 12/100`、`37%`、`[3/8]`。 */
function parseProgress(line) {
    let match = /进度\s*([\d,]+)\s*\/\s*([\d,]+)/.exec(line);
    if (match) {
        const done = Number(match[1].replace(/,/g, ''));
        const total = Number(match[2].replace(/,/g, ''));
        if (total > 0) {
            return {
                percent: Math.max(0, Math.min(100, (done / total) * 100)),
                label: `进度 ${done}/${total}`,
            };
        }
    }
    match = /(?:^|[^\d.])(\d{1,3}(?:\.\d+)?)\s*%/.exec(line);
    if (match) {
        return { percent: Number(match[1]), label: `进度 ${match[1]}%` };
    }
    match = /\[(\d+)\s*\/\s*(\d+)\]/.exec(line);
    if (match) {
        const total = Number(match[2]);
        if (total > 0) {
            return {
                percent: (Number(match[1]) / total) * 100,
                label: `进度 ${match[1]}/${total}`,
            };
        }
    }
    if (/开始回测|正在回测/.test(line)) return { percent: 0, label: '回测中…' };
    if (/回放/.test(line)) return { percent: 0, label: '回放中…' };
    if (/实时/.test(line)) return { percent: 0, label: '实时行情中…' };
    if (/优化/.test(line)) return { percent: 0, label: '参数优化中…' };
    return null;
}

function lineLevel(line) {
    if (/Traceback|Error|Exception|错误|失败|异常/.test(line)) return 'error';
    if (/Warn|警告/.test(line)) return 'warn';
    return 'info';
}

function nonceOf() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let text = '';
    for (let i = 0; i < 32; i += 1) {
        text += chars[Math.floor(Math.random() * chars.length)];
    }
    return text;
}

// ------------------------------------------------------------------ 日志页签
function logPanelHtml(nonce) {
    return `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font-family: var(--vscode-font-family); }
  #bar { display: flex; align-items: center; gap: 8px; padding: 6px 10px;
         position: sticky; top: 0; background: var(--vscode-editor-background);
         border-bottom: 1px solid var(--vscode-panel-border); }
  #track { flex: 1; height: 8px; border-radius: 4px; overflow: hidden;
           background: var(--vscode-input-background, #8883); }
  #fill { height: 100%; width: 0%; background: var(--vscode-progressBar-background,
          #0a7); transition: width .2s ease; }
  #fill.indeterminate { width: 100% !important;
      background: linear-gradient(90deg, transparent, #0a7, transparent);
      animation: slide 1.2s linear infinite; }
  @keyframes slide { from { transform: translateX(-100%); }
                     to { transform: translateX(100%); } }
  #ptext { font-size: 12px; opacity: .8; white-space: nowrap; }
  #log { margin: 0; padding: 8px 10px; font-family: var(--vscode-editor-font-family,
         monospace); font-size: 12px; line-height: 1.45; white-space: pre-wrap;
         word-break: break-all; }
  #log div.error { color: var(--vscode-errorForeground, #d33); }
  #log div.warn { color: var(--vscode-editorWarning-foreground, #b80); }
  #log div.info { color: var(--vscode-editor-foreground); }
</style></head>
<body>
<div id="bar">
  <div id="track"><div id="fill" class="indeterminate"></div></div>
  <span id="ptext">等待策略输出…</span>
</div>
<div id="log"></div>
<script nonce="${nonce}">
  const log = document.getElementById('log');
  const fill = document.getElementById('fill');
  const ptext = document.getElementById('ptext');
  window.addEventListener('message', (event) => {
    const msg = event.data || {};
    if (msg.type === 'lines') {
      const stick = log.scrollTop + log.clientHeight >= log.scrollHeight - 24;
      for (const item of msg.lines) {
        const row = document.createElement('div');
        row.className = item.level;
        row.textContent = item.text;
        log.appendChild(row);
      }
      while (log.childElementCount > 4000) log.removeChild(log.firstChild);
      if (stick) log.scrollTop = log.scrollHeight;
    } else if (msg.type === 'progress') {
      if (msg.percent === null || msg.percent === undefined) {
        fill.classList.add('indeterminate');
      } else {
        fill.classList.remove('indeterminate');
        fill.style.width = Math.max(0, Math.min(100, msg.percent)) + '%';
      }
      ptext.textContent = msg.label || '';
    } else if (msg.type === 'clear') {
      log.textContent = '';
    }
  });
</script>
</body></html>`;
}

/**
 * 图表/日志页签应该开在哪一列。
 *
 * `minibt.openBeside=false`（默认）→ 命令发起时所在的**代码列**：
 * 代码、日志、图表都是同一页签组里的标签，页面不会被拆成左右两半 ✓
 * `true` → `ViewColumn.Beside`（右侧新开一列，左右分屏）。
 *
 * ★ 不能直接用 `ViewColumn.Active`：日志先以「旁边」打开后，active 就变成
 *   右边那一列了，之后图表也跟着跑到右边，于是“整个页面宽度减半”（用户反馈 ✗）。
 *   所以优先用命令发起时记下的 `session.column`。
 */
function panelColumn() {
    const beside = vscode.workspace.getConfiguration('minibt')
        .get('openBeside', false);
    if (beside) return vscode.ViewColumn.Beside;
    return (session && session.column) || vscode.ViewColumn.One;
}

/**
 * 命令发起时代码所在的列（返回一个**具体**的列，不能用 `ViewColumn.Active`：
 * 它会在日志页签打开后漂移）。优先当前聚焦的编辑器，其次可见的 .py 编辑器。
 */
function sourceColumn() {
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.viewColumn) return editor.viewColumn;
    const visible = vscode.window.visibleTextEditors.find(
        (item) => item.document.fileName.endsWith('.py') && item.viewColumn);
    if (visible) return visible.viewColumn;
    return vscode.ViewColumn.One;
}

function openLogPanel(context, title) {
    const column = panelColumn();
    if (session && session.logPanel) {
        session.logPanel.reveal(column, true);
        session.logPanel.title = title || session.logPanel.title;
        return session.logPanel;
    }
    const panel = vscode.window.createWebviewPanel(
        'minibtLog', title || 'MiniBT 策略日志', column,
        { enableScripts: true, retainContextWhenHidden: true },
    );
    panel.webview.html = logPanelHtml(nonceOf());
    for (const item of (session && session.logLines) || []) {
        postLog([item]);
    }
    const ownSession = session;
    panel.onDidDispose(() => {
        if (session && session === ownSession) session.logPanel = null;
    });
    if (session) session.logPanel = panel;
    return panel;
}

function postLog(items) {
    if (session && session.logPanel) {
        session.logPanel.webview.postMessage({ type: 'lines', lines: items });
    }
}

function postProgress(progress) {
    if (session && session.logPanel) {
        session.logPanel.webview.postMessage({
            type: 'progress',
            percent: progress.percent,
            label: progress.label,
        });
    }
}

// ---------------------------------------------------------------- 图表页签

/** 图表页签的外壳：先显示状态，收到 URL 才把 iframe 换进来。 */
function chartShellHtml(nonce, title) {
    return `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; frame-src http://127.0.0.1:* http://localhost:*;">
<style>
  :root { color-scheme: light dark; }
  html, body { margin: 0; height: 100%; overflow: hidden; }
  iframe { border: 0; width: 100%; height: 100%; display: none; background: #000; }
  #status { font-family: var(--vscode-font-family); padding: 1.2em;
            color: var(--vscode-descriptionForeground); }
  #status h3 { margin: 0 0 .4em; font-weight: 600;
               color: var(--vscode-editor-foreground); }
  #status code { color: var(--vscode-textPreformat-foreground, #c60); }
  .spin { display: inline-block; width: 12px; height: 12px; margin-right: 8px;
          border: 2px solid var(--vscode-descriptionForeground);
          border-top-color: transparent; border-radius: 50%;
          animation: turn 1s linear infinite; vertical-align: -2px; }
  @keyframes turn { to { transform: rotate(360deg); } }
</style></head>
<body>
<iframe id="frame" allow="clipboard-read; clipboard-write"></iframe>
<div id="status">
  <h3>${title || 'MiniBT 图表'}</h3>
  <p><span class="spin"></span><span id="text">正在启动图表服务…</span></p>
</div>
<script nonce="${nonce}">
  const frame = document.getElementById('frame');
  const status = document.getElementById('status');
  const text = document.getElementById('text');
  // Ctrl+C：停止策略进程（等同「停止策略进程」按钮）。
  // 这里只覆盖“焦点在外壳上”的情况；图表在跨域 iframe 里时，由注入到图表页
  // 里的监听器（见 runner/vscode_runner.py）负责。两处都发 {type:'stop'}。
  let vscodeApi = null;
  try { vscodeApi = acquireVsCodeApi(); } catch (err) { vscodeApi = null; }
  window.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey)
        && (event.key === 'c' || event.key === 'C')) {
      event.preventDefault();
      try { if (vscodeApi) vscodeApi.postMessage({ type: 'stop' }); }
      catch (err) { /* 桥没就绪：忽略 */ }
    }
  }, true);
  window.addEventListener('message', (event) => {
    const msg = event.data || {};
    if (msg.type === 'url') {
      // 每次换 URL 都带上时间戳，避免 webview 复用旧页面
      frame.src = msg.url + (msg.url.includes('?') ? '&' : '?') + '_vscode=' + Date.now();
      frame.style.display = 'block';
      status.style.display = 'none';
    } else if (msg.type === 'status') {
      frame.style.display = 'none';
      status.style.display = 'block';
      text.textContent = msg.text || '';
    } else if (msg.type === 'error') {
      frame.style.display = 'none';
      status.style.display = 'block';
      status.innerHTML = '<h3>图表没起来</h3><p></p>';
      const detail = document.createElement('p');
      detail.textContent = msg.text || '';
      status.appendChild(detail);
      const hint = document.createElement('p');
      hint.innerHTML = '看 <b>MiniBT</b> 输出面板里的报错；'
        + '确认 <b>minibt.pythonPath</b> 的解释器里装了 minibt。';
      status.appendChild(hint);
    }
  });
</script>
</body></html>`;
}

function panelOptions() {
    return {
        enableScripts: true,           // 外壳脚本要把 iframe 换进来
        retainContextWhenHidden: true, // 切走再回来不重载图表
        localResourceRoots: [],
    };
}

/** 建/复用图表页签（先显示等待状态，不直接甩 iframe 错误页）。 */
function openChartPanel(context, title) {
    const column = panelColumn();
    if (session && session.panel) {
        session.panel.title = title;
        session.panel.reveal(column, false);
        if (session.kind !== 'live') {
            session.kind = 'live';
            session.panel.webview.html = chartShellHtml(nonceOf(), title);
        }
        return session.panel;
    }
    const panel = vscode.window.createWebviewPanel(
        'minibtChart', title, column, panelOptions());
    panel.iconPath = new vscode.ThemeIcon('graph');
    panel.webview.html = chartShellHtml(nonceOf(), title);
    attachPanel(context, panel, 'live', null);
    return panel;
}

function postChart(message) {
    if (session && session.panel) {
        session.panel.webview.postMessage(message);
    }
}

/** 静态快照：自包含 HTML 直接当页签内容（离线、可缩放、不占端口）。 */
function showStaticPanel(context, htmlPath, title) {
    let html;
    try {
        html = fs.readFileSync(htmlPath, 'utf8');
    } catch (error) {
        vscode.window.showWarningMessage(
            `MiniBT：读取 ${htmlPath} 失败：${error.message}`);
        return null;
    }
    let panel = session && session.panel;
    if (!panel) {
        panel = vscode.window.createWebviewPanel(
            'minibtChart', title, panelColumn(), panelOptions());
        panel.iconPath = new vscode.ThemeIcon('file-media');
        attachPanel(context, panel, 'static', htmlPath);
    } else {
        session.kind = 'static';
        session.panel.title = title;
        session.panel.reveal(panelColumn(), false);
        session.panel.iconPath = new vscode.ThemeIcon('file-media');
    }
    panel.webview.html = html;
    if (session) session.htmlPath = htmlPath;
    return panel;
}

function attachPanel(context, panel, kind, target) {
    if (!session) session = {};
    // 捕获本会话：旧页签的 dispose 回调不能去动“下一次运行”的新会话
    const ownSession = session;
    session.panel = panel;
    session.kind = kind;
    if (kind === 'live') session.url = target;
    else session.htmlPath = target;
    vscode.commands.executeCommand('setContext', 'minibt.chartOpen', true);
    // 外壳里的 Ctrl+C（见 chartShellHtml）会 post 过来：停掉策略进程
    panel.webview.onDidReceiveMessage((message) => {
        if (message && message.type === 'stop' && session === ownSession) {
            stopSession();
        }
    });
    panel.onDidDispose(() => {
        vscode.commands.executeCommand('setContext', 'minibt.chartOpen', false);
        if (!session || session !== ownSession) return;
        session.panel = null;
        const keep = vscode.workspace.getConfiguration('minibt')
            .get('keepAliveOnClose', false);
        if (!keep) stopSession();
    });
}

/** 杀掉整棵策略进程树（同步：确认停了再交给调用方）。 */
function stopChildProcess(child) {
    if (!child || child.exitCode !== null) return;
    getOutput().appendLine('[minibt] 停止策略进程 …');
    try {
        if (process.platform === 'win32') {
            cp.execFileSync('taskkill',
                ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' });
        } else {
            child.kill('SIGTERM');
        }
    } catch (error) {
        try { child.kill(); } catch (error2) { /* 已经没了 */ }
    }
}

function stopSession() {
    if (!session || session.stopping) return;
    // 标记停止中：面板的 onDidDispose 会回调 stopSession，免得递归
    session.stopping = true;
    const child = session.process;
    const panels = [session.panel, session.logPanel];
    session.process = null;
    session.panel = null;
    session.logPanel = null;
    // ★ 顺序：**先停服务**（同步杀进程，杀掉后才往下走），**再关页面**。
    //   否则先把图表/日志页签 dispose 掉，页面没了但本地服务还在跑 ✗。
    stopChildProcess(child);
    for (const target of panels) {
        if (!target) continue;
        try { target.dispose(); } catch (error) { /* 已经关了 */ }
    }
    vscode.commands.executeCommand('setContext', 'minibt.chartOpen', false);
}

// ------------------------------------------------------------------ 启动
async function pickScript() {
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.document.fileName.endsWith('.py')) {
        if (editor.document.isDirty) await editor.document.save();
        return editor.document.fileName;
    }
    const picked = await vscode.window.showOpenDialog({
        canSelectMany: false,
        filters: { 'Python 策略': ['py'] },
        openLabel: '运行这个策略',
    });
    return picked && picked.length ? picked[0].fsPath : undefined;
}

/**
 * 跑一次策略：把图表开在编辑器页签里（本地服务 + iframe，实时刷新）✓。
 */
async function start(context) {
    // ★ 先记下“命令发起时”的代码列：日志/图表之后都要回到这一列，
    //   同一个页签组内按标签切换，不拆分页面（用户要求）。
    const invokedColumn = sourceColumn();
    const script = await pickScript();
    if (!script) return false;
    stopSession();

    const config = vscode.workspace.getConfiguration('minibt');
    const python = resolvePython(config);      // { cmd, args }：能跑 minibt 的
    const pythonLabel = [python.cmd].concat(python.args).join(' ');
    const engine = config.get('engine', 'auto');
    const port = Number(config.get('port', 0)) || 0;
    const extra = config.get('extraPythonArgs', []) || [];
    const folders = vscode.workspace.workspaceFolders;
    const cwd = config.get('cwd', '') ||
        (folders && folders.length ? folders[0].uri.fsPath : path.dirname(script));
    const openBrowser = config.get('openBrowser', false);
    // VS Code 深浅色主题：用户没显式指定 theme 时，图表默认跟着 VS Code 走
    const colorTheme = vscode.window.activeColorTheme;
    const vsCodeTheme = (colorTheme &&
        (colorTheme.kind === 2 || colorTheme.kind === 3)) ? 'dark' : 'light';
    const runner = path.join(context.extensionPath, 'runner', 'vscode_runner.py');
    const env = Object.assign({}, process.env, {
        PYTHONPATH: [path.join(context.extensionPath, 'runner'), cwd,
            process.env.PYTHONPATH || ''].filter(Boolean).join(path.delimiter),
        PYTHONIOENCODING: 'utf-8',
        MINIBT_VSCODE: '1',
    });

    const name = path.basename(script);
    session = {
        process: null, panel: null, kind: null, url: null, htmlPath: null,
        logPanel: null, logLines: [], progress: null, script: script,
        column: invokedColumn,
    };
    const channel = getOutput();
    channel.clear();
    channel.appendLine(
        `[minibt] MiniBT Charts v${VERSION} · ${pythonLabel} → ${name}`
        + `（engine=${engine}）`);
    // ★ 不主动 show 输出面板：日志只在**编辑器页签**里显示（MiniBT 策略日志），
    //   否则底部的「输出」面板会被自动打开，同一份日志出现两遍（用户反馈 ✗）。
    //   输出面板仍保留内容，需要时可用命令「显示策略输出（原始日志）」手动查看。
    if (config.get('openLog', true)) {
        openLogPanel(context, `MiniBT 策略日志 — ${name}`);
    }

    const args = ['-u'].concat(extra, [runner, script, '--engine', engine,
        '--theme', vsCodeTheme, '--port', String(port), '--cwd', cwd]);
    if (openBrowser) args.push('--open');

    const child = cp.spawn(python.cmd, python.args.concat(args),
        { cwd, env });
    session.process = child;

    const onLine = (line) => {
        if (line.trim() === 'MINIBT_STOP') {
            // 图表页（跨域 iframe）里按了 Ctrl+C：停掉策略进程。
            // runner 收到图表页的回调后会打印这一行（见 vscode_runner.py）。
            // 内部信令，不写进日志。
            stopSession();
            return;
        }
        channel.appendLine(line);
        session.logLines.push({ text: line, level: lineLevel(line) });
        postLog([session.logLines[session.logLines.length - 1]]);
        const progress = parseProgress(line);
        if (progress) {
            session.progress = progress;
            postProgress(progress);
        }
        const urlMatch = /^MINIBT_URL=(\S+)$/.exec(line.trim());
        if (urlMatch) {
            const url = urlMatch[1];
            const title = `MiniBT 图表 — ${name}`;
            openChartPanel(context, title);
            postChart({ type: 'status', text: '正在启动图表服务…' });
            waitForPort(url, 60000).then((ready) => {
                if (!session || session.process !== child) return;
                if (ready) {
                    session.url = url;
                    getOutput().appendLine(`[minibt] 图表服务已就绪：${url}`);
                    postChart({ type: 'url', url: url });
                } else if (!session.htmlPath) {
                    postChart({
                        type: 'error',
                        text: `图表服务没起来（${url}）。`,
                    });
                }
            });
        }
        const htmlMatch = /^MINIBT_HTML=(\S.*)$/.exec(line.trim());
        if (htmlMatch) {
            const htmlPath = htmlMatch[1].trim();
            if (!fs.existsSync(htmlPath)) return;
            getOutput().appendLine(`[minibt] 静态图表页：${htmlPath}`);
            showStaticPanel(context, htmlPath, `MiniBT 图表（快照）— ${name}`);
        }
    };

    let buffer = '';
    child.stdout.on('data', (chunk) => {
        buffer += chunk.toString();
        let index;
        while ((index = buffer.indexOf('\n')) >= 0) {
            onLine(buffer.slice(0, index).replace(/\r$/, ''));
            buffer = buffer.slice(index + 1);
        }
    });
    child.stderr.on('data', (chunk) => {
        const text = chunk.toString();
        channel.append(text);
        for (const line of text.split('\n')) {
            if (line.trim()) {
                session.logLines.push({ text: line, level: lineLevel(line) });
                postLog([session.logLines[session.logLines.length - 1]]);
            }
        }
    });
    child.on('error', (error) => {
        vscode.window.showErrorMessage(
            `MiniBT：启动 ${pythonLabel} 失败 —— ${error.message}`
            + '（检查 minibt.pythonPath）');
    });
    child.on('exit', (code) => {
        channel.appendLine(`[minibt] 策略进程退出，code=${code}`);
        if (!session || session.process !== child) return;
        session.process = null;
        postProgress({
            percent: code === 0 ? 100 : null,
            label: code === 0 ? '已完成' : `已退出（code=${code}）`,
        });
        if (session.panel && session.kind === 'live') {
            postChart({
                type: 'status',
                text: `策略已结束（code=${code}）。想重跑按 Ctrl+Alt+M。`,
            });
        } else if (!session.panel && !session.htmlPath) {
            vscode.window.showInformationMessage(
                `MiniBT：${name} 跑完了，但没看到图表（策略里 isplot=False？）`);
        }
    });
    return true;
}

// ------------------------------------------------------------------ 看盘终端
//
// `minibt desk` 早就能脱离 Qt 跑（`--browser` = 本地 HTTP + SSE），所以这里和
// 「策略图表」用同一套办法：子进程 + `<iframe>`。

/** 读设置：settings.json 打底，密码优先 SecretStorage / 环境变量 ✓ */
async function readDeskSettings(context) {
    const config = vscode.workspace.getConfiguration('minibt');
    const settings = desk.normalizeSettings({
        account: config.get('desk.account', ''),
        password: config.get('desk.password', ''),
        futuHost: config.get('desk.futuHost', '127.0.0.1'),
        futuPort: config.get('desk.futuPort', 11111),
        stocks: config.get('desk.stocks', 'auto'),
        offline: config.get('desk.offline', false),
        theme: config.get('desk.theme', 'auto'),
        autoStart: config.get('desk.autoStart', false),
        port: config.get('desk.port', 0),
        pythonPath: config.get('pythonPath', 'python'),
    });
    // 主题 follow VS Code（`auto` 时按当前配色决定 ✓）
    if (settings.theme === 'auto') {
        const theme = vscode.window.activeColorTheme;
        settings.theme = (theme && (theme.kind === 2 || theme.kind === 3))
            ? 'dark' : 'light';
    }
    // 密码优先级：SecretStorage → 环境变量 → settings.json（明文兜底 ✓）
    if (!settings.password) {
        let stored = '';
        try {
            stored = await context.secrets.get('minibt.desk.password') || '';
        } catch (error) { /* 老 VS Code 没有 secrets */ }
        if (!stored) stored = process.env.MINIBT_TQ_PASSWORD || '';
        if (stored) settings.password = stored;
    }
    // 记住的「上次怎么选的」（离线 / 只连 Futu）→ 不再打扰用户 ✓
    // ⚠ 但如果 settings 里**已经配了账号+密码**，就不能再被"上次选了离线"压住
    //   （用户实测：配了账号却一直连不上 —— 就是这条把 offline 强制打开了 ✗）
    const remembered = context.globalState.get('minibt.desk.mode', '');
    const hasCreds = !!(settings.account && settings.password);
    if (!settings.offline && remembered === 'offline' && !hasCreds) {
        settings.offline = true;
    }
    if (hasCreds && remembered === 'offline') {
        // 配上凭据后清掉旧的"离线"记忆，避免下次又被压住 ✓
        try {
            await context.globalState.update('minibt.desk.mode', '');
        } catch (error) { /* ignore */ }
    }
    return settings;
}

/** 体检：按当前设置 + Futu OpenD 连通性决定「直接起 / 弹提醒」✓ */
async function reviewDeskState(context, settings) {
    let futuReachable = false;
    if (settings.stocks !== 'off') {
        futuReachable = await desk.probePort(settings.futuHost,
                                             settings.futuPort, 1200);
    }
    return desk.decideStart(Object.assign({}, settings, { futuReachable }));
}

/** 没配置好 → 弹提醒让用户选（选项会记住 ✓） */
async function askDeskStart(context, settings) {
    const nothing = '进入离线演示';
    const claim = '输入天勤账号';
    const futu = '只连 Futu 股票';
    const openSettings = '打开设置';
    const picked = await vscode.window.showWarningMessage(
        `MiniBT 看盘：${settings.account
            ? '设置了天勤账号但没有密码'
            : `没设置天勤账号，也没检测到 Futu OpenD`
              + `（${settings.futuHost}:${settings.futuPort}）`}`,
        { modal: false, detail: '看盘终端需要至少一路行情：天勤账号（期货）'
                + ' 或 FutuOpenD（股票）。也可以先进离线演示看看界面。' },
        claim, futu, nothing, openSettings);
    if (picked === claim) {
        const account = await vscode.window.showInputBox({
            prompt: '天勤账号（快期）', value: settings.account || '' });
        if (account) {
            await vscode.workspace.getConfiguration('minibt').update(
                'desk.account', account, vscode.ConfigurationTarget.Workspace);
            const password = await vscode.window.showInputBox({
                prompt: '天勤密码（存进 VS Code 加密存储，不写 settings.json）',
                password: true });
            if (password) {
                try {
                    await context.secrets.store('minibt.desk.password', password);
                } catch (error) { /* 忽略 */ }
            }
        }
        return 'retry';
    }
    if (picked === futu) {
        await context.globalState.update('minibt.desk.mode', 'stocks');
        return 'retry';
    }
    if (picked === nothing) {
        await context.globalState.update('minibt.desk.mode', 'offline');
        return 'offline';
    }
    if (picked === openSettings) {
        await vscode.commands.executeCommand(
            'workbench.action.openSettings', 'minibt.desk');
    }
    return 'cancel';
}

/** 起 desk 子进程 + 等 `/healthz` + 把页面放进编辑器页签 ✓ */
async function startDesk(context) {
    const config = vscode.workspace.getConfiguration('minibt');
    const settings = await readDeskSettings(context);
    const plan = await reviewDeskState(context, settings);
    let forcedOffline = false;
    if (plan.action === desk.ACTIONS.warn) {
        const answer = await askDeskStart(context, settings);
        if (answer === 'cancel') return false;
        if (answer === 'offline') forcedOffline = true;
        if (!forcedOffline) return startDesk(context);   // 重新读设置再体检 ✓
    }
    stopDeskSession();

    const python = resolvePython(config);
    const isOffline = !!(forcedOffline || plan.mode === 'offline');
    const args = desk.buildDeskArgs(settings, {
        offline: isOffline, theme: settings.theme,
    });
    const env = desk.buildDeskEnv(process.env,
                                  Object.assign({}, settings, { offline: isOffline }));
    // Python 扩展设的解释器（`resolvePython` 已经挑好）
    const child = cp.spawn(python.cmd, python.args.concat(args), {
        cwd: workdir(context, config),
        env: env,
        windowsHide: true,
    });

    deskSession = {
        process: child, panel: null, url: null, settings: settings,
        stopping: false, plan: plan,
    };
    const channel = getDeskOutput();
    channel.clear();
    channel.appendLine(
        `[desk] MiniBT Charts v${VERSION} · ${python.cmd} ${args.join(' ')}`);
    channel.appendLine(`[desk] ${plan.reason || ''}`);

    const panel = vscode.window.createWebviewPanel(
        'minibtDesk', 'MiniBT 看盘终端', panelColumn(), panelOptions());
    // 页签图标 = 标题栏按钮那张 K 线图（浅/深色两版 ✓）
    try {
        panel.iconPath = deskIcon(context);
    } catch (error) {
        panel.iconPath = new vscode.ThemeIcon('graph-line');
    }
    panel.webview.html = chartShellHtml(nonceOf(), 'MiniBT 看盘终端');
    deskSession.panel = panel;
    panel.webview.onDidReceiveMessage((message) => {
        if (message && message.type === 'stop') stopDeskSession();
    });
    panel.onDidDispose(() => {
        if (!deskSession || deskSession.panel !== panel) return;
        deskSession.panel = null;
        stopDeskSession();
    });
    vscode.commands.executeCommand('setContext', 'minibt.deskOpen', true);
    updateDeskStatus({ running: false });

    // 读 stdout：就绪行（`--json` 那行 JSON）或日志
    let ready = false;
    child.stdout.on('data', (chunk) => {
        String(chunk).split(/\r?\n/).forEach((line) => {
            if (!line.trim()) return;
            channel.appendLine(line);
            const info = desk.parseReadyLine(line);
            if (info && info.url && !ready) {
                ready = true;
                showDeskUrl(panel, info.url);
                updateDeskStatus({
                    running: true, offline: isOffline,
                    futures: !isOffline && plan.futures,
                    stocks: !isOffline && plan.stocks,
                });
            }
        });
    });
    child.stderr.on('data', (chunk) => channel.append(chunk.toString()));
    child.on('exit', (code) => {
        channel.appendLine(`[desk] 进程退出（code=${code}）`);
        if (deskSession && deskSession.process === child) {
            deskSession.process = null;
            updateDeskStatus({});
            if (code !== 0 && code !== null && deskSession.panel) {
                deskSession.panel.webview.postMessage({
                    type: 'error',
                    text: `看盘终端已退出（code=${code}）。看「MiniBT 看盘」输出面板。`,
                });
            }
        }
    });

    // 兜底：没有就绪行时轮询 `/healthz`（端口由 --json 告诉，猜不到就 15s 后报错）
    pollDeskReady(panel, () => deskSession && deskSession.process === child)
        .then((info) => {
            if (info) {
                updateDeskStatus({
                    running: true, offline: isOffline,
                    futures: !isOffline && plan.futures,
                    stocks: !isOffline && plan.stocks,
                });
            }
        });
    return true;
}

/** 轮询 `/healthz`（只有拿到端口才探；否则等 stdout 的 JSON ✓） */
async function pollDeskReady(panel) {
    for (let i = 0; i < 60; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        if (!deskSession || !deskSession.process) return null;
        const url = deskSession.url;
        if (!url) continue;
        try {
            const info = await fetchJson(url + 'healthz');
            if (info && info.ready) return info;
        } catch (error) { /* 还没起来 */ }
    }
    return null;
}

function fetchJson(url) {
    return new Promise((resolve, reject) => {
        const http = require('http');
        const request = http.get(url, { timeout: 1500 }, (response) => {
            let body = '';
            response.setEncoding('utf8');
            response.on('data', (chunk) => { body += chunk; });
            response.on('end', () => {
                try { resolve(JSON.parse(body)); }
                catch (error) { resolve(null); }
            });
        });
        request.on('timeout', () => { request.destroy(); resolve(null); });
        request.on('error', reject);
    });
}

/** 把 URL 交给 iframe 外壳（会带上时间戳避免复用旧页面 ✓） */
function showDeskUrl(panel, url) {
    if (!panel) return;
    deskSession && (deskSession.url = url);
    panel.webview.postMessage({ type: 'url', url: url });
    panel.title = 'MiniBT 看盘终端';
}

/** 看盘终端的图标（`media/desk-{light,dark}.svg`，和标题栏按钮同一张 ✓） */
function deskIcon(context) {
    const dark = vscode.window.activeColorTheme
        && vscode.window.activeColorTheme.kind === 2;
    const name = dark ? 'desk-dark.svg' : 'desk-light.svg';
    return {
        light: vscode.Uri.file(path.join(context.extensionPath, 'media', name)),
        dark: vscode.Uri.file(path.join(context.extensionPath, 'media', name)),
    };
}

/** 工作目录：`minibt.desk.cwd` → `minibt.cwd` → 工作区根 ✓ */
/**
 * 从 `start` 逐级向上找含 `minibt/__init__.py` 的目录。
 *
 * 本地开发时扩展目录（`vscode-minibt/`）就在仓库里，跑到它上一层才能
 * `python -m minibt` 用**源码版**（而不是 site-packages 里的旧版 ✓）。
 */
function findLocalMinibt(start) {
    let dir = start;
    for (let depth = 0; depth < 8; depth += 1) {
        try {
            if (fs.existsSync(path.join(dir, 'minibt', '__init__.py'))) {
                return dir;
            }
        } catch (error) { /* 跳过 */ }
        const parent = path.dirname(dir);
        if (!parent || parent === dir) break;
        dir = parent;
    }
    return '';
}

function workdir(context, config) {
    const configured = config.get('cwd', '') || '';
    if (configured) return configured;
    const folders = vscode.workspace.workspaceFolders;
    const root = folders && folders.length
        ? folders[0].uri.fsPath : context.extensionPath;
    return findLocalMinibt(root) || root;
}

function getDeskOutput() {
    if (!deskOutput) deskOutput = vscode.window.createOutputChannel('MiniBT 看盘');
    return deskOutput;
}
let deskOutput = null;

function stopDeskSession() {
    if (!deskSession || deskSession.stopping) return;
    deskSession.stopping = true;
    const child = deskSession.process;
    const panel = deskSession.panel;
    deskSession.process = null;
    deskSession.panel = null;
    deskSession.url = null;
    stopChildProcess(child);
    try { if (panel) panel.dispose(); } catch (error) { /* 已关 */ }
    deskSession = null;
    updateDeskStatus({});
    vscode.commands.executeCommand('setContext', 'minibt.deskOpen', false);
}

/** 状态栏：`● 已连接 · 期货+股票` / `○ 未启动`（点一下起停 ✓） */
function updateDeskStatus(state) {
    if (!deskStatus) return;
    deskStatus.text = desk.statusText(state || {});
    deskStatus.tooltip = (state && state.running)
        ? 'MiniBT 看盘终端运行中（点一下停止）'
        : '启动 MiniBT 看盘终端（Minibt desk）';
    deskStatus.command = (state && state.running)
        ? 'minibt.stopDesk' : 'minibt.openDesk';
}

// ---------------------------------------------------------------- 命令注册
function activate(context) {
    context.subscriptions.push(
        vscode.commands.registerCommand('minibt.runInEditor', async () => {
            await start(context);
        }),

        vscode.commands.registerCommand('minibt.showLog', () => {
            if (session && session.logPanel) {
                session.logPanel.reveal(panelColumn(), true);
            } else if (session && session.script) {
                openLogPanel(context, `MiniBT 策略日志 — ${
                    path.basename(session.script)}`);
            } else {
                getOutput().show(true);
            }
        }),

        vscode.commands.registerCommand('minibt.reloadChart', () => {
            if (!session || !session.panel) return;
            if (session.kind === 'live' && session.url) {
                postChart({ type: 'url', url: session.url });
            } else if (session.kind === 'static' && session.htmlPath) {
                showStaticPanel(context, session.htmlPath, session.panel.title);
            }
        }),

        vscode.commands.registerCommand('minibt.stopChart', () => stopSession()),

        vscode.commands.registerCommand('minibt.openInBrowser', () => {
            if (session && session.url) {
                vscode.env.openExternal(vscode.Uri.parse(session.url));
            } else if (session && session.htmlPath) {
                vscode.env.openExternal(vscode.Uri.file(session.htmlPath));
            } else {
                vscode.window.showInformationMessage('MiniBT：现在没有打开图表。');
            }
        }),

        vscode.commands.registerCommand('minibt.showOutput', () => {
            getOutput().show(true);
        }),

        // ---- 看盘终端（minibt desk）----
        vscode.commands.registerCommand('minibt.openDesk', async () => {
            try {
                await startDesk(context);
            } catch (error) {
                getDeskOutput().appendLine(`[desk] 启动失败：${error && error.stack}`);
                vscode.window.showErrorMessage(
                    `MiniBT 看盘启动失败：${error && error.message}`);
            }
        }),

        vscode.commands.registerCommand('minibt.stopDesk', () => stopDeskSession()),

        vscode.commands.registerCommand('minibt.showDeskOutput', () => {
            getDeskOutput().show(true);
        }),

        // 密码存 VS Code 加密存储（不写 settings.json ✓）
        vscode.commands.registerCommand('minibt.desk.setPassword', async () => {
            const password = await vscode.window.showInputBox({
                prompt: '天勤密码（存进 VS Code 加密存储，不会写 settings.json）',
                password: true,
            });
            if (!password) return;
            try {
                await context.secrets.store('minibt.desk.password', password);
                vscode.window.showInformationMessage('MiniBT：天勤密码已保存（加密存储）');
            } catch (error) {
                vscode.window.showErrorMessage(
                    `MiniBT：保存密码失败（${error && error.message}）`);
            }
        }),

        vscode.commands.registerCommand('minibt.desk.clearPassword', async () => {
            try {
                await context.secrets.delete('minibt.desk.password');
                vscode.window.showInformationMessage('MiniBT：已清除保存的天勤密码');
            } catch (error) { /* 老 VS Code 没有 secrets */ }
        }),
    );

    // 状态栏「MiniBT 看盘」：点一下起 / 停 ✓
    deskStatus = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right, 90);
    deskStatus.name = 'MiniBT 看盘';
    updateDeskStatus({});
    deskStatus.show();
    context.subscriptions.push(deskStatus);

    // 打开 VS Code 就自动起（两种触发）✓
    //   ① `minibt.desk.autoStart: true`（用户显式要求）
    //   ② settings.json 里**已配置账号 + 密码**（或 offline / 只连股票）
    //      → 自动登录，不用再点状态栏（用户实测：配了账号却没自动连 ✗）
    const deskConfig = vscode.workspace.getConfiguration('minibt');
    const autoStart = deskConfig.get('desk.autoStart', false);
    const configured = !!(String(deskConfig.get('desk.account', '') || '')
        && String(deskConfig.get('desk.password', '') || ''));
    const offline = !!deskConfig.get('desk.offline', false);
    const futuHost = String(deskConfig.get('desk.futuHost', '127.0.0.1'));
    const futuPort = Number(deskConfig.get('desk.futuPort', 11111)) || 11111;
    const stocksWanted = String(deskConfig.get('desk.stocks', 'auto'))
        !== 'off';
    // 诊断：把「读到了什么」写进「MiniBT 看盘」输出面板（排查没自动连 ✓）
    const deskLog = getDeskOutput();
    deskLog.appendLine(`[auto] account=${deskConfig.get('desk.account', '')
        ? '✓' : '✗'}  password=${String(deskConfig.get('desk.password', ''))
        ? '✓' : '✗'}  offline=${offline}  autoStart=${autoStart}`
        + `  futu=${futuHost}:${futuPort}`);
    if (autoStart || configured || offline) {
        deskLog.appendLine(`[auto] 满足自动启动条件 → 1.2s 后打开看盘终端`
            + (configured ? '（settings 里有账号+密码）' : ''));
        setTimeout(() => {
            vscode.commands.executeCommand('minibt.openDesk');
        }, 1200);
    } else if (stocksWanted) {
        // 没配置账号时：探一下 FutuOpenD，通就自动只连股票 ✓
        desk.probePort(futuHost, futuPort, 1200).then((ok) => {
            if (ok) {
                vscode.commands.executeCommand('minibt.openDesk');
            }
        });
    }
}

function deactivate() {
    stopSession();
    stopDeskSession();
}

module.exports = { activate, deactivate, resolvePython, desk };

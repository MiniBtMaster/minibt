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

/** 当前会话。 */
let session = null;

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

function openLogPanel(context, title) {
    if (session && session.logPanel) {
        session.logPanel.reveal(vscode.ViewColumn.Beside, true);
        session.logPanel.title = title || session.logPanel.title;
        return session.logPanel;
    }
    const panel = vscode.window.createWebviewPanel(
        'minibtLog', title || 'MiniBT 策略日志', vscode.ViewColumn.Beside,
        { enableScripts: true, retainContextWhenHidden: true },
    );
    panel.webview.html = logPanelHtml(nonceOf());
    for (const item of (session && session.logLines) || []) {
        postLog([item]);
    }
    panel.onDidDispose(() => {
        if (session) session.logPanel = null;
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
    if (session && session.panel) {
        session.panel.title = title;
        session.panel.reveal(vscode.ViewColumn.Active, false);
        if (session.kind !== 'live') {
            session.kind = 'live';
            session.panel.webview.html = chartShellHtml(nonceOf(), title);
        }
        return session.panel;
    }
    const panel = vscode.window.createWebviewPanel(
        'minibtChart', title, vscode.ViewColumn.Active, panelOptions());
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
            'minibtChart', title, vscode.ViewColumn.Active, panelOptions());
        panel.iconPath = new vscode.ThemeIcon('file-media');
        attachPanel(context, panel, 'static', htmlPath);
    } else {
        session.kind = 'static';
        session.panel.title = title;
        session.panel.reveal(vscode.ViewColumn.Active, false);
        session.panel.iconPath = new vscode.ThemeIcon('file-media');
    }
    panel.webview.html = html;
    if (session) session.htmlPath = htmlPath;
    return panel;
}

function attachPanel(context, panel, kind, target) {
    if (!session) session = {};
    session.panel = panel;
    session.kind = kind;
    if (kind === 'live') session.url = target;
    else session.htmlPath = target;
    vscode.commands.executeCommand('setContext', 'minibt.chartOpen', true);
    panel.onDidDispose(() => {
        vscode.commands.executeCommand('setContext', 'minibt.chartOpen', false);
        if (!session) return;
        session.panel = null;
        const keep = vscode.workspace.getConfiguration('minibt')
            .get('keepAliveOnClose', false);
        if (!keep) stopSession();
    });
}

function stopSession() {
    if (!session) return;
    const child = session.process;
    const panel = session.panel;
    const logPanel = session.logPanel;
    session.process = null;
    if (child && child.exitCode === null) {
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
    for (const target of [panel, logPanel]) {
        if (target) {
            target.webview.html = `<!DOCTYPE html><html><body
                style="font-family: sans-serif; padding: 1em; color: #999">
                <h3>已停止</h3>
                <p>策略进程已结束。按 <b>Ctrl+Alt+M</b> 重新运行。</p></body></html>`;
        }
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
    };
    const channel = getOutput();
    channel.clear();
    channel.appendLine(
        `[minibt] MiniBT Charts v${VERSION} · ${pythonLabel} → ${name}`
        + `（engine=${engine}）`);
    channel.show(true);
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

// ---------------------------------------------------------------- 命令注册
function activate(context) {
    context.subscriptions.push(
        vscode.commands.registerCommand('minibt.runInEditor', async () => {
            await start(context);
        }),

        vscode.commands.registerCommand('minibt.showLog', () => {
            if (session && session.logPanel) {
                session.logPanel.reveal(vscode.ViewColumn.Beside, true);
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
    );
}

function deactivate() {
    stopSession();
}

module.exports = { activate, deactivate, resolvePython };

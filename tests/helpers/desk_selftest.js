// MiniBT 看盘终端：**不用启动 VS Code** 的自检脚本（给 pytest 调用）。
//
// 做法：把 `vscode` 模块换成假对象 → require extension.js → activate →
// 调 `minibt.openDesk` → 等外壳收到 `{type:'url'}`（iframe 地址）→ 再停掉。
//
// 用法：
//   node tests/helpers/desk_selftest.js '{"minibt.pythonPath":"python", ...}'
// 输出：一行 JSON（`{ok, url, healthz, messages, commands, error}`）✓
const Module = require('module');
const path = require('path');

const configValues = JSON.parse(process.argv[2] || '{}');

const messages = [];
const errors = [];
const warnings = [];
const commands = {};
let statusItem = null;
let panel = null;

function makeChannel() {
    return {
        lines: [],
        appendLine(text) { this.lines.push(String(text)); },
        append(text) { this.lines.push(String(text)); },
        clear() { this.lines.length = 0; },
        show() {},
        dispose() {},
    };
}

const vscodeStub = {
    version: '1.85.0',
    window: {
        activeColorTheme: { kind: 2 },          // dark
        activeTextEditor: undefined,
        createOutputChannel: () => makeChannel(),
        createStatusBarItem: () => {
            statusItem = {
                text: '', tooltip: '', command: '', name: '',
                show() {}, hide() {}, dispose() {},
            };
            return statusItem;
        },
        createWebviewPanel: () => {
            panel = {
                title: '',
                iconPath: null,
                webview: {
                    html: '',
                    postMessage(message) { messages.push(message); },
                    onDidReceiveMessage(handler) { panel._onMessage = handler; },
                },
                onDidDispose(handler) { panel._onDispose = handler; },
                reveal() {},
                dispose() { if (panel._onDispose) panel._onDispose(); },
            };
            return panel;
        },
        showWarningMessage: async (text) => { warnings.push(String(text)); return undefined; },
        showInformationMessage: async () => undefined,
        showErrorMessage: async (text) => { errors.push(String(text)); },
        showInputBox: async () => undefined,
        showOpenDialog: async () => undefined,
    },
    workspace: {
        workspaceFolders: [],
        getConfiguration: () => ({
            get(key, fallback) {
                return key in configValues ? configValues[key] : fallback;
            },
            async update() {},
        }),
    },
    commands: {
        registerCommand(name, handler) {
            commands[name] = handler;
            return { dispose() {} };
        },
        async executeCommand() {},
    },
    StatusBarAlignment: { Left: 1, Right: 2 },
    ViewColumn: { Active: -1, Beside: -2, One: 1, Two: 2, Three: 3 },
    QuickPickItemKind: { Separator: -1, Default: 0 },
    ThemeIcon: class ThemeIcon { constructor(id) { this.id = id; } },
    Uri: { parse: (text) => ({ fsPath: text, toString: () => text }),
           file: (text) => ({ fsPath: text }) },
    ConfigurationTarget: { Global: 1, Workspace: 2, WorkspaceFolder: 3 },
    env: { openExternal: async () => true },
    ProgressLocation: { Notification: 15 },
};

// ------------------------------------------------------------ 拦截 require
const originalLoad = Module._load;
Module._load = function patched(request, parent, isMain) {
    if (request === 'vscode') return vscodeStub;
    return originalLoad.call(this, request, parent, isMain);
};

const extensionPath = path.resolve(__dirname, '..', '..', 'vscode-minibt');
const context = {
    extensionPath,
    subscriptions: [],
    secrets: {
        async get() { return undefined; },
        async store() {},
        async delete() {},
    },
    globalState: {
        _data: {},
        get(key, fallback) { return key in this._data ? this._data[key] : fallback; },
        async update(key, value) { this._data[key] = value; },
    },
};

function httpGetJson(url, timeoutMs) {
    return new Promise((resolve) => {
        const http = require('http');
        const request = http.get(url, { timeout: timeoutMs || 2000 },
            (response) => {
                let body = '';
                response.setEncoding('utf8');
                response.on('data', (chunk) => { body += chunk; });
                response.on('end', () => {
                    try { resolve(JSON.parse(body)); }
                    catch (error) { resolve(null); }
                });
            });
        request.on('timeout', () => { request.destroy(); resolve(null); });
        request.on('error', () => resolve(null));
    });
}

async function main() {
    const extension = require(path.join(extensionPath, 'extension.js'));
    await extension.activate(context);
    const result = {
        ok: false, url: null, healthz: null, messages: [],
        warn: false, status: statusItem ? statusItem.text : null,
        message: null, error: null,
    };
    try {
        await commands['minibt.openDesk']();
        // 等 iframe 地址（就绪行 / 轮询最多 30s）
        for (let i = 0; i < 120; i += 1) {
            const found = messages.find((item) => item && item.type === 'url');
            if (found) { result.url = found.url; break; }
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
        if (result.url) {
            result.healthz = await httpGetJson(result.url + 'healthz');
            result.ok = !!(result.healthz && result.healthz.ready);
        }
        result.messages = messages.map((item) => item && item.type);
        result.status = statusItem ? statusItem.text : null;
        await commands['minibt.stopDesk']();
    } catch (error) {
        result.error = String(error && (error.stack || error.message || error));
    }
    result.warn = warnings.length > 0;
    result.message = warnings[0] || null;
    if (errors.length) result.error = result.error || errors.join(' | ');
    process.stdout.write(JSON.stringify(result) + '\n');
    process.exit(result.ok ? 0 : 1);
}

main();

"""Drive tests/e2e/vp_e2e.html (generated from the real minibt VP JS) in a headless
browser via CDP and report whether the Volume Profile follows the mouse.

    python tests/e2e/vp_e2e_check.py
"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from pylightcharts.headless import find_browser          # noqa: E402
from websockets.sync.client import connect               # noqa: E402
from minibt.strategy.realtime import _vp_draw_js         # noqa: E402
from minibt.utils import VPStyle                          # noqa: E402

PORT = 9337


def build_page() -> pathlib.Path:
    """把 vp_hover.html 里手写的两个回调换成 minibt **真正生成**的 JS。"""
    base = (HERE / 'vp_hover.html').read_text(encoding='utf-8')
    draw = _vp_draw_js(4, VPStyle(), 'row.vmax', False, 'VPX')
    # 记录每次绘制用的锚点（应**恒定**= 最右可见根）与数据行（应跟随鼠标）：
    draw = draw.replace('const anchor = scope.mediaSize.width;',
                        'const anchor = scope.mediaSize.width; window.__hits.push(anchor);')
    draw = draw.replace('const row = hovered.originalData;',
                        'const row = hovered.originalData; window.__rows.push(row.lo);')
    draw = draw.replace(chr(92), chr(92) * 2).replace('`', chr(92) + '`')
    start = base.index("Lib.registerCallback('vp_draw'")
    end = base.index("Lib.registerCallback('vp_empty'")
    base = base[:start] + (
        "window.__hits = []; window.__rows = [];\n"
        "Lib.registerCallback('vp_draw', ['target','priceConverter','view'],\n"
        "  `" + draw + "`);\n"
        "Lib.registerCallback('vp_price', ['row','view'], "
        "'return [row.lo, row.hi];');\n  "
    ) + base[end:]
    # 十字线监听器与 minibt 生成的完全一致（含 applyOptions({}) 强制重绘）
    base = base.replace(
        "      h.addCrosshairListener((param) => {\n"
        "        window.__hover = (param && param.point) ? param.point.x : null;\n"
        "      });",
        "      window.__hover = null;\n"
        "      window.__listener = (param) => {\n"
        "        window.__hover = (param && param.point) ? param.point.x : null;\n"
        "        window.VPX = window.__hover;\n"   # ← rendererDraw 读的就是它
        "        window.__draws_forced = (window.__draws_forced || 0) + 1;\n"
        "        try { cs.series.applyOptions({}); } catch (e) {}\n"
        "      };\n"
        "      h.addCrosshairListener(window.__listener);")
    base = base.replace(
        "anchor: window.__anchors[window.__anchors.length - 1],",
        "anchor: window.__hits[window.__hits.length - 1],\n"
        "        row: window.__rows[window.__rows.length - 1],\n"
        "        hits: window.__hits.length,")
    out = HERE / 'vp_e2e.html'
    out.write_text(base, encoding='utf-8')
    return out


def main() -> int:
    page = build_page().resolve().as_uri()
    proc = subprocess.Popen(
        [find_browser(), '--headless=new', '--disable-gpu', '--no-sandbox',
         '--allow-file-access-from-files', f'--remote-debugging-port={PORT}',
         '--window-size=1000,700', page],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(4)
        targets = json.loads(urllib.request.urlopen(
            f'http://127.0.0.1:{PORT}/json/list', timeout=2).read())
        target = [t for t in targets if t.get('type') == 'page'][0]
        with connect(target['webSocketDebuggerUrl'], max_size=None) as ws:
            counter = [0]

            def send(method, params=None):
                counter[0] += 1
                ws.send(json.dumps({'id': counter[0], 'method': method,
                                    'params': params or {}}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get('id') == counter[0]:
                        return msg

            def evaluate(expr):
                msg = send('Runtime.evaluate',
                           {'expression': expr, 'returnByValue': True})
                return msg['result'].get('result', {}).get(
                    'value', msg['result'].get('exceptionDetails'))

            def move(x, y):
                send('Input.dispatchMouseEvent',
                     {'type': 'mouseMoved', 'x': x, 'y': y, 'button': 'none'})

            send('Runtime.enable')
            send('Input.enable')
            time.sleep(1.2)
            print('load        :', evaluate('JSON.stringify(window.__report())'))
            move(250, 300)
            time.sleep(0.6)
            print('hover x=250 :', evaluate('JSON.stringify(window.__report())'),
                  '  <- anchor 恒不变(=绘图区宽)，row 跟着鼠标')
            time.sleep(1.2)
            print('1.2s later  :', evaluate('JSON.stringify(window.__report())'),
                  '  <- 不应继续增长（无 runaway 重绘）')
            move(620, 300)
            time.sleep(0.6)
            first = evaluate('JSON.stringify(window.__report())')
            print('hover x=620 :', first)
            move(-50, 300)          # 移到图表左侧外
            time.sleep(0.6)
            print('mouse out   :', evaluate('JSON.stringify(window.__report())'),
                  '  <- 回落（anchor 仍不变，row 回到最右根）')
            print('errors      :', evaluate(
                '(window.__err || "none")'))
        return 0
    finally:
        proc.terminate()


if __name__ == '__main__':
    raise SystemExit(main())

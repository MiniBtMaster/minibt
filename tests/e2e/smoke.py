"""Render tests/e2e/smoke.html in a headless browser and report the result.

Uses Playwright when available, otherwise falls back to a local Chrome/Edge CLI.

    python tests/e2e/smoke.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Optional

# runnable from anywhere: `python tests/e2e/smoke.py` or from this folder
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from pylightcharts.headless import find_browser

HERE = pathlib.Path(__file__).resolve().parent
PAGE = HERE / 'smoke.html'
FAIL_MARKERS = ('RESULT_ERROR', 'PIXEL_ERROR')


def run_with_playwright() -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        page.goto(PAGE.as_uri())
        page.wait_for_timeout(2500)
        text = page.inner_text('#result')
        browser.close()
    return text


def run_with_cli() -> str:
    browser = find_browser()
    if not browser:
        raise SystemExit('No browser found (install playwright or set PYLIGHTCHARTS_CHROME)')
    result = subprocess.run(
        [browser, '--headless=new', '--disable-gpu', '--no-sandbox',
         '--allow-file-access-from-files', '--virtual-time-budget=12000',
         '--window-size=1000,700', '--dump-dom', PAGE.as_uri()],
        capture_output=True, text=True,
        # the page (and the dumped DOM) is UTF-8; on Windows the locale codec
        # (GBK) would choke on the legend's swatch character and hand back None
        encoding='utf-8', errors='replace',
    )
    match = re.search(r'<pre id="result">([^<]*)', result.stdout)
    if not match:
        raise SystemExit('could not find the result element in the dumped DOM')
    return match.group(1)


def main() -> int:
    text = run_with_playwright()
    backend = 'playwright'
    if text is None:
        text = run_with_cli()
        backend = 'cli'

    print(f'backend: {backend}')
    for line in text.split('|'):
        print('  ' + line.strip())

    failed = any(marker in text for marker in FAIL_MARKERS) or 'RESULT_OK' not in text
    if failed:
        print('SMOKE FAILED', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

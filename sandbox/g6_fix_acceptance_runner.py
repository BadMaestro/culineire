#!/usr/bin/env python3
"""G6-FIX acceptance: seat and crowd face move together under camera transform."""
import json
import math
import os
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("PLAYWRIGHT_MISSING", file=sys.stderr)
    sys.exit(2)

HTML = ROOT / "sandbox" / "g6_fix_acceptance.html"


def main():
    if not HTML.is_file():
        raise SystemExit(f"missing fixture: {HTML}")
    url = HTML.as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 1100})
        page.goto(url)
        page.wait_for_function("window.G6_RESULT != null", timeout=15000)
        result = page.evaluate("window.G6_RESULT")
        browser.close()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

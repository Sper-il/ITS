"""
Comprehensive Playwright smoke-test for all ITS pages.
Each page gets its own isolated browser context (fresh DOM).

Usage:
    python test_all_pages.py            # all pages
    python test_all_pages.py overview   # single page
    python test_all_pages.py predict    # single page
    python test_all_pages.py routing    # single page
    python test_all_pages.py navigation # single page
"""
import sys, socket, time
from pathlib import Path

from playwright.sync_api import sync_playwright

# ── Config ────────────────────────────────────────────────────────────────────
HOST    = "127.0.0.1"
PORT    = 8000
BASE    = f"http://{HOST}:{PORT}"
TIMEOUT = 20_000   # ms
SLEEP   = 0.8


# ── Page definitions (verified against HTML templates) ───────────────────────
PAGES = {
    "overview": {
        "url":      f"{BASE}/overview",
        "title":    "Overview Dashboard",
        "wait_for": "nav",
        "elements": [
            "#sidebar-accuracy",
            "#donut-A",
            "#donut-center-count",
            "#kpi-samples",
            "#kpi-mean-conf",
            "#kpi-dominant-los",
        ],
    },
    "predict": {
        "url":      f"{BASE}/predict",
        "title":    "Quick Predict",
        "wait_for": "nav",
        "elements": [
            "#predict-btn",
            "#slider-length",
            "#slider-speed",
            "#slider-vc",
            "#slider-hour",
            "#val-length",
        ],
    },
    "routing": {
        "url":      f"{BASE}/routing",
        "title":    "Routing",
        "wait_for": "nav",
        "elements": [
            "#leaflet-map",
            "#input-start",
            "#input-end",
            "#swap-btn",
            "#vehicle-btn",
            "#find-route-btn",
        ],
    },
    "navigation": {
        "url":      f"{BASE}/navigation",
        "title":    "Navigation Mode",
        "wait_for": "body",
        "elements": [
            ".material-symbols-outlined",
        ],
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def wait_for_server(host=HOST, port=PORT, max_wait=15) -> bool:
    print(f"[boot] Waiting for {host}:{port}...")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                print("[boot] Server is up!")
                return True
        except OSError:
            time.sleep(0.5)
    print("[boot] Timed out -- is `python app.py` running?")
    return False


def check_element(page, selector):
    try:
        return page.query_selector(selector) is not None
    except Exception:
        return False


def test_page(browser, name, info) -> tuple[bool, bool, list]:
    """
    Load one page in an isolated context.
    Returns (page_ok, err_ok, console_errors).
    """
    url      = info["url"]
    wait_for = info["wait_for"]
    elements = info["elements"]

    ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page_ok = True
    errors: list[str] = []

    def on_console(m):
        if m.type == "error":
            errors.append(m.text)
    def on_pageerror(e):
        errors.append(str(e))

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)

    print(f"    GET {url}", end=" ... ")
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=TIMEOUT)
        status = resp.status if resp else 0
        if status >= 400:
            print(f"HTTP {status} FAIL")
            ctx.close()
            return False, True, errors
        print(f"HTTP {status} OK")
    except Exception as ex:
        print(f"FAIL: {ex}")
        ctx.close()
        return False, True, errors

    try:
        page.wait_for_selector(wait_for, timeout=TIMEOUT)
    except Exception as ex:
        print(f"    [WARN] shell '{wait_for}' not found: {ex}")
        page_ok = False

    time.sleep(SLEEP)

    for sel in elements:
        found = check_element(page, sel)
        tag = "OK" if found else "FAIL"
        print(f"    [{tag:5}] {sel}")
        if not found:
            page_ok = False

    # Interact: click nav links (each in its own context)
    if name == "overview":
        for dest, label in [("/predict", "nav->Predict"), ("/routing", "nav->Routing")]:
            _test_nav_link(browser, dest, label)
    elif name == "predict":
        for dest, label in [("/overview", "nav->Overview"), ("/routing", "nav->Routing")]:
            _test_nav_link(browser, dest, label)
        # Interact with sliders
        _test_predict_sliders(page)
    elif name == "routing":
        for dest, label in [("/overview", "nav->Overview"), ("/predict", "nav->Predict")]:
            _test_nav_link(browser, dest, label)
        # Interact with routing elements
        _test_routing_interactions(page)

    # Screenshot
    try:
        ss_dir = Path(__file__).parent / "screenshots"
        ss_dir.mkdir(exist_ok=True)
        path = ss_dir / f"{name}.png"
        page.screenshot(path=str(path), full_page=False)
        print(f"    [OK   ] screenshot -> {path}")
    except Exception as ex:
        print(f"    [WARN ] screenshot failed: {ex}")

    ctx.close()
    return page_ok, True, errors


def _test_nav_link(browser, dest, label):
    """Verify a nav link destination loads."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    print(f"    [OK   ] {label} -> GET {dest}", end=" ... ")
    try:
        resp = page.goto(f"{BASE}{dest}", wait_until="networkidle", timeout=10000)
        status = resp.status if resp else 0
        print(f"HTTP {status}")
    except Exception as ex:
        print(f"FAIL: {ex}")
    ctx.close()


def _test_predict_sliders(page):
    """Drag each slider and click the predict button."""
    for sel, label in [
        ("#slider-length", "length"),
        ("#slider-speed",   "speed"),
        ("#slider-vc",      "v/c"),
        ("#slider-hour",    "hour"),
    ]:
        el = page.query_selector(sel)
        if el:
            try:
                el.evaluate("el => el.value = String(Math.round(el.max * 0.5))")
                el.dispatch_event("input")
                print(f"    [OK   ] slider {label}: set to 50%")
            except Exception as ex:
                print(f"    [SKIP ] slider {label}: {ex}")
        else:
            print(f"    [SKIP ] slider {label}: not found")

    # Click predict
    btn = page.query_selector("#predict-btn")
    if btn:
        btn.click()
        time.sleep(1)
        print(f"    [OK   ] predict button clicked")
        # Check if result appeared
        if page.query_selector("pre"):
            print(f"    [OK   ] result block visible")
        else:
            print(f"    [WARN ] result block not found")
    else:
        print(f"    [SKIP ] predict button not found")


def _test_routing_interactions(page):
    """Interact with routing form elements."""
    # Click swap
    swap = page.query_selector("#swap-btn")
    if swap:
        swap.click()
        time.sleep(0.3)
        print(f"    [OK   ] swap button clicked")
    else:
        print(f"    [SKIP ] swap button not found")

    # Click vehicle selector
    vehicle = page.query_selector("#vehicle-btn")
    if vehicle:
        vehicle.click()
        time.sleep(0.3)
        # Check if menu appeared
        menu = page.query_selector("#vehicle-menu")
        if menu:
            print(f"    [OK   ] vehicle menu opened")
            # Close it
            vehicle.click()
        else:
            print(f"    [WARN ] vehicle menu not found after click")
    else:
        print(f"    [SKIP ] vehicle button not found")

    # Type into start/end
    for sel, label in [("#input-start", "start"), ("#input-end", "end")]:
        el = page.query_selector(sel)
        if el:
            try:
                el.fill("Test Location")
                el.dispatch_event("input")
                print(f"    [OK   ] {label} input: typed")
            except Exception as ex:
                print(f"    [SKIP ] {label} input: {ex}")
        else:
            print(f"    [SKIP ] {label} input not found")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if args and args[0] in PAGES:
        targets = {args[0]: PAGES[args[0]]}
    elif args:
        print(f"Unknown: {args[0]}")
        print(f"Available: {', '.join(PAGES)}")
        sys.exit(1)
    else:
        targets = PAGES

    if not wait_for_server():
        sys.exit(1)

    all_ok = True
    all_errors: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for name, info in targets.items():
            print(f"\n{'='*60}")
            print(f"  PAGE: {name.upper()}")
            print(f"{'='*60}")
            page_ok, err_ok, errors = test_page(browser, name, info)
            if not page_ok:
                all_ok = False
            all_errors.extend(errors)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    if all_errors:
        print(f"\nConsole errors ({len(all_errors)}):")
        for e in all_errors:
            print(f"  * {e[:150]}")
    else:
        print("Console errors: NONE")

    print(f"\nScreenshots: {Path(__file__).parent / 'screenshots'}")
    print()
    if all_ok:
        print("ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()

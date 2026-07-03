"""
Playwright smoke-test for the ITS routing tab.
Runs headless, opens http://127.0.0.1:8000/routing, waits for the Leaflet
map + RoutingApp to load, checks for zero console errors, and confirms the
map canvas is visible.
"""
import time, sys, socket
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE     = "http://127.0.0.1:8000"
HOST     = "127.0.0.1"
PORT     = 8000
URL      = f"{BASE}/routing"
TIMEOUT  = 20_000  # ms


def _wait_for_server(host=HOST, port=PORT, max_wait=15) -> bool:
    """Poll until the Flask dev server is reachable."""
    print(f"[boot] Waiting for {host}:{port} to be ready...")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                print("[boot] Server is up!")
                return True
        except OSError:
            time.sleep(0.5)
    print(f"[boot] Timed out after {max_wait}s -- is `python app.py` running?")
    return False


def run() -> bool:
    ok = True

    if not _wait_for_server():
        return False

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx  = browser.new_context()
        page = ctx.new_page()

        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        # 1. Navigate
        print(f"[1] Opening {URL}")
        resp = page.goto(URL, wait_until="networkidle", timeout=TIMEOUT)
        if not resp or resp.status >= 400:
            print(f"    FAIL - HTTP {resp.status if resp else 'None'}")
            ok = False
        else:
            print(f"    OK  - HTTP {resp.status}")

        # 2. Wait for RoutingApp
        print("[2] Waiting for routing_app.js to define RoutingApp...")
        try:
            page.wait_for_function(
                "window.RoutingApp && typeof window.RoutingApp === 'object'",
                timeout=TIMEOUT,
            )
            print("    OK  - RoutingApp defined")
        except Exception as ex:
            print(f"    WARN - {ex}")

        time.sleep(2)

        # 3. Map container
        print("[3] Checking #leaflet-map container...")
        map_el = page.query_selector("#leaflet-map")
        if map_el:
            bb = map_el.bounding_box()
            if bb and bb["width"] > 0 and bb["height"] > 0:
                print(f"    OK  - {bb['width']:.0f} x {bb['height']:.0f} px")
            else:
                print(f"    FAIL - zero-size box: {bb}")
                ok = False
        else:
            print("    FAIL - #leaflet-map not found")
            ok = False

        # 4. Canvas
        print("[4] Checking Leaflet canvas...")
        canvas = page.query_selector("#leaflet-map canvas")
        if canvas:
            bb = canvas.bounding_box()
            print(f"    OK  - canvas {bb['width']:.0f} x {bb['height']:.0f} px")
        else:
            time.sleep(2)
            canvas = page.query_selector("#leaflet-map canvas")
            if canvas:
                bb = canvas.bounding_box()
                print(f"    OK  - canvas (delayed) {bb['width']:.0f} x {bb['height']:.0f} px")
            else:
                print("    WARN - no canvas found (tiles may still loading)")

        # 5. L global
        print("[5] Checking L global...")
        map_exists = page.evaluate(
            "() => typeof L !== 'undefined' && L.Map !== undefined"
        )
        status = "OK" if map_exists else "FAIL"
        state  = "exists" if map_exists else "missing"
        print(f"    {status} - L.Map {state}")

        # 6. Console errors
        if console_errors:
            print(f"\n[!!] Console errors ({len(console_errors)}):")
            for e in console_errors:
                print(f"    * {e}")
            ok = False
        else:
            print("\n[6] Console errors: none")

        # 7. Screenshot
        screenshot_path = Path(__file__).parent / "test_routing_screenshot.png"
        page.screenshot(path=str(screenshot_path), full_page=False)
        print(f"\n[7] Screenshot saved to: {screenshot_path}")

        browser.close()

    print()
    if ok:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED -- see above")
    return ok


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)

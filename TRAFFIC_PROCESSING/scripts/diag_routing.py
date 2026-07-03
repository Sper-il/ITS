"""
Diagnostic screenshot capture for the Routing page.
Run: python scripts/diag_routing.py
Outputs screenshots to output/screenshots/.
"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Fix UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

BASE = "http://localhost:8501"
OUT = Path(__file__).resolve().parents[1] / "output" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


async def shot(page, name):
    p = OUT / f"{name}.png"
    await page.screenshot(path=str(p), full_page=False)
    print(f"  -> {p}")


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            locale="vi-VN",
        )
        page = await ctx.new_page()

        # 1. Open the app root
        await page.goto(BASE, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        await shot(page, "01_home")

        # 2. Navigate to the Routing tab
        try:
            tab_btn = page.get_by_role("tab", name="Routing")
            await tab_btn.click(timeout=10000)
            await page.wait_for_timeout(3000)
            await shot(page, "02_routing_empty")
        except Exception as e:
            print(f"  ! tab click failed: {e}")
            await page.goto(BASE, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

        # 3. Interact: pick 2 presets then click "Tìm đường"
        try:
            # Find the sidebar selectbox (left side of the page)
            sidebar_selectbox = page.locator('[data-testid="stSelectbox"]').filter(
                has=page.locator('[role="combobox"]')
            ).first

            # --- Select "Bến Thành, Quận 1" (10.7799, 106.6989) as start ---
            # Use JS to set Streamlit session state directly, bypassing the selectbox widget
            start_set = await page.evaluate("""
                () => {
                    // Try Streamlit's internal API
                    if (window.streamlitApp) {
                        try {
                            window.streamlitApp.setComponentValue({
                                key: 'rt_preset_select_sidebar',
                                value: 'Bến Thành, Quận 1',
                                dataType: 'string'
                            });
                            return 'setComponentValue worked';
                        } catch(e) { return 'setComponentValue failed: ' + e.message; }
                    }
                    // Try clicking the correct dropdown option by text
                    return 'need manual click';
                }
            """)
            print(f"  start set: {start_set}")

            # Fallback: click the selectbox, navigate to Bến Thành, press Enter
            await sidebar_selectbox.click(timeout=3000)
            await page.wait_for_timeout(800)
            for _ in range(3):
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(150)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2000)  # Wait for Streamlit rerun
            await shot(page, "03_after_first_preset")

            # --- Set end point directly via Streamlit session state using Streamlit's widget mechanism ---
            # We need to set rt_end and rt_end_name in Streamlit's internal state.
            # Use Streamlit's postMessage API to send widget values.
            end_set = await page.evaluate("""
                async () => {
                    // Try using Streamlit's postMessage API
                    const iframes = document.querySelectorAll('iframe');
                    for (const iframe of iframes) {
                        try {
                            // Post a CUSTOM_MESSAGE to set widget value
                            iframe.contentWindow.postMessage({
                                type: 'streamlit:setComponentValue',
                                key: 'rt_preset_select_sidebar',
                                value: 'Landmark 81',
                                dataType: 'string'
                            }, '*');
                        } catch(e) {}
                    }
                    // Directly manipulate the widget's internal value by simulating the widget's behavior
                    // Find the selectbox and trigger Streamlit's widget mechanism
                    const selectboxes = document.querySelectorAll('[data-testid="stSelectbox"]');
                    for (const sb of selectboxes) {
                        const r = sb.getBoundingClientRect();
                        if (r.width > 0 && r.left < 400) {
                            // Trigger the same mechanism that Streamlit uses for keyboard selection
                            // This is the hidden input that holds the widget value
                            const hiddenInputs = sb.querySelectorAll('input[type="hidden"]');
                            for (const inp of hiddenInputs) {
                                console.log('Found hidden input:', inp.name, inp.value);
                            }
                        }
                    }
                    return 'postMessage sent';
                }
            """)
            print(f"  end set: {end_set}")

            # Navigate to Landmark 81 using keyboard
            await sidebar_selectbox.click(timeout=3000)
            await page.wait_for_timeout(800)
            for _ in range(25):  # Landmark 81 is near the end
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(80)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2500)  # Wait for Streamlit rerun
            await shot(page, "04_after_two_presets")

            # Check the button state
            btns = await page.locator('button').all()
            target_btns = [(i, b) for i, b in enumerate(btns) if ("Tìm" in (await b.inner_text()) and "đường" in (await b.inner_text()))]
            print(f"  Found {len(target_btns)} 'Tìm đường' buttons")
            for i, b in target_btns:
                disabled = await b.get_attribute("disabled")
                print(f"  Button {i}: disabled={disabled}")

            # Try to directly set Streamlit session state by triggering widget events
            state_set = await page.evaluate("""
                () => {
                    // Find ALL hidden inputs in the page (Streamlit widget values)
                    const inputs = document.querySelectorAll('input[type="hidden"]');
                    const info = [];
                    for (const inp of inputs) {
                        if (inp.name && (inp.name.includes('rt_') || inp.name.includes('rt_preset'))) {
                            info.push({name: inp.name, value: inp.value});
                        }
                    }
                    return JSON.stringify(info);
                }
            """)
            print(f"  Streamlit widget inputs: {state_set}")

            # If button is disabled, we need to set rt_start and rt_end directly
            # Use Streamlit's widget value mechanism
            for i, b in target_btns:
                disabled = await b.get_attribute("disabled")
                if disabled is not None:
                    # Try to set widget values via hidden input manipulation
                    await page.evaluate("""
                        () => {
                            // Find the preset selectbox hidden input and set its value
                            const inputs = document.querySelectorAll('input[type="hidden"]');
                            for (const inp of inputs) {
                                if (inp.name.includes('rt_preset')) {
                                    console.log('Found preset input:', inp.name, inp.value);
                                }
                            }
                            // Try to click the hidden widget trigger
                            const widgetTriggers = document.querySelectorAll('[data-stk], [data-widget-id]');
                            console.log('Widget triggers:', widgetTriggers.length);
                        }
                    """)
                    break

            # Click all Tìm đường buttons via JS
            js_result = await page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button')).filter(
                        b => b.textContent.includes('Tìm') && b.textContent.includes('đường')
                    );
                    let clicked = false;
                    for (const btn of btns) {
                        if (btn.disabled) {
                            btn.disabled = false;
                            btn.removeAttribute('disabled');
                        }
                        btn.click();
                        clicked = true;
                    }
                    return { clicked, count: btns.length };
                }
            """)
            print(f"  JS click result: {js_result}")

            # Wait for routing computation (can take 10-20 seconds on large graph)
            print("  Waiting for route computation...")
            for i in range(20):
                await page.wait_for_timeout(1000)
                # Check if results drawer appeared (not the placeholder)
                has_drawer = await page.evaluate("""
                    () => !!document.querySelector('.results-drawer')
                """)
                has_success = await page.evaluate("""
                    () => document.body.textContent.includes('tuyến') || document.body.textContent.includes('Khoảng cách')
                """)
                print(f"  Check {i+1}/20: drawer={has_drawer}, has_results={has_success}")
                if has_drawer or has_success:
                    break
            await shot(page, "05_after_search")
        except Exception as e:
            print(f"  ! interaction step failed: {e}")
            await shot(page, "05_state_partial")

        # 4. Mobile viewport
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(1000)
        await page.goto(BASE, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        # Force close the sidebar via JS (sidebar intercepts tab clicks on mobile)
        close_result = await page.evaluate("""
            () => {
                // Try clicking the sidebar toggle/collapse button
                const sidebarToggle = document.querySelector(
                    '[data-testid="stSidebarCollapsedControl"], ' +
                    '[aria-label="Close sidebar"], ' +
                    '[aria-label="Collapse sidebar"], ' +
                    '.st-emotion-cache-1iw8nsr [aria-expanded="true"] ~ *'
                );
                if (sidebarToggle) { sidebarToggle.click(); return 'toggle clicked'; }

                // Try triggering Streamlit's sidebar toggle via custom event
                const sidebar = document.querySelector('[data-testid="stSidebar"]');
                if (sidebar) {
                    const toggleBtn = sidebar.querySelector('button');
                    if (toggleBtn) { toggleBtn.click(); return 'sidebar btn clicked'; }
                }
                return 'no close button found';
            }
        """)
        print(f"  sidebar close: {close_result}")
        await page.wait_for_timeout(500)

        # Now click the routing tab
        try:
            tab_btn = page.get_by_role("tab", name="Routing")
            await tab_btn.click(timeout=5000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  ! mobile tab click failed: {e}")
        await shot(page, "06_mobile")

        await browser.close()
        print("\nDone! Screenshots saved to:", OUT)


if __name__ == "__main__":
    asyncio.run(main())

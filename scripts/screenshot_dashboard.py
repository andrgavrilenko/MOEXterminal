"""
Universal Playwright dashboard screenshotter.

Auto-detects tabs/sub-tabs or uses explicit CSS selectors.
Clicks through every tab combination and saves full-page screenshots.

Usage:
    python screenshot_dashboard.py URL [options]

Examples:
    # Auto-detect tabs
    python screenshot_dashboard.py http://localhost:8080

    # Explicit selectors (MOEX dashboard)
    python screenshot_dashboard.py http://188.68.222.166:8503/ \
        --tabs "div.tab" --subtabs "div.tc.active div.stab"

    # Custom output dir and timing
    python screenshot_dashboard.py http://localhost:3000 \
        --out ./my_screenshots --wait 5 --init-wait 10
"""

import argparse
import os
import re
import sys
import time

# Fix Windows console encoding for non-ASCII (Cyrillic, CJK, etc.)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

# Tab selector candidates in priority order
TAB_CANDIDATES = [
    '[role="tab"]',
    "nav a",
    ".nav-link",
    ".nav-tab",
    ".tab-btn",
    "div.tab",
    "button.tab",
    ".tab",
    "[data-tab]",
    "[data-t]",
]

# Sub-tab candidates — searched within the active tab's content area
SUBTAB_CANDIDATES = [
    '[role="tab"]',
    ".nav-link",
    ".sub-tab",
    ".stab",
    "[data-subtab]",
    "[data-a]",
    "[data-s]",
]

# Selectors to find the "active content" container for sub-tabs
ACTIVE_CONTAINER_CANDIDATES = [
    '[role="tabpanel"]:not([hidden])',
    ".tab-pane.active",
    ".tab-content.active",
    ".tc.active",
    ".panel.active",
]


def safe_filename(text: str) -> str:
    """Convert tab label to a safe filename component."""
    name = text.strip()
    name = name.replace(" ", "_").replace("/", "-").replace("&", "and")
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name[:80]  # cap length


def auto_detect(page, candidates: list[str], context: str = "") -> str | None:
    """Try each candidate selector; return the first one with 2+ matches."""
    for sel in candidates:
        try:
            count = page.locator(sel).count()
            if count >= 2:
                print(f"  Auto-detected {context}: '{sel}' ({count} elements)")
                return sel
        except Exception:
            continue
    return None


def find_active_container(page) -> str | None:
    """Find the active tab content container selector."""
    for sel in ACTIVE_CONTAINER_CANDIDATES:
        try:
            if page.locator(sel).count() > 0:
                return sel
        except Exception:
            continue
    return None


def detect_subtabs(page, explicit_selector: str | None) -> tuple[str | None, str]:
    """
    Detect sub-tabs. Returns (full_selector, description).
    If explicit_selector is given, use it directly.
    Otherwise, try to find sub-tabs inside the active container.
    """
    if explicit_selector:
        return explicit_selector, f"explicit: {explicit_selector}"

    container = find_active_container(page)
    if container:
        for candidate in SUBTAB_CANDIDATES:
            full = f"{container} {candidate}"
            try:
                count = page.locator(full).count()
                if count >= 2:
                    return full, f"auto: {full} ({count})"
            except Exception:
                continue

    # Try without container as fallback
    result = auto_detect(page, SUBTAB_CANDIDATES, "sub-tabs")
    if result:
        return result, f"auto: {result}"
    return None, "none found"


def screenshot(page, out_dir: str, name: str, full_page: bool = True):
    """Take and save a screenshot."""
    path = os.path.join(out_dir, f"{name}.png")
    page.screenshot(path=path, full_page=full_page)
    print(f"  -> {name}.png")


def main():
    parser = argparse.ArgumentParser(
        description="Screenshot all tabs of a web dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="Dashboard URL to screenshot")
    parser.add_argument(
        "--tabs", default=None,
        help="CSS selector for main tabs (default: auto-detect)",
    )
    parser.add_argument(
        "--subtabs", default=None,
        help="CSS selector for sub-tabs (default: auto-detect)",
    )
    parser.add_argument(
        "--out", default="./screenshots",
        help="Output directory (default: ./screenshots)",
    )
    parser.add_argument(
        "--wait", type=float, default=3,
        help="Seconds to wait after each click (default: 3)",
    )
    parser.add_argument(
        "--init-wait", type=float, default=8,
        help="Seconds to wait for initial page load (default: 8)",
    )
    parser.add_argument(
        "--viewport", default="1920x1080",
        help="Viewport WxH (default: 1920x1080)",
    )
    parser.add_argument(
        "--no-full-page", action="store_true",
        help="Viewport-only screenshot instead of full page",
    )
    args = parser.parse_args()

    # Parse viewport
    try:
        w, h = args.viewport.lower().split("x")
        viewport = {"width": int(w), "height": int(h)}
    except ValueError:
        parser.error(f"Invalid viewport format: {args.viewport}. Use WxH, e.g. 1920x1080")

    full_page = not args.no_full_page
    os.makedirs(args.out, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=viewport)
        page = context.new_page()

        print(f"Opening {args.url} ...")
        page.goto(args.url, timeout=60000)
        time.sleep(args.init_wait)

        # --- Detect main tabs ---
        tab_selector = args.tabs
        if not tab_selector:
            tab_selector = auto_detect(page, TAB_CANDIDATES, "main tabs")

        if not tab_selector:
            print("No tabs detected — taking a single full-page screenshot.")
            screenshot(page, args.out, "full_page", full_page)
            browser.close()
            return

        main_tabs = page.locator(tab_selector)
        main_count = main_tabs.count()
        print(f"\nMain tabs ({main_count}):")

        tab_info = []
        for i in range(main_count):
            tab = main_tabs.nth(i)
            text = tab.inner_text().strip() or f"tab_{i+1}"
            tab_info.append(text)
            print(f"  [{i+1}] {text}")

        total = 0

        for i, tab_text in enumerate(tab_info):
            prefix = f"{i+1:02d}"
            print(f"\n=== [{prefix}] {tab_text} ===")

            main_tabs.nth(i).click()
            time.sleep(args.wait)

            # --- Detect sub-tabs for this main tab ---
            sub_selector, sub_desc = detect_subtabs(page, args.subtabs)

            if sub_selector:
                sub_tabs = page.locator(sub_selector)
                sub_count = sub_tabs.count()

                if sub_count >= 2:
                    sub_info = []
                    for j in range(sub_count):
                        st_text = sub_tabs.nth(j).inner_text().strip() or f"sub_{j+1}"
                        sub_info.append(st_text)
                    print(f"  Sub-tabs ({sub_count}): {sub_info}")

                    for j, st_text in enumerate(sub_info):
                        sub_prefix = f"{prefix}_{j+1:02d}"
                        fname = f"{sub_prefix}_{safe_filename(tab_text)}_{safe_filename(st_text)}"
                        print(f"  --- [{sub_prefix}] {st_text} ---")
                        sub_tabs.nth(j).click()
                        time.sleep(args.wait)
                        screenshot(page, args.out, fname, full_page)
                        total += 1
                    continue

            # No sub-tabs — screenshot main tab
            fname = f"{prefix}_{safe_filename(tab_text)}"
            screenshot(page, args.out, fname, full_page)
            total += 1

        browser.close()
        print(f"\nDone! {total} screenshots saved to {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()

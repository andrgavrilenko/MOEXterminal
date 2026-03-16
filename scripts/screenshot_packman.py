"""
Screenshot all tabs/sub-tabs of packmanmarkets.ru.
Custom script that handles the site's specific DOM structure.
"""
import os
import re
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

URL = "https://www.packmanmarkets.ru/"
OUT = "./screenshots_2026-02-26"
WAIT = 4
INIT_WAIT = 15

# Only screenshot these sub-tabs (skip period buttons like 1Y, 3Y, etc.)
SKIP_STABS = {
    "Today", "-1D", "-1W", "-1M", "-1Y", "-3M", "-6M",
    "Alpha", "Equity",  # backtest toggles, not separate views
    "1Y", "3Y", "5Y", "10Y", "MAX",  # macro period buttons
    "Физ Net", "Физ Long", "Физ Short", "Юр Net", "Юр Long", "Юр Short", "Цена",  # OI chart toggles
}

# OFZ sub-types (ПД, Флоатер, ИН, CNY) are filters, not tabs
OFZ_SUBTYPES = {"ПД", "Флоатер", "ИН", "CNY"}


def safe_name(text):
    name = text.strip().replace(" ", "_").replace("/", "-").replace("&", "and")
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name[:60]


def get_visible_stabs(page):
    """Return list of (index, text) for visible .stab elements, excluding skipped ones."""
    stabs = page.locator(".stab")
    result = []
    seen = set()
    for j in range(stabs.count()):
        s = stabs.nth(j)
        if s.is_visible():
            t = s.inner_text().strip()
            if t and t not in seen and t not in SKIP_STABS and t not in OFZ_SUBTYPES:
                seen.add(t)
                result.append((j, t))
    return result


def screenshot(page, path, full_page=True):
    page.screenshot(path=path, full_page=full_page)
    print(f"    -> {os.path.basename(path)}")


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        print(f"Opening {URL} ...")
        page.goto(URL, timeout=60000)
        time.sleep(INIT_WAIT)

        tabs = page.locator("div.tab")
        tab_count = tabs.count()
        print(f"Found {tab_count} main tabs\n")

        structure = []  # for README

        for i in range(tab_count):
            tab_text = tabs.nth(i).inner_text().strip()
            prefix = f"{i+1:02d}"
            print(f"=== [{prefix}] {tab_text} ===")
            tabs.nth(i).click()
            time.sleep(WAIT)

            visible = get_visible_stabs(page)

            if not visible:
                # No sub-tabs — just screenshot main tab
                fname = f"{prefix}_{safe_name(tab_text)}.png"
                screenshot(page, os.path.join(OUT, fname))
                total += 1
                structure.append((tab_text, []))
                continue

            sub_names = []

            # Special handling for "Арбитраж & RV" which has nested sub-tabs
            if tab_text == "Арбитраж & RV":
                # First level: Арбитраж, Relative Value
                groups = [(j, t) for j, t in visible if t in ("Арбитраж", "Relative Value")]
                subs = [(j, t) for j, t in visible if t not in ("Арбитраж", "Relative Value")]

                for gi, (gj, gtext) in enumerate(groups):
                    page.locator(".stab").nth(gj).click()
                    time.sleep(WAIT)

                    # Re-detect visible sub-tabs after clicking group
                    inner = get_visible_stabs(page)
                    inner_subs = [(j, t) for j, t in inner if t not in ("Арбитраж", "Relative Value")]

                    for si, (sj, stext) in enumerate(inner_subs):
                        page.locator(".stab").nth(sj).click()
                        time.sleep(WAIT)
                        fname = f"{prefix}_{gi+1:02d}_{si+1:02d}_{safe_name(tab_text)}_{safe_name(gtext)}_{safe_name(stext)}.png"
                        screenshot(page, os.path.join(OUT, fname))
                        total += 1
                        sub_names.append(f"{gtext} > {stext}")

                structure.append((tab_text, sub_names))
                continue

            # Normal tabs with sub-tabs
            for si, (sj, stext) in enumerate(visible):
                page.locator(".stab").nth(sj).click()
                time.sleep(WAIT)
                fname = f"{prefix}_{si+1:02d}_{safe_name(tab_text)}_{safe_name(stext)}.png"
                screenshot(page, os.path.join(OUT, fname))
                total += 1
                sub_names.append(stext)

            structure.append((tab_text, sub_names))

        browser.close()

    # Write README
    readme_path = os.path.join(OUT, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("# Структура: Russian Market Packman Monitor\n")
        f.write("Дата: 2026-02-26\n")
        f.write(f"URL: {URL}\n\n")
        for i, (tab, subs) in enumerate(structure):
            f.write(f"{i+1}. {tab}\n")
            for j, sub in enumerate(subs):
                f.write(f"   {i+1}.{j+1}. {sub}\n")
        f.write(f"\nВсего: {total} скриншотов\n")
        f.write(f"\n## Файлы\n")
        for fname in sorted(os.listdir(OUT)):
            if fname.endswith(".png"):
                f.write(f"{fname}\n")

    print(f"\nDone! {total} screenshots -> {os.path.abspath(OUT)}")
    print(f"README: {readme_path}")


if __name__ == "__main__":
    main()

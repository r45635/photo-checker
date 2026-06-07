#!/usr/bin/env python3
"""
Take screenshots of the photo-checker UI for documentation.
All <img> elements are heavily blurred before saving.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent.parent / "docs" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Aggressively blur every <img> on the page
BLUR_JS = """
() => {
  const style = document.createElement('style');
  style.id = 'blur-override';
  style.textContent = `img { filter: blur(28px) !important; transform: scale(1.08); }`;
  document.head.appendChild(style);
}
"""


async def apply_blur(page) -> None:
    await page.evaluate(BLUR_JS)
    # Remove any existing override first to avoid stacking
    await page.evaluate("""
    () => {
        const old = document.getElementById('blur-override');
        if (old) old.remove();
        const style = document.createElement('style');
        style.id = 'blur-override';
        style.textContent = `img { filter: blur(28px) !important; transform: scale(1.08); }`;
        document.head.appendChild(style);
    }
    """)


async def shot(page, name: str, delay: float = 0.6) -> None:
    await apply_blur(page)
    await asyncio.sleep(delay)
    dest = OUT_DIR / f"{name}.png"
    await page.screenshot(path=str(dest), full_page=False)
    print(f"  saved {dest.name}")


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        # Inject blur on every page load
        await page.add_init_script("""
            const observer = new MutationObserver(() => {
                const old = document.getElementById('blur-override');
                if (!old) {
                    const s = document.createElement('style');
                    s.id = 'blur-override';
                    s.textContent = 'img { filter: blur(28px) !important; transform: scale(1.08); }';
                    document.head.appendChild(s);
                }
            });
            observer.observe(document.documentElement, { childList: true, subtree: true });
        """)

        await page.goto(f"{BASE_URL}/", wait_until="networkidle")

        # ── 1. YES filter — main grid ──────────────────────────────────────────
        print("1. Main grid (YES filter)…")
        await shot(page, "01_main_grid_yes", delay=1.0)

        # ── 2. NO filter ──────────────────────────────────────────────────────
        print("2. Main grid (NO filter)…")
        await page.get_by_text("NO", exact=True).first.click()
        await shot(page, "02_main_grid_no")

        # ── 3. ALL filter — full stats bar ────────────────────────────────────
        print("3. All results (full stats)…")
        await page.get_by_text("All", exact=True).first.click()
        await shot(page, "03_main_grid_all")

        # ── 4. Selection + batch bar (back to YES) ────────────────────────────
        print("4. Selection / batch bar…")
        await page.get_by_text("YES", exact=True).first.click()
        await asyncio.sleep(0.5)
        # Select first 4 cards by clicking their select buttons
        cards = await page.query_selector_all(".group.relative.rounded-xl")
        selected = 0
        for card in cards[:8]:
            try:
                # Hover to reveal overlay
                await card.hover()
                await asyncio.sleep(0.1)
                btn = await card.query_selector("button[aria-label='Select'], button[aria-label='Deselect']")
                if not btn:
                    btn = await card.query_selector("button")
                if btn:
                    await btn.click()
                    selected += 1
                    if selected >= 4:
                        break
            except Exception:
                continue
        await shot(page, "04_selection_batch_bar")

        # Deselect all
        try:
            clear = page.get_by_label("Clear selection")
            if await clear.is_visible():
                await clear.click()
                await asyncio.sleep(0.3)
        except Exception:
            pass

        # ── 5. Scan dialog ─────────────────────────────────────────────────────
        print("5. Scan dialog…")
        scan_btn = page.get_by_text("Scan folder", exact=True).first
        await scan_btn.click()
        await asyncio.sleep(0.5)
        await shot(page, "05_scan_dialog")
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)

        # ── 6. Detail panel — click a photo card ──────────────────────────────
        print("6. Detail panel…")
        cards = await page.query_selector_all(".group.relative.rounded-xl")
        if cards:
            # Click the card body (not the select button) to open detail panel
            box = await cards[0].bounding_box()
            if box:
                # Click lower-center of the card (info bar area, avoids select btn)
                await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] - 20)
                await asyncio.sleep(0.8)
                await shot(page, "06_detail_panel")
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.2)

        await browser.close()
        saved = sorted(OUT_DIR.glob("*.png"))
        print(f"\nDone — {len(saved)} screenshots in {OUT_DIR}")
        for f in saved:
            print(f"  {f.name}")


if __name__ == "__main__":
    asyncio.run(main())

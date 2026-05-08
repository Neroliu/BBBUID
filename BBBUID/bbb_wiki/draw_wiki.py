from pathlib import Path
from io import BytesIO

from PIL import Image

from gsuid_core.pool import to_thread


def _screenshot_wiki_sync(content_id: int) -> bytes:
    from playwright.sync_api import sync_playwright

    url = f"https://baike.mihoyo.com/bh3/wiki/content/{content_id}/detail?bbs_presentation_style=no_header"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 600})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        buf = page.screenshot(full_page=True)
        browser.close()
    return buf


async def screenshot_wiki(content_id: int) -> Image.Image:
    buf = await to_thread(_screenshot_wiki_sync, content_id)
    return Image.open(BytesIO(buf))

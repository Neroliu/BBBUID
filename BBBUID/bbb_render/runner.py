"""Playwright HTML → PNG bytes runner."""
from __future__ import annotations

from gsuid_core.logger import logger


async def render_html_to_bytes(
    html: str,
    width: int,
    height: int,
    device_scale_factor: int = 2,
    wait_selector: str | None = None,
) -> bytes:
    """Render an HTML string to PNG bytes via Playwright.

    `width` / `height` 是 viewport 尺寸（CSS 像素）；`device_scale_factor=2`
    出图分辨率翻倍以保证清晰度。若 HTML 内有需要等待加载的元素，传入
    `wait_selector` 让 Playwright 在截图前等它出现。
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=device_scale_factor,
            )
            page = await context.new_page()
            await page.set_content(html, wait_until="networkidle")
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=5000)
                except Exception as e:
                    logger.warning(f"[崩坏3] [HTML渲染] 等待元素超时: {e}")
            png_bytes = await page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": width, "height": height},
                omit_background=False,
            )
            return png_bytes
        finally:
            await browser.close()

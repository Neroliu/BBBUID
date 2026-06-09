"""Playwright HTML → PNG bytes runner."""
from __future__ import annotations

import tempfile
from pathlib import Path

from gsuid_core.logger import logger


async def render_html_to_bytes(
    html: str,
    width: int,
    height: int,
    device_scale_factor: int = 2,
    wait_selector: str | None = None,
    full_page: bool = False,
) -> bytes:
    """Render an HTML string to PNG bytes via Playwright.

    `width` / `height` 是 viewport 尺寸（CSS 像素）；`device_scale_factor=2`
    出图分辨率翻倍以保证清晰度。若 HTML 内有需要等待加载的元素，传入
    `wait_selector` 让 Playwright 在截图前等它出现。

    若 `full_page=True`，截图整张页面（包含 viewport 以外的内容），
    适合内容高度不定的页面（WIKI/帮助等）。否则按 viewport 大小裁剪。

    实现细节：HTML 通过临时文件 + `page.goto(file://...)` 加载，而**不是**
    `page.set_content`——后者会让页面的 origin 变成 `about:blank`，Chromium
    会拒绝其加载任何 `file://` 子资源（图片 / 字体 / CSS），导致渲染空白。
    """
    from playwright.async_api import async_playwright

    tmp = tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(html)
        tmp.close()
        tmp_path = Path(tmp.name)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=device_scale_factor,
                )
                page = await context.new_page()
                failures: list[str] = []
                page.on(
                    "requestfailed",
                    lambda r: failures.append(f"{r.url} ({r.failure})"),
                )
                await page.goto(tmp_path.as_uri(), wait_until="networkidle")
                try:
                    await page.evaluate("document.fonts.ready")
                except Exception:
                    pass
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=5000)
                    except Exception as e:
                        logger.warning(f"[崩坏3] [HTML渲染] 等待元素超时: {e}")
                if failures:
                    logger.warning(
                        f"[崩坏3] [HTML渲染] {len(failures)} 个资源加载失败，"
                        f"前 3 个: {failures[:3]}"
                    )
                if full_page:
                    png_bytes = await page.screenshot(
                        type="png",
                        full_page=True,
                        omit_background=False,
                    )
                else:
                    png_bytes = await page.screenshot(
                        type="png",
                        clip={"x": 0, "y": 0, "width": width, "height": height},
                        omit_background=False,
                    )
                return png_bytes
            finally:
                await browser.close()
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:
            pass

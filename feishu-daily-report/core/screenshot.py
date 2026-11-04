import asyncio
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright


class ScreenshotError(Exception):
    pass


async def _take_screenshot(html_path: Path, png_path: Path, width: int, height: int) -> Path:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})
            uri = html_path.resolve().as_uri()
            logger.info(f"加载页面: {uri}")
            await page.goto(uri, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            png_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(png_path), full_page=True, type="png")
            await browser.close()
            logger.info(f"截图已生成: {png_path}")
            return png_path
    except Exception as e:
        raise ScreenshotError(f"截图失败: {e}") from e


def screenshot_sync(html_path: Path, png_path: Path, width: int, height: int) -> Path:
    return asyncio.run(_take_screenshot(html_path, png_path, width, height))

"""Shared helpers for all ATS handlers."""
import asyncio
import logging
import random
from pathlib import Path

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def delay(min_s=0.5, max_s=1.8):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def safe_fill(page: Page, selector: str, value: str, timeout=5000) -> bool:
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.fill(selector, value)
        return True
    except Exception:
        return False


async def safe_click(page: Page, selector: str, timeout=5000) -> bool:
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.click(selector)
        return True
    except Exception:
        return False


async def upload_file(page: Page, selector: str, cv_path: str) -> bool:
    try:
        path = str(Path(cv_path).absolute())
        await page.set_input_files(selector, path)
        logger.info("CV uploaded to ATS form")
        return True
    except Exception as e:
        logger.warning(f"ATS CV upload failed: {e}")
        return False


async def fill_by_label(page: Page, label_text: str, value: str) -> bool:
    """Find an input associated with a label containing label_text and fill it."""
    if not value:
        return False
    try:
        # Try aria-label
        filled = await safe_fill(page, f'input[aria-label*="{label_text}" i]', value, 2000)
        if filled:
            return True
        # Try placeholder
        filled = await safe_fill(page, f'input[placeholder*="{label_text}" i]', value, 2000)
        if filled:
            return True
        # Try name attribute
        filled = await safe_fill(page, f'input[name*="{label_text}" i]', value, 2000)
        if filled:
            return True
        # Try finding label element and its for= target
        labels = await page.query_selector_all("label")
        for lbl in labels:
            text = (await lbl.inner_text()).strip().lower()
            if label_text.lower() in text:
                for_id = await lbl.get_attribute("for")
                if for_id:
                    filled = await safe_fill(page, f"#{for_id}", value, 2000)
                    if filled:
                        return True
    except Exception:
        pass
    return False

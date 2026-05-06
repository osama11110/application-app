import asyncio
import logging
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class BaseSite(ABC):
    name = "base"

    def __init__(self, page: Page, config: dict, cv_data: dict):
        self.page = page
        self.config = config
        self.cv_data = cv_data
        self.creds = config.get("credentials", {}).get(self.name, {})
        self.personal = cv_data.get("personal", {})
        self.cv_path = str(Path(config.get("cv_path", "cv/cv.pdf")).absolute())
        self.dry_run: bool = config.get("application", {}).get("dry_run", False)

    # ------------------------------------------------------------------ helpers
    async def delay(self, min_s: float = 0.8, max_s: float = 2.5):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def short_delay(self):
        await asyncio.sleep(random.uniform(0.2, 0.6))

    async def type_slowly(self, selector: str, text: str, clear: bool = True):
        el = await self.page.wait_for_selector(selector, timeout=6000)
        await el.click()
        if clear:
            await self.page.keyboard.press("Control+a")
            await self.page.keyboard.press("Delete")
        for ch in text:
            await self.page.keyboard.type(ch)
            await asyncio.sleep(random.uniform(0.04, 0.13))

    async def safe_click(self, selector: str, timeout: int = 6000) -> bool:
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)
            return True
        except Exception:
            return False

    async def safe_fill(self, selector: str, value: str, timeout: int = 6000) -> bool:
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.fill(selector, value)
            return True
        except Exception:
            return False

    async def upload_cv(self, file_input_selector: str) -> bool:
        try:
            await self.page.set_input_files(file_input_selector, self.cv_path)
            logger.info("CV uploaded")
            return True
        except Exception as e:
            logger.warning(f"CV upload failed: {e}")
            return False

    async def screenshot(self, label: str):
        if not self.config.get("application", {}).get("take_screenshots", True):
            return
        os.makedirs("screenshots", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"screenshots/{self.name}_{label}_{ts}.png"
        await self.page.screenshot(path=path, full_page=False)

    async def wait_for_captcha(self) -> bool:
        captcha_sels = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            '[class*="captcha"]',
            '[id*="captcha"]',
            '.cf-challenge-running',
        ]
        for sel in captcha_sels:
            if await self.page.query_selector(sel):
                logger.warning(f"CAPTCHA on {self.name} — solve it in the browser then press Enter")
                if not self.config.get("application", {}).get("headless", False):
                    input(f"\n[!] CAPTCHA detected on {self.name}. Solve it then press Enter: ")
                else:
                    await asyncio.sleep(30)
                return True
        return False

    async def try_selectors(self, selectors: list[str], timeout: int = 3000):
        """Return first matching element or None."""
        for sel in selectors:
            try:
                el = await self.page.wait_for_selector(sel, timeout=timeout)
                if el:
                    return el
            except Exception:
                continue
        return None

    # ---------------------------------------------------------------- abstract
    @abstractmethod
    async def login(self) -> bool:
        pass

    @abstractmethod
    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        pass

    @abstractmethod
    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        pass

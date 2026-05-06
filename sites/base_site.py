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

    async def manual_login(self, login_url: str) -> bool:
        """
        No credentials configured — open the login page so the user can
        log in manually. The session is saved to browser_profile/ and
        reused automatically on every future run.
        """
        from colorama import Fore, Style
        print(f"\n  {Fore.YELLOW}{'─'*54}")
        print(f"  {self.name.upper()} — no credentials in config.yaml")
        print(f"  Opening login page in the browser.")
        print(f"  Log in manually, then come back here and press Enter.")
        print(f"  Your session will be saved — you won't need to do")
        print(f"  this again on future runs.")
        print(f"  {'─'*54}{Style.RESET_ALL}")

        await self.page.goto(login_url, wait_until="domcontentloaded")
        await self.delay()
        # Dismiss cookie banner so login form is visible
        await self.safe_click(
            'button:has-text("Akzeptieren"), button:has-text("Accept all"), '
            'button:has-text("Alle akzeptieren"), [id*="cookie"] button, '
            '[data-testid*="accept"]',
            3000
        )
        input(f"\n  Press Enter once you are logged in to {self.name}... ")
        print()
        return True

    async def check_already_logged_in(self, home_url: str, logged_in_selector: str) -> bool:
        """
        Visit the site home and check for a selector that only appears
        when the user is logged in (e.g. profile avatar, dashboard link).
        Uses the saved browser_profile session.
        """
        try:
            await self.page.goto(home_url, wait_until="domcontentloaded")
            await self.delay(0.5, 1.5)
            el = await self.page.query_selector(logged_in_selector)
            return el is not None
        except Exception:
            return False

    # ---------------------------------------------------------------- abstract
    async def try_external_apply(self, home_domain: str, job: dict, cover_letter: str = "") -> bool:
        """
        Call this after clicking Apply on any site.
        If the browser has redirected to a company career portal,
        detect the ATS and apply automatically.
        Returns True if an external application was handled.
        """
        from .ats import detect_ats, is_external, get_handler

        current_url = self.page.url
        if not is_external(home_domain, current_url):
            return False  # Still on the same site — caller handles inline form

        ats = detect_ats(current_url)
        logger.info(f"External redirect detected → {ats} ({current_url[:70]})")
        await self.screenshot(f"ats_{ats}")

        handler = get_handler(ats)
        try:
            return await handler(self.page, job, self.cv_data, self.cv_path, cover_letter)
        except Exception as e:
            logger.error(f"ATS handler '{ats}' error: {e}")
            return False

    @abstractmethod
    async def login(self) -> bool:
        pass

    @abstractmethod
    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        pass

    @abstractmethod
    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        pass

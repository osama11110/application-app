import logging
import urllib.parse
from .base_site import BaseSite

logger = logging.getLogger(__name__)


class WillhabenAt(BaseSite):
    name = "willhaben"

    LOGIN_URL = "https://www.willhaben.at/iad/login"
    SEARCH_URL = "https://www.willhaben.at/jobs"

    async def login(self) -> bool:
        email = self.creds.get("email", "")
        password = self.creds.get("password", "")
        if not email or not password:
            if await self.check_already_logged_in(
                "https://www.willhaben.at",
                '[data-testid="header-profile-link"], [aria-label*="Profil"], a[href*="/meinkonto"]'
            ):
                logger.info("willhaben: already logged in via saved session")
                return True
            return await self.manual_login(self.LOGIN_URL)

        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self.delay()
        await self.safe_click('button[data-testid="ACCEPT_ALL"], button:has-text("Alle akzeptieren")', 3000)

        await self.safe_fill('input[name="username"], input[type="email"], #username', email)
        await self.delay(0.3, 0.7)
        await self.safe_fill('input[name="password"], input[type="password"]', password)
        await self.delay(0.3, 0.7)
        await self.safe_click('button[type="submit"], button:has-text("Anmelden")')
        await self.page.wait_for_load_state("domcontentloaded")
        await self.wait_for_captcha()

        success = "login" not in self.page.url.lower()
        logger.info(f"willhaben login {'OK' if success else 'FAILED'}")
        return success

    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        jobs = []
        for keyword in keywords[:5]:
            url = f"{self.SEARCH_URL}?keyword={urllib.parse.quote(keyword)}"
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.delay()

            for _ in range(3):
                cards = await self.page.query_selector_all(
                    '[data-testid="search-result-entry"], article.SearchResultRow, .job-item'
                )
                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            '[data-testid="result-title"] a, h3 a, .headline a'
                        )
                        company_el = await card.query_selector(
                            '[data-testid="company-name"], .advertiser-name'
                        )
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""
                        href = await title_el.get_attribute("href") if title_el else ""
                        job_url = href if href.startswith("http") else f"https://www.willhaben.at{href}"
                        loc_el = await card.query_selector(
                            '[data-testid="location"], .location, .address, [class*="location"]'
                        )
                        location = (await loc_el.inner_text()).strip() if loc_el else ""

                        if title and job_url not in [j["url"] for j in jobs]:
                            jobs.append({"title": title, "company": company, "location": location,
                                         "url": job_url, "site": self.name, "description": ""})
                    except Exception:
                        continue

                next_btn = await self.page.query_selector(
                    '[data-testid="pagination-next"], button[aria-label*="next"]'
                )
                if next_btn:
                    await next_btn.click()
                    await self.delay(1, 2)
                else:
                    break

                if len(jobs) >= self.config["search"].get("max_results_per_site", 30):
                    break

        logger.info(f"willhaben: found {len(jobs)} jobs")
        return jobs

    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        await self.page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay()

        try:
            desc_el = await self.page.query_selector('.description, .text-block, [data-testid="ad-detail-body"]')
            if desc_el:
                job["description"] = (await desc_el.inner_text())[:1500]
        except Exception:
            pass

        if self.dry_run:
            logger.info(f"[DRY RUN] {job['title']} @ {job['company']}")
            return True

        clicked = await self.safe_click(
            'a:has-text("Bewerben"), button:has-text("Jetzt bewerben"), '
            '[data-testid="contact-advertiser-button"]',
            5000
        )
        if not clicked:
            logger.warning(f"willhaben: no apply button for {job['title']}")
            return False

        await self.page.wait_for_load_state("domcontentloaded")
        await self.delay()

        if await self.try_external_apply("willhaben.at", job, cover_letter):
            return True

        # willhaben contact form
        await self.safe_fill('textarea[name="message"], textarea[placeholder*="Nachricht"]',
                             cover_letter or f"Sehr geehrte Damen und Herren,\n\nIch bewerbe mich für die Stelle als {job['title']}.\n\nMit freundlichen Grüßen,\n{self.personal.get('name', '')}")
        await self.safe_fill('input[name="phone"], input[id*="phone"]', self.personal.get("phone", ""))
        await self.upload_cv('input[type="file"]')
        await self.delay()

        submitted = await self.safe_click('button[type="submit"], button:has-text("Nachricht senden")', 5000)
        await self.delay(2, 3)
        await self.screenshot(f"applied_{job['company'][:20]}")
        logger.info(f"willhaben: {'applied' if submitted else 'failed'} -> {job['title']}")
        return submitted

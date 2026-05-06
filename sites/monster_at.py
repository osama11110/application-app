import logging
import urllib.parse
from .base_site import BaseSite

logger = logging.getLogger(__name__)


class MonsterAt(BaseSite):
    name = "monster"

    LOGIN_URL = "https://www.monster.at/profil/login"
    SEARCH_URL = "https://www.monster.at/jobs/suche/"

    async def login(self) -> bool:
        email = self.creds.get("email", "")
        password = self.creds.get("password", "")
        if not email or not password:
            if await self.check_already_logged_in(
                "https://www.monster.at",
                '.account-nav, [class*="loggedIn"], a[href*="/profil"]'
            ):
                logger.info("monster.at: already logged in via saved session")
                return True
            return await self.manual_login(self.LOGIN_URL)

        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self.delay()
        await self.safe_click('button[id*="cookie"], button:has-text("Akzeptieren")', 3000)

        await self.safe_fill('input[type="email"], input[name="email"], #email', email)
        await self.delay(0.3, 0.7)
        await self.safe_fill('input[type="password"], input[name="password"]', password)
        await self.delay(0.3, 0.7)
        await self.safe_click('button[type="submit"], button:has-text("Anmelden")')
        await self.page.wait_for_load_state("domcontentloaded")
        await self.wait_for_captcha()

        success = "login" not in self.page.url.lower()
        logger.info(f"monster.at login {'OK' if success else 'FAILED'}")
        return success

    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        jobs = []
        for keyword in keywords[:5]:
            url = (f"{self.SEARCH_URL}?"
                   f"q={urllib.parse.quote(keyword)}&"
                   f"where=%C3%96sterreich")
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.delay()

            for _ in range(3):
                cards = await self.page.query_selector_all(
                    '.job-cardstyle__JobCard, [data-testid="jobCard"], .results-card'
                )
                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            'h2 a, h3 a, [data-testid="jobTitle"], .job-title a'
                        )
                        company_el = await card.query_selector(
                            '[data-testid="company"], .company, .employer-name'
                        )
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""
                        href = await title_el.get_attribute("href") if title_el else ""
                        job_url = href if href.startswith("http") else f"https://www.monster.at{href}"
                        loc_el = await card.query_selector(
                            '[data-testid="jobLocation"], .location, .job-location, '
                            '[class*="location"]'
                        )
                        location = (await loc_el.inner_text()).strip() if loc_el else ""

                        if title and job_url not in [j["url"] for j in jobs]:
                            jobs.append({"title": title, "company": company, "location": location,
                                         "url": job_url, "site": self.name, "description": ""})
                    except Exception:
                        continue

                next_btn = await self.page.query_selector(
                    '[data-testid="pagination-next"], .pagination .next a, a[aria-label="Weiter"]'
                )
                if next_btn:
                    await next_btn.click()
                    await self.delay(1, 2)
                else:
                    break

                if len(jobs) >= self.config["search"].get("max_results_per_site", 30):
                    break

        logger.info(f"monster.at: found {len(jobs)} jobs")
        return jobs

    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        await self.page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay()

        try:
            desc_el = await self.page.query_selector('.job-description, [data-testid="jobDescription"]')
            if desc_el:
                job["description"] = (await desc_el.inner_text())[:1500]
        except Exception:
            pass

        if self.dry_run:
            logger.info(f"[DRY RUN] {job['title']} @ {job['company']}")
            return True

        clicked = await self.safe_click(
            'a:has-text("Jetzt bewerben"), button:has-text("Jetzt bewerben"), '
            '[data-testid="apply-button"]',
            5000
        )
        if not clicked:
            logger.warning(f"monster.at: no apply button for {job['title']}")
            return False

        await self.page.wait_for_load_state("domcontentloaded")
        await self.delay()
        await self.wait_for_captcha()

        if await self.try_external_apply("monster.at", job, cover_letter):
            return True

        await self.upload_cv('input[type="file"]')
        await self.delay()

        if cover_letter:
            await self.safe_fill('textarea[name*="cover"], textarea[name*="message"]', cover_letter)

        await self.safe_fill('input[name="phone"], input[id*="phone"]', self.personal.get("phone", ""))
        await self.delay(0.5, 1.5)

        submitted = await self.safe_click('button[type="submit"], button:has-text("Bewerbung senden")', 5000)
        await self.delay(2, 3)
        await self.screenshot(f"applied_{job['company'][:20]}")
        logger.info(f"monster.at: {'applied' if submitted else 'failed'} -> {job['title']}")
        return submitted

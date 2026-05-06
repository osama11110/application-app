import logging
import urllib.parse
from .base_site import BaseSite

logger = logging.getLogger(__name__)


class KarriereAt(BaseSite):
    name = "karriere_at"

    LOGIN_URL = "https://www.karriere.at/login"
    SEARCH_URL = "https://www.karriere.at/jobs"

    async def login(self) -> bool:
        email = self.creds.get("email", "")
        password = self.creds.get("password", "")
        if not email or not password:
            logger.warning("karriere.at: no credentials configured")
            return False

        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self.delay()

        # Accept cookies if banner present
        await self.safe_click('[data-testid="cmpAcceptBtn"], button:has-text("Alle akzeptieren")', 3000)
        await self.short_delay()

        email_sel = await self.try_selectors([
            'input[name="username"]', 'input[type="email"]', '#username', '#email'
        ])
        if not email_sel:
            logger.error("karriere.at: login email field not found")
            return False

        await email_sel.fill(email)
        await self.delay(0.3, 0.8)

        pass_sel = await self.try_selectors([
            'input[name="password"]', 'input[type="password"]', '#password'
        ])
        if pass_sel:
            await pass_sel.fill(password)

        await self.delay(0.5, 1.0)
        await self.safe_click('button[type="submit"]')
        await self.page.wait_for_load_state("domcontentloaded")
        await self.wait_for_captcha()

        success = "login" not in self.page.url.lower()
        logger.info(f"karriere.at login {'OK' if success else 'FAILED'}")
        return success

    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        jobs = []
        for keyword in keywords[:5]:
            url = (f"{self.SEARCH_URL}?"
                   f"keywords={urllib.parse.quote(keyword)}&"
                   f"location=Österreich&radius=100")
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.delay()

            max_pages = 3
            for _ in range(max_pages):
                cards = await self.page.query_selector_all(
                    '.m-jobsListItem, [data-testid="jobCard"], article.job-item'
                )
                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            '.m-jobsListItem__title a, [data-testid="jobTitle"], h2 a, .job-title a'
                        )
                        company_el = await card.query_selector(
                            '.m-jobsListItem__company, [data-testid="jobCompany"], .company-name'
                        )
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""
                        href = await title_el.get_attribute("href") if title_el else ""
                        job_url = href if href.startswith("http") else f"https://www.karriere.at{href}"
                        loc_el = await card.query_selector(
                            '.m-jobsListItem__location, [data-testid="jobLocation"], .job-location, .location'
                        )
                        location = (await loc_el.inner_text()).strip() if loc_el else ""

                        if title and job_url not in [j["url"] for j in jobs]:
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": job_url,
                                "site": self.name,
                                "description": "",
                            })
                    except Exception:
                        continue

                next_btn = await self.page.query_selector(
                    '[data-testid="pagination-next"], a[rel="next"], .pagination__next'
                )
                if next_btn:
                    await next_btn.click()
                    await self.delay(1, 2)
                else:
                    break

                if len(jobs) >= self.config["search"].get("max_results_per_site", 30):
                    break

        logger.info(f"karriere.at: found {len(jobs)} jobs")
        return jobs

    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        await self.page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay()

        # Grab description for logging
        try:
            desc_el = await self.page.query_selector('.m-jobContent, .job-description, [data-testid="jobDescription"]')
            if desc_el:
                job["description"] = (await desc_el.inner_text())[:1500]
        except Exception:
            pass

        if self.dry_run:
            logger.info(f"[DRY RUN] Would apply: {job['title']} @ {job['company']}")
            return True

        # Click apply button
        clicked = await self.safe_click(
            'button[data-action="apply"], a[data-action="apply"], '
            'button:has-text("Jetzt bewerben"), a:has-text("Jetzt bewerben"), '
            '[data-testid="applyButton"]',
            5000
        )
        if not clicked:
            logger.warning(f"karriere.at: no apply button found for {job['title']}")
            return False

        await self.page.wait_for_load_state("domcontentloaded")
        await self.delay()
        await self.wait_for_captcha()

        # Handle multi-step form
        # Step: upload CV
        await self.upload_cv('input[type="file"][accept*="pdf"], input[name="cv"]')
        await self.delay()

        # Cover letter / motivation text
        if cover_letter:
            await self.safe_fill(
                'textarea[name*="cover"], textarea[name*="motivation"], '
                'textarea[placeholder*="Anschreiben"], textarea[placeholder*="Motivationsschreiben"]',
                cover_letter
            )

        # Fill personal fields if shown
        await self.safe_fill('input[name="phone"], input[name="telefon"]',
                             self.personal.get("phone", ""))

        await self.delay(0.5, 1.5)
        # Submit
        submitted = await self.safe_click(
            'button[type="submit"]:has-text("Bewerbung"), '
            'button[type="submit"]:has-text("Senden"), '
            'button[type="submit"]',
            5000
        )
        await self.delay(2, 3)
        await self.screenshot(f"applied_{job['company'][:20]}")
        logger.info(f"karriere.at: {'applied' if submitted else 'submit failed'} -> {job['title']} @ {job['company']}")
        return submitted

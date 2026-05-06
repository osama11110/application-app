"""devjobs.at — Austrian IT & developer job portal."""
import logging
import urllib.parse
from .base_site import BaseSite

logger = logging.getLogger(__name__)


class DevJobsAt(BaseSite):
    name = "devjobs_at"

    LOGIN_URL  = "https://devjobs.at/login"
    SEARCH_URL = "https://devjobs.at/jobs"

    async def login(self) -> bool:
        email    = self.creds.get("email", "")
        password = self.creds.get("password", "")
        # devjobs.at allows applying without an account via email form,
        # so treat missing credentials as "guest mode" rather than skipping.
        if not email or not password:
            if await self.check_already_logged_in(
                "https://devjobs.at",
                '.user-menu, [class*="loggedIn"], a[href*="/dashboard"]'
            ):
                logger.info("devjobs.at: already logged in via saved session")
                return True
            # devjobs.at allows guest apply — skip login entirely
            logger.info("devjobs.at: no credentials — applying as guest")
            return True

        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self.delay()
        await self.safe_click('button:has-text("Akzeptieren"), [class*="cookie"] button', 3000)

        await self.safe_fill('input[type="email"], input[name="email"], #email', email)
        await self.delay(0.3, 0.7)
        await self.safe_fill('input[type="password"], input[name="password"]', password)
        await self.delay(0.3, 0.7)
        await self.safe_click('button[type="submit"], button:has-text("Anmelden"), button:has-text("Login")')
        await self.page.wait_for_load_state("domcontentloaded")
        await self.wait_for_captcha()

        success = "login" not in self.page.url.lower()
        logger.info(f"devjobs.at login {'OK' if success else 'FAILED'}")
        return success

    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        jobs = []

        for keyword in keywords[:6]:
            url = f"{self.SEARCH_URL}?q={urllib.parse.quote(keyword)}"
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.delay()

            for _ in range(3):
                cards = await self.page.query_selector_all(
                    '.job-listing, .job-card, article.job, '
                    '[data-testid="job-item"], .listing-item, .position-item'
                )
                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            'h2 a, h3 a, .job-title a, .position-title a, '
                            '.listing-title a, [class*="title"] a'
                        )
                        company_el = await card.query_selector(
                            '.company-name, .employer, .company, '
                            '[class*="company"], [class*="employer"]'
                        )
                        loc_el = await card.query_selector(
                            '.location, .job-location, [class*="location"], '
                            '.city, [class*="city"]'
                        )

                        title   = (await title_el.inner_text()).strip()   if title_el   else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""
                        location_txt = (await loc_el.inner_text()).strip() if loc_el    else "Austria"

                        href    = await title_el.get_attribute("href") if title_el else ""
                        job_url = href if href.startswith("http") else f"https://devjobs.at{href}"

                        if title and job_url not in [j["url"] for j in jobs]:
                            jobs.append({
                                "title":       title,
                                "company":     company,
                                "location":    location_txt,
                                "url":         job_url,
                                "site":        self.name,
                                "description": "",
                            })
                    except Exception:
                        continue

                next_btn = await self.page.query_selector(
                    'a[rel="next"], .pagination-next a, '
                    '[aria-label*="next"], [aria-label*="Weiter"]'
                )
                if next_btn:
                    await next_btn.click()
                    await self.delay(1, 2)
                else:
                    break

                if len(jobs) >= self.config["search"].get("max_results_per_site", 20):
                    break

        logger.info(f"devjobs.at: found {len(jobs)} jobs")
        return jobs

    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        await self.page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay()

        # Grab description
        try:
            desc_el = await self.page.query_selector(
                '.job-description, .description, .content, '
                '[class*="description"], [class*="content"]'
            )
            if desc_el:
                job["description"] = (await desc_el.inner_text())[:1500]
        except Exception:
            pass

        if self.dry_run:
            logger.info(f"[DRY RUN] {job['title']} @ {job['company']}")
            return True

        # Click apply button
        clicked = await self.safe_click(
            'a:has-text("Jetzt bewerben"), button:has-text("Jetzt bewerben"), '
            'a:has-text("Apply"), button:has-text("Apply"), '
            'a:has-text("Bewerben"), .apply-button, [data-action="apply"]',
            5000
        )
        if not clicked:
            logger.warning(f"devjobs.at: no apply button found for {job['title']}")
            return False

        await self.page.wait_for_load_state("domcontentloaded")
        await self.delay()
        await self.wait_for_captcha()

        # Redirect to external ATS?
        if await self.try_external_apply("devjobs.at", job, cover_letter):
            return True

        # Inline application form
        await self.safe_fill(
            'input[name="first_name"], input[name="vorname"], input[placeholder*="Vorname"]',
            self.personal.get("first_name", "")
        )
        await self.safe_fill(
            'input[name="last_name"], input[name="nachname"], input[placeholder*="Nachname"]',
            self.personal.get("last_name", "")
        )
        await self.safe_fill(
            'input[type="email"], input[name="email"]',
            self.personal.get("email", "")
        )
        await self.safe_fill(
            'input[type="tel"], input[name="phone"], input[name="telefon"]',
            self.personal.get("phone", "")
        )

        await self.upload_cv('input[type="file"]')
        await self.delay()

        if cover_letter:
            await self.safe_fill(
                'textarea[name*="cover"], textarea[name*="message"], '
                'textarea[name*="motivation"], textarea[placeholder*="Anschreiben"]',
                cover_letter
            )

        await self.delay(0.5, 1.5)
        submitted = await self.safe_click(
            'button[type="submit"], input[type="submit"], '
            'button:has-text("Bewerbung absenden"), button:has-text("Senden")',
            5000
        )
        await self.delay(2, 3)
        await self.screenshot(f"applied_{job['company'][:20]}")
        logger.info(f"devjobs.at: {'applied' if submitted else 'failed'} -> {job['title']}")
        return submitted

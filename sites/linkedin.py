import logging
import urllib.parse
from .base_site import BaseSite

logger = logging.getLogger(__name__)


class LinkedIn(BaseSite):
    name = "linkedin"

    LOGIN_URL = "https://www.linkedin.com/login"
    SEARCH_URL = "https://www.linkedin.com/jobs/search/"

    async def login(self) -> bool:
        email = self.creds.get("email", "")
        password = self.creds.get("password", "")
        if not email or not password:
            logger.warning("LinkedIn: no credentials configured")
            return False

        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self.delay()

        await self.safe_fill('#username', email)
        await self.delay(0.3, 0.8)
        await self.safe_fill('#password', password)
        await self.delay(0.3, 0.8)
        await self.safe_click('button[type="submit"]')
        await self.page.wait_for_load_state("domcontentloaded")
        await self.wait_for_captcha()
        await self.delay(2, 3)

        success = "feed" in self.page.url or "jobs" in self.page.url or "mynetwork" in self.page.url
        logger.info(f"LinkedIn login {'OK' if success else 'FAILED'} ({self.page.url})")
        return success

    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        jobs = []
        for keyword in keywords[:5]:
            params = urllib.parse.urlencode({
                "keywords": keyword,
                "location": "Austria",
                "f_AL": "true",   # Easy Apply only
                "sortBy": "DD",   # Most recent
            })
            await self.page.goto(f"{self.SEARCH_URL}?{params}", wait_until="domcontentloaded")
            await self.delay(2, 4)

            for _ in range(3):
                cards = await self.page.query_selector_all(
                    '.job-card-container, [data-testid="job-card"], .jobs-search-results__list-item'
                )
                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            '.job-card-list__title, .job-card-container__link, a.job-card-container__link'
                        )
                        company_el = await card.query_selector(
                            '.job-card-container__company-name, .job-card-container__primary-description'
                        )
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""
                        href = await title_el.get_attribute("href") if title_el else ""
                        job_url = href.split("?")[0] if href.startswith("http") else f"https://www.linkedin.com{href.split('?')[0]}"
                        loc_el = await card.query_selector(
                            '.job-card-container__metadata-item, '
                            '[data-testid="job-insight"], .job-card-list__footer-wrapper li'
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
                                "easy_apply": True,
                            })
                    except Exception:
                        continue

                # Scroll to load more
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.delay(1, 2)
                next_btn = await self.page.query_selector('button[aria-label="View next page"]')
                if next_btn:
                    await next_btn.click()
                    await self.delay(2, 3)
                else:
                    break

                if len(jobs) >= self.config["search"].get("max_results_per_site", 30):
                    break

        logger.info(f"LinkedIn: found {len(jobs)} jobs")
        return jobs

    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        await self.page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay(2, 3)

        # Get job description
        try:
            desc_el = await self.page.query_selector('.jobs-description, [data-testid="job-description"]')
            if desc_el:
                job["description"] = (await desc_el.inner_text())[:1500]
        except Exception:
            pass

        if self.dry_run:
            logger.info(f"[DRY RUN] Would apply: {job['title']} @ {job['company']}")
            return True

        # Click Easy Apply
        clicked = await self.safe_click(
            'button.jobs-apply-button, button[aria-label*="Easy Apply"], '
            '.jobs-s-apply button',
            5000
        )
        if not clicked:
            logger.warning(f"LinkedIn: Easy Apply button not found for {job['title']}")
            return False

        await self.delay(1, 2)

        # Walk through multi-step Easy Apply modal
        for step in range(8):
            await self.wait_for_captcha()

            # Fill phone if shown
            await self.safe_fill(
                'input[id*="phoneNumber"], input[name*="phone"]',
                self.personal.get("phone", "")
            )

            # Upload CV if file input appears
            cv_input = await self.page.query_selector('input[type="file"]')
            if cv_input:
                await self.upload_cv('input[type="file"]')
                await self.delay()

            # Fill cover letter / additional info text areas
            textareas = await self.page.query_selector_all('textarea')
            for ta in textareas:
                val = await ta.input_value()
                if not val and cover_letter:
                    await ta.fill(cover_letter[:2000])

            # Answer Yes/No radio questions (default: Yes)
            radios = await self.page.query_selector_all('fieldset input[type="radio"][value="Yes"]')
            for radio in radios:
                is_checked = await radio.is_checked()
                if not is_checked:
                    await radio.click()

            await self.delay(0.5, 1)

            # Try Next or Submit
            submitted = await self.safe_click(
                'button[aria-label="Submit application"]', 2000
            )
            if submitted:
                await self.delay(2, 3)
                await self.screenshot(f"applied_{job['company'][:20]}")
                logger.info(f"LinkedIn: applied -> {job['title']} @ {job['company']}")
                return True

            next_ok = await self.safe_click(
                'button[aria-label="Continue to next step"], '
                'button[aria-label="Review your application"], '
                'button:has-text("Next"), button:has-text("Review")',
                3000
            )
            if not next_ok:
                break
            await self.delay(1, 2)

        logger.warning(f"LinkedIn: could not complete application for {job['title']}")
        return False

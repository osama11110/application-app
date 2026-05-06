import logging
import urllib.parse
from .base_site import BaseSite

logger = logging.getLogger(__name__)


class IndeedAt(BaseSite):
    name = "indeed"

    LOGIN_URL = "https://secure.indeed.com/account/login"
    SEARCH_URL = "https://at.indeed.com/jobs"

    async def login(self) -> bool:
        email = self.creds.get("email", "")
        password = self.creds.get("password", "")
        if not email or not password:
            if await self.check_already_logged_in(
                "https://at.indeed.com",
                '#UserOptionsDropdownBtn, [data-testid="UserDropdown"], a[href*="/account"]'
            ):
                logger.info("indeed: already logged in via saved session")
                return True
            return await self.manual_login(self.LOGIN_URL)

        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
        await self.delay()

        await self.safe_fill('#login-email-input, input[type="email"]', email)
        await self.delay(0.3, 0.7)
        await self.safe_click('button[type="submit"], button:has-text("Continue")')
        await self.delay()

        await self.safe_fill('#login-password-input, input[type="password"]', password)
        await self.delay(0.3, 0.7)
        await self.safe_click('button[type="submit"], button:has-text("Sign In")')
        await self.page.wait_for_load_state("domcontentloaded")
        await self.wait_for_captcha()

        success = "resumes" in self.page.url or "homepage" in self.page.url or "myindeed" in self.page.url
        logger.info(f"indeed login {'OK' if success else 'FAILED'}")
        return success

    async def search_jobs(self, keywords: list[str], location: str) -> list[dict]:
        jobs = []
        for keyword in keywords[:5]:
            url = (f"{self.SEARCH_URL}?"
                   f"q={urllib.parse.quote(keyword)}&"
                   f"l=%C3%96sterreich&"
                   f"sort=date")
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.delay()

            for _ in range(3):
                cards = await self.page.query_selector_all(
                    '.job_seen_beacon, [data-testid="jobCard"], .resultContent'
                )
                for card in cards:
                    try:
                        title_el = await card.query_selector(
                            'h2 a span, [data-testid="jobTitle"] a, .jcs-JobTitle a'
                        )
                        company_el = await card.query_selector(
                            '[data-testid="company-name"], .companyName, .css-1h7lukg'
                        )
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""

                        link_el = await card.query_selector('h2 a, [data-testid="jobTitle"] a')
                        href = await link_el.get_attribute("href") if link_el else ""
                        job_url = href if href.startswith("http") else f"https://at.indeed.com{href}"
                        loc_el = await card.query_selector(
                            '[data-testid="jobLocation"], .companyLocation, '
                            '.css-1restlb, [class*="location"]'
                        )
                        location = (await loc_el.inner_text()).strip() if loc_el else ""

                        if title and job_url not in [j["url"] for j in jobs]:
                            jobs.append({"title": title, "company": company, "location": location,
                                         "url": job_url, "site": self.name, "description": ""})
                    except Exception:
                        continue

                next_btn = await self.page.query_selector(
                    'a[data-testid="pagination-page-next"], a[aria-label="Next Page"]'
                )
                if next_btn:
                    await next_btn.click()
                    await self.delay(1, 2)
                else:
                    break

                if len(jobs) >= self.config["search"].get("max_results_per_site", 30):
                    break

        logger.info(f"indeed: found {len(jobs)} jobs")
        return jobs

    async def apply_to_job(self, job: dict, cover_letter: str = "") -> bool:
        await self.page.goto(job["url"], wait_until="domcontentloaded")
        await self.delay()

        try:
            desc_el = await self.page.query_selector('#jobDescriptionText, .jobsearch-jobDescriptionText')
            if desc_el:
                job["description"] = (await desc_el.inner_text())[:1500]
        except Exception:
            pass

        if self.dry_run:
            logger.info(f"[DRY RUN] {job['title']} @ {job['company']}")
            return True

        clicked = await self.safe_click(
            'button#indeedApplyButton, [data-testid="indeedApplyButton"], '
            'button:has-text("Jetzt bewerben"), button:has-text("Apply now")',
            5000
        )
        if not clicked:
            logger.warning(f"indeed: no apply button for {job['title']}")
            return False

        await self.page.wait_for_load_state("domcontentloaded")
        await self.delay()
        await self.wait_for_captcha()

        if await self.try_external_apply("indeed.com", job, cover_letter):
            return True

        # Indeed uses multi-step inline form
        for _ in range(6):
            await self.safe_fill('input[name="applicant.name"], input[aria-label*="name"]',
                                 self.personal.get("name", ""))
            await self.safe_fill('input[name="applicant.phoneNumber"], input[aria-label*="phone"]',
                                 self.personal.get("phone", ""))

            cv_input = await self.page.query_selector('input[type="file"]')
            if cv_input:
                await self.upload_cv('input[type="file"]')
                await self.delay()

            if cover_letter:
                await self.safe_fill('textarea[aria-label*="cover"], textarea[name*="coverLetter"]', cover_letter)

            submitted = await self.safe_click('button[aria-label="Submit your application"]', 2000)
            if submitted:
                await self.delay(2, 3)
                await self.screenshot(f"applied_{job['company'][:20]}")
                logger.info(f"indeed: applied -> {job['title']} @ {job['company']}")
                return True

            cont = await self.safe_click(
                'button:has-text("Continue"), button[aria-label*="Continue"]', 2000
            )
            if not cont:
                break
            await self.delay()

        logger.warning(f"indeed: could not complete application for {job['title']}")
        return False

"""SmartRecruiters ATS handler."""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"SmartRecruiters apply: {page.url[:80]}")

    await delay()

    # Click apply button on job detail
    await safe_click(page, 'button.btn-apply, a.btn-apply, '
                           'button:has-text("Apply"), a:has-text("Apply Now")', 3000)
    await page.wait_for_load_state("domcontentloaded")
    await delay()

    # Resume upload first (SmartRecruiters often parses it to fill fields)
    await upload_file(page, 'input[type="file"][accept*="pdf"], input[type="file"]', cv_path)
    await delay(1, 2)

    await safe_fill(page, 'input[name="firstName"], input[id*="firstName"]',
                    personal.get("first_name", ""))
    await safe_fill(page, 'input[name="lastName"], input[id*="lastName"]',
                    personal.get("last_name", ""))
    await safe_fill(page, 'input[name="email"], input[type="email"]', personal.get("email", ""))
    await safe_fill(page, 'input[name="phone"], input[type="tel"]',   personal.get("phone", ""))

    linkedin = personal.get("linkedin", "")
    if linkedin:
        await safe_fill(page, 'input[name*="linkedin"], input[placeholder*="LinkedIn"]', linkedin, 2000)

    if cover_letter:
        await safe_fill(page, 'textarea[name*="message"], textarea[name*="cover"]', cover_letter, 2000)

    await delay(0.5, 1.5)

    for _ in range(5):
        submit = await page.query_selector(
            'button[data-action="next"], button:has-text("Submit"), button:has-text("Continue")'
        )
        if not submit:
            break
        label = (await submit.inner_text()).strip().lower()
        await submit.click()
        await delay(1, 2)
        if "submit" in label:
            logger.info("SmartRecruiters: submitted")
            return True

    logger.warning("SmartRecruiters: could not complete application")
    return False

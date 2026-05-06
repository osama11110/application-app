"""Lever ATS handler — jobs.lever.co"""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"Lever apply: {page.url[:80]}")

    # Lever shows a job detail page first — click Apply
    await safe_click(page, 'a[data-qa="btn-apply-bottom"], a[data-qa="btn-apply"], '
                           '.postings-btn-submit, a:has-text("Apply for this job")', 3000)
    await delay()

    await safe_fill(page, 'input[name="name"]',
                    f"{personal.get('first_name','')} {personal.get('last_name','')}".strip())
    await safe_fill(page, 'input[name="email"]',   personal.get("email", ""))
    await safe_fill(page, 'input[name="phone"]',   personal.get("phone", ""))
    await safe_fill(page, 'input[name="org"]',
                    cv_data.get("experience", [{}])[0].get("company", "") if cv_data.get("experience") else "")
    await delay(0.3, 0.8)

    # LinkedIn / website
    linkedin = personal.get("linkedin", "")
    if linkedin:
        await safe_fill(page, 'input[name="urls[LinkedIn]"], input[placeholder*="LinkedIn"]', linkedin, 2000)

    website = personal.get("website", "")
    if website:
        await safe_fill(page, 'input[name="urls[Portfolio]"], input[placeholder*="website"]', website, 2000)

    # Resume upload
    await upload_file(page, 'input[type="file"]', cv_path)
    await delay()

    # Cover letter
    if cover_letter:
        await safe_fill(page, 'textarea[name="comments"], textarea[placeholder*="cover"]', cover_letter, 2000)

    await delay(0.5, 1.5)
    submitted = await safe_click(page, 'button[type="submit"], .template-btn-submit, '
                                       'button:has-text("Submit application")')
    await delay(2, 3)
    logger.info(f"Lever: {'submitted' if submitted else 'submit failed'}")
    return submitted

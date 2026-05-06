"""Greenhouse ATS handler — boards.greenhouse.io"""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file, fill_by_label

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"Greenhouse apply: {page.url[:80]}")

    await delay()

    await safe_fill(page, '#first_name, input[name="first_name"]', personal.get("first_name", ""))
    await safe_fill(page, '#last_name, input[name="last_name"]',   personal.get("last_name", ""))
    await safe_fill(page, '#email, input[name="email"]',           personal.get("email", ""))
    await safe_fill(page, '#phone, input[name="phone"]',           personal.get("phone", ""))
    await delay(0.3, 0.8)

    # Resume upload
    await upload_file(page, 'input[type="file"]', cv_path)
    await delay()

    # Cover letter text area
    if cover_letter:
        filled = await safe_fill(page, '#cover_letter_text, textarea[name*="cover"]', cover_letter, 2000)
        if not filled:
            # Greenhouse sometimes has a cover letter file upload
            cl_upload = await page.query_selector('input[id*="cover_letter"][type="file"]')
            # Skip if only file upload available — paste text is preferred

    # LinkedIn
    linkedin = personal.get("linkedin", "")
    if linkedin:
        await safe_fill(page, 'input[id*="linkedin"], input[name*="linkedin"]', linkedin, 2000)

    # Website
    website = personal.get("website", "")
    if website:
        await safe_fill(page, 'input[id*="website"], input[name*="website"]', website, 2000)

    # Answer custom demographic / screening questions
    await _answer_custom_questions(page, cv_data, job)

    await delay(0.5, 1.5)
    submitted = await safe_click(page, '#submit_app, button[type="submit"]')
    await delay(2, 3)
    logger.info(f"Greenhouse: {'submitted' if submitted else 'submit failed'}")
    return submitted


async def _answer_custom_questions(page: Page, cv_data: dict, job: dict):
    """Handle common Greenhouse custom questions."""
    personal = cv_data.get("personal", {})

    # Yes/No selects — default Yes for work authorization
    selects = await page.query_selector_all("select")
    for sel in selects:
        label_el = await page.query_selector(f'label[for="{await sel.get_attribute("id")}"]')
        label_text = (await label_el.inner_text()).lower() if label_el else ""
        if any(w in label_text for w in ["authoriz", "eligible", "legal", "berechtigt", "arbeitserlaub"]):
            await sel.select_option(index=1)  # usually "Yes"
        elif any(w in label_text for w in ["sponsor", "visa"]):
            work_permit = cv_data.get("work_permit", "EU citizen").lower()
            idx = 2 if "eu" in work_permit or "citizen" in work_permit else 1
            await sel.select_option(index=idx)

    # Text inputs for salary
    salary = cv_data.get("salary_expectation", "")
    if salary:
        await fill_by_label(page, "salary", salary)
        await fill_by_label(page, "gehalt", salary)
        await fill_by_label(page, "lohn", salary)

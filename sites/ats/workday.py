"""Workday ATS handler — used by large corporations."""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file, fill_by_label

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"Workday apply: {page.url[:80]}")

    await delay()

    # Workday often requires account — try guest/manual apply first
    await safe_click(page, 'a[data-automation-id="applyManually"], '
                           'button:has-text("Apply Manually"), '
                           'button:has-text("Manuell bewerben")', 3000)
    await delay()

    # Click Apply button if on job detail
    await safe_click(page, 'a[data-automation-id="applyButton"], '
                           'button[data-automation-id="applyButton"]', 3000)
    await page.wait_for_load_state("domcontentloaded")
    await delay()

    # Resume upload — try My Experience section
    await upload_file(page, 'input[data-automation-id="file-upload-input"], '
                            'input[type="file"]', cv_path)
    await delay()

    # Personal info fields
    await safe_fill(page,
                    'input[data-automation-id="legalNameSection_firstName"], '
                    'input[id*="firstName"]',
                    personal.get("first_name", ""))
    await safe_fill(page,
                    'input[data-automation-id="legalNameSection_lastName"], '
                    'input[id*="lastName"]',
                    personal.get("last_name", ""))
    await safe_fill(page, 'input[data-automation-id="email"], input[type="email"]',
                    personal.get("email", ""))
    await safe_fill(page, 'input[data-automation-id="phone"], input[type="tel"]',
                    personal.get("phone", ""))
    await delay(0.3, 0.8)

    # Address
    city = personal.get("city", "")
    if city:
        await fill_by_label(page, "city", city)
        await fill_by_label(page, "stadt", city)

    await fill_by_label(page, "country", personal.get("country", "Austria"))

    # Cover letter
    if cover_letter:
        await safe_fill(page,
                        'textarea[data-automation-id="coverLetter"], textarea[name*="cover"]',
                        cover_letter, 2000)

    # Walk through multi-step — click Next up to 6 times
    for _ in range(6):
        await delay(0.5, 1)
        next_clicked = await safe_click(
            page,
            'button[data-automation-id="bottom-navigation-next-btn"], '
            'button:has-text("Next"), button:has-text("Weiter")',
            3000
        )
        if not next_clicked:
            break
        await page.wait_for_load_state("domcontentloaded")
        await delay()

        # Upload CV if file input appears on this step
        file_inp = await page.query_selector('input[type="file"]')
        if file_inp:
            await upload_file(page, 'input[type="file"]', cv_path)

        # Check for submit button
        submit = await page.query_selector(
            'button[data-automation-id="bottom-navigation-review-btn"], '
            'button:has-text("Submit")'
        )
        if submit:
            await submit.click()
            await delay(2, 3)
            logger.info("Workday: submitted")
            return True

    logger.warning("Workday: could not complete all steps — may need manual review")
    return False

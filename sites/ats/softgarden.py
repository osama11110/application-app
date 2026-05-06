"""Softgarden ATS handler — common in DACH region."""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file, fill_by_label

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"Softgarden apply: {page.url[:80]}")

    await delay()

    # Navigate to application form if on job detail
    await safe_click(page, 'a:has-text("Jetzt bewerben"), a:has-text("Bewerben jetzt"), '
                           'button:has-text("Bewerben"), .apply-button', 3000)
    await page.wait_for_load_state("domcontentloaded")
    await delay()

    # Salutation
    title_sel = await page.query_selector('select[name*="salutation"], select[name*="anrede"]')
    if title_sel:
        await title_sel.select_option(index=1)

    await safe_fill(page, 'input[name="firstName"], input[name*="vorname"]',
                    personal.get("first_name", ""))
    await safe_fill(page, 'input[name="lastName"], input[name*="nachname"]',
                    personal.get("last_name", ""))
    await safe_fill(page, 'input[name="email"], input[type="email"]', personal.get("email", ""))
    await safe_fill(page, 'input[name="phone"], input[type="tel"]',   personal.get("phone", ""))
    await delay(0.3, 0.8)

    city = personal.get("city", "")
    if city:
        await fill_by_label(page, "city", city)
        await fill_by_label(page, "ort", city)

    # CV upload
    await upload_file(page, 'input[type="file"]', cv_path)
    await delay()

    # Cover letter
    if cover_letter:
        await safe_fill(page,
                        'textarea[name*="cover"], textarea[name*="letter"], '
                        'textarea[placeholder*="Anschreiben"]',
                        cover_letter, 2000)

    await fill_by_label(page, "gehaltsvorstellung", cv_data.get("salary_expectation", ""))
    await fill_by_label(page, "eintrittstermin", "Nach Vereinbarung")

    await delay(0.5, 1.5)
    submitted = await safe_click(page,
                                 'button[type="submit"], button:has-text("Bewerbung absenden"), '
                                 'button:has-text("Jetzt bewerben")')
    await delay(2, 3)
    logger.info(f"Softgarden: {'submitted' if submitted else 'submit failed'}")
    return submitted

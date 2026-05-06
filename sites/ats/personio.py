"""Personio ATS handler — very common in Austria/DACH startups."""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file, fill_by_label

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"Personio apply: {page.url[:80]}")

    # Accept cookies if shown
    await safe_click(page, 'button[id*="accept"], button:has-text("Akzeptieren"), '
                           'button:has-text("Accept all")', 3000)
    await delay()

    # Click Apply button on job detail page
    applied_page = await safe_click(
        page,
        'a[data-testid="cta-button"], button:has-text("Jetzt bewerben"), '
        'a:has-text("Jetzt bewerben"), button:has-text("Apply now")',
        3000
    )
    if applied_page:
        await page.wait_for_load_state("domcontentloaded")
        await delay()

    # Personal info
    await safe_fill(page, 'input[name="first_name"], input[id*="first_name"], '
                          'input[placeholder*="Vorname"]',
                    personal.get("first_name", ""))
    await safe_fill(page, 'input[name="last_name"], input[id*="last_name"], '
                          'input[placeholder*="Nachname"]',
                    personal.get("last_name", ""))
    await safe_fill(page, 'input[name="email"], input[type="email"]', personal.get("email", ""))
    await safe_fill(page, 'input[name="phone"], input[type="tel"]',   personal.get("phone", ""))
    await delay(0.3, 0.8)

    # City / address
    city = personal.get("city", "")
    if city:
        await fill_by_label(page, "city", city)
        await fill_by_label(page, "stadt", city)
        await fill_by_label(page, "ort", city)

    # Document uploads — Personio often has separate CV and cover letter uploads
    file_inputs = await page.query_selector_all('input[type="file"]')
    if len(file_inputs) >= 1:
        await upload_file(page, 'input[type="file"]:first-of-type', cv_path)
    await delay()

    # Cover letter text
    if cover_letter:
        await safe_fill(page,
                        'textarea[name*="cover"], textarea[name*="motivation"], '
                        'textarea[placeholder*="Anschreiben"], textarea[placeholder*="Motivationsschreiben"]',
                        cover_letter, 2000)

    # Salary expectation
    salary = cv_data.get("salary_expectation", "")
    if salary:
        await fill_by_label(page, "salary", salary)
        await fill_by_label(page, "gehalt", salary)
        await fill_by_label(page, "gehaltsvorstellung", salary)

    # Availability / start date
    await fill_by_label(page, "availability", "Ab sofort möglich")
    await fill_by_label(page, "startdatum", "Nach Vereinbarung")
    await fill_by_label(page, "eintrittsdatum", "Nach Vereinbarung")

    await delay(0.5, 1.5)
    submitted = await safe_click(page,
                                 'button[type="submit"], button:has-text("Bewerbung absenden"), '
                                 'button:has-text("Submit"), button:has-text("Senden")')
    await delay(2, 3)
    logger.info(f"Personio: {'submitted' if submitted else 'submit failed'}")
    return submitted

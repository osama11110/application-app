"""eRecruiter ATS handler — widely used in Austria."""
import logging
from playwright.async_api import Page
from .base_ats import delay, safe_fill, safe_click, upload_file, fill_by_label

logger = logging.getLogger(__name__)


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    personal = cv_data.get("personal", {})
    logger.info(f"eRecruiter apply: {page.url[:80]}")

    await delay()

    # Click Jetzt bewerben
    await safe_click(page, 'a:has-text("Jetzt bewerben"), button:has-text("Jetzt bewerben"), '
                           'a:has-text("Bewerben"), .btn-apply', 3000)
    await page.wait_for_load_state("domcontentloaded")
    await delay()

    # Personal data
    await safe_fill(page, 'input[name*="vorname"], input[id*="vorname"], '
                          'input[placeholder*="Vorname"]',
                    personal.get("first_name", ""))
    await safe_fill(page, 'input[name*="nachname"], input[id*="nachname"], '
                          'input[placeholder*="Nachname"]',
                    personal.get("last_name", ""))
    await safe_fill(page, 'input[name*="email"], input[type="email"]', personal.get("email", ""))
    await safe_fill(page, 'input[name*="telefon"], input[name*="phone"], input[type="tel"]',
                    personal.get("phone", ""))
    await delay(0.3, 0.8)

    # Title/salutation select (Herr/Frau)
    title_sel = await page.query_selector('select[name*="anrede"], select[name*="title"], '
                                          'select[id*="anrede"]')
    if title_sel:
        await title_sel.select_option(index=1)

    # Address fields
    city = personal.get("city", "")
    if city:
        await fill_by_label(page, "ort", city)
        await fill_by_label(page, "wohnort", city)
        await fill_by_label(page, "stadt", city)

    # CV upload
    await upload_file(page, 'input[type="file"]', cv_path)
    await delay()

    # Cover letter / motivation
    if cover_letter:
        await safe_fill(page,
                        'textarea[name*="anschreiben"], textarea[name*="motivation"], '
                        'textarea[name*="bewerbungsschreiben"], '
                        'textarea[placeholder*="Anschreiben"]',
                        cover_letter, 2000)

    # Salary
    salary = cv_data.get("salary_expectation", "")
    if salary:
        await fill_by_label(page, "gehaltsvorstellung", salary)
        await fill_by_label(page, "gehalt", salary)

    # Earliest start date
    await fill_by_label(page, "eintrittsdatum", "Nach Vereinbarung")
    await fill_by_label(page, "frühestmöglicher", "Nach Vereinbarung")

    await delay(0.5, 1.5)
    submitted = await safe_click(page,
                                 'button[type="submit"], input[type="submit"], '
                                 'button:has-text("Bewerbung absenden"), '
                                 'button:has-text("Jetzt bewerben")')
    await delay(2, 3)
    logger.info(f"eRecruiter: {'submitted' if submitted else 'submit failed'}")
    return submitted

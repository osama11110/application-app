"""
Generic ATS handler — intelligent form filler for unknown company career portals.
Uses label-text matching to map CV data to form fields.
"""
import logging
import re
from playwright.async_api import Page
from .base_ats import delay, safe_click, upload_file

logger = logging.getLogger(__name__)

# Maps keywords found in labels/placeholders to CV data keys
FIELD_MAP = {
    # Name fields
    ("first name", "vorname", "first_name", "given name"):    "first_name",
    ("last name",  "nachname", "last_name", "surname", "family name"): "last_name",
    ("full name",  "name", "ihr name", "your name"):          "full_name",

    # Contact
    ("email", "e-mail", "e mail"):                            "email",
    ("phone", "telefon", "mobile", "handy", "tel"):           "phone",

    # Address
    ("city", "stadt", "ort", "wohnort", "location"):          "city",
    ("country", "land"):                                       "country",
    ("zip", "plz", "postcode", "postal"):                     "zip",
    ("address", "adresse", "straße", "street"):               "address",

    # Professional
    ("linkedin",):                                             "linkedin",
    ("website", "portfolio", "github", "homepage"):           "website",
    ("salary", "gehalt", "gehaltsvorstellung", "lohn"):       "salary",
    ("availability", "verfügbar", "eintrittsdatum",
     "start date", "startdatum", "eintrittstermin"):           "availability",
    ("nationality", "nationalität"):                           "nationality",
}


def _get_value(cv_data: dict, field_key: str) -> str:
    personal = cv_data.get("personal", {})
    mapping = {
        "first_name":   personal.get("first_name", ""),
        "last_name":    personal.get("last_name", ""),
        "full_name":    personal.get("name", ""),
        "email":        personal.get("email", ""),
        "phone":        personal.get("phone", ""),
        "city":         personal.get("city", ""),
        "country":      personal.get("country", "Austria"),
        "zip":          "",
        "address":      personal.get("address", ""),
        "linkedin":     personal.get("linkedin", ""),
        "website":      personal.get("website", ""),
        "salary":       cv_data.get("salary_expectation", ""),
        "availability": "Nach Vereinbarung",
        "nationality":  personal.get("country", ""),
    }
    return mapping.get(field_key, "")


def _match_field(label_text: str) -> str | None:
    lt = label_text.lower().strip()
    lt = re.sub(r'[*:\(\)]', '', lt).strip()
    for keywords, field_key in FIELD_MAP.items():
        if any(kw in lt for kw in keywords):
            return field_key
    return None


async def apply(page: Page, job: dict, cv_data: dict, cv_path: str, cover_letter: str) -> bool:
    logger.info(f"Generic ATS apply: {page.url[:80]}")
    await delay()

    # Accept cookies if present
    await safe_click(page, 'button:has-text("Accept"), button:has-text("Akzeptieren"), '
                           'button:has-text("Accept all"), [id*="cookie"] button', 3000)
    await delay(0.3, 0.8)

    # Click any visible apply button
    await safe_click(page,
                     'a:has-text("Jetzt bewerben"), button:has-text("Jetzt bewerben"), '
                     'a:has-text("Apply"), button:has-text("Apply now"), '
                     'a:has-text("Apply for this position"), .apply-btn, '
                     '[data-action="apply"]', 3000)
    await page.wait_for_load_state("domcontentloaded")
    await delay()

    filled_count = 0

    # --- Fill text inputs by label ---
    inputs = await page.query_selector_all('input[type="text"], input[type="email"], '
                                           'input[type="tel"], input[type="url"]')
    for inp in inputs:
        # Try to find associated label
        inp_id  = await inp.get_attribute("id") or ""
        name    = await inp.get_attribute("name") or ""
        ph      = await inp.get_attribute("placeholder") or ""
        aria    = await inp.get_attribute("aria-label") or ""

        label_text = ""
        if inp_id:
            lbl = await page.query_selector(f'label[for="{inp_id}"]')
            if lbl:
                label_text = await lbl.inner_text()
        if not label_text:
            label_text = aria or ph or name

        field_key = _match_field(label_text)
        if field_key:
            value = _get_value(cv_data, field_key)
            if value:
                try:
                    await inp.fill(value)
                    filled_count += 1
                    await delay(0.1, 0.3)
                except Exception:
                    pass

    # --- Fill textareas ---
    textareas = await page.query_selector_all("textarea")
    for ta in textareas:
        ta_id   = await ta.get_attribute("id") or ""
        name    = await ta.get_attribute("name") or ""
        ph      = await ta.get_attribute("placeholder") or ""
        aria    = await ta.get_attribute("aria-label") or ""

        label_text = ""
        if ta_id:
            lbl = await page.query_selector(f'label[for="{ta_id}"]')
            if lbl:
                label_text = await lbl.inner_text()
        if not label_text:
            label_text = aria or ph or name

        lt = label_text.lower()
        val = await ta.input_value()
        if val:
            continue  # already filled

        if any(w in lt for w in ["cover", "anschreiben", "motivation", "letter", "message", "nachricht"]):
            if cover_letter:
                await ta.fill(cover_letter[:3000])
                filled_count += 1
        elif any(w in lt for w in ["summary", "zusammenfassung", "about", "über mich"]):
            summary = cv_data.get("summary", "")
            if summary:
                await ta.fill(summary)
                filled_count += 1

    # --- Upload CV ---
    file_inputs = await page.query_selector_all('input[type="file"]')
    if file_inputs:
        uploaded = await upload_file(page, 'input[type="file"]', cv_path)
        if uploaded:
            filled_count += 1
    await delay()

    # --- Handle selects (Yes/No, salutation) ---
    selects = await page.query_selector_all("select")
    for sel in selects:
        sel_id = await sel.get_attribute("id") or ""
        name   = await sel.get_attribute("name") or ""
        lbl_text = ""
        if sel_id:
            lbl = await page.query_selector(f'label[for="{sel_id}"]')
            if lbl:
                lbl_text = (await lbl.inner_text()).lower()

        # Salutation
        if any(w in lbl_text or w in name.lower()
               for w in ["anrede", "salutation", "title", "gender"]):
            await sel.select_option(index=1)
        # Work authorization — Yes
        elif any(w in lbl_text for w in ["authoriz", "eligible", "legal", "erlaubnis"]):
            await sel.select_option(index=1)

    logger.info(f"Generic ATS: filled {filled_count} fields on {page.url[:60]}")

    await delay(0.5, 1.5)

    # Try to submit
    submitted = await safe_click(page,
                                 'button[type="submit"], input[type="submit"], '
                                 'button:has-text("Submit"), button:has-text("Senden"), '
                                 'button:has-text("Bewerbung absenden"), '
                                 'button:has-text("Bewerbung senden")')
    await delay(2, 3)

    if not submitted:
        logger.warning(f"Generic ATS: could not find submit button — screenshot saved")
        import os
        from datetime import datetime
        os.makedirs("screenshots", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        await page.screenshot(path=f"screenshots/ats_manual_needed_{ts}.png")

    logger.info(f"Generic ATS: {'submitted' if submitted else 'needs manual review'}")
    return submitted

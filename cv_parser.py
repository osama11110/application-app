import json
import logging
import re
from pathlib import Path

import pdfplumber
import anthropic
from docx import Document

logger = logging.getLogger(__name__)


def _extract_pdf(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _extract_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_cv_text(cv_path: str) -> str:
    p = Path(cv_path)
    if not p.exists():
        raise FileNotFoundError(f"CV not found: {cv_path}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(cv_path)
    if suffix in (".docx", ".doc"):
        return _extract_docx(cv_path)
    raise ValueError(f"Unsupported CV format '{suffix}'. Use PDF or DOCX.")


def parse_cv(cv_path: str, api_key: str) -> dict:
    cached = Path("cv/parsed_cv.json")
    if cached.exists():
        logger.info("Loading cached CV parse")
        with open(cached, encoding="utf-8") as f:
            return json.load(f)

    logger.info(f"Parsing CV: {cv_path}")
    text = extract_cv_text(cv_path)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system="You are a CV parsing assistant. Return only valid JSON, no markdown fences.",
        messages=[{
            "role": "user",
            "content": f"""Parse this CV into structured JSON.

CV TEXT:
{text}

Return this exact JSON structure (fill every field; empty string if unknown):
{{
  "personal": {{
    "name": "",
    "first_name": "",
    "last_name": "",
    "email": "",
    "phone": "",
    "address": "",
    "city": "",
    "country": "",
    "linkedin": "",
    "website": "",
    "github": ""
  }},
  "summary": "",
  "skills": [],
  "languages": [{{"language": "", "level": ""}}],
  "experience": [{{
    "title": "",
    "company": "",
    "location": "",
    "start": "",
    "end": "",
    "description": ""
  }}],
  "education": [{{
    "degree": "",
    "field": "",
    "institution": "",
    "location": "",
    "start": "",
    "end": ""
  }}],
  "certifications": [],
  "job_titles_to_search": [],
  "keywords": [],
  "salary_expectation": "",
  "work_permit": "EU citizen"
}}

Rules:
- job_titles_to_search: 8-12 job titles this person should target based on experience
- keywords: 25-35 professional/technical keywords for job search
- salary_expectation: estimate for Austrian market if not in CV (format: "€X,000 - €Y,000")
- work_permit: infer from nationality/address or default to "EU citizen"
"""
        }]
    )

    content = response.content[0].text.strip()
    m = re.search(r'\{.*\}', content, re.DOTALL)
    data = json.loads(m.group() if m else content)

    cached.parent.mkdir(exist_ok=True)
    with open(cached, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(
        f"CV parsed -> {data['personal'].get('name')} | "
        f"{len(data.get('skills', []))} skills | "
        f"{len(data.get('job_titles_to_search', []))} search titles"
    )
    return data

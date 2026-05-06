import logging
import anthropic

logger = logging.getLogger(__name__)


class AIHelper:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def score_job_match(self, cv_data: dict, job: dict) -> int:
        skills = ", ".join(cv_data.get("skills", [])[:20])
        titles = ", ".join(cv_data.get("job_titles_to_search", []))
        langs = ", ".join(
            f"{l['language']} ({l['level']})"
            for l in cv_data.get("languages", [])
        )
        exp_count = len(cv_data.get("experience", []))

        prompt = (
            f"Rate 0-100 how well this job matches the candidate. Return ONLY the number.\n\n"
            f"CANDIDATE: roles={titles} | skills={skills} | "
            f"experience={exp_count} positions | languages={langs}\n\n"
            f"JOB: {job.get('title','')} at {job.get('company','')}\n"
            f"DESCRIPTION: {job.get('description','')[:800]}"
        )

        resp = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            return max(0, min(100, int(resp.content[0].text.strip())))
        except ValueError:
            return 50

    def generate_cover_letter(self, cv_data: dict, job: dict) -> str:
        personal = cv_data.get("personal", {})
        job_desc = job.get("description", "")
        lang = self.detect_language(job_desc or job.get("title", ""))

        if lang == "de":
            style = "Write in formal German (Sie form). Austrian business style."
        else:
            style = "Write in professional English."

        prompt = (
            f"{style}\n\n"
            f"Write a 3-paragraph cover letter for this application.\n"
            f"No header/salutation needed - just the body paragraphs.\n\n"
            f"CANDIDATE: {personal.get('name')} | "
            f"Skills: {', '.join(cv_data.get('skills', [])[:12])} | "
            f"Summary: {cv_data.get('summary', '')}\n\n"
            f"JOB: {job.get('title','')} at {job.get('company','')}\n"
            f"DESCRIPTION: {job_desc[:700]}\n\n"
            f"Para 1: Why this role + most relevant experience.\n"
            f"Para 2: Specific skills matching job requirements.\n"
            f"Para 3: Enthusiasm + call to action.\n"
            f"Max 280 words."
        )

        resp = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()

    def answer_question(self, cv_data: dict, question: str, job: dict) -> str:
        personal = cv_data.get("personal", {})
        prompt = (
            f"Answer this job application question concisely (max 80 words).\n"
            f"Answer in the same language as the question.\n\n"
            f"CANDIDATE: {personal.get('name')} | "
            f"Skills: {', '.join(cv_data.get('skills', [])[:10])} | "
            f"Work permit: {cv_data.get('work_permit', 'EU citizen')} | "
            f"Salary expectation: {cv_data.get('salary_expectation', '')} | "
            f"Latest role: {cv_data.get('experience', [{}])[0].get('title','') if cv_data.get('experience') else ''}\n\n"
            f"JOB: {job.get('title','')}\n"
            f"QUESTION: {question}"
        )
        resp = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()

    @staticmethod
    def detect_language(text: str) -> str:
        german = ["und", "der", "die", "das", "ist", "wir", "Sie", "mit",
                  "für", "als", "auf", "ein", "eine", "nicht", "auch"]
        hits = sum(1 for w in german if f" {w} " in f" {text.lower()} ")
        return "de" if hits >= 2 else "en"

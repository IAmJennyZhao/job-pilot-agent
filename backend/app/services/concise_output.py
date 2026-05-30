import re
from collections.abc import Iterable

from app import schemas

SOFT_SKILL_RE = re.compile(
    r"\b("
    r"collaboration|communication|stakeholder|cross-functional|teamwork|"
    r"leadership|written|verbal|presentation|interpersonal|relationship|"
    r"self-starter|ownership mindset|attention to detail"
    r")\b",
    re.IGNORECASE,
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def compact_text(value: str | None, limit: int = 150) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    trimmed = text[: limit + 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{trimmed}..."


def _key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", value.casefold())
    tokens = [token for token in normalized.split() if token not in STOP_WORDS]
    return " ".join(tokens)


def _too_similar(candidate_key: str, used_keys: set[str]) -> bool:
    if candidate_key in used_keys:
        return True
    candidate_tokens = set(candidate_key.split())
    if not candidate_tokens:
        return True
    for used_key in used_keys:
        used_tokens = set(used_key.split())
        if not used_tokens:
            continue
        overlap = candidate_tokens & used_tokens
        if len(overlap) >= 2 and len(overlap) / min(len(candidate_tokens), len(used_tokens)) >= 0.75:
            return True
    return False


def compact_items(
    items: Iterable[str],
    *,
    limit: int = 5,
    used_keys: set[str] | None = None,
    tech_only: bool = False,
    text_limit: int = 70,
) -> list[str]:
    used = used_keys if used_keys is not None else set()
    result: list[str] = []
    for item in items:
        text = compact_text(item, text_limit)
        if not text:
            continue
        if tech_only and SOFT_SKILL_RE.search(text):
            continue
        key = _key(text)
        if _too_similar(key, used):
            continue
        used.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_extraction_output(output: schemas.JobExtractionOutput) -> schemas.JobExtractionOutput:
    output.summary = compact_text(output.summary, 140)
    output.responsibilities = compact_items(output.responsibilities, limit=5, text_limit=58)
    output.required_skills = compact_items(output.required_skills, limit=6, tech_only=True, text_limit=42)
    output.benefits = compact_items(output.benefits, limit=5, text_limit=48)
    output.warnings = compact_items(output.warnings, limit=4, text_limit=90)
    return output


def normalize_job_insights(output: schemas.JobInsightsOutput) -> schemas.JobInsightsOutput:
    output.summary = compact_text(output.summary, 120)
    used: set[str] = set()
    output.role_focus = compact_items(output.role_focus, limit=3, used_keys=used, text_limit=52)
    output.responsibilities = compact_items(output.responsibilities, limit=5, used_keys=used, text_limit=58)
    output.must_have_skills = compact_items(output.must_have_skills, limit=5, used_keys=used, tech_only=True, text_limit=42)
    output.nice_to_have_skills = compact_items(output.nice_to_have_skills, limit=5, used_keys=used, tech_only=True, text_limit=42)
    output.seniority_signal = compact_text(output.seniority_signal, 80) if output.seniority_signal else None
    output.concerns = compact_items(output.concerns, limit=3, text_limit=60)
    return output


def normalize_company_research_output(output: schemas.CompanyResearchOutput) -> schemas.CompanyResearchOutput:
    output.summary = compact_text(output.summary, 100)
    output.themes = compact_items(output.themes, limit=5, text_limit=58)
    output.coverage_note = compact_text(output.coverage_note, 110)
    return output


def normalize_resume_fit_output(output: schemas.ResumeFitOutput) -> schemas.ResumeFitOutput:
    output.top_company_fit = compact_items(output.top_company_fit, limit=4, text_limit=58)
    output.resume_keywords = compact_items(output.resume_keywords, limit=8, tech_only=True, text_limit=38)
    output.risks_gaps = compact_items(output.risks_gaps, limit=4, text_limit=58)
    return output


def normalize_interview_prep_output(output: schemas.AdvancedInterviewPrepOutput) -> schemas.AdvancedInterviewPrepOutput:
    output.expected_questions = output.expected_questions[:8]
    for question in output.expected_questions:
        question.question = compact_text(question.question, 120)
        question.why_it_matters = compact_text(question.why_it_matters, 90)
    return output

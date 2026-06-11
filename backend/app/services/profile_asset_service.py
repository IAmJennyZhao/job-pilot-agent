import logging
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, status
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, prompts, schemas
from app.config import get_settings
from app.services import profile_service

logger = logging.getLogger(__name__)

MAX_RECENT_JOB_DAYS = 30
INACTIVE_GAP_STATUSES = {
    models.JobStatus.archived,
    models.JobStatus.ghosted,
    models.JobStatus.withdrawn,
    models.JobStatus.rejected,
}
TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]{1,}")
STOP_WORDS = {
    "and",
    "are",
    "build",
    "company",
    "experience",
    "for",
    "from",
    "have",
    "job",
    "role",
    "the",
    "this",
    "with",
    "work",
    "you",
}


def ensure_active_profile(db: Session) -> models.ResumeProfile:
    profile = profile_service.get_active_profile(db)
    if profile:
        return profile
    return profile_service.create_active_profile(db, schemas.ResumeProfileCreate())


def _storage_root() -> Path:
    root = Path(get_settings().asset_storage_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(filename: str | None) -> str:
    raw = Path(filename or "resume.pdf").name
    safe = re.sub(r"[^a-zA-Z0-9._ -]+", "", raw).strip()
    return safe or "resume.pdf"


def _store_pdf(filename: str | None, content: bytes) -> Path:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded PDF was empty")
    safe = _safe_filename(filename)
    if not safe.casefold().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a PDF file")
    directory = _storage_root() / "resume-pdfs"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4()}-{safe}"
    path.write_bytes(content)
    return path


def extract_pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        logger.exception("Could not read uploaded PDF (path=%s)", path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not read PDF: {exc}") from exc
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No readable text was found in the PDF")
    return text.strip()


def parse_resume_text(resume_text: str) -> schemas.ResumeParseOutput:
    from app.services import ai_service

    return ai_service.get_structured_output(
        schemas.ResumeParseOutput,
        prompts.SYSTEM_PROMPT,
        prompts.resume_parse_prompt(resume_text),
    )


def _parse_to_option_values(output: schemas.ResumeParseOutput) -> dict:
    return {
        "candidate_name": output.name,
        "summary": output.summary,
        "target_roles": output.target_roles,
        "target_keywords": output.target_keywords,
        "skills": output.skills,
        "skill_groups": [group.model_dump() for group in output.skill_groups],
        "projects": [item.model_dump() for item in output.projects],
        "experience": [item.model_dump() for item in output.experience],
        "education": [item.model_dump() for item in output.education],
        "certifications": output.certifications,
    }


def import_resume_pdf(
    db: Session,
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> models.ResumeOption:
    profile = ensure_active_profile(db)
    path = _store_pdf(filename, content)
    parsed_text = extract_pdf_text(path)
    output = parse_resume_text(parsed_text)
    title = Path(_safe_filename(filename)).stem or "Imported Resume"
    option = models.ResumeOption(
        resume_profile_id=profile.id,
        title=title,
        source_filename=_safe_filename(filename),
        file_path=str(path),
        content_type=content_type or "application/pdf",
        file_size=len(content),
        parsed_text=parsed_text,
        status=models.ResumeOptionStatus.draft,
        **_parse_to_option_values(output),
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def list_resume_options(db: Session) -> list[models.ResumeOption]:
    profile = ensure_active_profile(db)
    return list(
        db.scalars(
            select(models.ResumeOption)
            .where(models.ResumeOption.resume_profile_id == profile.id)
            .order_by(models.ResumeOption.updated_at.desc())
        ).all()
    )


def get_resume_option(db: Session, option_id: str) -> models.ResumeOption | None:
    return db.get(models.ResumeOption, option_id)


def create_resume_option(db: Session, payload: schemas.ResumeOptionCreate) -> models.ResumeOption:
    profile = ensure_active_profile(db)
    option = models.ResumeOption(resume_profile_id=profile.id, **payload.model_dump())
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def update_resume_option(
    db: Session,
    option: models.ResumeOption,
    payload: schemas.ResumeOptionUpdate,
) -> models.ResumeOption:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(option, key, value)
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def _unique_strings(*lists: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for values in lists:
        for value in values or []:
            text = value.strip()
            key = text.casefold()
            if text and key not in seen:
                output.append(text)
                seen.add(key)
    return output


def _merge_object_lists(existing: list[dict], incoming: list[dict]) -> list[dict]:
    output = list(existing or [])
    seen = {repr(item) for item in output}
    for item in incoming or []:
        key = repr(item)
        if key not in seen:
            output.append(item)
            seen.add(key)
    return output


def _merge_skill_groups(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_category: dict[str, dict] = {}
    for group in [*(existing or []), *(incoming or [])]:
        category = str(group.get("category") or "Skills").strip() or "Skills"
        key = category.casefold()
        current = by_category.setdefault(key, {"category": category, "skills": []})
        current["skills"] = _unique_strings(current["skills"], list(group.get("skills") or []))
    return list(by_category.values())


def merge_resume_option_into_profile(profile: models.ResumeProfile, option: models.ResumeOption) -> None:
    if not profile.name and option.candidate_name:
        profile.name = option.candidate_name
    if not profile.summary and option.summary:
        profile.summary = option.summary
    if not profile.resume_text.strip() and option.parsed_text.strip():
        profile.resume_text = option.parsed_text
    profile.target_roles = _unique_strings(profile.target_roles, option.target_roles)
    profile.skills = _unique_strings(profile.skills, option.skills)
    profile.skill_groups = _merge_skill_groups(profile.skill_groups, option.skill_groups)
    profile.certifications = _unique_strings(profile.certifications, option.certifications)
    profile.experience = _merge_object_lists(profile.experience, option.experience)
    profile.projects = _merge_object_lists(profile.projects, option.projects)
    profile.education = _merge_object_lists(profile.education, option.education)


def confirm_resume_option(
    db: Session,
    option: models.ResumeOption,
    payload: schemas.ResumeOptionConfirmRequest,
) -> models.ResumeOption:
    option.status = models.ResumeOptionStatus.ready
    if payload.merge_into_profile:
        merge_resume_option_into_profile(option.resume_profile, option)
        db.add(option.resume_profile)
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def delete_resume_option(db: Session, option: models.ResumeOption) -> None:
    path = Path(option.file_path) if option.file_path else None
    db.delete(option)
    db.commit()
    if path and path.exists():
        path.unlink()


def resume_option_file_path(option: models.ResumeOption) -> Path:
    if not option.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume PDF not found")
    path = Path(option.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume PDF not found")
    return path


def list_cover_letter_templates(db: Session) -> list[models.CoverLetterTemplate]:
    profile = ensure_active_profile(db)
    return list(
        db.scalars(
            select(models.CoverLetterTemplate)
            .where(models.CoverLetterTemplate.resume_profile_id == profile.id)
            .order_by(models.CoverLetterTemplate.updated_at.desc())
        ).all()
    )


def get_cover_letter_template(db: Session, template_id: str) -> models.CoverLetterTemplate | None:
    return db.get(models.CoverLetterTemplate, template_id)


def create_cover_letter_template(
    db: Session,
    payload: schemas.CoverLetterTemplateCreate,
) -> models.CoverLetterTemplate:
    profile = ensure_active_profile(db)
    template = models.CoverLetterTemplate(resume_profile_id=profile.id, **payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_cover_letter_template(
    db: Session,
    template: models.CoverLetterTemplate,
    payload: schemas.CoverLetterTemplateUpdate,
) -> models.CoverLetterTemplate:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def delete_cover_letter_template(db: Session, template: models.CoverLetterTemplate) -> None:
    db.delete(template)
    db.commit()


def _tokens(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in TOKEN_PATTERN.findall(value.casefold()):
            if token in STOP_WORDS or len(token) < 2:
                continue
            if token not in seen:
                output.append(token)
                seen.add(token)
    return output


def _job_keywords(job: models.Job) -> list[str]:
    values = [
        job.company,
        job.role_title,
        job.category.value,
        job.summary or "",
        *(job.required_skills or []),
    ]
    if job.analysis:
        values.extend(
            [
                *(job.analysis.required_skills or []),
                *(job.analysis.preferred_skills or []),
                *(job.analysis.technologies or []),
                *(job.analysis.resume_keywords or []),
            ]
        )
    return _tokens(values)


def _resume_asset_keywords(option: models.ResumeOption) -> list[str]:
    values = [
        option.title,
        option.summary or "",
        *(option.target_roles or []),
        *(option.target_keywords or []),
        *(option.skills or []),
        *(option.certifications or []),
    ]
    return _tokens(values)


def _cover_asset_keywords(template: models.CoverLetterTemplate) -> list[str]:
    return _tokens(
        [
            template.title,
            template.body,
            template.notes or "",
            *(template.target_roles or []),
            *(template.target_keywords or []),
        ]
    )


def _rank_asset(asset_id: str, title: str, asset_keywords: list[str], job_keywords: list[str]) -> dict:
    job_set = set(job_keywords)
    asset_set = set(asset_keywords)
    matched = sorted(job_set.intersection(asset_set))
    missing = [keyword for keyword in job_keywords if keyword not in asset_set][:10]
    score = int(round((len(matched) / max(len(job_set), 1)) * 100))
    reasons = [f"Matches {len(matched)} of {len(job_set)} job keywords"]
    if matched[:3]:
        reasons.append(f"Strongest overlaps: {', '.join(matched[:3])}")
    return {
        "asset_id": asset_id,
        "title": title,
        "score": min(score, 100),
        "matched_keywords": matched[:12],
        "missing_keywords": missing,
        "reasons": reasons,
    }


def keyword_rankings_for_job(
    db: Session,
    job: models.Job,
) -> tuple[list[dict], list[dict]]:
    keywords = _job_keywords(job)
    resume_rankings = [
        _rank_asset(option.id, option.title, _resume_asset_keywords(option), keywords)
        for option in list_resume_options(db)
        if option.status == models.ResumeOptionStatus.ready
    ]
    cover_rankings = [
        _rank_asset(template.id, template.title, _cover_asset_keywords(template), keywords)
        for template in list_cover_letter_templates(db)
    ]
    return (
        sorted(resume_rankings, key=lambda item: item["score"], reverse=True),
        sorted(cover_rankings, key=lambda item: item["score"], reverse=True),
    )


def create_keyword_recommendation_snapshot(
    db: Session,
    job: models.Job,
) -> models.AssetRecommendationSnapshot:
    resume_rankings, cover_rankings = keyword_rankings_for_job(db, job)
    snapshot = models.AssetRecommendationSnapshot(
        job_id=job.id,
        source=models.RecommendationSource.keyword,
        resume_rankings=resume_rankings,
        cover_letter_rankings=cover_rankings,
        errors=[],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _ai_payload_resume(option: models.ResumeOption) -> dict:
    return {
        "asset_id": option.id,
        "title": option.title,
        "target_roles": option.target_roles,
        "target_keywords": option.target_keywords,
        "summary": option.summary,
        "skills": option.skills,
    }


def _ai_payload_cover(template: models.CoverLetterTemplate) -> dict:
    return {
        "asset_id": template.id,
        "title": template.title,
        "target_roles": template.target_roles,
        "target_keywords": template.target_keywords,
        "body_preview": template.body[:1200],
    }


def create_ai_recommendation_snapshot(
    db: Session,
    job: models.Job,
) -> models.AssetRecommendationSnapshot:
    from app.services import ai_service

    resumes = [option for option in list_resume_options(db) if option.status == models.ResumeOptionStatus.ready]
    templates = list_cover_letter_templates(db)
    output = ai_service.get_structured_output(
        schemas.AIAssetRankingOutput,
        prompts.SYSTEM_PROMPT,
        prompts.asset_ranking_prompt(
            job.company,
            job.role_title,
            job.source_content or job.summary or "",
            [_ai_payload_resume(option) for option in resumes],
            [_ai_payload_cover(template) for template in templates],
        ),
    )
    resume_ids = {option.id for option in resumes}
    template_ids = {template.id for template in templates}
    snapshot = models.AssetRecommendationSnapshot(
        job_id=job.id,
        source=models.RecommendationSource.ai,
        resume_rankings=[
            item.model_dump()
            for item in output.resume_rankings
            if item.asset_id in resume_ids
        ],
        cover_letter_rankings=[
            item.model_dump()
            for item in output.cover_letter_rankings
            if item.asset_id in template_ids
        ],
        errors=[],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def latest_asset_recommendation(
    db: Session,
    job_id: str,
) -> models.AssetRecommendationSnapshot | None:
    return db.scalars(
        select(models.AssetRecommendationSnapshot)
        .where(models.AssetRecommendationSnapshot.job_id == job_id)
        .order_by(models.AssetRecommendationSnapshot.created_at.desc())
        .limit(1)
    ).first()


def best_resume_option_for_job(db: Session, job: models.Job) -> models.ResumeOption | None:
    if job.selected_resume_option_id:
        selected = db.get(models.ResumeOption, job.selected_resume_option_id)
        if selected:
            return selected
    resume_rankings, _ = keyword_rankings_for_job(db, job)
    if not resume_rankings:
        return None
    return db.get(models.ResumeOption, resume_rankings[0]["asset_id"])


def _latest_movement_or_update(job: models.Job) -> datetime:
    timestamps = [job.updated_at, job.created_at]
    timestamps.extend(event.changed_at for event in job.status_events)
    values = [value for value in timestamps if value is not None]
    return max(values)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def generate_coverage_gaps(db: Session) -> schemas.CoverageGapResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_RECENT_JOB_DAYS)
    jobs = [
        job
        for job in db.scalars(select(models.Job).order_by(models.Job.updated_at.desc())).all()
        if job.status not in INACTIVE_GAP_STATUSES and _as_utc(_latest_movement_or_update(job)) >= cutoff
    ]
    resume_options = [option for option in list_resume_options(db) if option.status == models.ResumeOptionStatus.ready]
    templates = list_cover_letter_templates(db)
    gaps: list[schemas.CoverageGap] = []

    by_category: dict[str, list[models.Job]] = {}
    for job in jobs:
        by_category.setdefault(job.category.value, []).append(job)

    for category, category_jobs in by_category.items():
        keywords = _tokens(
            [
                category,
                *[job.role_title for job in category_jobs],
                *[skill for job in category_jobs for skill in (job.required_skills or [])],
            ]
        )
        if not keywords:
            continue
        best_resume = max(
            (
                _rank_asset(option.id, option.title, _resume_asset_keywords(option), keywords)["score"]
                for option in resume_options
            ),
            default=0,
        )
        best_cover = max(
            (
                _rank_asset(template.id, template.title, _cover_asset_keywords(template), keywords)["score"]
                for template in templates
            ),
            default=0,
        )
        affected = [job.id for job in category_jobs]
        if best_resume < 45:
            gaps.append(
                schemas.CoverageGap(
                    asset_type="resume",
                    title=f"{category} resume option",
                    rationale="Recent jobs in this category do not strongly match an existing ready resume option.",
                    affected_job_ids=affected,
                    target_keywords=keywords[:10],
                )
            )
        if best_cover < 45:
            gaps.append(
                schemas.CoverageGap(
                    asset_type="cover_letter",
                    title=f"{category} cover letter template",
                    rationale="Recent jobs in this category do not strongly match an existing cover letter template.",
                    affected_job_ids=affected,
                    target_keywords=keywords[:10],
                )
            )

    return schemas.CoverageGapResponse(
        generated_at=datetime.now(timezone.utc),
        jobs_considered=len(jobs),
        gaps=gaps,
    )


def clear_storage_for_tests() -> None:
    root = _storage_root()
    if root.exists():
        shutil.rmtree(root)

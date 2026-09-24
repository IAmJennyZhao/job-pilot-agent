from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.services import job_service

SOURCE_PRECEDENCE = {
    models.SkillGapSource.resume_match: 0,
    models.SkillGapSource.interview_feedback: 1,
    models.SkillGapSource.job_analysis: 2,
}


def _priority_for_count(count: int) -> models.Priority:
    if count >= 3:
        return models.Priority.high
    if count == 2:
        return models.Priority.medium
    return models.Priority.low


def _source_rank(source_value: str) -> int:
    try:
        return SOURCE_PRECEDENCE[models.SkillGapSource(source_value)]
    except ValueError:
        return 99


def upsert_skill_gaps(
    db: Session,
    profile_id: str,
    skills: Iterable[str],
    source: models.SkillGapSource,
    suggested_action_prefix: str,
) -> None:
    # Dedupe case-insensitively up front: the session has autoflush disabled, so a
    # repeated skill in one batch would not see the pending row and would duplicate it.
    normalized: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        cleaned = skill.strip() if skill else ""
        if not cleaned or cleaned.casefold() in seen:
            continue
        seen.add(cleaned.casefold())
        normalized.append(cleaned)
    for skill in normalized:
        existing = db.scalars(
            select(models.SkillGap).where(
                models.SkillGap.resume_profile_id == profile_id,
                models.SkillGap.skill_name.ilike(skill),
            )
        ).first()
        if existing:
            existing.count += 1
            existing.priority = _priority_for_count(existing.count)
            current_best_rank = min(
                (_source_rank(value) for value in existing.sources),
                default=99,
            )
            if SOURCE_PRECEDENCE[source] < current_best_rank:
                existing.suggested_action = f"{suggested_action_prefix}: {existing.skill_name}"
            if source.value not in existing.sources:
                # Reassign instead of mutating so SQLAlchemy detects the JSON change.
                existing.sources = sorted({*existing.sources, source.value}, key=_source_rank)
            db.add(existing)
            continue
        db.add(
            models.SkillGap(
                resume_profile_id=profile_id,
                skill_name=skill,
                sources=[source.value],
                count=1,
                priority=models.Priority.low,
                user_level=models.UserLevel.unknown,
                suggested_action=f"{suggested_action_prefix}: {skill}",
            )
        )
    db.commit()


def list_skill_gaps(db: Session, profile_id: str | None = None) -> list[schemas.SkillGapRead]:
    statement = select(models.SkillGap)
    if profile_id:
        statement = statement.where(models.SkillGap.resume_profile_id == profile_id)
    gaps = list(db.scalars(statement).all())
    jobs = list(db.scalars(select(models.Job).where(models.Job.status.in_(job_service.OPEN_OPPORTUNITY_STATUSES))))
    latest_suggestions = {}
    for suggestion in db.scalars(select(models.ResumeSuggestion).order_by(models.ResumeSuggestion.created_at.desc())):
        latest_suggestions.setdefault((suggestion.resume_profile_id, suggestion.job_id), suggestion)
    evidence = {}
    for owner in {gap.resume_profile_id for gap in gaps}:
        for job in jobs:
            suggestion = latest_suggestions.get((owner, job.id))
            skills = ([*suggestion.missing_skills, *suggestion.weak_skills] if suggestion else
                      [*job.analysis.required_skills, *job.analysis.technologies] if job.analysis else job.required_skills)
            for skill in skills:
                evidence.setdefault((owner, skill.strip().casefold()), set()).add(job.id)
    rows = []
    for gap in gaps:
        count = len(evidence.get((gap.resume_profile_id, gap.skill_name.strip().casefold()), set()))
        rows.append(schemas.SkillGapRead.model_validate(gap).model_copy(update={
            "active_job_count": count, "priority": _priority_for_count(count),
        }))
    return sorted(rows, key=lambda row: (-row.active_job_count, row.skill_name.casefold()))

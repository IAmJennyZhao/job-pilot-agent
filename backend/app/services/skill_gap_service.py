from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def _priority_for_count(count: int) -> models.Priority:
    if count >= 3:
        return models.Priority.high
    if count == 2:
        return models.Priority.medium
    return models.Priority.low


def upsert_skill_gaps(
    db: Session,
    profile_id: str,
    skills: Iterable[str],
    source: models.SkillGapSource,
    suggested_action_prefix: str,
) -> None:
    normalized = [skill.strip() for skill in skills if skill and skill.strip()]
    for skill in normalized:
        existing = db.scalars(
            select(models.SkillGap).where(
                models.SkillGap.resume_profile_id == profile_id,
                models.SkillGap.source == source,
                models.SkillGap.skill_name.ilike(skill),
            )
        ).first()
        if existing:
            existing.count += 1
            existing.priority = _priority_for_count(existing.count)
            db.add(existing)
            continue
        db.add(
            models.SkillGap(
                resume_profile_id=profile_id,
                skill_name=skill,
                source=source,
                count=1,
                priority=models.Priority.low,
                user_level=models.UserLevel.unknown,
                suggested_action=f"{suggested_action_prefix}: {skill}",
            )
        )
    db.commit()


def list_skill_gaps(db: Session, profile_id: str | None = None) -> list[models.SkillGap]:
    statement = select(models.SkillGap).order_by(
        models.SkillGap.priority.desc(),
        models.SkillGap.count.desc(),
        models.SkillGap.updated_at.desc(),
    )
    if profile_id:
        statement = statement.where(models.SkillGap.resume_profile_id == profile_id)
    return list(db.scalars(statement).all())


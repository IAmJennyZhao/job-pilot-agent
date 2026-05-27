from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


def get_active_profile(db: Session) -> models.ResumeProfile | None:
    return db.scalars(
        select(models.ResumeProfile)
        .where(models.ResumeProfile.is_active.is_(True))
        .order_by(models.ResumeProfile.updated_at.desc())
        .limit(1)
    ).first()


def create_active_profile(
    db: Session,
    payload: schemas.ResumeProfileCreate,
) -> models.ResumeProfile:
    for profile in db.scalars(select(models.ResumeProfile)).all():
        profile.is_active = False
    profile = models.ResumeProfile(**payload.model_dump(), is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(
    db: Session,
    profile: models.ResumeProfile,
    payload: schemas.ResumeProfileUpdate,
) -> models.ResumeProfile:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


def save_job(db: Session, payload: schemas.JobCreate) -> models.Job:
    job = models.Job(
        company=payload.company,
        role_title=payload.role_title,
        job_url=str(payload.job_url) if payload.job_url else None,
        job_description=payload.job_description,
        notes=payload.notes,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(db: Session, include_archived: bool = False) -> list[models.Job]:
    statement = select(models.Job).order_by(models.Job.updated_at.desc())
    if not include_archived:
        statement = statement.where(models.Job.status != models.JobStatus.archived)
    return list(db.scalars(statement).all())


def get_job(db: Session, job_id: str) -> models.Job | None:
    return db.get(models.Job, job_id)


def update_job(db: Session, job: models.Job, payload: schemas.JobUpdate) -> models.Job:
    values = payload.model_dump(exclude_unset=True)
    if "job_url" in values and values["job_url"] is not None:
        values["job_url"] = str(values["job_url"])
    for key, value in values.items():
        setattr(job, key, value)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_application_status(
    db: Session,
    job: models.Job,
    status: models.JobStatus,
    notes: str | None = None,
) -> models.Job:
    job.status = status
    if notes is not None:
        job.notes = notes
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def archive_job(db: Session, job: models.Job) -> models.Job:
    return update_application_status(db, job, models.JobStatus.archived)


def latest_resume_suggestion(
    db: Session,
    job_id: str,
) -> models.ResumeSuggestion | None:
    return db.scalars(
        select(models.ResumeSuggestion)
        .where(models.ResumeSuggestion.job_id == job_id)
        .order_by(models.ResumeSuggestion.created_at.desc())
        .limit(1)
    ).first()


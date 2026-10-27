from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import job_intake_service, job_service
from app.intake_schemas import IntakeReview, IntakeSave
from app.services import intake_preferences, intake_review_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/intake/evaluate")
def evaluate_intake(payload: IntakeReview, db: Session = Depends(get_db)):
    return intake_preferences.evaluate(db, payload)


@router.post("/intake/save", response_model=schemas.JobDetail)
def save_intake(payload: IntakeSave, db: Session = Depends(get_db)):
    return intake_review_service.save(db, payload)


@router.get("/{job_id}/intake")
def intake_preparation(job_id: str, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return intake_review_service.preparation(db, job)


@router.post("/extract-preview", response_model=schemas.JobExtractPreview)
def extract_job_preview(payload: schemas.JobExtractPreviewRequest, db: Session = Depends(get_db)):
    return job_intake_service.extract_preview(db, payload)


@router.post("", response_model=schemas.JobDetail, status_code=status.HTTP_201_CREATED)
def create_job(payload: schemas.JobCreate, db: Session = Depends(get_db)):
    return job_service.save_job(db, payload)


@router.get("", response_model=list[schemas.JobListItem])
def get_jobs(
    include_archived: bool = False,
    search: str | None = None,
    status_filter: models.JobStatus | None = None,
    category: models.JobCategory | None = None,
    health_filter: str | None = None,
    funnel_stage: str | None = None,
    funnel_from: str | None = None,
    saved_since: date | None = None,
    funnel_stopped: bool = False,
    db: Session = Depends(get_db),
):
    try:
        return job_service.list_job_items(
            db,
            include_archived=include_archived,
            search=search,
            status=status_filter,
            category=category,
            health_filter=health_filter,
            funnel_stage=funnel_stage,
            funnel_from=funnel_from,
            saved_since=saved_since,
            funnel_stopped=funnel_stopped,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=schemas.JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return schemas.JobDetail.model_validate(job).model_copy(
        update={
            "latest_resume_suggestion": job_service.latest_resume_suggestion(db, job_id),
            "latest_advanced_analysis": job_service.latest_advanced_analysis(db, job_id),
            "latest_asset_recommendation": job_service.latest_asset_recommendation(db, job_id),
        }
    )


@router.patch("/{job_id}", response_model=schemas.JobRead)
def update_job(job_id: str, payload: schemas.JobUpdate, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    try:
        return job_service.update_job(db, job, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{job_id}/status-events", response_model=schemas.JobDetail)
def create_status_event(
    job_id: str,
    payload: schemas.JobStatusEventCreate,
    db: Session = Depends(get_db),
):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_service.create_status_event(db, job, payload)


@router.patch("/{job_id}/status-events/{event_id}", response_model=schemas.JobDetail)
def update_status_event(
    job_id: str,
    event_id: str,
    payload: schemas.JobStatusEventUpdate,
    db: Session = Depends(get_db),
):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    try:
        return job_service.update_status_event(db, job, event_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{job_id}/status-events/{event_id}", response_model=schemas.JobDetail)
def delete_status_event(
    job_id: str,
    event_id: str,
    db: Session = Depends(get_db),
):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    try:
        return job_service.delete_status_event(db, job, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{job_id}", response_model=schemas.JobRead)
def archive_job(job_id: str, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_service.archive_job(db, job)

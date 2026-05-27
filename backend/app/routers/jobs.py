from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=schemas.JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: schemas.JobCreate, db: Session = Depends(get_db)):
    return job_service.save_job(db, payload)


@router.get("", response_model=list[schemas.JobRead])
def get_jobs(include_archived: bool = False, db: Session = Depends(get_db)):
    return job_service.list_jobs(db, include_archived=include_archived)


@router.get("/{job_id}", response_model=schemas.JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return schemas.JobDetail.model_validate(job).model_copy(
        update={"latest_resume_suggestion": job_service.latest_resume_suggestion(db, job_id)}
    )


@router.patch("/{job_id}", response_model=schemas.JobRead)
def update_job(job_id: str, payload: schemas.JobUpdate, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_service.update_job(db, job, payload)


@router.delete("/{job_id}", response_model=schemas.JobRead)
def archive_job(job_id: str, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_service.archive_job(db, job)


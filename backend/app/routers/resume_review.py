from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.review_schemas import SaveResumeEdit, RestoreResumeRevision, ReviewResume
from app.services import resume_review as service

router = APIRouter(prefix="/api/tailoring/resumes", tags=["resume-review"])


@router.get("/{baseline_id}")
def get_resume_review(baseline_id: str, revision_id: str | None = None, db: Session = Depends(get_db)):
    return service.view(db, baseline_id, revision_id)


@router.post("/{baseline_id}/revisions")
def save_revision(baseline_id: str, payload: SaveResumeEdit, response: Response, db: Session = Depends(get_db)):
    revision_id, created = service.save(db, baseline_id, payload)
    response.status_code = 201 if created else 200
    return service.view(db, baseline_id, revision_id)


@router.post("/{baseline_id}/restore")
def restore_revision(baseline_id: str, payload: RestoreResumeRevision, response: Response, db: Session = Depends(get_db)):
    revision_id, created = service.save(db, baseline_id, payload, restore=True)
    response.status_code = 201 if created else 200
    return service.view(db, baseline_id, revision_id)


@router.post("/{baseline_id}/review")
def mark_reviewed(baseline_id: str, payload: ReviewResume, response: Response, db: Session = Depends(get_db)):
    response.status_code = 201 if service.approve(db, baseline_id, payload) else 200
    return service.view(db, baseline_id, payload.revision_id)

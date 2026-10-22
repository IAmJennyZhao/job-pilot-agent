from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.letter_schemas import GenerateLetter, SaveLetterEdit, CheckLetter
from app.review_schemas import RestoreResumeRevision, ReviewResume
from app.routers.resume_generation import job_or_404
from app.services import cover_letters as service, resume_generation as runs, resume_review as review

router = APIRouter(prefix="/api", tags=["cover-letters"])


@router.get("/jobs/{job_id}/cover-letters")
def workspace(job_id: str, db: Session = Depends(get_db)):
    result = runs.workspace(db, job_or_404(db, job_id), "cover_letter")
    result["templates"] = [{"id": t.id, "title": t.title} for t in db.scalars(select(models.CoverLetterTemplate)
        .where(models.CoverLetterTemplate.resume_profile_id == runs.profile_id(db)).order_by(models.CoverLetterTemplate.title))]
    return result


def generate(db, job, payload, response, parent_id=None):
    run_id, created = runs.start(db, job, payload, parent_id, "cover_letter")
    engine = db.get_bind()
    db.close()
    if created:
        service.execute(engine, run_id)
    response.status_code = 201 if created else 200
    return runs.run_view(db, service.scoped(db, run_id))


@router.post("/jobs/{job_id}/cover-letters")
def create(job_id: str, payload: GenerateLetter, response: Response, db: Session = Depends(get_db)):
    return generate(db, job_or_404(db, job_id), payload, response)


@router.get("/cover-letters/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    runs.expire_runs(db)
    return runs.run_view(db, service.scoped(db, run_id))


@router.post("/cover-letters/runs/{run_id}/retry")
def retry(run_id: str, payload: GenerateLetter, response: Response, db: Session = Depends(get_db)):
    parent = service.scoped(db, run_id)
    return generate(db, job_or_404(db, parent.job_id), payload, response, parent.id)


@router.get("/cover-letters/{baseline_id}")
def get_review(baseline_id: str, revision_id: str | None = None, db: Session = Depends(get_db)):
    return service.view(db, baseline_id, revision_id)


@router.post("/cover-letters/{baseline_id}/revisions")
def save(baseline_id: str, payload: SaveLetterEdit, response: Response, db: Session = Depends(get_db)):
    service.baseline(db, baseline_id)
    revision_id, created = review.save(db, baseline_id, payload)
    response.status_code = 201 if created else 200
    return service.view(db, baseline_id, revision_id)


@router.post("/cover-letters/{baseline_id}/restore")
def restore(baseline_id: str, payload: RestoreResumeRevision, response: Response, db: Session = Depends(get_db)):
    service.baseline(db, baseline_id)
    revision_id, created = review.save(db, baseline_id, payload, restore=True)
    response.status_code = 201 if created else 200
    return service.view(db, baseline_id, revision_id)


@router.post("/cover-letters/{baseline_id}/check")
def check(baseline_id: str, payload: CheckLetter, db: Session = Depends(get_db)):
    service.check(db, baseline_id, payload)
    return service.view(db, baseline_id, payload.expected_revision_id)


@router.post("/cover-letters/{baseline_id}/review")
def approve(baseline_id: str, payload: ReviewResume, response: Response, db: Session = Depends(get_db)):
    service.baseline(db, baseline_id)
    response.status_code = 201 if review.approve(db, baseline_id, payload) else 200
    return service.view(db, baseline_id, payload.revision_id)


@router.get("/cover-letters/{baseline_id}/revisions/{revision_id}/download/{variant}/{format}")
def download(baseline_id: str, revision_id: str, variant: int, format: str, db: Session = Depends(get_db)):
    data = service.download(db, baseline_id, revision_id, variant, format)
    return Response(data, media_type="text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="cover-letter-{revision_id[:8]}-{variant+1}.{format}"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

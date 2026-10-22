from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.generation_schemas import GenerateResume
from app.services import job_service, resume_generation as service

router = APIRouter(prefix="/api", tags=["resume-generation"])


def job_or_404(db, job_id):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}/tailoring")
def get_workspace(job_id: str, db: Session = Depends(get_db)):
    return service.workspace(db, job_or_404(db, job_id))


@router.get("/tailoring/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    service.expire_runs(db)
    run = service.scoped_run(db, run_id)
    if run.snapshot.get("document_kind", "resume") != "resume":
        raise HTTPException(404, "Resume run not found.")
    return service.run_view(db, run)


def generate(db, job, payload, response, parent_id=None):
    run_id, created = service.start(db, job, payload, parent_id)
    engine = db.get_bind()
    db.close()  # No request-scoped transaction survives a provider call.
    if created:
        service.execute(engine, run_id)
    response.status_code = 201 if created else 200
    return service.run_view(db, service.scoped_run(db, run_id))


@router.post("/jobs/{job_id}/tailoring/resume")
def generate_resume(job_id: str, payload: GenerateResume, response: Response, db: Session = Depends(get_db)):
    return generate(db, job_or_404(db, job_id), payload, response)


@router.post("/tailoring/runs/{run_id}/retry")
def retry_resume(run_id: str, payload: GenerateResume, response: Response, db: Session = Depends(get_db)):
    parent = service.scoped_run(db, run_id)
    return generate(db, job_or_404(db, parent.job_id), payload, response, parent.id)

from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.review_schemas import SaveResumeEdit, RestoreResumeRevision, ReviewResume, ApproveResumeExport
from app.services import resume_review as service
from app.services import resume_rendering as rendering

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


@router.get("/{baseline_id}/renders")
def list_renders(baseline_id: str, revision_id: str, db: Session = Depends(get_db)):
    return rendering.history(db, baseline_id, revision_id)


@router.post("/{baseline_id}/renders")
def render_resume(baseline_id: str, payload: ReviewResume, db: Session = Depends(get_db)):
    return rendering.create(db, baseline_id, payload)


@router.post("/{baseline_id}/renders/{render_id}/preview")
def preview_render(baseline_id: str, render_id: str, db: Session = Depends(get_db)):
    return rendering.preview(db, baseline_id, render_id)


@router.post("/{baseline_id}/renders/{render_id}/approve")
def approve_export(baseline_id: str, render_id: str, payload: ApproveResumeExport, db: Session = Depends(get_db)):
    if not payload.layout_reviewed:
        raise HTTPException(422, "Inspect the PDF layout before final approval.")
    return rendering.approve(db, baseline_id, render_id, payload)


@router.get("/{baseline_id}/renders/{render_id}/download/{format}")
def download_export(baseline_id: str, render_id: str, format: str, db: Session = Depends(get_db)):
    data, checksum = rendering.download(db, baseline_id, render_id, format)
    return Response(data, media_type={"pdf": "application/pdf", "tex": "application/x-tex", "txt": "text/plain; charset=utf-8"}[format],
        headers={"Content-Disposition": f'attachment; filename="resume-{render_id[:8]}.{format}"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "ETag": f'"{checksum}"'})


@router.delete("/{baseline_id}/renders/{render_id}", status_code=204)
def remove_draft_preview(baseline_id: str, render_id: str, db: Session = Depends(get_db)):
    rendering.delete_draft(db, baseline_id, render_id)

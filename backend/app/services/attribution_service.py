import hashlib
import json
from urllib.parse import urlsplit

from sqlalchemy.orm import Session
from app import models


def capture(db: Session, job: models.Job) -> None:
    """Freeze reporting labels when progression beyond Saved is first recorded."""
    from app.services.job_service import furthest_stage_rank
    if furthest_stage_rank(job) < 1 or db.get(models.ApplicationAttribution, job.id):
        return
    option = db.get(models.ResumeOption, job.selected_resume_option_id) if job.selected_resume_option_id else None
    version = "No resume selected"
    if option:
        content = {column.name: getattr(option, column.name) for column in option.__table__.columns
                   if column.name not in {"file_path", "created_at", "updated_at", "status"}}
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:8]
        version = f"{option.title} · {digest}"
    source = (urlsplit(job.source_url or "").hostname or "Unknown / manual").removeprefix("www.")
    db.add(models.ApplicationAttribution(job_id=job.id, source=source, category=job.category.value, resume_version=version))

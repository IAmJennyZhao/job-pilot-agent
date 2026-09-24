import csv
import io
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.services import backup_service

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/backup")
def backup(db: Session = Depends(get_db)):
    return Response(backup_service.export_archive(db), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="job-pilot-backup.json"'})


@router.get("/jobs.csv")
def export_jobs(db: Session = Depends(get_db)):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["Company", "Role", "Category", "Status", "Source URL", "Notes", "Next action", "Due date", "Action completed"])
    actions = {action.job_id: action for action in db.scalars(select(models.JobAction)).all()}
    def safe(value):
        text = str(value or "")
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text
    for job in db.scalars(select(models.Job).order_by(models.Job.created_at, models.Job.id)).all():
        action = actions.get(job.id)
        writer.writerow([safe(value) for value in [job.company, job.role_title, job.category.value, job.status.value, job.source_url, job.notes,
            action.title if action else "", action.due_date if action else "", action.completed_at.isoformat() if action and action.completed_at else ""]])
    return Response(buffer.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="job-pilot-jobs.csv"'})


async def read_archive(file: UploadFile):
    content = await file.read(backup_service.MAX_BYTES + 1)
    await file.close()
    return content


@router.post("/restore-preview")
async def restore_preview(file: UploadFile = File(...)):
    return backup_service.preview(await read_archive(file))


@router.post("/restore")
async def restore(file: UploadFile = File(...), sha256: str = Form(...), confirmation: str = Form(...), db: Session = Depends(get_db)):
    if confirmation != "RESTORE":
        raise HTTPException(400, "Type RESTORE to confirm replacing all saved data")
    return backup_service.restore(db, await read_archive(file), sha256)


@router.get("/recovery/{recovery_id}")
def recovery(recovery_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", recovery_id):
        raise HTTPException(404, "Recovery backup not found")
    path = Path(get_settings().asset_storage_dir) / "backups" / f"{recovery_id}.json"
    if not path.is_file():
        raise HTTPException(404, "Recovery backup not found")
    return FileResponse(path, media_type="application/json", filename="job-pilot-before-restore.json")


@router.get("/recoveries")
def recoveries():
    root = Path(get_settings().asset_storage_dir) / "backups"
    return sorted([{"id": path.stem, "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), "bytes": path.stat().st_size}
        for path in root.glob("*.json") if re.fullmatch(r"[a-f0-9]{32}", path.stem)], key=lambda item: item["created_at"], reverse=True)

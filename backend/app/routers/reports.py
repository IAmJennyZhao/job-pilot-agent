from collections import defaultdict
from datetime import date, datetime, time, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.database import get_db
from app.services.job_service import furthest_stage_rank

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/outcomes")
def outcomes(saved_since: date | None = None, db: Session = Depends(get_db)):
    statement = select(models.Job).options(selectinload(models.Job.links), selectinload(models.Job.status_events))
    if saved_since:
        statement = statement.where(models.Job.created_at >= datetime.combine(saved_since, time.min, tzinfo=timezone.utc))
    jobs = db.scalars(statement).all()
    attributions = {row.job_id: row for row in db.scalars(select(models.ApplicationAttribution)).all()}
    groups = {"source": defaultdict(list), "category": defaultdict(list), "resume": defaultdict(list)}
    for job in jobs:
        attribution = attributions.get(job.id)
        source = urlsplit(job.source_url or "").hostname or "Unknown / manual"
        groups["source"][attribution.source if attribution else source.removeprefix("www.")].append(job)
        groups["category"][attribution.category if attribution else job.category.value].append(job)
        groups["resume"][attribution.resume_version if attribution else "Not recorded at application"].append(job)
    result = {}
    for dimension, grouped in groups.items():
        rows = []
        for label, members in grouped.items():
            ranks = [furthest_stage_rank(job) for job in members]
            applied = sum(rank >= 1 for rank in ranks)
            interviews = sum(rank >= 2 for rank in ranks)
            offers = sum(rank >= 5 for rank in ranks)
            rows.append({"label": label, "saved": len(members), "applied": applied, "interviews": interviews, "offers": offers,
                         "interview_rate": round(100 * interviews / applied, 1) if applied else None,
                         "offer_rate": round(100 * offers / applied, 1) if applied else None,
                         "job_ids": [job.id for job in members]})
        result[dimension] = sorted(rows, key=lambda row: (-row["applied"], row["label"]))
    return {"groups": result, "total_jobs": len(jobs)}

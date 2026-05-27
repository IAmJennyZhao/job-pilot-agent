from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import skill_gap_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    jobs = list(db.scalars(select(models.Job)).all())
    active_jobs = [job for job in jobs if job.status != models.JobStatus.archived]
    archived_jobs = len(jobs) - len(active_jobs)
    status_counts = Counter(job.status.value for job in jobs)
    by_status = {
        status.value: status_counts.get(status.value, 0)
        for status in models.JobStatus
    }
    recent_interviews = list(
        db.scalars(
            select(models.InterviewSession)
            .order_by(models.InterviewSession.updated_at.desc())
            .limit(5)
        ).all()
    )
    top_skill_gaps = skill_gap_service.list_skill_gaps(db)[:5]
    needs_resume_tailoring = sum(
        1
        for job in active_jobs
        if job.status == models.JobStatus.saved or job.fit_score is None
    )
    interviewing = sum(
        1
        for job in active_jobs
        if job.status
        in {
            models.JobStatus.recruiter_screen,
            models.JobStatus.tech_screen,
            models.JobStatus.final_interview,
        }
    )

    if needs_resume_tailoring:
        next_action = "Tailor a resume for a saved job."
    elif interviewing:
        next_action = "Practice interview questions for an active interview."
    elif top_skill_gaps:
        next_action = f"Study {top_skill_gaps[0].skill_name}."
    else:
        next_action = "Add a job description to start tracking your search."

    return schemas.DashboardSummary(
        total_jobs=len(active_jobs),
        archived_jobs=archived_jobs,
        by_status=by_status,
        needs_resume_tailoring=needs_resume_tailoring,
        interviewing=interviewing,
        top_skill_gaps=top_skill_gaps,
        recent_interviews=recent_interviews,
        next_recommended_action=next_action,
    )

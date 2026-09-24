from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app import models, schemas
from app.database import get_db
from app.services import skill_gap_service, job_service

router = APIRouter(prefix="/api/skill-gaps", tags=["skill gaps"])


@router.get("", response_model=list[schemas.SkillGapRead])
def get_skill_gaps(profile_id: str | None = None, db: Session = Depends(get_db)):
    return skill_gap_service.list_skill_gaps(db, profile_id)


@router.get("/{skill_gap_id}/evidence")
def get_skill_evidence(skill_gap_id: str, db: Session = Depends(get_db)):
    gap = db.get(models.SkillGap, skill_gap_id)
    if not gap:
        raise HTTPException(status_code=404, detail="Skill gap not found")
    key = gap.skill_name.strip().casefold()
    matches = lambda values: any(str(value).strip().casefold() == key for value in values)
    evidence = {}
    for suggestion in db.scalars(select(models.ResumeSuggestion).where(models.ResumeSuggestion.resume_profile_id == gap.resume_profile_id)):
        if matches([*suggestion.missing_skills, *suggestion.weak_skills]):
            job = db.get(models.Job, suggestion.job_id)
            if job:
                evidence[(job.id, "Resume match")] = {"label": f"{job.company} — {job.role_title}", "href": f"/jobs/{job.id}", "source": "Resume match"}
    for analysis in db.scalars(select(models.JobAnalysis)):
        if matches([*analysis.required_skills, *analysis.technologies]):
            job = analysis.job
            evidence[(job.id, "Job analysis")] = {"label": f"{job.company} — {job.role_title}", "href": f"/jobs/{job.id}", "source": "Job analysis"}
    for session in db.scalars(select(models.InterviewSession).where(models.InterviewSession.resume_profile_id == gap.resume_profile_id)):
        if any(matches((message.feedback or {}).get("missing_skill_names", [])) for message in session.messages):
            evidence[(session.id, "Interview feedback")] = {"label": session.title or session.target_role or "Interview practice", "href": f"/interview/sessions/{session.id}", "source": "Interview feedback"}
    # Include the current open-job evidence used by active_job_count, including
    # manually captured requirements without an AI analysis record.
    for job in db.scalars(select(models.Job).where(models.Job.status.in_(job_service.OPEN_OPPORTUNITY_STATUSES))):
        suggestion = db.scalars(select(models.ResumeSuggestion).where(models.ResumeSuggestion.job_id == job.id, models.ResumeSuggestion.resume_profile_id == gap.resume_profile_id).order_by(models.ResumeSuggestion.created_at.desc())).first()
        values = ([*suggestion.missing_skills, *suggestion.weak_skills] if suggestion else
                  [*job.analysis.required_skills, *job.analysis.technologies] if job.analysis else job.required_skills)
        if matches(values) and not any(identity[0] == job.id for identity in evidence):
            evidence[(job.id, "Current job requirements")] = {"label": f"{job.company} — {job.role_title}", "href": f"/jobs/{job.id}", "source": "Current job requirements"}
    return list(evidence.values())


@router.patch("/{skill_gap_id}", response_model=schemas.SkillGapRead)
def update_skill_gap(
    skill_gap_id: str,
    payload: schemas.SkillGapUpdate,
    db: Session = Depends(get_db),
):
    gap = db.get(models.SkillGap, skill_gap_id)
    if not gap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill gap not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(gap, key, value)
    db.add(gap)
    db.commit()
    db.refresh(gap)
    return next(row for row in skill_gap_service.list_skill_gaps(db, gap.resume_profile_id) if row.id == gap.id)


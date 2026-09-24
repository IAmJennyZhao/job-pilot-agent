from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import profile_service

router = APIRouter(prefix="/api/study-plans", tags=["study plans"])


def _get_plan_or_404(db: Session, plan_id: str) -> models.SavedStudyPlan:
    plan = db.get(models.SavedStudyPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan not found")
    return plan


@router.get("", response_model=list[schemas.SavedStudyPlanRead])
def list_study_plans(profile_id: str | None = None, db: Session = Depends(get_db)):
    statement = select(models.SavedStudyPlan).order_by(models.SavedStudyPlan.created_at.desc())
    if profile_id:
        statement = statement.where(models.SavedStudyPlan.resume_profile_id == profile_id)
    return list(db.scalars(statement).all())


@router.post("", response_model=schemas.SavedStudyPlanRead, status_code=status.HTTP_201_CREATED)
def save_study_plan(payload: schemas.SavedStudyPlanCreate, db: Session = Depends(get_db)):
    profile = (
        db.get(models.ResumeProfile, payload.resume_profile_id)
        if payload.resume_profile_id
        else profile_service.get_active_profile(db)
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")
    plan = models.SavedStudyPlan(
        resume_profile_id=profile.id,
        title=payload.title,
        timeframe=payload.timeframe,
        time_budget_hours=payload.time_budget_hours,
        time_budget_unit=payload.time_budget_unit,
        mode=payload.mode,
        focus_skills=payload.focus_skills,
        plan=payload.plan.model_dump(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=schemas.SavedStudyPlanRead)
def rename_study_plan(plan_id: str, payload: schemas.SavedStudyPlanUpdate, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    if payload.title is not None:
        plan.title = payload.title
    if payload.completed_tasks is not None:
        valid = {f"task:{i}:{j}" for i, period in enumerate(plan.plan.get("study_plan", [])) for j, _ in enumerate(period["tasks"])}
        valid.update(f"project:{i}" for i, _ in enumerate(plan.plan.get("project_ideas", [])))
        if not set(payload.completed_tasks) <= valid:
            raise HTTPException(status_code=400, detail="Unknown study task")
        plan.plan = {**plan.plan, "completed_tasks": list(dict.fromkeys(payload.completed_tasks))}
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_plan(plan_id: str, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    db.delete(plan)
    db.commit()

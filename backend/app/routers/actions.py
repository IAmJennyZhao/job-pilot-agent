from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ActionWrite(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    due_date: date
    completed: bool = False

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a next action")
        return value.strip()


class ActionRead(schemas.CareerPilotModel):
    job_id: str
    title: str
    due_date: date
    completed_at: datetime | None
    company: str
    role_title: str
    status: models.JobStatus


def view(action: models.JobAction) -> ActionRead:
    return ActionRead(job_id=action.job_id, title=action.title, due_date=action.due_date,
                      completed_at=action.completed_at, company=action.job.company,
                      role_title=action.job.role_title, status=action.job.status)


@router.get("", response_model=list[ActionRead])
def list_actions(db: Session = Depends(get_db)):
    return [view(action) for action in db.scalars(
        select(models.JobAction).options(joinedload(models.JobAction.job))
        .order_by(models.JobAction.due_date, models.JobAction.job_id)
    ).all()]


@router.get("/{job_id}", response_model=ActionRead | None)
def get_action(job_id: str, db: Session = Depends(get_db)):
    if not db.get(models.Job, job_id):
        raise HTTPException(404, "Job not found")
    action = db.get(models.JobAction, job_id)
    return view(action) if action else None


@router.put("/{job_id}", response_model=ActionRead)
def save_action(job_id: str, payload: ActionWrite, db: Session = Depends(get_db)):
    if not db.get(models.Job, job_id):
        raise HTTPException(404, "Job not found")
    action = db.get(models.JobAction, job_id)
    if action is None:
        action = models.JobAction(job_id=job_id)
        db.add(action)
    action.title = payload.title
    action.due_date = payload.due_date
    action.completed_at = (action.completed_at or datetime.now(timezone.utc)) if payload.completed else None
    db.commit()
    db.refresh(action)
    return view(action)


@router.delete("/{job_id}", status_code=204)
def delete_action(job_id: str, db: Session = Depends(get_db)):
    action = db.get(models.JobAction, job_id)
    if action:
        db.delete(action)
        db.commit()

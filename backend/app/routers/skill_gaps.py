from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import skill_gap_service

router = APIRouter(prefix="/api/skill-gaps", tags=["skill gaps"])


@router.get("", response_model=list[schemas.SkillGapRead])
def get_skill_gaps(profile_id: str | None = None, db: Session = Depends(get_db)):
    return skill_gap_service.list_skill_gaps(db, profile_id)


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
    return gap


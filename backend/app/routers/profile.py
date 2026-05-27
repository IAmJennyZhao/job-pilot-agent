from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import profile_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=schemas.ResumeProfileRead | None)
def get_profile(db: Session = Depends(get_db)):
    return profile_service.get_active_profile(db)


@router.post("", response_model=schemas.ResumeProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: schemas.ResumeProfileCreate, db: Session = Depends(get_db)):
    return profile_service.create_active_profile(db, payload)


@router.patch("/{profile_id}", response_model=schemas.ResumeProfileRead)
def update_profile(
    profile_id: str,
    payload: schemas.ResumeProfileUpdate,
    db: Session = Depends(get_db),
):
    profile = db.get(models.ResumeProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile_service.update_profile(db, profile, payload)

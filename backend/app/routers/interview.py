from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import interview_service

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/practice-sets", response_model=schemas.InterviewPracticeSetResponse, status_code=status.HTTP_201_CREATED)
def create_practice_set(payload: schemas.InterviewPracticeSetCreate, db: Session = Depends(get_db)):
    return interview_service.create_practice_set(db, payload)


@router.post("/answers/evaluate", response_model=schemas.InterviewPracticeAnswerFeedback)
def evaluate_practice_answer(payload: schemas.InterviewPracticeAnswerCreate, db: Session = Depends(get_db)):
    return interview_service.evaluate_practice_answer(db, payload)


@router.get("/insights", response_model=schemas.InterviewInsights)
def interview_insights(db: Session = Depends(get_db)):
    return interview_service.interview_insights(db)


@router.post("/sessions", response_model=schemas.InterviewSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: schemas.InterviewSessionCreate, db: Session = Depends(get_db)):
    if payload.job_id and not db.get(models.Job, payload.job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if payload.resume_profile_id and not db.get(models.ResumeProfile, payload.resume_profile_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")
    session = models.InterviewSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[schemas.InterviewSessionRead])
def list_sessions(db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(models.InterviewSession)
            .order_by(models.InterviewSession.updated_at.desc())
            .limit(50)
        ).all()
    )


@router.get("/sessions/{session_id}", response_model=schemas.InterviewSessionRead)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(models.InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post(
    "/sessions/{session_id}/messages",
    response_model=schemas.InterviewMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: str,
    payload: schemas.InterviewMessageCreate,
    db: Session = Depends(get_db),
):
    if not db.get(models.InterviewSession, session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    message = models.InterviewMessage(session_id=session_id, **payload.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


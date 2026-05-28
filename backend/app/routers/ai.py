from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import ai_service, profile_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_job_or_404(db: Session, job_id: str) -> models.Job:
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/analyze-job/{job_id}", response_model=schemas.JobAnalysisRead)
def analyze_job(job_id: str, db: Session = Depends(get_db)):
    return ai_service.analyze_job_description(db, _get_job_or_404(db, job_id))


@router.get("/readiness/{job_id}", response_model=schemas.AIReadiness)
def ai_readiness(job_id: str, db: Session = Depends(get_db)):
    return ai_service.ai_readiness(db, _get_job_or_404(db, job_id))


@router.post("/run-job-intelligence/{job_id}", response_model=schemas.JobIntelligenceResponse)
def run_job_intelligence(job_id: str, db: Session = Depends(get_db)):
    return ai_service.run_job_intelligence(db, _get_job_or_404(db, job_id))


@router.post("/suggest-resume/{job_id}", response_model=schemas.ResumeSuggestionRead)
def suggest_resume(job_id: str, db: Session = Depends(get_db)):
    profile = profile_service.get_active_profile(db)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")
    return ai_service.suggest_resume_changes(db, _get_job_or_404(db, job_id), profile)


@router.post(
    "/generate-interview-questions/{job_id}",
    response_model=schemas.InterviewQuestionResponse,
)
def generate_interview_questions(
    job_id: str,
    payload: schemas.GenerateInterviewQuestionsRequest,
    db: Session = Depends(get_db),
):
    profile = (
        db.get(models.ResumeProfile, payload.resume_profile_id)
        if payload.resume_profile_id
        else profile_service.get_active_profile(db)
    )
    return ai_service.generate_interview_questions(
        db,
        _get_job_or_404(db, job_id),
        profile,
        payload,
    )


@router.post("/evaluate-interview-answer", response_model=schemas.InterviewAnswerFeedback)
def evaluate_interview_answer(
    payload: schemas.EvaluateInterviewAnswerRequest,
    db: Session = Depends(get_db),
):
    return ai_service.evaluate_interview_answer(db, payload)


@router.post("/generate-study-plan", response_model=schemas.StudyPlanResponse)
def generate_study_plan(payload: schemas.StudyPlanRequest, db: Session = Depends(get_db)):
    return ai_service.generate_study_plan(db, payload)

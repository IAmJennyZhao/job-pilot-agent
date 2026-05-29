from typing import TypeVar

from fastapi import HTTPException, status
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, prompts, schemas
from app.config import get_settings
from app.services import profile_service, skill_gap_service

T = TypeVar("T", bound=BaseModel)


def get_structured_output(
    output_model: type[T],
    system_prompt: str,
    user_prompt: str,
) -> T:
    settings = get_settings()
    api_key = settings.openai_api_key.strip() if settings.openai_api_key else ""
    model = settings.openai_model.strip() if settings.openai_model else ""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured. Add it to .env to use AI actions.",
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_MODEL is not configured. Add it to .env to use AI actions.",
        )

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.parse(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            text_format=output_model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI request failed: {exc}",
        ) from exc
    if response.output_parsed is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned no structured output.",
        )
    return response.output_parsed


def get_research_structured_output(
    output_model: type[T],
    system_prompt: str,
    user_prompt: str,
) -> T:
    settings = get_settings()
    api_key = settings.openai_api_key.strip() if settings.openai_api_key else ""
    model = settings.openai_research_model.strip() if settings.openai_research_model else ""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured. Add it to .env to use AI actions.",
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_RESEARCH_MODEL is not configured. Add it to .env to use web-sourced analysis.",
        )

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.parse(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            text_format=output_model,
            tools=[{"type": "web_search_preview"}],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI research request failed: {exc}",
        ) from exc
    if response.output_parsed is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned no structured research output.",
        )
    return response.output_parsed


def ai_readiness(db: Session, job: models.Job) -> schemas.AIReadiness:
    settings = get_settings()
    model = settings.openai_model.strip() if settings.openai_model else None
    research_model = settings.openai_research_model.strip() if settings.openai_research_model else None
    profile = profile_service.get_active_profile(db)
    has_api_key = bool(settings.openai_api_key and settings.openai_api_key.strip())
    has_model = bool(model)
    has_research_model = bool(research_model)
    has_profile = profile is not None
    has_resume_text = bool(profile and profile.resume_text.strip())
    has_skills = bool(profile and profile.skills)

    missing_requirements: list[str] = []
    if not has_api_key:
        missing_requirements.append("OPENAI_API_KEY")
    if not has_model:
        missing_requirements.append("OPENAI_MODEL")
    if not has_profile:
        missing_requirements.append("Active resume profile")
    if has_profile and not has_resume_text:
        missing_requirements.append("Resume text")
    if has_profile and not has_skills:
        missing_requirements.append("Skills")

    return schemas.AIReadiness(
        ready=not missing_requirements,
        has_openai_api_key=has_api_key,
        has_openai_model=has_model,
        has_openai_research_model=has_research_model,
        model=model,
        research_model=research_model,
        job_id=job.id,
        profile_id=profile.id if profile else None,
        has_profile=has_profile,
        has_resume_text=has_resume_text,
        has_skills=has_skills,
        missing_requirements=missing_requirements,
    )


def _job_source_text(job: models.Job) -> str:
    return job.source_content or job.summary or "\n".join(job.responsibilities)


def analyze_job_description(db: Session, job: models.Job) -> models.JobAnalysis:
    output = get_structured_output(
        schemas.JobAnalysisOutput,
        prompts.SYSTEM_PROMPT,
        prompts.job_analysis_prompt(job.company, job.role_title, _job_source_text(job)),
    )
    analysis = job.analysis or models.JobAnalysis(job_id=job.id, summary=output.summary)
    for key, value in output.model_dump().items():
        setattr(analysis, key, value)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    profile = profile_service.get_active_profile(db)
    if profile:
        skill_gap_service.upsert_skill_gaps(
            db,
            profile.id,
            [*output.required_skills, *output.technologies],
            models.SkillGapSource.job_analysis,
            "Review job requirement",
        )
    return analysis


def suggest_resume_changes(
    db: Session,
    job: models.Job,
    profile: models.ResumeProfile,
) -> models.ResumeSuggestion:
    output = get_structured_output(
        schemas.ResumeSuggestionOutput,
        prompts.SYSTEM_PROMPT,
        prompts.resume_suggestion_prompt(
            job.company,
            job.role_title,
            _job_source_text(job),
            profile.resume_text,
            profile.summary,
            profile.skills,
        ),
    )
    suggestion = models.ResumeSuggestion(
        job_id=job.id,
        resume_profile_id=profile.id,
        matched_skills=output.matched_skills,
        missing_skills=output.missing_skills,
        weak_skills=output.weak_skills,
        keyword_suggestions=output.keyword_suggestions,
        bullet_suggestions=[item.model_dump() for item in output.bullet_suggestions],
        fit_score=output.fit_score,
    )
    job.fit_score = output.fit_score
    db.add_all([suggestion, job])
    db.commit()
    db.refresh(suggestion)

    skill_gap_service.upsert_skill_gaps(
        db,
        profile.id,
        [*output.missing_skills, *output.weak_skills],
        models.SkillGapSource.resume_match,
        "Build proof or study plan for",
    )
    return suggestion


def _error_message(exc: HTTPException) -> str:
    return exc.detail if isinstance(exc.detail, str) else str(exc.detail)


def run_job_intelligence(db: Session, job: models.Job) -> schemas.JobIntelligenceResponse:
    analysis = analyze_job_description(db, job)
    profile = profile_service.get_active_profile(db)
    if not profile:
        return schemas.JobIntelligenceResponse(
            status="partial",
            analysis=schemas.JobAnalysisRead.model_validate(analysis),
            resume_suggestion=None,
            errors=["Resume profile not found. Create an active profile before running resume match."],
        )

    try:
        suggestion = suggest_resume_changes(db, job, profile)
    except HTTPException as exc:
        return schemas.JobIntelligenceResponse(
            status="partial",
            analysis=schemas.JobAnalysisRead.model_validate(analysis),
            resume_suggestion=None,
            errors=[_error_message(exc)],
        )

    return schemas.JobIntelligenceResponse(
        status="complete",
        analysis=schemas.JobAnalysisRead.model_validate(analysis),
        resume_suggestion=schemas.ResumeSuggestionRead.model_validate(suggestion),
        errors=[],
    )


def generate_interview_questions(
    db: Session,
    job: models.Job,
    profile: models.ResumeProfile | None,
    request: schemas.GenerateInterviewQuestionsRequest,
) -> schemas.InterviewQuestionResponse:
    output = get_structured_output(
        schemas.InterviewQuestionsOutput,
        prompts.SYSTEM_PROMPT,
        prompts.interview_questions_prompt(
            job.company,
            job.role_title,
            _job_source_text(job),
            profile.resume_text if profile else "",
            request.question_type,
            request.count,
        ),
    )
    session = models.InterviewSession(
        job_id=job.id,
        resume_profile_id=profile.id if profile else None,
        mode=models.InterviewMode.question_list,
        title=f"{job.role_title} questions",
    )
    db.add(session)
    db.flush()
    for question in output.questions:
        db.add(
            models.InterviewMessage(
                session_id=session.id,
                role=models.MessageRole.ai,
                content=question.question,
                question_type=question.type,
                feedback={
                    "why_it_matters": question.why_it_matters,
                    "strong_answer_should_include": question.strong_answer_should_include,
                },
            )
        )
    db.commit()
    db.refresh(session)
    return schemas.InterviewQuestionResponse(session_id=session.id, questions=output.questions)


def evaluate_interview_answer(
    db: Session,
    request: schemas.EvaluateInterviewAnswerRequest,
) -> schemas.InterviewAnswerFeedback:
    job = db.get(models.Job, request.job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    output = get_structured_output(
        schemas.InterviewAnswerFeedbackOutput,
        prompts.SYSTEM_PROMPT,
        prompts.interview_feedback_prompt(
            job.company,
            job.role_title,
            _job_source_text(job),
            request.question,
            request.answer,
        ),
    )

    session = db.get(models.InterviewSession, request.session_id) if request.session_id else None
    if not session:
        profile = profile_service.get_active_profile(db)
        session = models.InterviewSession(
            job_id=job.id,
            resume_profile_id=profile.id if profile else None,
            mode=models.InterviewMode.live_practice,
            title=f"{job.role_title} practice",
        )
        db.add(session)
        db.flush()

    db.add_all(
        [
            models.InterviewMessage(
                session_id=session.id,
                role=models.MessageRole.ai,
                content=request.question,
            ),
            models.InterviewMessage(
                session_id=session.id,
                role=models.MessageRole.user,
                content=request.answer,
            ),
            models.InterviewMessage(
                session_id=session.id,
                role=models.MessageRole.ai,
                content=output.follow_up_question,
                score=output.score,
                feedback=output.model_dump(),
            ),
        ]
    )
    db.commit()

    profile_id = session.resume_profile_id
    if profile_id:
        skill_gap_service.upsert_skill_gaps(
            db,
            profile_id,
            output.what_was_missing,
            models.SkillGapSource.interview_feedback,
            "Practice interview answer for",
        )

    return schemas.InterviewAnswerFeedback(**output.model_dump(), session_id=session.id)


def generate_study_plan(
    db: Session,
    request: schemas.StudyPlanRequest,
) -> schemas.StudyPlanResponse:
    profile = (
        db.get(models.ResumeProfile, request.resume_profile_id)
        if request.resume_profile_id
        else profile_service.get_active_profile(db)
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume profile not found")

    gaps = list(
        db.scalars(
            select(models.SkillGap)
            .where(models.SkillGap.resume_profile_id == profile.id)
            .order_by(models.SkillGap.count.desc())
            .limit(20)
        ).all()
    )
    gap_payload = [
        {
            "skill_name": gap.skill_name,
            "count": gap.count,
            "priority": gap.priority.value,
            "user_level": gap.user_level.value,
            "suggested_action": gap.suggested_action,
        }
        for gap in gaps
    ]
    return get_structured_output(
        schemas.StudyPlanResponse,
        prompts.SYSTEM_PROMPT,
        prompts.study_plan_prompt(
            request.timeframe,
            request.target_roles or profile.target_roles,
            gap_payload,
            profile.resume_text,
        ),
    )

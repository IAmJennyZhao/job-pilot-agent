import logging
from typing import TypeVar

from fastapi import HTTPException, status
import httpx
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, prompts, schemas
from app.config import get_settings
from app.services import profile_asset_service, profile_service, skill_gap_service

logger = logging.getLogger(__name__)

# Tailoring has bounded calls and metadata while existing callers retain their contract.
from app.services.tailoring_provider import get_tailoring_output

T = TypeVar("T", bound=BaseModel)
OPENAI_TIMEOUT_SECONDS = 60.0


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

    try:
        with httpx.Client(trust_env=False, timeout=OPENAI_TIMEOUT_SECONDS) as http_client:
            options = {"max_retries": 0} if output_model is schemas.JobExtractionOutput else {}
            client = OpenAI(api_key=api_key, http_client=http_client, **options)
            response = client.responses.parse(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                text_format=output_model,
            )
    except Exception as exc:
        if output_model is schemas.JobExtractionOutput:
            logger.warning("Basic job extraction failed (%s)", type(exc).__name__)
            raise HTTPException(502, "Could not extract job basics. Retry or use manual entry; your draft is preserved.") from None
        logger.exception("OpenAI request failed (model=%s, output=%s)", model, output_model.__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI request failed: {exc}",
        ) from exc
    if response.output_parsed is None:
        logger.error("OpenAI returned no structured output (model=%s, output=%s)", model, output_model.__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned no structured output.",
        )
    return response.output_parsed


def ai_readiness(db: Session, job: models.Job) -> schemas.AIReadiness:
    settings = get_settings()
    model = settings.openai_model.strip() if settings.openai_model else None
    profile = profile_service.get_active_profile(db)
    has_api_key = bool(settings.openai_api_key and settings.openai_api_key.strip())
    has_model = bool(model)
    has_tavily_api_key = bool(settings.tavily_api_key and settings.tavily_api_key.strip())
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
        has_tavily_api_key=has_tavily_api_key,
        model=model,
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
    resume_option: models.ResumeOption | None = None,
) -> models.ResumeSuggestion:
    resume_text = resume_option.parsed_text if resume_option else profile.resume_text
    profile_summary = (resume_option.summary if resume_option else None) or profile.summary
    skills = resume_option.skills if resume_option and resume_option.skills else profile.skills
    output = get_structured_output(
        schemas.ResumeSuggestionOutput,
        prompts.SYSTEM_PROMPT,
        prompts.resume_suggestion_prompt(
            job.company,
            job.role_title,
            _job_source_text(job),
            resume_text,
            profile_summary,
            skills,
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
    asset_recommendation: models.AssetRecommendationSnapshot | None = None
    if profile:
        asset_recommendation = profile_asset_service.create_keyword_recommendation_snapshot(db, job)
    if not profile:
        return schemas.JobIntelligenceResponse(
            status="partial",
            analysis=schemas.JobAnalysisRead.model_validate(analysis),
            resume_suggestion=None,
            asset_recommendation=None,
            errors=["Resume profile not found. Create an active profile before running resume match."],
        )

    resume_option = profile_asset_service.best_resume_option_for_job(db, job)
    try:
        suggestion = suggest_resume_changes(db, job, profile, resume_option=resume_option)
    except HTTPException as exc:
        return schemas.JobIntelligenceResponse(
            status="partial",
            analysis=schemas.JobAnalysisRead.model_validate(analysis),
            resume_suggestion=None,
            asset_recommendation=(
                schemas.AssetRecommendationRead.model_validate(asset_recommendation)
                if asset_recommendation
                else None
            ),
            errors=[_error_message(exc)],
        )

    return schemas.JobIntelligenceResponse(
        status="complete",
        analysis=schemas.JobAnalysisRead.model_validate(analysis),
        resume_suggestion=schemas.ResumeSuggestionRead.model_validate(suggestion),
        asset_recommendation=(
            schemas.AssetRecommendationRead.model_validate(asset_recommendation)
            if asset_recommendation
            else None
        ),
        errors=[],
    )


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

    focus_skills = [skill.strip() for skill in request.focus_skills if skill and skill.strip()]
    focus_keys = {skill.casefold() for skill in focus_skills}
    gaps = [gap for gap in skill_gap_service.list_skill_gaps(db, profile.id)
            if gap.user_level != models.UserLevel.high and (not focus_keys or gap.skill_name.casefold() in focus_keys)][:20]
    gap_payload = [
        {
            "skill_name": gap.skill_name,
            "active_jobs_affected": gap.active_job_count,
            "historical_mentions": gap.count,
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
            focus_skills=focus_skills,
            time_budget_hours=request.time_budget_hours,
            time_budget_unit=request.time_budget_unit,
            mode=request.mode,
        ),
    )

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, prompts, schemas
from app.services import ai_service, profile_service
from app.services.concise_output import (
    normalize_company_research_output,
    normalize_interview_prep_output,
    normalize_job_insights,
    normalize_resume_fit_output,
)
from app.services.research_service import CompanyResearchRetrievalAgent


def normalize_company_name(company_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", company_name.casefold()).strip()
    return re.sub(r"\s+", " ", normalized)


def _job_source_text(job: models.Job) -> str:
    return job.source_content or job.summary or "\n".join(job.responsibilities)


def _error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return str(exc)


def get_latest_analysis(db: Session, job_id: str) -> models.AdvancedJobAnalysis | None:
    return db.scalars(
        select(models.AdvancedJobAnalysis)
        .where(models.AdvancedJobAnalysis.job_id == job_id)
        .order_by(models.AdvancedJobAnalysis.created_at.desc())
        .limit(1)
    ).first()


def get_company_research(
    db: Session,
    company_name: str,
) -> models.CompanyResearchSnapshot | None:
    normalized = normalize_company_name(company_name)
    return db.scalars(
        select(models.CompanyResearchSnapshot).where(
            models.CompanyResearchSnapshot.normalized_company_name == normalized
        )
    ).first()


def _company_payload(snapshot: models.CompanyResearchSnapshot) -> dict:
    return {
        "sentiment": snapshot.sentiment,
        "summary": snapshot.summary,
        "themes": snapshot.themes,
        "source_links": snapshot.source_links,
        "confidence": snapshot.confidence,
        "coverage_note": snapshot.coverage_note,
    }


def _save_company_research(
    db: Session,
    company_name: str,
    output: schemas.CompanyResearchOutput,
) -> models.CompanyResearchSnapshot:
    normalized = normalize_company_name(company_name)
    snapshot = get_company_research(db, company_name) or models.CompanyResearchSnapshot(
        company_name=company_name,
        normalized_company_name=normalized,
    )
    snapshot.company_name = company_name
    output = normalize_company_research_output(output)
    snapshot.sentiment = output.sentiment
    snapshot.summary = output.summary
    snapshot.themes = output.themes
    snapshot.source_links = [link.model_dump() for link in output.source_links]
    snapshot.confidence = output.confidence
    snapshot.coverage_note = output.coverage_note
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


class PostingAnalysisAgent:
    @staticmethod
    def run(job: models.Job, job_source: str) -> schemas.JobInsightsOutput:
        output = ai_service.get_structured_output(
            schemas.JobInsightsOutput,
            prompts.SYSTEM_PROMPT,
            prompts.advanced_posting_analysis_prompt(job.company, job.role_title, job_source),
        )
        return normalize_job_insights(output)


class CompanyResearchAgent:
    def __init__(
        self,
        retrieval_agent: CompanyResearchRetrievalAgent | None = None,
    ) -> None:
        self.retrieval_agent = retrieval_agent or CompanyResearchRetrievalAgent()

    def run(self, db: Session, job: models.Job) -> models.CompanyResearchSnapshot:
        research_context = self.retrieval_agent.run(job.company, job.role_title)
        output = ai_service.get_structured_output(
            schemas.CompanyResearchOutput,
            prompts.SYSTEM_PROMPT,
            prompts.company_research_prompt(
                job.company,
                job.role_title,
                research_context.prompt_text(),
                research_context.warnings,
            ),
        )
        if research_context.warnings:
            warning_note = " ".join(research_context.warnings)
            output.coverage_note = f"{output.coverage_note} {warning_note}".strip()
        return _save_company_research(db, job.company, output)


class ResumeFitAgent:
    @staticmethod
    def run(
        job: models.Job,
        job_source: str,
        profile: models.ResumeProfile,
    ) -> schemas.ResumeFitOutput:
        output = ai_service.get_structured_output(
            schemas.ResumeFitOutput,
            prompts.SYSTEM_PROMPT,
            prompts.resume_fit_prompt(
                job.company,
                job.role_title,
                job_source,
                profile.summary,
                profile.resume_text,
                profile.skills,
            ),
        )
        return normalize_resume_fit_output(output)


class InterviewPrepAgent:
    @staticmethod
    def run(
        job: models.Job,
        job_source: str,
        profile: models.ResumeProfile | None,
    ) -> schemas.AdvancedInterviewPrepOutput:
        output = ai_service.get_structured_output(
            schemas.AdvancedInterviewPrepOutput,
            prompts.SYSTEM_PROMPT,
            prompts.advanced_interview_prep_prompt(
                job.company,
                job.role_title,
                job_source,
                profile.resume_text if profile else "",
            ),
        )
        return normalize_interview_prep_output(output)


def run_advanced_analysis(
    db: Session,
    job: models.Job,
    refresh_company: bool = False,
) -> schemas.AdvancedAnalysisResponse:
    profile = profile_service.get_active_profile(db)
    job_source = _job_source_text(job)
    errors: list[str] = []
    job_insights: dict | None = None
    company_research = None if refresh_company else get_company_research(db, job.company)
    resume_fit: schemas.ResumeFitOutput | None = None
    interview_prep: schemas.AdvancedInterviewPrepOutput | None = None

    try:
        posting_output = PostingAnalysisAgent.run(job, job_source)
        job_insights = posting_output.model_dump()
    except Exception as exc:
        errors.append(f"Posting analysis failed: {_error_message(exc)}")

    if company_research is None:
        try:
            company_research = CompanyResearchAgent().run(db, job)
        except Exception as exc:
            errors.append(f"Company research failed: {_error_message(exc)}")

    if profile:
        try:
            resume_fit = ResumeFitAgent.run(job, job_source, profile)
        except Exception as exc:
            errors.append(f"Resume fit failed: {_error_message(exc)}")
    else:
        errors.append("Resume fit skipped: Active resume profile not found.")

    try:
        interview_prep = InterviewPrepAgent.run(job, job_source, profile)
    except Exception as exc:
        errors.append(f"Interview prep failed: {_error_message(exc)}")

    source_links = company_research.source_links if company_research else []
    analysis = get_latest_analysis(db, job.id) or models.AdvancedJobAnalysis(job_id=job.id)
    analysis.company_research_id = company_research.id if company_research else None
    analysis.status = "partial" if errors else "complete"
    analysis.job_insights = job_insights
    analysis.company_sentiment = _company_payload(company_research) if company_research else None
    analysis.top_company_fit = resume_fit.top_company_fit if resume_fit else []
    analysis.resume_keywords = resume_fit.resume_keywords if resume_fit else []
    analysis.risks_gaps = resume_fit.risks_gaps if resume_fit else []
    analysis.expected_questions = [
        question.model_dump() for question in interview_prep.expected_questions
    ] if interview_prep else []
    analysis.source_links = source_links
    analysis.errors = errors
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return schemas.AdvancedAnalysisResponse(
        status=analysis.status,
        analysis=schemas.AdvancedJobAnalysisRead.model_validate(analysis),
        company_research=(
            schemas.CompanyResearchRead.model_validate(company_research)
            if company_research
            else None
        ),
        errors=errors,
    )

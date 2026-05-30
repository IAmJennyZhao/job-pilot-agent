from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal, init_db
from app.schemas import JobCreate, ResumeProfileCreate
from app.services import job_service, profile_service


def ensure_profile(db: Session) -> models.ResumeProfile:
    profile = profile_service.get_active_profile(db)
    if profile:
        return profile

    return profile_service.create_active_profile(
        db,
        ResumeProfileCreate(
            name="Demo AI Engineer",
            target_roles=["Applied AI Engineer", "AI Software Engineer"],
            summary="Software engineer building AI-enabled products with Python, React, and retrieval systems.",
            skills=["Python", "FastAPI", "React", "TypeScript", "Postgres", "RAG", "OpenAI API"],
            resume_text=(
                "Built production APIs with FastAPI and SQLAlchemy. Created AI prototypes using "
                "OpenAI APIs, retrieval workflows, and React dashboards. Led projects that turned "
                "ambiguous product ideas into working demos."
            ),
            projects=[
                {
                    "name": "AI Support Assistant",
                    "description": "RAG prototype with FastAPI, Postgres, and OpenAI structured outputs.",
                }
            ],
            experience=[
                {
                    "company": "ExampleCo",
                    "role": "Software Engineer",
                    "bullets": [
                        "Built internal dashboards with React and TypeScript.",
                        "Designed FastAPI services backed by Postgres.",
                    ],
                }
            ],
            education=[{"school": "Demo University", "credential": "BS Computer Science"}],
            certifications=["OpenAI API projects"],
        ),
    )


def find_job(db: Session, company: str, role_title: str) -> models.Job | None:
    return db.scalars(
        select(models.Job).where(
            models.Job.company == company,
            models.Job.role_title == role_title,
        )
    ).first()


def ensure_job(
    db: Session,
    payload: JobCreate,
    status: models.JobStatus,
    notes: str,
    fit_score: int | None = None,
) -> models.Job:
    job = find_job(db, payload.company, payload.role_title)
    if not job:
        job = job_service.save_job(db, payload)

    job.company = payload.company
    job.role_title = payload.role_title
    job.category = payload.category
    job.location = payload.location
    job.remote_type = payload.remote_type
    job.summary = payload.summary
    job.responsibilities = payload.responsibilities
    job.required_skills = payload.required_skills
    job.pay_min = payload.pay_min
    job.pay_max = payload.pay_max
    job.pay_currency = payload.pay_currency
    job.pay_period = payload.pay_period
    job.pay_raw = payload.pay_raw
    annual_min, annual_max, conversion_note = job_service.annualize_pay(
        payload.pay_min,
        payload.pay_max,
        payload.pay_period,
    )
    job.pay_annual_min = annual_min
    job.pay_annual_max = annual_max
    job.pay_conversion_note = conversion_note
    job.benefits = payload.benefits
    job.source_content = payload.source_content
    job.extraction_confidence = payload.extraction_confidence
    job.extraction_warnings = payload.extraction_warnings
    job.notes = notes
    job.status = status
    job.fit_score = fit_score
    job.links.clear()
    for link in payload.links:
        job.links.append(
            models.JobLink(kind=link.kind, label=link.label, url=str(link.url))
        )
    db.add(job)
    db.commit()
    db.refresh(job)
    if not job.status_events:
        db.add(models.JobStatusEvent(job_id=job.id, from_status=None, to_status=status))
        db.commit()
    return job


def ensure_analysis(db: Session, job: models.Job, payload: dict) -> None:
    analysis = job.analysis or models.JobAnalysis(job_id=job.id, summary=payload["summary"])
    for key, value in payload.items():
        setattr(analysis, key, value)
    db.add(analysis)
    db.commit()


def ensure_resume_suggestion(db: Session, job: models.Job, profile: models.ResumeProfile) -> None:
    suggestion = db.scalars(
        select(models.ResumeSuggestion).where(
            models.ResumeSuggestion.job_id == job.id,
            models.ResumeSuggestion.resume_profile_id == profile.id,
        )
    ).first()
    if not suggestion:
        suggestion = models.ResumeSuggestion(job_id=job.id, resume_profile_id=profile.id)

    suggestion.matched_skills = ["Python", "FastAPI", "React", "RAG", "OpenAI API"]
    suggestion.missing_skills = ["LangChain", "LangGraph"]
    suggestion.weak_skills = ["LLM evaluation"]
    suggestion.keyword_suggestions = ["agentic workflows", "vector search", "evaluation"]
    suggestion.bullet_suggestions = [
        {
            "original": "Created AI prototypes using OpenAI APIs.",
            "suggested": "Built FastAPI-backed AI prototypes using OpenAI APIs, retrieval workflows, and React dashboards.",
            "reason": "Connects existing work to the job's product and stack language.",
        }
    ]
    suggestion.fit_score = 82
    job.fit_score = 82
    db.add_all([suggestion, job])
    db.commit()


def ensure_interview_session(db: Session, job: models.Job, profile: models.ResumeProfile) -> None:
    title = "AI Software Engineer tech screen"
    existing = db.scalars(
        select(models.InterviewSession).where(
            models.InterviewSession.job_id == job.id,
            models.InterviewSession.title == title,
        )
    ).first()
    if existing:
        return

    db.add(
        models.InterviewSession(
            job_id=job.id,
            resume_profile_id=profile.id,
            mode=models.InterviewMode.question_list,
            title=title,
        )
    )
    db.commit()


def ensure_skill_gaps(db: Session, profile: models.ResumeProfile, skills: list[str]) -> None:
    for skill in skills:
        existing = db.scalars(
            select(models.SkillGap).where(
                models.SkillGap.resume_profile_id == profile.id,
                models.SkillGap.source == models.SkillGapSource.resume_match,
                models.SkillGap.skill_name.ilike(skill),
            )
        ).first()
        if existing:
            continue
        db.add(
            models.SkillGap(
                resume_profile_id=profile.id,
                skill_name=skill,
                source=models.SkillGapSource.resume_match,
                count=1,
                priority=models.Priority.low,
                user_level=models.UserLevel.unknown,
                suggested_action=f"Build a small proof project for: {skill}",
            )
        )
    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        profile = ensure_profile(db)

        job_one = ensure_job(
            db,
            JobCreate(
                company="Northstar AI",
                role_title="Applied AI Engineer",
                category=models.JobCategory.ai_ml_engineer,
                location="Remote",
                remote_type="Remote",
                summary="Applied AI role focused on production LLM features and React interfaces.",
                responsibilities=[
                    "Build AI product features",
                    "Create evaluation workflows",
                    "Ship customer-facing interfaces",
                ],
                required_skills=["Python", "FastAPI", "LLM APIs", "React"],
                pay_min=130000,
                pay_max=170000,
                pay_currency="USD",
                pay_period="year",
                benefits=["Health insurance", "Remote work stipend", "Equity"],
                links=[
                    {
                        "kind": models.JobLinkKind.source,
                        "label": "Job Posting",
                        "url": "https://example.com/jobs/applied-ai-engineer",
                    }
                ],
                source_content=(
                    "Build AI product features with Python, FastAPI, LLM APIs, vector search, "
                    "evaluation workflows, and customer-facing React interfaces. Experience with "
                    "LangChain or LangGraph and cloud deployment preferred."
                ),
                extraction_confidence=94,
                notes="Resume tailored once. Still needs stronger LangChain and evaluation examples.",
            ),
            models.JobStatus.saved,
            "Resume tailored once. Still needs stronger LangChain and evaluation examples.",
            fit_score=82,
        )
        job_two = ensure_job(
            db,
            JobCreate(
                company="VectorWorks",
                role_title="GenAI Software Engineer",
                category=models.JobCategory.ai_ml_engineer,
                location="New York, NY",
                remote_type="Hybrid",
                summary="GenAI engineering role focused on LLM tools, embeddings, and production monitoring.",
                responsibilities=[
                    "Own LLM-powered internal tools",
                    "Build prompt evaluation workflows",
                    "Monitor production AI features",
                ],
                required_skills=["Python", "TypeScript", "Postgres", "Embeddings"],
                pay_raw="$110k-$145k base plus annual bonus",
                benefits=["Medical benefits", "401k match", "Hybrid work"],
                links=[
                    {
                        "kind": models.JobLinkKind.source,
                        "label": "Job Posting",
                        "url": "https://example.com/jobs/genai-engineer",
                    }
                ],
                source_content=(
                    "Own LLM-powered tools using Python, TypeScript, Postgres, embeddings, "
                    "prompt evaluation, and production monitoring. AWS Bedrock experience a plus."
                ),
                extraction_confidence=91,
                notes="Need stronger cloud and eval examples.",
            ),
            models.JobStatus.applied,
            "Need stronger cloud and eval examples.",
        )
        job_three = ensure_job(
            db,
            JobCreate(
                company="AgentOps Labs",
                role_title="AI Software Engineer",
                category=models.JobCategory.ai_ml_engineer,
                location="San Francisco, CA",
                remote_type="Remote",
                summary="Agentic workflow role with tracing, evaluation, and observability expectations.",
                responsibilities=[
                    "Design agentic workflow features",
                    "Build evaluation harnesses",
                    "Prepare production observability",
                ],
                required_skills=["Python", "TypeScript", "FastAPI", "React", "System design"],
                pay_min=150000,
                pay_max=190000,
                pay_currency="USD",
                pay_period="year",
                benefits=["Flexible PTO", "Health insurance", "Learning budget"],
                links=[
                    {
                        "kind": models.JobLinkKind.source,
                        "label": "Job Posting",
                        "url": "https://example.com/jobs/ai-software-engineer",
                    }
                ],
                source_content=(
                    "Design agentic workflow features with Python, TypeScript, tracing, "
                    "evaluation harnesses, and production observability. Experience with "
                    "FastAPI, React, LangGraph, and system design interviews expected."
                ),
                extraction_confidence=89,
                notes="Tech screen scheduled. Prepare to discuss workflow tracing and evals.",
            ),
            models.JobStatus.tech_screen,
            "Tech screen scheduled. Prepare to discuss workflow tracing and evals.",
            fit_score=68,
        )
        ensure_job(
            db,
            JobCreate(
                company="Legacy Cloud",
                role_title="Backend Platform Engineer",
                category=models.JobCategory.backend_engineer,
                location="Austin, TX",
                remote_type="On-site",
                summary="Backend platform role for enterprise SaaS services and deployment pipelines.",
                responsibilities=[
                    "Maintain backend services",
                    "Own internal APIs",
                    "Support deployment pipelines",
                ],
                required_skills=["Backend services", "Internal APIs", "Deployment pipelines"],
                pay_raw="Compensation not listed",
                benefits=[],
                links=[
                    {
                        "kind": models.JobLinkKind.source,
                        "label": "Job Posting",
                        "url": "https://example.com/jobs/backend-platform-engineer",
                    }
                ],
                source_content=(
                    "Maintain backend services, internal APIs, and deployment pipelines for "
                    "enterprise SaaS systems. AI product experience is optional."
                ),
                extraction_confidence=88,
                notes="Archived after reviewing role fit.",
            ),
            models.JobStatus.archived,
            "Archived after reviewing role fit.",
        )

        ensure_analysis(
            db,
            job_one,
            {
                "summary": "Applied AI role focused on production LLM features and React interfaces.",
                "responsibilities": [
                    "Build AI product features",
                    "Create evaluation workflows",
                    "Ship customer-facing interfaces",
                ],
                "required_skills": ["Python", "FastAPI", "LLM APIs", "React"],
                "preferred_skills": ["LangChain", "LangGraph", "Cloud deployment"],
                "technologies": ["Vector search", "OpenAI API", "Postgres"],
                "resume_keywords": ["AI product", "evaluation", "RAG", "React"],
                "interview_topics": ["RAG architecture", "LLM evaluation", "FastAPI service design"],
            },
        )
        ensure_resume_suggestion(db, job_one, profile)
        ensure_analysis(
            db,
            job_two,
            {
                "summary": "GenAI engineering role focused on LLM tools, embeddings, and production monitoring.",
                "responsibilities": [
                    "Own LLM-powered internal tools",
                    "Build prompt evaluation workflows",
                    "Monitor production AI features",
                ],
                "required_skills": ["Python", "TypeScript", "Postgres", "Embeddings"],
                "preferred_skills": ["AWS Bedrock", "Production monitoring"],
                "technologies": ["OpenAI API", "Postgres", "Embeddings"],
                "resume_keywords": ["prompt evaluation", "monitoring", "embeddings"],
                "interview_topics": ["Embedding search", "LLM reliability", "Production monitoring"],
            },
        )
        ensure_interview_session(db, job_three, profile)
        ensure_skill_gaps(db, profile, ["LangChain", "LangGraph", "AWS Bedrock", "LLM evaluation"])
        print("Seed data ready.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

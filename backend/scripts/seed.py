from sqlalchemy import select

from app import models
from app.database import SessionLocal, init_db
from app.services import job_service, profile_service, skill_gap_service
from app.schemas import JobCreate, ResumeProfileCreate


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.scalars(select(models.Job).limit(1)).first():
            print("Seed data already exists.")
            return

        profile = profile_service.create_active_profile(
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

        job_one = job_service.save_job(
            db,
            JobCreate(
                company="Northstar AI",
                role_title="Applied AI Engineer",
                job_url="https://example.com/jobs/applied-ai-engineer",
                job_description=(
                    "Build AI product features with Python, FastAPI, LLM APIs, vector search, "
                    "evaluation workflows, and customer-facing React interfaces. Experience with "
                    "LangChain or LangGraph and cloud deployment preferred."
                ),
                notes="Strong fit; emphasize FastAPI, React, and RAG work.",
            ),
        )
        job_two = job_service.save_job(
            db,
            JobCreate(
                company="VectorWorks",
                role_title="GenAI Software Engineer",
                job_url="https://example.com/jobs/genai-engineer",
                job_description=(
                    "Own LLM-powered tools using Python, TypeScript, Postgres, embeddings, "
                    "prompt evaluation, and production monitoring. AWS Bedrock experience a plus."
                ),
                notes="Need stronger cloud and eval examples.",
            ),
        )
        job_service.update_application_status(db, job_two, models.JobStatus.applied)

        db.add(
            models.JobAnalysis(
                job_id=job_one.id,
                summary="Applied AI role focused on production LLM features and React interfaces.",
                responsibilities=[
                    "Build AI product features",
                    "Create evaluation workflows",
                    "Ship customer-facing interfaces",
                ],
                required_skills=["Python", "FastAPI", "LLM APIs", "React"],
                preferred_skills=["LangChain", "LangGraph", "Cloud deployment"],
                technologies=["Vector search", "OpenAI API", "Postgres"],
                resume_keywords=["AI product", "evaluation", "RAG", "React"],
                interview_topics=["RAG architecture", "LLM evaluation", "FastAPI service design"],
            )
        )
        db.add(
            models.InterviewSession(
                job_id=job_one.id,
                resume_profile_id=profile.id,
                mode=models.InterviewMode.question_list,
                title="Applied AI Engineer practice",
            )
        )
        db.commit()
        skill_gap_service.upsert_skill_gaps(
            db,
            profile.id,
            ["LangChain", "LangGraph", "AWS Bedrock"],
            models.SkillGapSource.resume_match,
            "Build a small proof project for",
        )
        print("Seed data created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()


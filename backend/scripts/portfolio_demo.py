"""Isolated portfolio screenshot server. Never opens the normal application DB.

All identities, employers, source evidence and AI output below are fictional.
The ordinary application services still own generation, review and persistence.
"""
import atexit
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
temporary = tempfile.TemporaryDirectory(prefix="jobpilot-portfolio-")
database = Path(temporary.name) / "demo.sqlite"
assert database.resolve() != (ROOT / "careerpilot.db").resolve()
os.environ.update(DATABASE_URL=f"sqlite:///{database.as_posix()}", AUTO_MIGRATE="0",
                  ASSET_STORAGE_DIR=str(Path(temporary.name) / "files"),
                  OPENAI_API_KEY="demo-only-no-network", OPENAI_MODEL="portfolio-demo",
                  TAVILY_API_KEY="", BACKEND_CORS_ORIGINS="http://127.0.0.1:3120")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import Base, get_engine
from app import logging_config
logging_config.LOG_DIR = Path(temporary.name) / "logs"
logging_config.LOG_FILE = logging_config.LOG_DIR / "app.log"
from app.main import app
from app.services import ai_service
from app.services import resume_v6
from app.services.advanced_analysis_service import CompanyResearchRetrievalAgent
from tailoring_fixtures import bank_data, import_payload
from test_intake_preferences import preferences
import yaml

# Release SQLite handles before TemporaryDirectory's Windows cleanup runs.
atexit.register(lambda: get_engine().dispose())

AS_OF = datetime(2026, 10, 26, 16, tzinfo=timezone.utc)
CLAIMS = [
    ("R-1", "Built FastAPI services with idempotency keys and transaction-safe updates.", ["Python", "FastAPI", "PostgreSQL"]),
    ("R-1", "Created accessible React and TypeScript dashboards with recoverable form drafts.", ["React", "TypeScript"]),
    ("R-1", "Added integration tests for API retries, concurrent writes, and failed transactions.", ["Python", "SQL", "pytest"]),
    ("R-2", "Built a retrieval assistant that pairs generated answers with supporting source passages.", ["Python", "Retrieval"]),
    ("R-2", "Evaluated retrieval relevance on 40 sample questions and recorded unanswered cases.", ["Python", "Evaluation"]),
]
SKILLS = list(dict.fromkeys(skill for _, _, skills in CLAIMS for skill in skills))
POSTING = """Backend Engineer - Cedarline Studio
Build reliable FastAPI services for a collaborative research workspace.
Create transaction-safe PostgreSQL APIs and accessible product interfaces.
Write integration tests for retries, concurrency, and interrupted workflows.
Partner with product engineers on retrieval and evaluation features.
Required: Python, FastAPI, SQL, and clear written communication.
Preferred: React, TypeScript, retrieval evaluation, and observability.
USD 145000-170000 annual base salary; this band applies to NYC residents.
Remote anywhere in the United States, including NYC. Minimum 2 years required.
Full-time employment. Apply directly to Cedarline Studio.
"""
ANSWER = "I built a research workspace with a FastAPI backend and a React interface. Repeated submissions could create duplicate records, so I introduced idempotency keys and kept related updates in one database transaction. I added integration tests for retries, concurrent writes, and failed requests. That made the failure paths reproducible and gave the team confidence that a retry would preserve the original result."


def source_bundle():
    bank = bank_data()
    bank.update(bank_version="portfolio.1", prepared_at="2026-10-26",
                identity={"name": "Alex Rivera", "email": "alex.rivera@example.test", "location": "Brooklyn, NY", "source_id": "S-1"},
                sources=[{"id": "S-1", "independently_verified": False, "source_excerpt": "Fictional candidate evidence authored for portfolio screenshots."}],
                education=[{"id": "E-1", "institution": "Lakeview Institute of Technology", "degree": "B.S. Computer Science", "source_id": "S-1"}],
                records=[{"id": "R-1", "kind": "employment", "employer": "Lumen Grove Studio", "title_display": "Software Engineer", "start": "2024-06", "end": "2026-09", "source_id": "S-1"},
                         {"id": "R-2", "kind": "project", "name": "Searchlight research assistant", "source_id": "S-1"}],
                implementation_profiles=[], protected_metrics=[], planned_or_unverified_capabilities=[],
                claims=[], technology_catalog=[], skill_groups=[{"id": "SK-1", "label": "Engineering", "values": SKILLS, "source_id": "S-1"}])
    bank["approval"] = {"status": "approved", "approved_claim_ids": [f"C-{i+1}" for i in range(len(CLAIMS))], "excluded_claim_ids": [], "approved_by": "Alex Rivera (demo)"}
    bank["generation_policy"]["blocked_claim_ids"] = []
    for index, (record, text, skills) in enumerate(CLAIMS):
        bank["claims"].append({"id": f"C-{index+1}", "record_id": record, "source_id": "S-1", "text": text, "evidence_status": "source_supported", "generation_eligible": True,
                               "technologies": skills, "technology_ids": [f"T-{SKILLS.index(skill)}" for skill in skills], "constraints": []})
    for index, skill in enumerate(SKILLS):
        claims = [claim for claim in bank["claims"] if skill in claim["technologies"]]
        bank["technology_catalog"].append({"id": f"T-{index}", "name": skill, "aliases": [], "claim_ids": [c["id"] for c in claims], "eligible_claim_ids": [c["id"] for c in claims], "listed_skill_group_ids": ["SK-1"], "record_ids": list(dict.fromkeys(c["record_id"] for c in claims)), "relationship": "Used in the documented demo work."})
    result = import_payload(bank)
    result["bank_markdown"] = result["bank_markdown"].replace("# Synthetic source", "# Alex Rivera - reviewed experience")
    result.update(preferences_yaml=yaml.safe_dump(preferences().model_dump(by_alias=True)), template_tex="Reference layout for the fictional portfolio candidate.", style_guide="Use concise bullets, clear section headings, and evidence-backed statements.")
    return result


def demo_output(output_model, *args):
    if output_model is schemas.JobExtractionOutput:
        return schemas.JobExtractionOutput(company="Cedarline Studio", role_title="Backend Engineer", category="Backend Engineer", location="New York, NY / US Remote", remote_type="Remote", summary="Build reliable APIs for a collaborative research workspace.", responsibilities=["Design transaction-safe FastAPI services", "Build retrieval and evaluation features", "Test retries and concurrent updates"], required_skills=["Python", "FastAPI", "SQL", "Communication"], pay_min=145000, pay_max=170000, pay_currency="USD", pay_period="year", benefits=["Flexible working hours", "Learning budget", "Health coverage"], confidence=96, warnings=[])
    if output_model is schemas.JobAnalysisOutput:
        return schemas.JobAnalysisOutput(summary="Product engineering role focused on reliable APIs and useful AI features.", responsibilities=["Design service boundaries", "Test critical failure paths", "Collaborate on retrieval workflows"], required_skills=["Python", "FastAPI", "SQL"], preferred_skills=["Observability", "Evaluation"], technologies=["PostgreSQL", "React"], resume_keywords=["transaction safety", "retrieval", "integration testing"], interview_topics=["API reliability", "retrieval evaluation"])
    if output_model is schemas.ResumeSuggestionOutput:
        return schemas.ResumeSuggestionOutput(matched_skills=["Python", "FastAPI", "React", "SQL"], missing_skills=["Observability"], weak_skills=["Evaluation"], keyword_suggestions=["API reliability", "transaction safety"], bullet_suggestions=[], fit_score=86)
    if output_model is schemas.JobInsightsOutput:
        return schemas.JobInsightsOutput(summary="Build reliable product APIs and evidence-grounded research features.", role_focus=["API reliability", "Product engineering"], responsibilities=["Own backend services", "Improve retrieval quality"], must_have_skills=["Python", "FastAPI", "SQL"], nice_to_have_skills=["Evaluation", "Observability"], seniority_signal="Independent ownership with cross-functional collaboration.", concerns=[])
    if output_model is schemas.ResumeFitOutput:
        return schemas.ResumeFitOutput(top_company_fit=["Reliable API delivery", "Evidence-grounded product work"], resume_keywords=["FastAPI", "transactions", "retrieval evaluation"], risks_gaps=["Add a concrete observability example"])
    if output_model is schemas.CompanyResearchOutput:
        return schemas.CompanyResearchOutput(sentiment="positive", summary="The demo company emphasizes small teams, clear ownership, and thoughtful product delivery.", themes=["Engineering ownership", "Collaborative product work"], confidence=78, coverage_note="Illustrative company context for this fictional demonstration.")
    if output_model is schemas.AdvancedInterviewPrepOutput:
        return schemas.AdvancedInterviewPrepOutput(expected_questions=[schemas.AdvancedInterviewQuestion(question="How would you make a retried API request safe?", type="technical", why_it_matters="Tests reliability and transaction design."), schemas.AdvancedInterviewQuestion(question="Describe a product decision you made with incomplete information.", type="behavioral", why_it_matters="Explores communication and judgment.")])
    if output_model is schemas.InterviewQuestionsOutput:
        return schemas.InterviewQuestionsOutput(questions=[schemas.InterviewQuestion(question="Tell me about a time you made an unreliable workflow more dependable.", type="behavioral", why_it_matters="Connects technical decisions to a clear result.", strong_answer_should_include=["The failure mode", "Your specific contribution", "How you verified the result"]), schemas.InterviewQuestion(question="How would you design an idempotent API endpoint?", type="technical", why_it_matters="Explores retry safety and transaction boundaries.", strong_answer_should_include=["Request identity", "Concurrent requests", "Failure recovery"]), schemas.InterviewQuestion(question="How would you evaluate a retrieval assistant before release?", type="technical", why_it_matters="Checks evidence and evaluation judgment.", strong_answer_should_include=["Representative questions", "Grounding", "Failure cases"])])
    if output_model is schemas.InterviewAnswerFeedbackOutput:
        return schemas.InterviewAnswerFeedbackOutput(score=84, what_went_well=["Clear failure mode and a specific technical contribution", "Explained how retries and transactions work together"], what_was_missing=["Add one measured before-and-after result"], suggested_better_answer=ANSWER + " I would close with the observed change in duplicate requests and the test coverage we added.", coaching_notes=["Keep the setup short and spend more time on the result."], evidence_to_add=["A measured reliability improvement"], weak_point_tags=["specific_evidence"], missing_skill_names=[], follow_up_question="")
    raise RuntimeError(f"No external AI calls are allowed in the portfolio demo: {output_model.__name__}")


def demo_resume(output_model, system, payload, **kwargs):
    data = json.loads(payload)
    metadata = {"model": "portfolio-demo", "provider_call": False}
    if data["stage"] == "write":
        claims = data["approved_evidence"]["claims"]
        plan = resume_v6.WriterPlan(bullets=[{"record_id": c["record_id"], "text": c["text"], "evidence_ids": [c["id"]]} for c in claims], skills=["Python", "FastAPI", "SQL", "React", "TypeScript"])
        metadata.update(composition_plan=plan.model_dump(), composition_version=4)
        return resume_v6.compile_plan(plan, data), metadata
    if data["stage"] == "review":
        return resume_v6.Advisory(findings=[{"bullet_id": b["bullet_id"], "verdict": "supported", "explanation": "The wording matches its cited source evidence."} for b in data["bullets"]]), metadata
    raise RuntimeError("Only the current writer and factual-review demo stages are supported.")


ai_service.get_structured_output = demo_output
ai_service.get_tailoring_output = demo_resume
CompanyResearchRetrievalAgent.run = lambda *_: SimpleNamespace(prompt_text=lambda: "Fictional portfolio company context.", warnings=[])
Base.metadata.create_all(get_engine())
manifest = {"fictional": True, "as_of": "2026-10-26", "candidate": "Alex Rivera"}


def checked(response):
    assert response.is_success, (response.status_code, response.text[:1000])
    return response.json()


with TestClient(app) as client:
    profile = checked(client.post("/api/profile", json={"name": "Alex Rivera", "summary": "Software engineer building reliable APIs and thoughtful AI-enabled products.", "target_roles": ["Backend Engineer", "AI/ML Engineer"], "skills": SKILLS, "resume_text": "\n".join(text for _, text, _ in CLAIMS), "experience": [{"company": "Lumen Grove Studio", "role": "Software Engineer", "highlights": [text for record, text, _ in CLAIMS if record == "R-1"]}], "projects": [{"name": "Searchlight", "description": "Evidence-grounded research assistant"}], "education": [{"school": "Lakeview Institute of Technology", "degree": "B.S. Computer Science"}]}))
    resume = checked(client.post("/api/profile/resume-options", json={"title": "Backend & AI engineering", "status": "ready", "summary": "Reliable APIs, accessible interfaces, and evidence-grounded AI features.", "skills": SKILLS, "parsed_text": "\n".join(text for _, text, _ in CLAIMS)}))
    source = checked(client.post("/api/profile/tailoring-sources/import", json=source_bundle()))
    checked(client.post(f"/api/profile/tailoring-sources/{source['id']}/activate", json={"expected_hash": source["bundle_hash"], "expected_active_id": None}))
    companies = ["Cedarline Studio", "Harborlight Systems", "Juniper Works", "Aster Grove", "Northbridge Collective", "Willowstone Labs", "Lumen Harbor", "Pineglass Studio", "Copperleaf Digital", "Orchard Finch", "Meadow Arc", "Papertrail Cloud", "Beacon Birch", "Maple Current", "Cove & Circuit", "Fieldnote Works", "Summit Fern", "Birchline Software", "Slate Orchard", "Clearwater Loop", "Daybreak Grove", "Silverpond Labs", "Mosaic Pines", "Lantern Vale", "Spruce Signal", "Ember Coast", "Redwood Finch", "Driftwood Labs", "Clover Ridge", "Bluebird Circuit", "Stonepath Studio", "Hearthside Cloud"]
    statuses = ["Saved"] * 8 + ["Applied"] * 8 + ["Recruiter Screen"] * 4 + ["Tech Screen"] * 2 + ["Final Interview", "Offer"] + ["Rejected"] * 3 + ["Ghosted"] * 2 + ["Withdrawn"] + ["Archived"] * 2
    stages = ["Saved", "Applied", "Recruiter Screen", "Tech Screen", "Final Interview", "Offer"]
    jobs = []
    for index, (company, status) in enumerate(zip(companies, statuses)):
        role, category = [("Backend Engineer", "Backend Engineer"), ("AI Product Engineer", "AI/ML Engineer"), ("Full Stack Engineer", "Full Stack Engineer"), ("Platform Engineer", "Product/Platform Engineer")][index % 4]
        minimum = [145000, 150000, 135000, 155000][index % 4]
        job = checked(client.post("/api/jobs", json={"company": company, "role_title": role, "category": category, "remote_type": "Hybrid" if index % 3 == 2 else "Remote", "location": "New York, NY" if index % 3 == 2 else "US Remote", "summary": "Build reliable product APIs and research tools with a small, collaborative engineering team.", "responsibilities": ["Design reliable APIs and transaction-safe workflows", "Ship accessible product features", "Evaluate retrieval quality with practical test cases"], "required_skills": ["Python", "FastAPI", "SQL", "Communication"], "pay_min": minimum, "pay_max": minimum + 25000, "pay_currency": "USD", "pay_period": "year", "benefits": ["Health coverage", "Flexible hours", "Learning budget"], "source_content": POSTING.replace("Backend Engineer - Cedarline Studio", f"{role} - {company}").replace("145000-170000", f"{minimum}-{minimum + 25000}"), "extraction_confidence": 94 + index % 4, "links": [{"kind": "source", "label": "Job posting", "url": f"https://{['careers', 'opportunities', 'community'][index % 3]}.example.test/{index+1}"}]}))
        checked(client.patch(f"/api/jobs/{job['id']}", json={"selected_resume_option_id": resume["id"]}))
        rank = stages.index(status) if status in stages else [1, 2, 3][index % 3]
        history = stages[:rank + 1]
        if status not in stages:
            history.append(status)
        for step in history[1:]:
            checked(client.patch(f"/api/jobs/{job['id']}", json={"status": step}))
        checked(client.post(f"/api/ai/run-job-intelligence/{job['id']}"))
        jobs.append(job)
    manifest.update(hero_job_id=jobs[0]["id"], practice_job_id=jobs[9]["id"], posting=POSTING, answer=ANSWER)
    checked(client.post(f"/api/ai/run-advanced-analysis/{jobs[0]['id']}"))
    for index, title, due in [(9, "Follow up after the recruiter conversation", "2026-10-26"), (16, "Prepare examples for the technical interview", "2026-10-27"), (1, "Review the role and tailor my resume", "2026-10-28")]:
        checked(client.put(f"/api/actions/{jobs[index]['id']}", json={"title": title, "due_date": due}))
    for title, ideas, completed in [("API reliability lab", ["Build an idempotent job queue with retry-safe updates", "Add tracing and a failure-recovery dashboard"], ["project:0"]), ("Retrieval evaluation toolkit", ["Create a small benchmark of answerable and unanswerable questions", "Compare retrieval changes with an evidence-quality scorecard"], [])]:
        plan = checked(client.post("/api/study-plans", json={"title": title, "mode": "project_ideas", "timeframe": "2 weeks", "time_budget_hours": 4, "time_budget_unit": "week", "focus_skills": ["Observability", "Evaluation"], "plan": {"top_gaps": ["Observability", "Evaluation"], "priority_order": ["Observability", "Evaluation"], "study_plan": [], "project_ideas": ideas}}))
        checked(client.patch(f"/api/study-plans/{plan['id']}", json={"completed_tasks": completed}))
    for index in range(3):
        practice = checked(client.post("/api/interview/practice-sets", json={"job_id": jobs[9]["id"], "target_category": "Backend Engineer", "target_role": "Backend engineering practice", "count": 3}))
        checked(client.post("/api/interview/answers/evaluate", json={"session_id": practice["session_id"], "question_id": practice["questions"][0]["id"], "answer": ANSWER, "elapsed_seconds": 94 + index * 7, "time_limit_seconds": 120}))
        manifest["practice_session_id"] = practice["session_id"]
    # Authored demo dates make the pipeline, staleness and intake chronology coherent.
    with Session(get_engine()) as db:
        for index, entry in enumerate(jobs):
            record = db.get(models.Job, entry["id"])
            created = AS_OF - timedelta(days=8 + index)
            moved = AS_OF - timedelta(days=15 if index == 9 else 2 + index % 5)
            record.created_at = created if created < moved else moved - timedelta(days=5)
            record.updated_at = moved
            events = sorted(record.status_events, key=lambda event: (event.changed_at, event.id))
            for position, event in enumerate(events):
                event.changed_at = moved - timedelta(days=len(events) - position - 1)
        db.commit()


@app.get("/api/demo/manifest")
def demo_manifest():
    return manifest


if __name__ == "__main__":
    import uvicorn
    print(f"Portfolio-only temporary database: {database}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8120)

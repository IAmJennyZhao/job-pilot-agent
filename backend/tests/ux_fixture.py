"""Disposable, synthetic UI verification server: py tests/ux_fixture.py.

Creates a fresh temporary database. Never reads or changes the user's database.
AI responses are deterministic fixtures; no external AI requests are made.
"""
import os
import sys
import tempfile
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
directory = Path(tempfile.mkdtemp(prefix="job-pilot-synthetic-ux-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(directory / 'synthetic.db').as_posix()}"
os.environ["AUTO_MIGRATE"] = "0"
os.environ["OPENAI_API_KEY"] = "synthetic-ui-key"
os.environ["OPENAI_MODEL"] = "synthetic-ui-model"
os.environ["ASSET_STORAGE_DIR"] = str(directory / "storage")
os.environ["BACKEND_CORS_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:3100"

from fastapi.testclient import TestClient
from app import models, schemas
from app.database import Base, get_engine
from app.main import app
from app.services import ai_service
from generation_fixtures import fake_generation
from letter_fixtures import fake_letter
from app.letter_schemas import LetterDraft, LetterAssessment
from app.generation_schemas import RevisedResume
from app.services.tailoring_provider import ProviderFailure
from test_api import create_job, fake_analysis_output, fake_resume_suggestion_output

ready_for_ui = False
failed_generation_jobs = set()


def fixture_generation(output_model, system, payload, **kwargs):
    import json
    import time
    data = json.loads(payload)
    time.sleep(0.35)
    if output_model in {LetterDraft, LetterAssessment}:
        return fake_letter(output_model, system, payload, **kwargs)
    if output_model is RevisedResume and "SYNTHETIC_FAIL_ONCE" in data["job"]["source_content"] and data["job"]["id"] not in failed_generation_jobs:
        failed_generation_jobs.add(data["job"]["id"])
        raise ProviderFailure("Synthetic provider timeout. Retry explicitly from saved checkpoints.")
    return fake_generation(output_model, system, payload, **kwargs)


ai_service.get_tailoring_output = fixture_generation


@app.middleware("http")
async def optional_ui_latency(request, call_next):
    if ready_for_ui and request.method in {"POST", "PATCH"}:
        await asyncio.sleep(float(os.environ.get("UI_FIXTURE_DELAY", "0")))
    return await call_next(request)


def fake_output(output_model, *_args):
    if output_model is schemas.JobExtractionOutput:
        return schemas.JobExtractionOutput(company="Synthetic Intake Employer", role_title="Backend Engineer", summary="Build APIs.", confidence=90,
            pay_min=100000, pay_max=120000, pay_currency="USD", pay_period="year",
            preference_facts={key: {"value": value, "origin": "posting", "quote": quote} for key, value, quote in [
                ("salary_component", "base", "USD 100000-120000 annual base salary"),
                ("salary_band", "applicable", "NYC salary band"),
                ("nyc_compatible", "yes", "Remote anywhere including NYC"),
                ("required_years", 2, "Minimum 2 years required") ]})
    if output_model is schemas.InterviewQuestionsOutput:
        return schemas.InterviewQuestionsOutput(questions=[
            schemas.InterviewQuestion(question="How would you design a reliable API?", type="technical", why_it_matters="Synthetic test question", strong_answer_should_include=["Retries"]),
            schemas.InterviewQuestion(question="Describe a team project.", type="behavioral", why_it_matters="Synthetic test question", strong_answer_should_include=["Result"]),
            schemas.InterviewQuestion(question="How do you test an API?", type="technical", why_it_matters="Synthetic test question", strong_answer_should_include=["Integration tests"]),
        ])
    if output_model is schemas.JobAnalysisOutput:
        return fake_analysis_output()
    if output_model is schemas.ResumeSuggestionOutput:
        return fake_resume_suggestion_output()
    if output_model is schemas.InterviewAnswerFeedbackOutput:
        return schemas.InterviewAnswerFeedbackOutput(score=80, what_went_well=["Clear structure"],
            what_was_missing=["Add a measured result"], suggested_better_answer="Explain the result of your API work.",
            coaching_notes=["Keep the example concise"], evidence_to_add=["Response latency"],
            weak_point_tags=["specific_evidence"], missing_skill_names=[], follow_up_question="")
    raise RuntimeError("This synthetic verification server does not call external AI services.")


ai_service.get_structured_output = fake_output
Base.metadata.create_all(get_engine())
with TestClient(app) as client:
    profile = client.post('/api/profile', json={'name': 'Synthetic UX Tester', 'resume_text': 'Python FastAPI developer', 'skills': ['Python'], 'target_roles': ['Backend Engineer'], 'experience': [], 'projects': [], 'education': []})
    assert profile.status_code == 201
    for stage in ["Saved", "Applied", "Tech Screen", "Offer"]:
        create_job(client, company=f"Synthetic {stage} Co", status=stage)
    job = create_job(client, company="Synthetic Rejected Co", status="Tech Screen")
    client.post(f"/api/ai/run-job-intelligence/{job['id']}")
    client.patch(f"/api/jobs/{job['id']}", json={"status": "Rejected"})
    for status in ["Ghosted", "Archived", "Withdrawn"]:
        create_job(client, company=f"Synthetic {status} Co", status=status)
    for title in ['Synthetic Resume A', 'Synthetic Resume B']:
        assert client.post('/api/profile/resume-options', json={'title': title, 'status': 'draft', 'parsed_text': 'Synthetic Python developer', 'skills': ['Python'], 'experience': [{'company': 'Synthetic Company', 'role': 'Engineer', 'highlights': ['Built a demo']}]}).status_code == 201
    assert client.post('/api/profile/cover-letter-templates', json={'title': 'Synthetic Letter', 'body': 'Hello synthetic hiring team'}).status_code == 201
    assert client.post('/api/study-plans', json={'title': 'Synthetic Study Plan', 'timeframe': '1 week', 'plan': {'top_gaps': ['Python'], 'priority_order': ['Python'], 'study_plan': [{'period': 'Week 1', 'focus': 'Practice', 'tasks': ['Build an API', 'Write tests']}], 'project_ideas': ['Ship a demo']}}).status_code == 201
    assert client.post('/api/interview/practice-sets', json={'target_category': 'Backend Engineer', 'target_role': 'Synthetic Platform Engineer', 'count': 3}).status_code == 201

print(f"Synthetic UI verification database: {directory}", flush=True)
ready_for_ui = True
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get("UI_FIXTURE_PORT", "8000")))

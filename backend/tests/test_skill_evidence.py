from app import schemas
from app.services import ai_service
from test_api import create_profile, create_job, fake_analysis_output, fake_resume_suggestion_output


def test_skill_evidence_links_to_matching_job(client, monkeypatch):
    create_profile(client)
    job = create_job(client)
    monkeypatch.setattr(ai_service, "get_structured_output", lambda model, *_: fake_analysis_output() if model is schemas.JobAnalysisOutput else fake_resume_suggestion_output())
    assert client.post(f"/api/ai/run-job-intelligence/{job['id']}").status_code == 200
    gaps = client.get('/api/skill-gaps').json()
    gap = next(gap for gap in gaps if gap['skill_name'] == 'LangChain')
    evidence = client.get(f"/api/skill-gaps/{gap['id']}/evidence")
    assert evidence.status_code == 200
    assert evidence.json() == [{'label': f"{job['company']} — {job['role_title']}", 'href': f"/jobs/{job['id']}", 'source': 'Resume match'}]
    assert client.get('/api/skill-gaps/missing/evidence').status_code == 404


def test_skill_priority_counts_unique_open_jobs_not_repeat_mentions(client, monkeypatch):
    create_profile(client)
    job = create_job(client)
    monkeypatch.setattr(ai_service, "get_structured_output", lambda model, *_: fake_analysis_output() if model is schemas.JobAnalysisOutput else fake_resume_suggestion_output())
    for _ in range(3):
        assert client.post(f"/api/ai/run-job-intelligence/{job['id']}").status_code == 200
    gap = next(row for row in client.get('/api/skill-gaps').json() if row['skill_name'] == 'LangChain')
    assert gap['count'] >= 3
    assert gap['active_job_count'] == 1
    assert gap['priority'] == 'low'
    client.patch(f"/api/jobs/{job['id']}", json={'status': 'Rejected'})
    gap = next(row for row in client.get('/api/skill-gaps').json() if row['skill_name'] == 'LangChain')
    assert gap['active_job_count'] == 0


def test_active_skill_evidence_includes_manual_job_requirements(client, monkeypatch):
    create_profile(client)
    analyzed = create_job(client)
    monkeypatch.setattr(ai_service, "get_structured_output", lambda model, *_: fake_analysis_output() if model is schemas.JobAnalysisOutput else fake_resume_suggestion_output())
    client.post(f"/api/ai/run-job-intelligence/{analyzed['id']}")
    manual = create_job(client, company="Manual requirements", required_skills=['LangChain'])
    gap = next(row for row in client.get('/api/skill-gaps').json() if row['skill_name'] == 'LangChain')
    assert gap['active_job_count'] == 2
    sources = client.get(f"/api/skill-gaps/{gap['id']}/evidence").json()
    assert any(source['href'] == f"/jobs/{manual['id']}" for source in sources)

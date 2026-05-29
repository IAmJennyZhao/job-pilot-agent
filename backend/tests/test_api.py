from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.services import ai_service


def job_payload(**overrides):
    payload = {
        "company": "Acme AI",
        "role_title": "Applied AI Engineer",
        "category": "AI/ML Engineer",
        "location": "Remote",
        "remote_type": "Remote",
        "summary": "Build FastAPI and React AI tools.",
        "responsibilities": ["Build APIs", "Ship React dashboards"],
        "required_skills": ["Python", "FastAPI", "React"],
        "pay_min": 120000,
        "pay_max": 160000,
        "pay_currency": "USD",
        "pay_period": "year",
        "pay_raw": "$120k-$160k base",
        "benefits": ["Health insurance", "Remote work"],
        "source_content": "Build FastAPI and React AI tools with OpenAI APIs.",
        "links": [{"kind": "source", "label": "Job Posting", "url": "https://example.com/job"}],
        "notes": "Looks promising.",
        "extraction_confidence": 91,
        "extraction_warnings": [],
    }
    payload.update(overrides)
    return payload


def create_job(client, **overrides):
    response = client.post("/api/jobs", json=job_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def create_profile(client):
    response = client.post(
        "/api/profile",
        json={
            "name": "Test User",
            "target_roles": ["Applied AI Engineer"],
            "resume_text": "Python, FastAPI, React, OpenAI API.",
            "summary": "AI product engineer.",
            "skills": ["Python", "FastAPI", "React"],
            "projects": [],
            "experience": [],
            "education": [],
            "certifications": [],
        },
    )
    assert response.status_code == 201
    return response.json()


def fake_extraction_output():
    return schemas.JobExtractionOutput(
        company="Acme AI",
        role_title="Applied AI Engineer",
        category=models.JobCategory.ai_ml_engineer,
        location="Remote",
        remote_type="Remote",
        summary="Build AI job search tools.",
        responsibilities=["Build APIs", "Create dashboards"],
        required_skills=["Python", "FastAPI", "React"],
        pay_min=120000,
        pay_max=160000,
        pay_currency="USD",
        pay_period="year",
        pay_raw=None,
        benefits=["Health insurance", "Remote work stipend"],
        links=[
            schemas.JobLinkBase(
                kind=models.JobLinkKind.company_portal,
                label="Company portal",
                url="https://example.com/careers",
            )
        ],
        confidence=88,
        warnings=["Compensation was not listed."],
    )


def fake_job_insights_output():
    return schemas.JobInsightsOutput(
        summary="Applied AI role with product engineering expectations.",
        role_focus=["LLM product features", "API delivery"],
        responsibilities=["Build AI features", "Own backend services"],
        must_have_skills=["Python", "FastAPI", "React"],
        nice_to_have_skills=["Evaluation", "Vector search"],
        seniority_signal="Mid-level to senior ownership language.",
        concerns=["Broad AI platform scope"],
    )


def fake_company_research_output():
    return schemas.CompanyResearchOutput(
        sentiment="mixed",
        summary="Employees highlight strong technical work with some execution pressure.",
        themes=["Strong engineering culture", "Fast pace"],
        source_links=[schemas.SourceLink(title="Employee reviews", url="https://example.com/reviews")],
        confidence=74,
        coverage_note="Public review coverage is limited.",
    )


def fake_resume_fit_output():
    return schemas.ResumeFitOutput(
        top_company_fit=["AI product engineering", "FastAPI services"],
        resume_keywords=["LLM features", "evaluation", "React"],
        risks_gaps=["Cloud deployment depth"],
    )


def fake_advanced_interview_output():
    return schemas.AdvancedInterviewPrepOutput(
        expected_questions=[
            schemas.AdvancedInterviewQuestion(
                question="How would you evaluate an LLM feature before launch?",
                type="technical",
                why_it_matters="The role expects production AI judgment.",
            )
        ]
    )


def fake_analysis_output():
    return schemas.JobAnalysisOutput(
        summary="AI platform role.",
        responsibilities=["Build APIs"],
        required_skills=["Python", "FastAPI"],
        preferred_skills=["LangChain"],
        technologies=["FastAPI", "Vector search"],
        resume_keywords=["AI", "FastAPI"],
        interview_topics=["API design"],
    )


def fake_resume_suggestion_output():
    return schemas.ResumeSuggestionOutput(
        matched_skills=["Python"],
        missing_skills=["LangChain", "AWS Bedrock"],
        weak_skills=["System design"],
        keyword_suggestions=["agentic workflows"],
        bullet_suggestions=[
            schemas.BulletSuggestion(
                original="Built APIs.",
                suggested="Built FastAPI services for AI workflows.",
                reason="Highlights role-relevant backend AI work.",
            )
        ],
        fit_score=72,
    )


def test_extract_preview_from_pasted_content(client, monkeypatch):
    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        assert output_model is schemas.JobExtractionOutput
        return fake_extraction_output()

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(
        "/api/jobs/extract-preview",
        json={
            "source_url": "https://example.com/job",
            "source_content": "We need Python, FastAPI, and React.",
        },
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["company"] == "Acme AI"
    assert preview["category"] == "AI/ML Engineer"
    assert preview["source_content"] == "We need Python, FastAPI, and React."
    assert preview["links"][0]["kind"] == "source"
    assert preview["links"][0]["label"] == "Job Posting"
    assert preview["links"] == [{"kind": "source", "label": "Job Posting", "url": "https://example.com/job"}]
    assert preview["pay_min"] == 120000
    assert preview["pay_max"] == 160000
    assert preview["pay_currency"] == "USD"
    assert preview["pay_period"] == "year"
    assert preview["benefits"] == ["Health insurance", "Remote work stipend"]
    assert preview["duplicate_candidates"] == []


def test_extract_preview_fetches_url_content(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_intake_service.fetch_job_page_text",
        lambda _url: "Fetched posting content with Python and FastAPI.",
    )

    def fake_structured_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.JobExtractionOutput
        assert "Fetched posting content" in user_prompt
        return fake_extraction_output()

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post("/api/jobs/extract-preview", json={"source_url": "https://example.com/job"})
    assert response.status_code == 200
    preview = response.json()
    assert "fetched from the URL" in preview["warnings"][0]
    assert preview["source_content"] == "Fetched posting content with Python and FastAPI."


def test_extract_preview_failure_allows_manual_create(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key=None, openai_model="gpt-5-mini", openai_research_model=None),
    )

    response = client.post(
        "/api/jobs/extract-preview",
        json={"source_content": "Manual fallback should still be possible."},
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]

    job = create_job(
        client,
        company="Manual Co",
        role_title="Backend Engineer",
        category="Backend Engineer",
        extraction_confidence=None,
        extraction_warnings=["Manual fallback was used."],
    )
    assert job["company"] == "Manual Co"
    assert job["status_events"][0]["to_status"] == "Saved"


def test_extract_preview_reports_duplicate_candidates(client, monkeypatch):
    create_job(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        assert output_model is schemas.JobExtractionOutput
        return fake_extraction_output()

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(
        "/api/jobs/extract-preview",
        json={"source_url": "https://example.com/job", "source_content": "Duplicate posting."},
    )

    assert response.status_code == 200
    duplicates = response.json()["duplicate_candidates"]
    assert len(duplicates) == 1
    assert set(duplicates[0]["matched_on"]) == {"company_role", "url"}


def test_job_status_history_search_filter_and_archive(client):
    job = create_job(client)
    other = create_job(
        client,
        company="Data Tools",
        role_title="Data Engineer",
        category="Data Engineer",
        links=[
            {"kind": "source", "label": "Job Posting", "url": "https://example.com/data"},
            {"kind": "company_info", "label": "Company Info", "url": "https://example.com/about"},
        ],
    )
    assert job["pay_raw"] == "$120k-$160k base"
    assert job["benefits"] == ["Health insurance", "Remote work"]
    assert other["links"][1]["kind"] == "company_info"

    response = client.patch(f"/api/jobs/{job['id']}", json={"status": "Applied", "status_note": "Applied on portal."})
    assert response.status_code == 200
    assert response.json()["status"] == "Applied"

    response = client.get(f"/api/jobs/{job['id']}")
    detail = response.json()
    assert [event["to_status"] for event in detail["status_events"]] == ["Saved", "Applied"]
    assert detail["status_events"][1]["note"] == "Applied on portal."

    response = client.get("/api/jobs?search=data")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [other["id"]]

    response = client.get("/api/jobs?category=AI%2FML+Engineer")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [job["id"]]

    response = client.patch(f"/api/jobs/{other['id']}", json={"status": "Archived"})
    assert response.status_code == 200

    response = client.get("/api/jobs")
    assert all(item["status"] != "Archived" for item in response.json())

    response = client.get("/api/jobs?include_archived=true")
    assert any(item["status"] == "Archived" for item in response.json())


def test_profile_dashboard_and_skill_gap(client):
    profile = create_profile(client)
    create_job(client)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["total_jobs"] == 1
    assert dashboard["archived_jobs"] == 0
    assert dashboard["by_status"]["Saved"] == 1
    assert dashboard["by_status"]["Withdrawn"] == 0
    assert set(dashboard["by_status"]) == {
        "Saved",
        "Applied",
        "Recruiter Screen",
        "Tech Screen",
        "Final Interview",
        "Offer",
        "Rejected",
        "Withdrawn",
        "Archived",
    }

    response = client.get("/api/skill-gaps")
    assert response.status_code == 200
    assert response.json() == []

    response = client.patch(f"/api/profile/{profile['id']}", json={"skills": ["Python", "SQL"]})
    assert response.status_code == 200
    assert response.json()["skills"] == ["Python", "SQL"]


def test_job_list_top_gaps_sources(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    response = client.get("/api/jobs")
    listed_job = response.json()[0]
    assert listed_job["top_gaps"] == ["Python", "FastAPI", "React"]
    assert listed_job["top_gaps_source"] == "analysis"

    def fake_suggestion(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.ResumeSuggestionOutput:
            return fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_suggestion)

    response = client.post(f"/api/ai/suggest-resume/{job['id']}")
    assert response.status_code == 200

    response = client.get("/api/jobs")
    listed_job = response.json()[0]
    assert listed_job["top_gaps"] == ["LangChain", "AWS Bedrock", "System design"]
    assert listed_job["top_gaps_source"] == "resume_match"


def test_ai_config_requires_key_and_model(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key=None, openai_model="gpt-5-mini", openai_research_model=None),
    )
    with pytest.raises(HTTPException) as missing_key:
        ai_service.get_structured_output(schemas.JobAnalysisOutput, "system", "user")
    assert missing_key.value.status_code == 503
    assert "OPENAI_API_KEY" in missing_key.value.detail

    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key="sk-test", openai_model=None, openai_research_model="gpt-5-mini"),
    )
    with pytest.raises(HTTPException) as missing_model:
        ai_service.get_structured_output(schemas.JobAnalysisOutput, "system", "user")
    assert missing_model.value.status_code == 503
    assert "OPENAI_MODEL" in missing_model.value.detail

    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key="sk-test", openai_model="gpt-5-mini", openai_research_model=None),
    )
    with pytest.raises(HTTPException) as missing_research_model:
        ai_service.get_research_structured_output(schemas.CompanyResearchOutput, "system", "user")
    assert missing_research_model.value.status_code == 503
    assert "OPENAI_RESEARCH_MODEL" in missing_research_model.value.detail


def test_ai_readiness_reports_missing_requirements(client, monkeypatch):
    job = create_job(client)
    response = client.post(
        "/api/profile",
        json={
            "name": "Incomplete User",
            "target_roles": [],
            "resume_text": "",
            "summary": None,
            "skills": [],
            "projects": [],
            "experience": [],
            "education": [],
            "certifications": [],
        },
    )
    assert response.status_code == 201
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key=None, openai_model=None, openai_research_model=None),
    )

    response = client.get(f"/api/ai/readiness/{job['id']}")
    assert response.status_code == 200
    readiness = response.json()
    assert readiness["ready"] is False
    assert readiness["model"] is None
    assert readiness["research_model"] is None
    assert readiness["has_openai_research_model"] is False
    assert "openai_api_key" not in readiness
    assert set(readiness["missing_requirements"]) == {
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "Resume text",
        "Skills",
    }


def test_run_job_intelligence_completes_and_persists(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return fake_analysis_output()
        if output_model is schemas.ResumeSuggestionOutput:
            return fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/run-job-intelligence/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "complete"
    assert result["analysis"]["summary"] == "AI platform role."
    assert result["resume_suggestion"]["fit_score"] == 72
    assert result["errors"] == []

    response = client.get(f"/api/jobs/{job['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["analysis"]["required_skills"] == ["Python", "FastAPI"]
    assert detail["latest_resume_suggestion"]["missing_skills"] == ["LangChain", "AWS Bedrock"]
    assert detail["fit_score"] == 72


def test_run_job_intelligence_partial_failure_keeps_analysis(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return fake_analysis_output()
        if output_model is schemas.ResumeSuggestionOutput:
            raise HTTPException(status_code=502, detail="Resume match failed")
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/run-job-intelligence/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "partial"
    assert result["analysis"]["summary"] == "AI platform role."
    assert result["resume_suggestion"] is None
    assert result["errors"] == ["Resume match failed"]

    response = client.get(f"/api/jobs/{job['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["analysis"]["technologies"] == ["FastAPI", "Vector search"]
    assert detail["latest_resume_suggestion"] is None


def test_run_advanced_analysis_persists_sections_and_company_research(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobInsightsOutput:
            return fake_job_insights_output()
        if output_model is schemas.ResumeFitOutput:
            return fake_resume_fit_output()
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr(
        "app.services.ai_service.get_research_structured_output",
        lambda output_model, _system_prompt, _user_prompt: fake_company_research_output()
        if output_model is schemas.CompanyResearchOutput
        else None,
    )

    response = client.post(f"/api/ai/run-advanced-analysis/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "complete"
    assert result["company_research"]["normalized_company_name"] == "acme ai"
    assert result["analysis"]["job_insights"]["must_have_skills"] == ["Python", "FastAPI", "React"]
    assert result["analysis"]["company_sentiment"]["sentiment"] == "mixed"
    assert result["analysis"]["top_company_fit"] == ["AI product engineering", "FastAPI services"]
    assert result["analysis"]["expected_questions"][0]["type"] == "technical"

    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert detail["latest_advanced_analysis"]["resume_keywords"] == ["LLM features", "evaluation", "React"]


def test_advanced_analysis_reuses_company_research_for_same_company(client, monkeypatch):
    first = create_job(client)
    second = create_job(
        client,
        role_title="AI Platform Engineer",
        links=[{"kind": "source", "label": "Job Posting", "url": "https://example.com/job-two"}],
    )
    create_profile(client)
    research_calls = 0

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobInsightsOutput:
            return fake_job_insights_output()
        if output_model is schemas.ResumeFitOutput:
            return fake_resume_fit_output()
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        raise AssertionError("Unexpected model")

    def fake_research_output(output_model, _system_prompt, _user_prompt):
        nonlocal research_calls
        assert output_model is schemas.CompanyResearchOutput
        research_calls += 1
        return fake_company_research_output()

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr("app.services.ai_service.get_research_structured_output", fake_research_output)

    assert client.post(f"/api/ai/run-advanced-analysis/{first['id']}").status_code == 200
    assert client.post(f"/api/ai/run-advanced-analysis/{second['id']}").status_code == 200
    assert research_calls == 1

    assert client.post(f"/api/ai/run-advanced-analysis/{second['id']}?refresh_company=true").status_code == 200
    assert research_calls == 2


def test_advanced_analysis_partial_when_research_model_missing(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobInsightsOutput:
            return fake_job_insights_output()
        if output_model is schemas.ResumeFitOutput:
            return fake_resume_fit_output()
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(
            openai_api_key="sk-test",
            openai_model="gpt-5-mini",
            openai_research_model=None,
        ),
    )

    response = client.post(f"/api/ai/run-advanced-analysis/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "partial"
    assert result["company_research"] is None
    assert result["analysis"]["job_insights"]["summary"] == "Applied AI role with product engineering expectations."
    assert result["analysis"]["company_sentiment"] is None
    assert any("OPENAI_RESEARCH_MODEL" in error for error in result["errors"])


def test_interview_session_and_message(client):
    job = create_job(client)
    profile = create_profile(client)
    response = client.post(
        "/api/interview/sessions",
        json={"job_id": job["id"], "resume_profile_id": profile["id"], "mode": "question_list"},
    )
    assert response.status_code == 201
    session = response.json()

    response = client.post(
        f"/api/interview/sessions/{session['id']}/messages",
        json={"role": "ai", "content": "Tell me about your FastAPI work.", "question_type": "technical"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "ai"

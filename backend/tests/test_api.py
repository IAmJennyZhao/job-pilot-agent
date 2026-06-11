import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from app import models, schemas
from app.database import _ensure_skill_gaps_merged
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
        responsibility_highlights=["AI features"],
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
        highlight_phrases=["technical work"],
        source_links=[schemas.SourceLink(title="Employee reviews", url="https://example.com/reviews")],
        confidence=74,
        coverage_note="Public review coverage is limited.",
    )


def fake_resume_fit_output():
    return schemas.ResumeFitOutput(
        top_company_fit=["AI product engineering", "FastAPI services"],
        fit_highlights=["AI product"],
        resume_keywords=["LLM features", "evaluation", "React"],
        risks_gaps=["Cloud deployment depth"],
        gap_highlights=["Cloud deployment"],
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


def fake_resume_parse_output():
    return schemas.ResumeParseOutput(
        name="Resume User",
        target_roles=["Applied AI Engineer"],
        target_keywords=["FastAPI", "LLM APIs"],
        summary="Applied AI engineer with backend experience.",
        skills=["Python", "FastAPI", "OpenAI API"],
        skill_groups=[schemas.SkillGroup(category="Backend", skills=["Python", "FastAPI"])],
        projects=[
            schemas.ProjectItem(
                name="CareerPilot",
                description="AI job search workspace.",
                technologies=["FastAPI", "React"],
                bullets=["Built resume matching flows."],
            )
        ],
        experience=[
            schemas.ExperienceItem(
                company="Acme",
                role_title="Software Engineer",
                bullets=["Built FastAPI services."],
            )
        ],
        education=[schemas.EducationItem(school="State University", degree="BS")],
        certifications=["OpenAI API project"],
    )


def test_resume_pdf_import_confirm_merge_and_template_crud(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.profile_asset_service.extract_pdf_text",
        lambda _path: "Python FastAPI OpenAI API resume text.",
    )
    monkeypatch.setattr(
        "app.services.profile_asset_service.parse_resume_text",
        lambda _text: fake_resume_parse_output(),
    )

    response = client.post(
        "/api/profile/resume-options/import",
        files={"file": ("applied-ai.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 201
    option = response.json()
    assert option["title"] == "applied-ai"
    assert option["status"] == "draft"
    assert option["candidate_name"] == "Resume User"
    assert option["skill_groups"] == [{"category": "Backend", "skills": ["Python", "FastAPI"]}]

    response = client.get(f"/api/profile/resume-options/{option['id']}/download")
    assert response.status_code == 200

    response = client.post(
        f"/api/profile/resume-options/{option['id']}/confirm",
        json={"merge_into_profile": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

    profile = client.get("/api/profile").json()
    assert profile["name"] == "Resume User"
    assert profile["skills"] == ["Python", "FastAPI", "OpenAI API"]
    assert profile["experience"][0]["company"] == "Acme"

    response = client.post(
        "/api/profile/cover-letter-templates",
        json={
            "title": "Applied AI Template",
            "target_roles": ["Applied AI Engineer"],
            "target_keywords": ["FastAPI"],
            "body": "I build applied AI products.",
        },
    )
    assert response.status_code == 201
    template = response.json()

    response = client.patch(
        f"/api/profile/cover-letter-templates/{template['id']}",
        json={"target_keywords": ["FastAPI", "OpenAI API"], "notes": "Primary AI template"},
    )
    assert response.status_code == 200
    assert response.json()["target_keywords"] == ["FastAPI", "OpenAI API"]

    response = client.get("/api/profile/cover-letter-templates")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [template["id"]]

    assert client.delete(f"/api/profile/cover-letter-templates/{template['id']}").status_code == 204
    assert client.delete(f"/api/profile/resume-options/{option['id']}").status_code == 204


def test_job_intelligence_ranks_assets_and_saves_selection(client, monkeypatch):
    profile = create_profile(client)
    job = create_job(client, required_skills=["LangChain", "FastAPI"], source_content="Need LangChain and FastAPI.")

    response = client.post(
        "/api/profile/resume-options",
        json={
            "title": "AI Platform Resume",
            "status": "ready",
            "parsed_text": "LangChain resume option text with FastAPI services.",
            "summary": "AI platform engineer.",
            "target_roles": ["AI Platform Engineer"],
            "target_keywords": ["LangChain", "FastAPI"],
            "skills": ["LangChain", "FastAPI"],
            "skill_groups": [{"category": "AI", "skills": ["LangChain"]}],
            "projects": [],
            "experience": [],
            "education": [],
            "certifications": [],
        },
    )
    assert response.status_code == 201
    resume_option = response.json()

    response = client.post(
        "/api/profile/cover-letter-templates",
        json={
            "title": "AI Platform Cover",
            "target_roles": ["AI Platform Engineer"],
            "target_keywords": ["LangChain", "FastAPI"],
            "body": "I connect LangChain systems with FastAPI services.",
        },
    )
    assert response.status_code == 201
    template = response.json()

    def fake_structured_output(output_model, _system_prompt, user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return schemas.JobAnalysisOutput(
                summary="AI platform role.",
                responsibilities=["Build AI services"],
                required_skills=["LangChain", "FastAPI"],
                preferred_skills=[],
                technologies=["LangChain"],
                resume_keywords=["LangChain", "FastAPI"],
                interview_topics=["AI services"],
            )
        if output_model is schemas.ResumeSuggestionOutput:
            assert "LangChain resume option text" in user_prompt
            return fake_resume_suggestion_output()
        if output_model is schemas.AIAssetRankingOutput:
            return schemas.AIAssetRankingOutput(
                resume_rankings=[
                    schemas.AssetRanking(
                        asset_id=resume_option["id"],
                        title="AI Platform Resume",
                        score=91,
                        matched_keywords=["LangChain"],
                        reasons=["Best AI platform match"],
                    )
                ],
                cover_letter_rankings=[
                    schemas.AssetRanking(
                        asset_id=template["id"],
                        title="AI Platform Cover",
                        score=88,
                        matched_keywords=["FastAPI"],
                        reasons=["Best template match"],
                    )
                ],
            )
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/run-job-intelligence/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["asset_recommendation"]["resume_rankings"][0]["asset_id"] == resume_option["id"]
    assert result["asset_recommendation"]["cover_letter_rankings"][0]["asset_id"] == template["id"]
    assert result["resume_suggestion"]["fit_score"] == 72

    response = client.patch(
        f"/api/jobs/{job['id']}",
        json={
            "selected_resume_option_id": resume_option["id"],
            "selected_cover_letter_template_id": template["id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["selected_resume_option_id"] == resume_option["id"]

    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert detail["selected_cover_letter_template_id"] == template["id"]
    assert detail["latest_asset_recommendation"]["source"] == "keyword"

    response = client.post(f"/api/ai/rank-assets/{job['id']}")
    assert response.status_code == 200
    assert response.json()["source"] == "ai"
    assert response.json()["resume_rankings"][0]["score"] == 91

    devops = create_job(
        client,
        company="Infra Co",
        role_title="DevOps Engineer",
        category="DevOps/Infrastructure",
        required_skills=["Kubernetes"],
        source_content="Run Kubernetes infrastructure.",
    )
    response = client.get(f"/api/jobs/{devops['id']}")
    assert response.status_code == 200
    response = client.post("/api/profile/coverage-gaps")
    assert response.status_code == 200
    gaps = response.json()["gaps"]
    assert any(gap["title"] == "DevOps/Infrastructure resume option" for gap in gaps)

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


def test_extract_preview_compacts_repeated_and_soft_skill_output(client, monkeypatch):
    def fake_structured_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.JobExtractionOutput
        assert "Required skills must be technical only" in user_prompt
        return schemas.JobExtractionOutput(
            company="Acme AI",
            role_title="Applied AI Engineer",
            category=models.JobCategory.ai_ml_engineer,
            location="Remote",
            remote_type="Remote",
            summary="Build AI job search tools with product and platform ownership across several teams.",
            responsibilities=["Build APIs", "Build APIs", "Ship React dashboards"],
            required_skills=[
                "Python",
                "Strong collaboration and communication skills",
                "FastAPI",
                "Python",
            ],
            benefits=["Health insurance", "Health insurance"],
            confidence=88,
            warnings=[],
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(
        "/api/jobs/extract-preview",
        json={"source_content": "We need Python, FastAPI, and React."},
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["responsibilities"] == ["Build APIs", "Ship React dashboards"]
    assert preview["required_skills"] == ["Python", "FastAPI"]
    assert preview["benefits"] == ["Health insurance"]


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
        lambda: SimpleNamespace(openai_api_key=None, openai_model="gpt-5-mini", tavily_api_key=None),
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
    assert job["pay_annual_min"] == 120000
    assert job["pay_annual_max"] == 160000
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
    ghosted = create_job(
        client,
        company="Silent Co",
        role_title="Frontend Engineer",
        category="Frontend Engineer",
        status="Ghosted",
    )

    response = client.get("/api/jobs")
    assert all(item["status"] not in {"Archived", "Ghosted"} for item in response.json())

    response = client.get("/api/jobs?include_archived=true")
    statuses = {item["id"]: item["status"] for item in response.json()}
    assert statuses[other["id"]] == "Archived"
    assert statuses[ghosted["id"]] == "Ghosted"


def test_profile_dashboard_and_skill_gap(client):
    profile = create_profile(client)
    create_job(client)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["total_jobs"] == 1
    assert dashboard["archived_jobs"] == 0
    assert dashboard["ghosted_jobs"] == 0
    assert dashboard["by_status"]["Saved"] == 1
    assert dashboard["by_status"]["Withdrawn"] == 0
    assert dashboard["by_status"]["Ghosted"] == 0
    assert dashboard["health"]["active_jobs"] == 1
    assert dashboard["health"]["missing_data"] == 1
    assert dashboard["sankey"]["nodes"]
    assert set(dashboard["by_status"]) == {
        "Saved",
        "Applied",
        "Recruiter Screen",
        "Tech Screen",
        "Final Interview",
        "Offer",
        "Rejected",
        "Withdrawn",
        "Ghosted",
        "Archived",
    }

    response = client.get("/api/skill-gaps")
    assert response.status_code == 200
    assert response.json() == []

    response = client.patch(f"/api/profile/{profile['id']}", json={"skills": ["Python", "SQL"]})
    assert response.status_code == 200
    assert response.json()["skills"] == ["Python", "SQL"]


def test_dashboard_implied_sankey_collapses_regressions_and_branches_terminal(client):
    regressed = create_job(client, company="Loop Co", role_title="Platform Engineer")
    base_time = datetime.now(timezone.utc).replace(microsecond=0)

    response = client.post(
        f"/api/jobs/{regressed['id']}/status-events",
        json={"to_status": "Tech Screen", "changed_at": (base_time + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 200
    response = client.post(
        f"/api/jobs/{regressed['id']}/status-events",
        json={"to_status": "Applied", "changed_at": (base_time + timedelta(days=2)).isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Applied"

    ghosted = create_job(client, company="Silent Co", role_title="Backend Engineer", status="Ghosted")

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    dashboard = response.json()
    links = {(link["source"], link["target"]): link["value"] for link in dashboard["sankey"]["links"]}
    assert links[("Saved", "Applied")] >= 1
    assert links[("Applied", "Recruiter Screen")] >= 1
    assert links[("Recruiter Screen", "Tech Screen")] >= 1
    assert ("Tech Screen", "Applied") not in links
    assert links[("Saved", "Ghosted")] >= 1
    assert dashboard["ghosted_jobs"] == 1
    assert dashboard["by_status"]["Ghosted"] == 1

    response = client.get("/api/jobs")
    assert all(item["id"] != ghosted["id"] for item in response.json())


def test_dashboard_stage_based_stale_thresholds(client):
    stale_saved = create_job(client, company="Old Saved", role_title="AI Engineer")
    fresh_applied = create_job(client, company="Fresh Applied", role_title="AI Engineer")
    now = datetime.now(timezone.utc).replace(microsecond=0)

    response = client.patch(
        f"/api/jobs/{stale_saved['id']}/status-events/{stale_saved['status_events'][0]['id']}",
        json={"changed_at": (now - timedelta(days=8)).isoformat()},
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/jobs/{fresh_applied['id']}/status-events",
        json={"to_status": "Applied", "changed_at": (now - timedelta(days=13)).isoformat()},
    )
    assert response.status_code == 200

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    stale_ids = {item["id"] for item in response.json()["search_health"]["stale_jobs"]}
    assert stale_saved["id"] in stale_ids
    assert fresh_applied["id"] not in stale_ids

    response = client.get("/api/jobs?health_filter=stale")
    assert response.status_code == 200
    stale_filter_ids = {item["id"] for item in response.json()}
    assert stale_saved["id"] in stale_filter_ids
    assert fresh_applied["id"] not in stale_filter_ids


def test_dashboard_health_counts_are_not_limited_to_visible_insights(client):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for index in range(7):
        job = create_job(client, company=f"Stale Missing {index}", role_title="AI Engineer")
        response = client.patch(
            f"/api/jobs/{job['id']}/status-events/{job['status_events'][0]['id']}",
            json={"changed_at": (now - timedelta(days=8)).isoformat()},
        )
        assert response.status_code == 200

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["health"]["stale_jobs"] == 7
    assert dashboard["health"]["missing_data"] == 7
    assert len(dashboard["search_health"]["stale_jobs"]) == 6
    assert len(dashboard["search_health"]["missing_data"]) == 6


def test_jobs_missing_data_filter_and_dashboard_count_unique_jobs(client, monkeypatch):
    create_profile(client)
    complete = create_job(client, company="Complete Co", role_title="Analyzed Engineer")
    missing = create_job(
        client,
        company="Missing Co",
        role_title="Incomplete Engineer",
        pay_min=None,
        pay_max=None,
        pay_raw=None,
        extraction_confidence=45,
    )
    ghosted = create_job(
        client,
        company="Hidden Missing Co",
        role_title="Silent Engineer",
        pay_min=None,
        pay_max=None,
        pay_raw=None,
        extraction_confidence=20,
        status="Ghosted",
    )

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return fake_analysis_output()
        if output_model is schemas.ResumeSuggestionOutput:
            return fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/run-job-intelligence/{complete['id']}")
    assert response.status_code == 200

    response = client.get("/api/jobs?health_filter=missing_data")
    assert response.status_code == 200
    missing_ids = {item["id"] for item in response.json()}
    assert missing["id"] in missing_ids
    assert complete["id"] not in missing_ids
    assert ghosted["id"] not in missing_ids

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["health"]["missing_data"] == 1
    assert [item["id"] for item in dashboard["search_health"]["missing_data"]] == [missing["id"]]


def test_dashboard_needs_analysis_is_limited_and_progression_prioritized(client):
    saved = create_job(client, company="Saved Co", role_title="Saved Engineer", status="Saved")
    applied = create_job(client, company="Applied Co", role_title="Applied Engineer", status="Applied")
    recruiter = create_job(client, company="Recruiter Co", role_title="Recruiter Engineer", status="Recruiter Screen")
    tech = create_job(client, company="Tech Co", role_title="Tech Engineer", status="Tech Screen")

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    needs_analysis_ids = [item["id"] for item in response.json()["search_health"]["needs_analysis"]]
    assert needs_analysis_ids == [tech["id"], recruiter["id"], applied["id"]]
    assert saved["id"] not in needs_analysis_ids


def test_dashboard_skill_gaps_are_active_opportunity_weighted(client, monkeypatch):
    create_profile(client)
    matched = create_job(client, company="Matched Co", role_title="AI Engineer")
    fallback = create_job(
        client,
        company="Fallback Co",
        role_title="AI Platform Engineer",
        required_skills=["LangChain", "FastAPI"],
    )
    ghosted = create_job(
        client,
        company="Ghosted Co",
        role_title="ML Engineer",
        required_skills=["Kubernetes"],
        status="Ghosted",
    )

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return fake_analysis_output()
        if output_model is schemas.ResumeSuggestionOutput:
            return fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/run-job-intelligence/{matched['id']}")
    assert response.status_code == 200

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    gaps = response.json()["top_skill_gaps"]
    assert gaps[0]["skill_name"] == "LangChain"
    assert gaps[0]["count"] == 2
    assert gaps[0]["source"] == "resume_match"
    assert all(gap["skill_name"] != "Kubernetes" for gap in gaps)
    assert response.json()["ghosted_jobs"] == 1
    assert all(job["status"] != "Ghosted" for gap in gaps for job in gap["affected_jobs"])


def run_intelligence_with_fakes(client, monkeypatch, resume_suggestion_output=None):
    job = create_job(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return fake_analysis_output()
        if output_model is schemas.ResumeSuggestionOutput:
            return resume_suggestion_output or fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    response = client.post(f"/api/ai/run-job-intelligence/{job['id']}")
    assert response.status_code == 200
    return job


def test_skill_gaps_merge_sources_and_derive_priority(client, monkeypatch):
    create_profile(client)
    suggestion = fake_resume_suggestion_output().model_copy(
        update={"missing_skills": ["FastAPI", "LangChain"], "weak_skills": []}
    )
    run_intelligence_with_fakes(client, monkeypatch, resume_suggestion_output=suggestion)

    gaps = {gap["skill_name"]: gap for gap in client.get("/api/skill-gaps").json()}
    # FastAPI appears twice in the analysis output (required skill + technology) and once
    # in the resume match: one row, batch-deduped, with both sources.
    assert sorted(gaps) == ["FastAPI", "LangChain", "Python", "Vector search"]
    fastapi = gaps["FastAPI"]
    assert fastapi["count"] == 2
    assert fastapi["sources"] == ["resume_match", "job_analysis"]
    assert fastapi["priority"] == "medium"
    assert fastapi["suggested_action"] == "Build proof or study plan for: FastAPI"
    assert gaps["Python"]["sources"] == ["job_analysis"]
    assert gaps["Python"]["count"] == 1
    assert gaps["Python"]["priority"] == "low"


def test_skill_gap_patch_ignores_priority_and_count(client, monkeypatch):
    create_profile(client)
    run_intelligence_with_fakes(client, monkeypatch)

    gap = client.get("/api/skill-gaps").json()[0]
    response = client.patch(
        f"/api/skill-gaps/{gap['id']}",
        json={"priority": "high", "count": 99, "user_level": "medium"},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["priority"] == gap["priority"]
    assert updated["count"] == gap["count"]
    assert updated["user_level"] == "medium"


def test_study_plan_excludes_known_skills(client, monkeypatch):
    create_profile(client)
    run_intelligence_with_fakes(client, monkeypatch)

    gaps = client.get("/api/skill-gaps").json()
    langchain = next(gap for gap in gaps if gap["skill_name"] == "LangChain")
    response = client.patch(f"/api/skill-gaps/{langchain['id']}", json={"user_level": "high"})
    assert response.status_code == 200

    captured = {}

    def fake_plan_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.StudyPlanResponse
        captured["prompt"] = user_prompt
        return schemas.StudyPlanResponse(top_gaps=[], priority_order=[], study_plan=[], project_ideas=[])

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_plan_output)
    response = client.post("/api/ai/generate-study-plan", json={"timeframe": "2 weeks"})
    assert response.status_code == 200
    assert "LangChain" not in captured["prompt"]
    assert "AWS Bedrock" in captured["prompt"]


def test_study_plan_honors_focus_skills_mode_and_time_budget(client, monkeypatch):
    create_profile(client)
    run_intelligence_with_fakes(client, monkeypatch)

    captured = {}

    def fake_plan_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.StudyPlanResponse
        captured["prompt"] = user_prompt
        return schemas.StudyPlanResponse(top_gaps=[], priority_order=[], study_plan=[], project_ideas=[])

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_plan_output)
    response = client.post(
        "/api/ai/generate-study-plan",
        json={
            "timeframe": "2 weeks",
            "focus_skills": ["LangChain"],
            "time_budget_hours": 3,
            "time_budget_unit": "week",
            "mode": "project_ideas",
        },
    )
    assert response.status_code == 200
    prompt = captured["prompt"]
    assert "LangChain" in prompt
    # Non-selected gaps are excluded from the gap payload (resume text doesn't mention these).
    assert "AWS Bedrock" not in prompt
    assert "Vector search" not in prompt
    assert "Cover ONLY these skills" in prompt
    assert "3 hours available per week" in prompt
    assert "Return an empty study_plan list" in prompt
    assert "Week 1, Week 2" in prompt

    # Weekly-plan mode flips the instruction; 1 week timeframe flips period granularity.
    response = client.post(
        "/api/ai/generate-study-plan",
        json={"timeframe": "1 week", "mode": "weekly_plan"},
    )
    assert response.status_code == 200
    assert "Return an empty project_ideas list" in captured["prompt"]
    assert "Day 1, Day 2" in captured["prompt"]


def test_saved_study_plan_crud(client):
    plan_payload = {
        "title": "LangChain sprint",
        "timeframe": "2 weeks",
        "time_budget_hours": 3,
        "time_budget_unit": "week",
        "mode": "both",
        "focus_skills": ["LangChain"],
        "plan": {
            "top_gaps": ["LangChain"],
            "priority_order": ["LangChain"],
            "study_plan": [{"period": "Week 1", "focus": "LangChain basics", "tasks": ["Do the tutorial"]}],
            "project_ideas": ["Build a RAG demo"],
        },
    }

    response = client.post("/api/study-plans", json=plan_payload)
    assert response.status_code == 404  # no profile yet

    profile = create_profile(client)
    response = client.post("/api/study-plans", json=plan_payload)
    assert response.status_code == 201
    saved = response.json()
    assert saved["title"] == "LangChain sprint"
    assert saved["resume_profile_id"] == profile["id"]
    assert saved["focus_skills"] == ["LangChain"]
    assert saved["plan"]["study_plan"][0]["period"] == "Week 1"

    response = client.post("/api/study-plans", json={**plan_payload, "title": "Second plan"})
    assert response.status_code == 201

    response = client.get("/api/study-plans")
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == 2
    assert {plan["title"] for plan in plans} == {"LangChain sprint", "Second plan"}

    response = client.patch(f"/api/study-plans/{saved['id']}", json={"title": "Renamed sprint"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed sprint"

    response = client.delete(f"/api/study-plans/{saved['id']}")
    assert response.status_code == 204
    response = client.delete(f"/api/study-plans/{saved['id']}")
    assert response.status_code == 404

    response = client.get("/api/study-plans")
    assert [plan["title"] for plan in response.json()] == ["Second plan"]


def test_dashboard_skill_gaps_exclude_known_skills(client, monkeypatch):
    create_profile(client)
    create_job(
        client,
        company="Fallback Co",
        role_title="AI Platform Engineer",
        required_skills=["LangChain", "FastAPI"],
    )
    run_intelligence_with_fakes(client, monkeypatch)

    gaps = client.get("/api/skill-gaps").json()
    langchain = next(gap for gap in gaps if gap["skill_name"] == "LangChain")
    response = client.patch(f"/api/skill-gaps/{langchain['id']}", json={"user_level": "high"})
    assert response.status_code == 200

    dashboard = client.get("/api/dashboard/summary").json()
    top_gaps = dashboard["top_skill_gaps"]
    assert top_gaps
    assert all(gap["skill_name"] != "LangChain" for gap in top_gaps)


def test_startup_migration_merges_duplicate_skill_gap_rows():
    engine = create_engine("sqlite://", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE skill_gaps (
                    id VARCHAR(36) NOT NULL,
                    resume_profile_id VARCHAR(36) NOT NULL,
                    skill_name VARCHAR(255) NOT NULL,
                    source VARCHAR(32) NOT NULL,
                    count INTEGER NOT NULL,
                    priority VARCHAR(32) NOT NULL,
                    user_level VARCHAR(32) NOT NULL,
                    suggested_action TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        old_rows = [
            ("gap-1", "profile-1", "LangChain", "job_analysis", 2, "medium", "unknown",
             "Review job requirement: LangChain", "2026-01-01 10:00:00", "2026-01-02 10:00:00"),
            ("gap-2", "profile-1", "langchain", "resume_match", 1, "low", "medium",
             "Build proof or study plan for: langchain", "2026-01-03 10:00:00", "2026-01-04 10:00:00"),
            ("gap-3", "profile-1", "Kubernetes", "interview_feedback", 1, "low", "unknown",
             "Practice interview answer for: Kubernetes", "2026-01-05 10:00:00", "2026-01-05 10:00:00"),
            ("gap-4", "profile-2", "LangChain", "job_analysis", 1, "low", "unknown",
             "Review job requirement: LangChain", "2026-01-06 10:00:00", "2026-01-06 10:00:00"),
        ]
        for row in old_rows:
            connection.execute(
                text(
                    "INSERT INTO skill_gaps VALUES (:id, :profile, :skill, :source, :count,"
                    " :priority, :user_level, :action, :created_at, :updated_at)"
                ),
                dict(zip(
                    ["id", "profile", "skill", "source", "count", "priority", "user_level",
                     "action", "created_at", "updated_at"],
                    row,
                )),
            )
        _ensure_skill_gaps_merged(connection)

    with engine.connect() as connection:
        rows = {
            (row["resume_profile_id"], row["skill_name"]): row
            for row in connection.execute(text("SELECT * FROM skill_gaps")).mappings()
        }
    assert len(rows) == 3

    merged = rows[("profile-1", "LangChain")]
    assert merged["id"] == "gap-1"
    assert merged["count"] == 3
    assert json.loads(merged["sources"]) == ["resume_match", "job_analysis"]
    assert merged["priority"] == "high"
    assert merged["user_level"] == "medium"
    assert merged["suggested_action"] == "Build proof or study plan for: langchain"
    assert merged["created_at"] == "2026-01-01 10:00:00"
    assert merged["updated_at"] == "2026-01-04 10:00:00"

    other_profile = rows[("profile-2", "LangChain")]
    assert json.loads(other_profile["sources"]) == ["job_analysis"]
    assert other_profile["priority"] == "low"

    # Re-running must be a no-op now that the table is in the new shape.
    with engine.begin() as connection:
        _ensure_skill_gaps_merged(connection)
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM skill_gaps")).scalar_one()
    assert count == 3


def test_job_list_top_gaps_sources(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    response = client.get("/api/jobs")
    listed_job = response.json()[0]
    assert listed_job["top_gaps"] == ["Python", "FastAPI", "React"]
    assert listed_job["top_gaps_source"] == "analysis"

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return fake_analysis_output()
        if output_model is schemas.ResumeSuggestionOutput:
            return fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/run-job-intelligence/{job['id']}")
    assert response.status_code == 200

    response = client.get("/api/jobs")
    listed_job = response.json()[0]
    assert listed_job["top_gaps"] == ["LangChain", "AWS Bedrock", "System design"]
    assert listed_job["top_gaps_source"] == "resume_match"


def test_pay_annualization_for_non_yearly_periods(client):
    hourly = create_job(
        client,
        pay_min=50,
        pay_max=75,
        pay_period="hour",
        pay_raw=None,
    )
    assert hourly["pay_annual_min"] == 104000
    assert hourly["pay_annual_max"] == 156000
    assert "40 hours/week" in hourly["pay_conversion_note"]

    response = client.patch(
        f"/api/jobs/{hourly['id']}",
        json={"pay_min": 9000, "pay_max": 12000, "pay_period": "month", "pay_raw": None},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["pay_annual_min"] == 108000
    assert updated["pay_annual_max"] == 144000
    assert "12 months/year" in updated["pay_conversion_note"]

    unknown = create_job(client, pay_min=3000, pay_max=5000, pay_period="contract", pay_raw="$3k-$5k contract")
    assert unknown["pay_annual_min"] is None
    assert unknown["pay_annual_max"] is None
    assert unknown["pay_conversion_note"] is None


def test_status_event_hard_edit_add_delete_reconciles_current_status(client):
    job = create_job(client)
    base_time = datetime.now(timezone.utc).replace(microsecond=0)

    response = client.post(
        f"/api/jobs/{job['id']}/status-events",
        json={
            "to_status": "Applied",
            "changed_at": (base_time + timedelta(days=1)).isoformat(),
            "note": "Applied on portal.",
        },
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "Applied"
    applied_event = detail["status_events"][-1]
    assert applied_event["from_status"] == "Saved"

    response = client.post(
        f"/api/jobs/{job['id']}/status-events",
        json={
            "to_status": "Tech Screen",
            "changed_at": (base_time + timedelta(days=3)).isoformat(),
            "note": "Wrong stage.",
        },
    )
    assert response.status_code == 200
    tech_event = response.json()["status_events"][-1]

    response = client.patch(
        f"/api/jobs/{job['id']}/status-events/{tech_event['id']}",
        json={
            "to_status": "Recruiter Screen",
            "changed_at": (base_time + timedelta(days=2)).isoformat(),
            "note": "Corrected stage.",
        },
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "Recruiter Screen"
    assert [event["to_status"] for event in detail["status_events"]] == ["Saved", "Applied", "Recruiter Screen"]
    assert detail["status_events"][2]["from_status"] == "Applied"
    assert detail["status_events"][2]["note"] == "Corrected stage."

    response = client.delete(f"/api/jobs/{job['id']}/status-events/{tech_event['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "Applied"
    assert [event["to_status"] for event in detail["status_events"]] == ["Saved", "Applied"]


def test_ai_config_requires_key_and_model(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key=None, openai_model="gpt-5-mini", tavily_api_key=None),
    )
    with pytest.raises(HTTPException) as missing_key:
        ai_service.get_structured_output(schemas.JobAnalysisOutput, "system", "user")
    assert missing_key.value.status_code == 503
    assert "OPENAI_API_KEY" in missing_key.value.detail

    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key="sk-test", openai_model=None, tavily_api_key="tvly-test"),
    )
    with pytest.raises(HTTPException) as missing_model:
        ai_service.get_structured_output(schemas.JobAnalysisOutput, "system", "user")
    assert missing_model.value.status_code == 503
    assert "OPENAI_MODEL" in missing_model.value.detail


def test_openai_client_ignores_inherited_proxy_env(monkeypatch):
    clients = []

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            clients.append(self)

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return None

    class FakeResponses:
        def parse(self, **kwargs):
            assert kwargs["model"] == "gpt-test"
            assert kwargs["text_format"] is schemas.JobAnalysisOutput
            return SimpleNamespace(output_parsed=fake_analysis_output())

    class FakeOpenAI:
        def __init__(self, api_key, http_client):
            assert api_key == "sk-test"
            assert http_client is clients[0]
            self.responses = FakeResponses()

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(openai_api_key="sk-test", openai_model="gpt-test", tavily_api_key=None),
    )
    monkeypatch.setattr(ai_service.httpx, "Client", FakeHttpClient)
    monkeypatch.setattr(ai_service, "OpenAI", FakeOpenAI)

    output = ai_service.get_structured_output(schemas.JobAnalysisOutput, "system", "user")

    assert output.summary == "AI platform role."
    assert clients[0].kwargs["trust_env"] is False
    assert clients[0].kwargs["timeout"] == ai_service.OPENAI_TIMEOUT_SECONDS


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
        lambda: SimpleNamespace(openai_api_key=None, openai_model=None, tavily_api_key=None),
    )

    response = client.get(f"/api/ai/readiness/{job['id']}")
    assert response.status_code == 200
    readiness = response.json()
    assert readiness["ready"] is False
    assert readiness["model"] is None
    assert readiness["has_tavily_api_key"] is False
    assert "openai_api_key" not in readiness
    assert set(readiness["missing_requirements"]) == {
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "Resume text",
        "Skills",
    }


def test_removed_legacy_ai_endpoints_return_not_found(client):
    job = create_job(client)

    removed_requests = [
        ("post", f"/api/ai/analyze-job/{job['id']}", {}),
        ("post", f"/api/ai/suggest-resume/{job['id']}", {}),
        ("post", f"/api/ai/generate-interview-questions/{job['id']}", {"question_type": "mixed", "count": 1}),
        (
            "post",
            "/api/ai/evaluate-interview-answer",
            {"job_id": job["id"], "question": "Question?", "answer": "Answer."},
        ),
    ]

    for method, path, payload in removed_requests:
        response = getattr(client, method)(path, json=payload)
        assert response.status_code == 404


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
        if output_model is schemas.CompanyResearchOutput:
            return fake_company_research_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr(
        "app.services.advanced_analysis_service.CompanyResearchRetrievalAgent.run",
        lambda _self, _company, _role_title: SimpleNamespace(
            prompt_text=lambda: "Review source text.",
            warnings=[],
        ),
    )

    response = client.post(f"/api/ai/run-advanced-analysis/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "complete"
    assert result["company_research"]["normalized_company_name"] == "acme ai"
    assert result["analysis"]["job_insights"]["must_have_skills"] == ["Python", "FastAPI", "React"]
    assert result["analysis"]["company_sentiment"]["sentiment"] == "mixed"
    assert result["analysis"]["company_sentiment"]["highlight_phrases"] == ["technical work"]
    assert result["analysis"]["top_company_fit"] == ["AI product engineering", "FastAPI services"]
    assert result["analysis"]["highlight_phrases"] == {
        "responsibilities": ["AI features"],
        "fit": ["AI product"],
        "gaps": ["Cloud deployment"],
    }
    assert result["company_research"]["highlight_phrases"] == ["technical work"]
    assert result["analysis"]["expected_questions"][0]["type"] == "technical"

    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert detail["latest_advanced_analysis"]["resume_keywords"] == ["LLM features", "evaluation", "React"]


def test_advanced_analysis_compacts_duplicate_and_soft_skill_output(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, user_prompt):
        if output_model is schemas.JobInsightsOutput:
            assert "must_have_skills and nice_to_have_skills: technical" in user_prompt
            return schemas.JobInsightsOutput(
                summary="Applied AI role with product engineering expectations and repeated collaboration language.",
                role_focus=[
                    "LLM product ownership",
                    "Cross-functional collaboration with stakeholders",
                ],
                responsibilities=[
                    "Build and deploy applied AI solutions for enterprise use cases across product workflows",
                    "Build and deploy applied AI solutions for enterprise use cases across product workflows",
                    "Own backend services that support real-time user-facing automation",
                ],
                responsibility_highlights=["applied AI solutions", "backend services"],
                must_have_skills=[
                    "Python",
                    "Strong collaboration and communication skills",
                    "FastAPI",
                    "Python",
                ],
                nice_to_have_skills=["FastAPI", "Vector search"],
                seniority_signal="Mid-level ownership language with lots of implementation scope.",
                concerns=["Broad AI platform scope", "Broad AI platform scope"],
            )
        if output_model is schemas.ResumeFitOutput:
            return schemas.ResumeFitOutput(
                top_company_fit=[
                    "AI product engineering for support automation teams",
                    "AI product engineering for support automation teams",
                ],
                fit_highlights=["AI product engineering"],
                resume_keywords=["LLM features", "LLM features", "React"],
                risks_gaps=[
                    "Cloud deployment depth for production AI services",
                    "Cloud deployment depth for production AI services",
                ],
                gap_highlights=["Cloud deployment"],
            )
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        if output_model is schemas.CompanyResearchOutput:
            return schemas.CompanyResearchOutput(
                sentiment="mixed",
                summary="Employees mention strong technical work and fast execution pressure across teams.",
                themes=["Fast pace", "Fast pace", "Strong engineering culture"],
                highlight_phrases=["technical work", "engineering culture"],
                source_links=[],
                confidence=74,
                coverage_note="Public review coverage is limited but usable for directional signals.",
            )
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr(
        "app.services.advanced_analysis_service.CompanyResearchRetrievalAgent.run",
        lambda _self, _company, _role_title: SimpleNamespace(
            prompt_text=lambda: "Review source text.",
            warnings=[],
        ),
    )

    response = client.post(f"/api/ai/run-advanced-analysis/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    insights = result["analysis"]["job_insights"]
    assert insights["responsibilities"] == [
        "Build and deploy applied AI solutions for enterprise use cases across product workflows",
        "Own backend services that support real-time user-facing automation",
    ]
    assert insights["must_have_skills"] == ["Python", "FastAPI"]
    assert insights["nice_to_have_skills"] == ["Vector search"]
    assert insights["concerns"] == ["Broad AI platform scope"]
    assert result["analysis"]["highlight_phrases"] == {
        "responsibilities": ["applied AI solutions"],
        "fit": ["AI product engineering"],
        "gaps": ["Cloud deployment"],
    }
    assert result["analysis"]["top_company_fit"] == ["AI product engineering for support automation teams"]
    assert result["analysis"]["risks_gaps"] == ["Cloud deployment depth for production AI services"]
    assert result["analysis"]["resume_keywords"] == ["LLM features", "React"]
    assert result["company_research"]["themes"] == ["Fast pace", "Strong engineering culture"]
    assert result["company_research"]["highlight_phrases"] == ["technical work", "engineering culture"]
    narrative_items = [
        *insights["responsibilities"],
        *result["analysis"]["top_company_fit"],
        *result["analysis"]["risks_gaps"],
        result["company_research"]["summary"],
        *result["company_research"]["themes"],
    ]
    assert all("..." not in item for item in narrative_items)


def test_advanced_analysis_reuses_company_research_for_same_company(client, monkeypatch):
    first = create_job(client)
    second = create_job(
        client,
        role_title="AI Platform Engineer",
        links=[{"kind": "source", "label": "Job Posting", "url": "https://example.com/job-two"}],
    )
    create_profile(client)
    retrieval_calls = 0

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobInsightsOutput:
            return fake_job_insights_output()
        if output_model is schemas.ResumeFitOutput:
            return fake_resume_fit_output()
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        if output_model is schemas.CompanyResearchOutput:
            return fake_company_research_output()
        raise AssertionError("Unexpected model")

    def fake_retrieval(_self, _company, _role_title):
        nonlocal retrieval_calls
        retrieval_calls += 1
        return SimpleNamespace(prompt_text=lambda: "Review source text.", warnings=[])

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr("app.services.advanced_analysis_service.CompanyResearchRetrievalAgent.run", fake_retrieval)

    first_response = client.post(f"/api/ai/run-advanced-analysis/{first['id']}")
    assert first_response.status_code == 200
    second_response = client.post(f"/api/ai/run-advanced-analysis/{second['id']}")
    assert second_response.status_code == 200
    assert retrieval_calls == 1
    assert second_response.json()["analysis"]["company_sentiment"]["highlight_phrases"] == ["technical work"]

    assert client.post(f"/api/ai/run-advanced-analysis/{second['id']}?refresh_company=true").status_code == 200
    assert retrieval_calls == 2


def test_advanced_analysis_uses_limited_company_research_without_tavily(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobInsightsOutput:
            return fake_job_insights_output()
        if output_model is schemas.ResumeFitOutput:
            return fake_resume_fit_output()
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        if output_model is schemas.CompanyResearchOutput:
            return fake_company_research_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)
    monkeypatch.setattr(
        "app.services.advanced_analysis_service.CompanyResearchRetrievalAgent.run",
        lambda _self, _company, _role_title: SimpleNamespace(
            prompt_text=lambda: "No public web snippets were retrieved.",
            warnings=["TAVILY_API_KEY is not configured; company research used limited context only."],
        ),
    )

    response = client.post(f"/api/ai/run-advanced-analysis/{job['id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "complete"
    assert result["company_research"]["sentiment"] == "mixed"
    assert result["analysis"]["job_insights"]["summary"] == "Applied AI role with product engineering expectations."
    assert "TAVILY_API_KEY" in result["company_research"]["coverage_note"]
    assert result["errors"] == []


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


def test_standalone_role_practice_set_creates_session_without_job(client, monkeypatch):
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.InterviewQuestionsOutput
        assert "Backend Engineer" in user_prompt
        assert "API Platform Engineer" in user_prompt
        assert "tech_screen" in user_prompt
        return schemas.InterviewQuestionsOutput(
            questions=[
                schemas.InterviewQuestion(
                    question="How would you design a resilient API integration?",
                    type="system_design",
                    why_it_matters="Tests backend design judgment.",
                    strong_answer_should_include=["Retries", "Idempotency", "Observability"],
                )
            ]
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(
        "/api/interview/practice-sets",
        json={
            "target_category": "Backend Engineer",
            "target_role": "API Platform Engineer",
            "stage": "tech_screen",
            "question_type": "system_design",
            "count": 1,
        },
    )

    assert response.status_code == 201
    practice_set = response.json()
    assert practice_set["job_id"] is None
    assert practice_set["target_category"] == "Backend Engineer"
    assert practice_set["target_role"] == "API Platform Engineer"
    assert practice_set["generated_count"] == 1
    assert practice_set["questions"][0]["source"] == "generated"

    sessions = client.get("/api/interview/sessions").json()
    assert sessions[0]["job_id"] is None
    assert sessions[0]["target_category"] == "Backend Engineer"
    assert sessions[0]["stage"] == "tech_screen"


def test_practice_set_reuses_advanced_questions_then_generates_remainder(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_advanced_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobInsightsOutput:
            return fake_job_insights_output()
        if output_model is schemas.ResumeFitOutput:
            return fake_resume_fit_output()
        if output_model is schemas.AdvancedInterviewPrepOutput:
            return fake_advanced_interview_output()
        if output_model is schemas.CompanyResearchOutput:
            return fake_company_research_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_advanced_output)
    monkeypatch.setattr(
        "app.services.advanced_analysis_service.CompanyResearchRetrievalAgent.run",
        lambda _self, _company, _role_title: SimpleNamespace(
            prompt_text=lambda: "Review source text.",
            warnings=[],
        ),
    )
    assert client.post(f"/api/ai/run-advanced-analysis/{job['id']}").status_code == 200

    def fake_practice_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.InterviewQuestionsOutput
        assert "Already-used questions" in user_prompt
        return schemas.InterviewQuestionsOutput(
            questions=[
                schemas.InterviewQuestion(
                    question="How would you monitor model quality after launch?",
                    type="technical",
                    why_it_matters="Tests production ownership.",
                    strong_answer_should_include=["Metrics", "Feedback loops"],
                ),
                schemas.InterviewQuestion(
                    question="Tell me about a time you changed direction based on evaluation data.",
                    type="behavioral",
                    why_it_matters="Tests evidence-driven iteration.",
                    strong_answer_should_include=["Situation", "Data", "Outcome"],
                ),
            ]
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_practice_output)

    response = client.post(
        "/api/interview/practice-sets",
        json={
            "job_id": job["id"],
            "stage": "mixed",
            "question_type": "mixed",
            "count": 3,
        },
    )

    assert response.status_code == 201
    practice_set = response.json()
    assert practice_set["reused_count"] == 1
    assert practice_set["generated_count"] == 2
    assert practice_set["questions"][0]["source"] == "advanced_analysis"
    assert practice_set["questions"][0]["content"] == "How would you evaluate an LLM feature before launch?"


def test_practice_answer_feedback_follow_up_insights_and_skill_gaps(client, monkeypatch):
    create_profile(client)

    def fake_question_output(output_model, _system_prompt, _user_prompt):
        assert output_model is schemas.InterviewQuestionsOutput
        return schemas.InterviewQuestionsOutput(
            questions=[
                schemas.InterviewQuestion(
                    question="How do you approach production incident debugging?",
                    type="technical",
                    why_it_matters="Tests operational judgment.",
                    strong_answer_should_include=["Triage", "Instrumentation", "Prevention"],
                )
            ]
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_question_output)
    response = client.post(
        "/api/interview/practice-sets",
        json={
            "target_category": "DevOps/Infrastructure",
            "target_role": "Platform Engineer",
            "stage": "tech_screen",
            "question_type": "technical",
            "count": 1,
        },
    )
    assert response.status_code == 201
    practice_set = response.json()
    question_id = practice_set["questions"][0]["id"]

    def fake_feedback_output(output_model, _system_prompt, user_prompt):
        assert output_model is schemas.InterviewAnswerFeedbackOutput
        assert "Platform Engineer" in user_prompt
        return schemas.InterviewAnswerFeedbackOutput(
            score=62,
            what_went_well=["Clear first step"],
            what_was_missing=["Needs stronger incident structure"],
            suggested_better_answer="I would start by scoping impact, then inspect telemetry and rollback options.",
            coaching_notes=["Use a tighter STAR structure."],
            evidence_to_add=["Mention a concrete monitoring or rollback example."],
            weak_point_tags=["answer_structure", "missing_skill"],
            missing_skill_names=["Incident response"],
            follow_up_question="Walk through a real incident and the metric that confirmed recovery.",
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_feedback_output)
    response = client.post(
        "/api/interview/answers/evaluate",
        json={
            "session_id": practice_set["session_id"],
            "question_id": question_id,
            "answer": "I would check logs and fix the issue.",
        },
    )

    assert response.status_code == 200
    feedback = response.json()
    assert feedback["score"] == 62
    assert feedback["follow_up_question_id"]
    assert feedback["follow_up"]["source"] == "follow_up"
    assert feedback["weak_point_tags"] == ["answer_structure", "missing_skill"]

    insights = client.get("/api/interview/insights").json()
    assert insights["average_score"] == 62
    assert [item["tag"] for item in insights["weak_points"]] == ["answer_structure", "missing_skill"]
    assert insights["coaching_themes"] == ["Use a tighter STAR structure."]
    recent_score = insights["recent_scores"][0]
    assert recent_score["message_id"]
    assert recent_score["session_id"] == practice_set["session_id"]
    assert recent_score["question_id"] == question_id
    assert recent_score["question"] == "How do you approach production incident debugging?"
    assert recent_score["answer"] == "I would check logs and fix the issue."
    assert recent_score["feedback"]["what_was_missing"] == ["Needs stronger incident structure"]
    assert recent_score["created_at"]
    assert recent_score["weak_point_tags"] == ["answer_structure", "missing_skill"]
    for weak_point in insights["weak_points"]:
        assert weak_point["examples"]
        assert all(weak_point["tag"] in example["weak_point_tags"] for example in weak_point["examples"])
    assert insights["trends"]["overall"][0]["score"] == 62
    assert insights["trends"]["knowledge"][0]["score"] == 62
    assert insights["trends"]["interview_skills"][0]["score"] == 62

    skill_gaps = client.get("/api/skill-gaps").json()
    assert [gap["skill_name"] for gap in skill_gaps] == ["Incident response"]


def test_resume_session_returns_only_unanswered_questions(client, monkeypatch):
    create_profile(client)

    def fake_question_output(output_model, _system_prompt, _user_prompt):
        assert output_model is schemas.InterviewQuestionsOutput
        return schemas.InterviewQuestionsOutput(
            questions=[
                schemas.InterviewQuestion(
                    question="How do you approach production incident debugging?",
                    type="technical",
                    why_it_matters="Tests operational judgment.",
                    strong_answer_should_include=["Triage", "Instrumentation", "Prevention"],
                ),
                schemas.InterviewQuestion(
                    question="Tell me about a time you mentored a teammate.",
                    type="behavioral",
                    why_it_matters="Tests leadership.",
                    strong_answer_should_include=["Situation", "Action", "Result"],
                ),
            ]
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_question_output)
    response = client.post(
        "/api/interview/practice-sets",
        json={
            "target_category": "DevOps/Infrastructure",
            "target_role": "Platform Engineer",
            "stage": "tech_screen",
            "question_type": "technical",
            "count": 2,
        },
    )
    assert response.status_code == 201
    practice_set = response.json()
    session_id = practice_set["session_id"]
    first_question_id = practice_set["questions"][0]["id"]
    second_question_id = practice_set["questions"][1]["id"]

    def fake_feedback_output(output_model, _system_prompt, _user_prompt):
        assert output_model is schemas.InterviewAnswerFeedbackOutput
        return schemas.InterviewAnswerFeedbackOutput(
            score=80,
            what_went_well=["Clear structure"],
            what_was_missing=[],
            suggested_better_answer="Looks solid.",
            coaching_notes=[],
            evidence_to_add=[],
            weak_point_tags=[],
            missing_skill_names=[],
            follow_up_question="What metric proved the incident was resolved?",
        )

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_feedback_output)
    response = client.post(
        "/api/interview/answers/evaluate",
        json={
            "session_id": session_id,
            "question_id": first_question_id,
            "answer": "I would scope impact, inspect telemetry, and roll back if needed.",
        },
    )
    assert response.status_code == 200
    follow_up_id = response.json()["follow_up_question_id"]
    assert follow_up_id

    response = client.get(f"/api/interview/sessions/{session_id}/resume")
    assert response.status_code == 200
    resume = response.json()
    assert resume["session_id"] == session_id
    resumed_ids = {question["id"] for question in resume["questions"]}
    assert resumed_ids == {second_question_id, follow_up_id}
    assert resume["reused_count"] == len(resume["questions"])
    assert resume["generated_count"] == 0

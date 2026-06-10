from datetime import datetime, timedelta, timezone
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

    def fake_suggestion(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.ResumeSuggestionOutput:
            return fake_resume_suggestion_output()
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_suggestion)

    response = client.post(f"/api/ai/suggest-resume/{matched['id']}")
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

    skill_gaps = client.get("/api/skill-gaps").json()
    assert [gap["skill_name"] for gap in skill_gaps] == ["Incident response"]

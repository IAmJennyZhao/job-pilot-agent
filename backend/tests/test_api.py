from app import schemas


def create_job(client):
    response = client.post(
        "/api/jobs",
        json={
            "company": "Acme AI",
            "role_title": "Applied AI Engineer",
            "job_url": "https://example.com/job",
            "job_description": "Build FastAPI and React AI tools with OpenAI APIs.",
            "notes": "Looks promising.",
        },
    )
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


def test_job_crud_and_archive(client):
    job = create_job(client)

    response = client.patch(f"/api/jobs/{job['id']}", json={"status": "Applied"})
    assert response.status_code == 200
    assert response.json()["status"] == "Applied"

    response = client.delete(f"/api/jobs/{job['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "Archived"

    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/api/jobs?include_archived=true")
    assert response.status_code == 200
    archived_jobs = response.json()
    assert len(archived_jobs) == 1
    assert archived_jobs[0]["status"] == "Archived"

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    assert response.json()["total_jobs"] == 0
    assert response.json()["archived_jobs"] == 1

    response = client.patch(f"/api/jobs/{job['id']}", json={"status": "Saved"})
    assert response.status_code == 200
    assert response.json()["status"] == "Saved"

    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_profile_dashboard_and_skill_gap(client):
    profile = create_profile(client)
    create_job(client)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["total_jobs"] == 1
    assert dashboard["archived_jobs"] == 0
    assert dashboard["by_status"]["Saved"] == 1
    assert dashboard["by_status"]["Archived"] == 0
    assert set(dashboard["by_status"]) == {
        "Saved",
        "Resume Tailored",
        "Applied",
        "Recruiter Screen",
        "Tech Screen",
        "Final Interview",
        "Offer",
        "Rejected",
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

    def fake_analysis(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return schemas.JobAnalysisOutput(
                summary="AI platform role.",
                responsibilities=["Build APIs"],
                required_skills=["Python", "FastAPI"],
                preferred_skills=["LangChain"],
                technologies=["FastAPI", "Vector search"],
                resume_keywords=["AI", "FastAPI"],
                interview_topics=["API design"],
            )
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_analysis)

    response = client.post(f"/api/ai/analyze-job/{job['id']}")
    assert response.status_code == 200

    response = client.get("/api/jobs")
    assert response.status_code == 200
    listed_job = response.json()[0]
    assert listed_job["top_gaps"] == ["Python", "FastAPI", "Vector search"]
    assert listed_job["top_gaps_source"] == "analysis"

    def fake_suggestion(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.ResumeSuggestionOutput:
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
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_suggestion)

    response = client.post(f"/api/ai/suggest-resume/{job['id']}")
    assert response.status_code == 200

    response = client.get("/api/jobs")
    assert response.status_code == 200
    listed_job = response.json()[0]
    assert listed_job["top_gaps"] == ["LangChain", "AWS Bedrock", "System design"]
    assert listed_job["top_gaps_source"] == "resume_match"


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


def test_ai_endpoint_saves_mocked_analysis(client, monkeypatch):
    job = create_job(client)
    create_profile(client)

    def fake_structured_output(output_model, _system_prompt, _user_prompt):
        if output_model is schemas.JobAnalysisOutput:
            return schemas.JobAnalysisOutput(
                summary="AI platform role.",
                responsibilities=["Build APIs"],
                required_skills=["Python"],
                preferred_skills=["LangChain"],
                technologies=["FastAPI"],
                resume_keywords=["AI", "FastAPI"],
                interview_topics=["API design"],
            )
        raise AssertionError("Unexpected model")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake_structured_output)

    response = client.post(f"/api/ai/analyze-job/{job['id']}")
    assert response.status_code == 200
    assert response.json()["summary"] == "AI platform role."

    response = client.get(f"/api/jobs/{job['id']}")
    assert response.status_code == 200
    assert response.json()["analysis"]["required_skills"] == ["Python"]

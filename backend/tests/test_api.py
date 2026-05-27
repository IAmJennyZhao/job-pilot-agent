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


def test_profile_dashboard_and_skill_gap(client):
    profile = create_profile(client)
    create_job(client)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    assert response.json()["total_jobs"] == 1

    response = client.get("/api/skill-gaps")
    assert response.status_code == 200
    assert response.json() == []

    response = client.patch(f"/api/profile/{profile['id']}", json={"skills": ["Python", "SQL"]})
    assert response.status_code == 200
    assert response.json()["skills"] == ["Python", "SQL"]


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


from app import models
from app.database import get_db
from app.main import app


def test_outcomes_freeze_resume_version_and_show_denominators(client):
    client.post("/api/profile", json={"name": "Tester"})
    resume = client.post("/api/profile/resume-options", json={"title": "Backend", "parsed_text": "Version one"}).json()
    job = client.post("/api/jobs", json={"company": "Acme", "role_title": "Engineer", "category": "Backend Engineer", "links": [{"kind": "source", "label": "Posting", "url": "https://www.example.com/job/1"}]}).json()
    client.patch(f"/api/jobs/{job['id']}", json={"selected_resume_option_id": resume["id"], "status": "Applied"})
    first = client.get("/api/reports/outcomes").json()
    version = first["groups"]["resume"][0]["label"]
    assert version.startswith("Backend · ")
    assert first["groups"]["source"][0]["label"] == "example.com"
    client.patch(f"/api/profile/resume-options/{resume['id']}", json={"title": "Renamed", "parsed_text": "Version two"})
    client.patch(f"/api/jobs/{job['id']}", json={"status": "Offer", "category": "Other"})
    client.delete(f"/api/jobs/{job['id']}")
    result = client.get("/api/reports/outcomes").json()
    row = result["groups"]["resume"][0]
    assert row["label"] == version
    assert (row["applied"], row["interviews"], row["offers"]) == (1, 1, 1)
    assert row["interview_rate"] == 100
    assert result["groups"]["category"][0]["label"] == "Backend Engineer"
    assert client.get("/api/reports/outcomes?saved_since=2099-01-01").json()["total_jobs"] == 0


def test_legacy_and_saved_jobs_have_no_invented_resume_attribution(client):
    with next(app.dependency_overrides[get_db]()) as db:
        db.add(models.Job(company="Legacy", role_title="Engineer", status=models.JobStatus.applied))
        db.commit()
    client.post("/api/jobs", json={"company": "Saved", "role_title": "Engineer"})
    row = client.get("/api/reports/outcomes").json()["groups"]["resume"][0]
    assert row["label"] == "Not recorded at application"
    assert row["saved"] == 2 and row["applied"] == 1 and row["interviews"] == 0

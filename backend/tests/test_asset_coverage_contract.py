from datetime import datetime, timedelta, timezone

from app import models
from app.database import get_db
from app.main import app
from app.services import profile_asset_service


def test_coverage_threshold_45_counts_only_ready_resumes(client):
    client.post("/api/profile", json={"name": "Coverage fixture"})
    job = client.post("/api/jobs", json={"company": "Threshold", "category": "Other", "role_title": "alpha beta gamma delta epsilon zeta eta theta iota kappa", "status": "Saved"}).json()
    ready = client.post("/api/profile/resume-options", json={"title": "alpha", "skills": ["other", "alpha", "beta", "gamma", "delta"], "status": "ready"}).json()
    # Five of eleven category keywords rounds to exactly 45: no gap at the threshold.
    result = client.post("/api/profile/coverage-gaps").json()
    assert not any(gap["asset_type"] == "resume" for gap in result["gaps"])
    assert next(gap for gap in result["gaps"] if gap["asset_type"] == "cover_letter")["affected_job_ids"] == [job["id"]]
    client.patch(f"/api/profile/resume-options/{ready['id']}", json={"skills": ["other", "alpha", "beta", "gamma"]})
    client.post("/api/profile/resume-options", json={"title": "alpha", "skills": ["other", "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa"], "status": "draft"})
    result = client.post("/api/profile/coverage-gaps").json()
    assert next(gap for gap in result["gaps"] if gap["asset_type"] == "resume")["affected_job_ids"] == [job["id"]]


def test_coverage_uses_latest_activity_within_30_days_and_excludes_closed_statuses(client, monkeypatch):
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)
    monkeypatch.setattr(profile_asset_service, "datetime", FrozenDateTime)
    ids = {}
    for label, status in [("old", "Saved"), ("boundary", "Saved"), ("recent_event", "Applied"), ("archived", "Archived"), ("ghosted", "Ghosted"), ("withdrawn", "Withdrawn"), ("rejected", "Rejected")]:
        response = client.post("/api/jobs", json={"company": label, "role_title": "Category fixture", "status": status})
        assert response.status_code == 201
        ids[label] = response.json()["id"]
    db = next(app.dependency_overrides[get_db]())
    for label, job_id in ids.items():
        job = db.get(models.Job, job_id)
        age = 31 if label in {"old", "recent_event"} else 30 if label == "boundary" else 1
        job.created_at = job.updated_at = now - timedelta(days=age)
        for event in job.status_events:
            event.changed_at = now - timedelta(days=29 if label == "recent_event" else age)
    db.commit()
    result = client.post("/api/profile/coverage-gaps").json()
    assert result["jobs_considered"] == 2
    assert result["gaps"]
    for gap in result["gaps"]:
        assert set(gap["affected_job_ids"]) == {ids["boundary"], ids["recent_event"]}

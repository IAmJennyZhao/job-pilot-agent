from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.database import get_db
from app.main import app
from app.services import job_service
from test_api import create_job


@pytest.fixture
def now(monkeypatch):
    instant = datetime(2035, 1, 15, 12, tzinfo=timezone.utc)
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant if tz else instant.replace(tzinfo=None)
    monkeypatch.setattr(job_service, "datetime", FrozenDateTime)
    return instant


def test_complete_reasons_are_uncapped_and_match_health_populations(client, now):
    ids = {create_job(client, pay_min=None, pay_max=None, pay_raw=None, extraction_confidence=0)["id"] for _ in range(12)}
    for status in ["Archived", "Rejected", "Withdrawn", "Ghosted"]:
        create_job(client, status=status, pay_min=None, pay_max=None, pay_raw=None, extraction_confidence=None)
    result = client.get("/api/dashboard/summary").json()
    suggestions = result["action_suggestions"]
    assert {item["id"] for item in suggestions} == ids
    assert len(suggestions) == 12  # No five-job/three-analysis preview truncation.
    for item in suggestions:
        assert [reason["kind"] for reason in item["reasons"]] == ["stale", "analysis", "pay", "confidence"]
        assert "Missing fit score and job analysis" in [reason["label"] for reason in item["reasons"]]
    for health in ["stale", "missing-data", "needs-analysis", "missing-pay", "low-confidence"]:
        rows = client.get("/api/jobs", params={"health_filter": health, "include_archived": True}).json()
        assert {job["id"] for job in rows} == ids
    assert result["health"]["stale_jobs"] == result["health"]["missing_data"] == 12
    assert len(result["search_health"]["stale_jobs"]) == 6  # Existing contract unchanged.
    assert len(result["search_health"]["needs_analysis"]) == 3


@pytest.mark.parametrize("status,days", [("Saved", 7), ("Applied", 14), ("Recruiter Screen", 7), ("Tech Screen", 7), ("Final Interview", 7)])
def test_stale_uses_latest_status_movement_and_exact_threshold(client, now, status, days):
    boundary = create_job(client, status=status)
    before = create_job(client, status=status)
    offer = create_job(client, status="Offer")
    with next(app.dependency_overrides[get_db]()) as db:
        for payload, delta in [(boundary, timedelta(days=days)), (before, timedelta(days=days, seconds=-1)), (offer, timedelta(days=100))]:
            job = db.get(models.Job, payload["id"])
            job.created_at = now - timedelta(days=200)
            job.updated_at = now  # Editing fields must not reset status movement.
            for event in job.status_events:
                event.changed_at = now - delta
        db.commit()
    result = client.get("/api/dashboard/summary").json()
    stale = {item["id"] for item in result["action_suggestions"] if any(reason["kind"] == "stale" for reason in item["reasons"])}
    assert stale == {boundary["id"]}
    assert result["health"]["stale_jobs"] == 1


def test_scheduling_cannot_resolve_suggestions_or_change_job_history(client, now):
    job = create_job(client, status="Applied", pay_min=None, pay_max=None, pay_raw=None)
    path = f"/api/jobs/{job['id']}"
    before = client.get(path).json()
    reasons = client.get("/api/dashboard/summary").json()["action_suggestions"]
    task = f"/api/actions/{job['id']}"
    for completed, due in [(False, "2035-01-15"), (True, "2035-01-15"), (False, "2035-01-16")]:
        response = client.put(task, json={"title": "Review stale application", "due_date": due, "completed": completed})
        assert response.status_code == 200
        assert bool(response.json()["completed_at"]) == completed
        after = client.get(path).json()
        for field in ["status", "status_events", "updated_at", "created_at"]:
            assert after[field] == before[field]
        assert client.get("/api/dashboard/summary").json()["action_suggestions"] == reasons
    assert client.get("/api/dashboard/summary?saved_since=2099-01-01").json()["action_suggestions"] == []
    assert client.get("/api/actions").json()[0]["job_id"] == job["id"]
    client.patch(path, json={"status": "Archived"})
    assert client.get("/api/dashboard/summary").json()["action_suggestions"] == []
    assert client.get("/api/actions").json()[0]["status"] == "Archived"


def test_reasons_resolve_from_job_data_and_most_recent_movement(client, now):
    job = create_job(client, status="Applied", pay_min=0, pay_max=None, pay_raw=None, extraction_confidence=80)
    with next(app.dependency_overrides[get_db]()) as db:
        record = db.get(models.Job, job["id"])
        record.fit_score = 0  # Zero is present; it must not be labelled missing.
        for event in record.status_events:
            event.changed_at = now - timedelta(days=100)
        db.add(models.JobStatusEvent(job_id=record.id, from_status=models.JobStatus.saved, to_status=models.JobStatus.applied, changed_at=now))
        db.commit()
    suggestions = client.get("/api/dashboard/summary").json()["action_suggestions"]
    assert suggestions[0]["reasons"] == [{"kind": "analysis", "label": "Missing job analysis"}]
    with next(app.dependency_overrides[get_db]()) as db:
        db.add(models.JobAnalysis(job_id=job["id"], summary="Existing analysis"))
        db.commit()
    assert client.get("/api/dashboard/summary").json()["action_suggestions"] == []

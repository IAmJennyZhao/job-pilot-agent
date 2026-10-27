from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.database import get_db
from app.main import app
from test_api import create_job


def test_saved_utc_boundary_preserves_distinct_populations_and_all_drilldowns(client):
    boundary = datetime(2026, 11, 1, tzinfo=timezone.utc)
    jobs = []
    open_ids = set()
    for stage in ["Saved", "Applied", "Recruiter Screen", "Tech Screen", "Final Interview", "Offer"]:
        job = create_job(client, company=f"Included {stage}", status=stage, pay_min=None, pay_max=None, pay_raw=None, extraction_confidence=None)
        jobs.append(job)
        open_ids.add(job["id"])
    for initial, terminal in [("Tech Screen", "Rejected"), ("Applied", "Withdrawn"), ("Recruiter Screen", "Ghosted"), ("Offer", "Archived")]:
        job = create_job(client, company=terminal, status=initial)
        assert client.patch(f"/api/jobs/{job['id']}", json={"status": terminal}).status_code == 200
        jobs.append(job)
    old = create_job(client, company="Before inclusive boundary", status="Offer")
    with next(app.dependency_overrides[get_db]()) as db:
        for index, row in enumerate(jobs):
            record = db.get(models.Job, row["id"])
            record.created_at = boundary + timedelta(seconds=index)
        record = db.get(models.Job, old["id"])
        record.created_at = boundary - timedelta(microseconds=1)
        record.updated_at = boundary + timedelta(days=10)  # Recent activity does not add an old save to the cohort.
        for event in record.status_events:
            event.changed_at = record.updated_at
        db.commit()
    params = {"saved_since": "2026-11-01"}
    dashboard = client.get("/api/dashboard/summary", params=params).json()
    outcomes = client.get("/api/reports/outcomes", params=params).json()
    assert dashboard["health"]["active_jobs"] == len(open_ids) == 6
    assert dashboard["health"]["archived_jobs"] == dashboard["health"]["ghosted_jobs"] == 1
    assert next(node["count"] for node in dashboard["sankey"]["nodes"] if node["id"] == "Saved") == 9
    assert outcomes["total_jobs"] == 10  # Outcomes deliberately includes Archived.
    expected = {row["id"] for row in jobs}
    for rows in outcomes["groups"].values():
        ids = [job_id for row in rows for job_id in row["job_ids"]]
        assert set(ids) == expected and len(ids) == len(expected)
        assert sum(row["saved"] for row in rows) == 10
        assert sum(row["applied"] for row in rows) == 9
        assert sum(row["interviews"] for row in rows) == 7
        assert sum(row["offers"] for row in rows) == 2
    for name in ["active", "missing_data", "missing_pay", "missing_fit", "low_confidence"]:
        rows = client.get("/api/jobs", params={**params, "health_filter": name, "include_archived": True}).json()
        assert {row["id"] for row in rows} == open_ids
        assert len(rows) == dashboard["health"]["active_jobs" if name == "active" else name]
    for node in dashboard["sankey"]["nodes"]:
        rows = client.get("/api/jobs", params={**params, "funnel_stage": node["id"]}).json()
        assert len(rows) == node["count"]
        assert old["id"] not in {row["id"] for row in rows}
    for link in dashboard["sankey"]["links"]:
        rows = client.get("/api/jobs", params={**params, "funnel_stage": link["target"], "funnel_from": link["source"]}).json()
        assert len(rows) == link["value"]
    assert client.get("/api/reports/outcomes").json()["total_jobs"] == 11


@pytest.mark.parametrize("path", ["/api/dashboard/summary", "/api/reports/outcomes", "/api/jobs"])
def test_invalid_cohort_dates_do_not_silently_fall_back_to_all_time(client, path):
    assert client.get(path, params={"saved_since": "2026-02-30"}).status_code == 422

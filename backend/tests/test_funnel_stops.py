"""Remaining flow must reconcile without mistaking current status for history."""
from datetime import datetime, timezone

import pytest

from app import models
from app.database import get_db
from app.main import app
from test_api import create_job


def test_all_stage_exits_reconcile_with_exact_drilldowns(client):
    stages = ["Saved", "Applied", "Recruiter Screen", "Tech Screen", "Final Interview", "Offer"]
    expected = {}
    for stage in stages:
        remaining = create_job(client, company=f"Remaining {stage}", status=stage)
        expected[stage] = {remaining["id"]}
        for terminal in ["Rejected", "Withdrawn", "Ghosted", "Archived"]:
            job = create_job(client, company=f"{terminal} after {stage}", status=stage)
            client.patch(f"/api/jobs/{job['id']}", json={"status": terminal})

    regressed = create_job(client, company="Moved back", status="Tech Screen")
    client.patch(f"/api/jobs/{regressed['id']}", json={"status": "Applied"})
    expected["Tech Screen"].add(regressed["id"])
    old = create_job(client, company="Before cohort", status="Offer")
    with next(app.dependency_overrides[get_db]()) as db:
        db.get(models.Job, old["id"]).created_at = datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        # Exact UTC boundary is included, irrespective of later status edits.
        db.get(models.Job, regressed["id"]).created_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()

    cohort = {"saved_since": "2000-01-01"}
    graph = client.get("/api/dashboard/summary", params=cohort).json()["sankey"]
    for stage in stages:
        for include_archived in [False, True]:
            result = client.get("/api/jobs", params={**cohort, "funnel_stage": stage, "funnel_stopped": True, "include_archived": include_archived})
            assert result.status_code == 200
            assert {job["id"] for job in result.json()} == expected[stage]
        reached = next(node["count"] for node in graph["nodes"] if node["id"] == stage)
        outgoing = sum(link["value"] for link in graph["links"] if link["source"] == stage)
        assert reached == outgoing + len(expected[stage])
    # Closed totals are exactly the union of source-specific branches.
    for terminal in ["Rejected", "Withdrawn", "Ghosted"]:
        count = next(node["count"] for node in graph["nodes"] if node["id"] == terminal)
        assert count == sum(link["value"] for link in graph["links"] if link["target"] == terminal)
    for link in graph["links"]:
        rows = client.get("/api/jobs", params={**cohort, "funnel_stage": link["target"], "funnel_from": link["source"]}).json()
        assert len(rows) == link["value"]
    rows = client.get("/api/jobs", params={**cohort, "funnel_stage": "Tech Screen", "funnel_stopped": True, "search": "Moved back", "status_filter": "Applied"}).json()
    assert [job["id"] for job in rows] == [regressed["id"]]


@pytest.mark.parametrize("params", [
    {"funnel_stopped": True},
    {"funnel_stopped": True, "funnel_stage": "Rejected"},
    {"funnel_stopped": True, "funnel_stage": "Applied", "funnel_from": "Saved"},
])
def test_invalid_stop_filters_rejected(client, params):
    assert client.get("/api/jobs", params=params).status_code == 400


def test_zero_and_single_job_funnels(client):
    empty = client.get("/api/dashboard/summary").json()["sankey"]
    assert all(node["count"] == 0 for node in empty["nodes"])
    assert empty["links"] == []
    job = create_job(client, status="Saved")
    graph = client.get("/api/dashboard/summary").json()["sankey"]
    assert graph["links"] == []
    assert graph["nodes"][0]["count"] == 1
    assert [row["id"] for row in client.get("/api/jobs?funnel_stage=Saved&funnel_stopped=true").json()] == [job["id"]]

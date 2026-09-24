from test_api import create_job


def test_every_funnel_node_and_link_opens_exact_population(client):
    for stage in ["Saved", "Applied", "Tech Screen", "Offer"]:
        create_job(client, company=stage, status=stage)
    for stage in ["Applied", "Tech Screen"]:
        job = create_job(client, company=f"Rejected from {stage}", status=stage)
        client.patch(f"/api/jobs/{job['id']}", json={"status": "Rejected"})
    create_job(client, status="Archived")
    summary = client.get("/api/dashboard/summary").json()
    for node in summary["sankey"]["nodes"]:
        response = client.get("/api/jobs", params={"funnel_stage": node["id"]})
        assert response.status_code == 200
        assert len(response.json()) == node["count"], node
    for link in summary["sankey"]["links"]:
        response = client.get("/api/jobs", params={"funnel_stage": link["target"], "funnel_from": link["source"]})
        assert response.status_code == 200
        assert len(response.json()) == link["value"], link


def test_active_excludes_withdrawn_and_closed_jobs(client):
    active = create_job(client, status="Applied")
    for status in ["Withdrawn", "Rejected", "Ghosted", "Archived"]:
        create_job(client, status=status)
    summary = client.get("/api/dashboard/summary").json()
    assert summary["health"]["active_jobs"] == 1
    jobs = client.get("/api/jobs", params={"health_filter": "active"}).json()
    assert [job["id"] for job in jobs] == [active["id"]]


def test_invalid_funnel_filter_is_rejected(client):
    assert client.get("/api/jobs?funnel_stage=typo").status_code == 400
    assert client.get("/api/jobs?funnel_from=Applied").status_code == 400


def test_funnel_filter_keeps_regressions_and_respects_additional_filters(client):
    progressed = create_job(client, company="Progressed", status="Tech Screen")
    client.patch(f"/api/jobs/{progressed['id']}", json={"status": "Applied"})
    create_job(client, company="Other", status="Applied")
    result = client.get('/api/jobs', params={'funnel_stage': 'Tech Screen', 'status_filter': 'Applied', 'search': 'Progressed'})
    assert [row['id'] for row in result.json()] == [progressed['id']]
    assert client.get('/api/jobs?funnel_stage=Offer&funnel_from=Saved').status_code == 400


def test_dashboard_coverage_drilldowns_exclude_closed_jobs(client):
    active = create_job(client, status="Applied", pay_min=None, pay_max=None, pay_raw=None, extraction_confidence=30)
    create_job(client, status="Withdrawn", pay_min=None, pay_max=None, pay_raw=None, extraction_confidence=30)
    for filter in ['missing_pay', 'missing_fit', 'low_confidence', 'needs_analysis']:
        response = client.get('/api/jobs', params={'health_filter': filter, 'include_archived': True})
        assert response.status_code == 200
        assert [row['id'] for row in response.json()] == [active['id']]

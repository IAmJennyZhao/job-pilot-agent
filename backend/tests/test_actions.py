def make_job(client):
    response = client.post("/api/jobs", json={"company": "Action Test", "role_title": "Engineer"})
    assert response.status_code == 201
    return response.json()["id"]


def test_action_lifecycle_and_validation(client):
    job = make_job(client)
    assert client.get(f"/api/actions/{job}").json() is None
    path = f"/api/actions/{job}"
    assert client.put(path, json={"title": "  ", "due_date": "2026-09-24"}).status_code == 422
    assert client.put(path, json={"title": "Follow up", "due_date": "bad"}).status_code == 422
    payload = {"title": " Follow up ", "due_date": "2026-09-24"}
    result = client.put(path, json=payload)
    assert result.status_code == 200
    assert result.json()["title"] == "Follow up"
    assert result.json()["completed_at"] is None
    assert client.get(path).json()["company"] == "Action Test"
    done = client.put(path, json={**payload, "completed": True}).json()
    assert done["completed_at"].endswith("Z")
    assert client.put(path, json={**payload, "completed": True}).json()["completed_at"] == done["completed_at"]
    reopened = client.put(path, json={**payload, "due_date": "2026-09-26"}).json()
    assert reopened["completed_at"] is None
    assert reopened["due_date"] == "2026-09-26"
    assert len(client.get("/api/actions").json()) == 1
    assert client.delete(path).status_code == 204
    assert client.get(path).json() is None
    assert client.put("/api/actions/missing", json=payload).status_code == 404


def test_agenda_keeps_closed_jobs_and_orders_by_due_date(client):
    first, second = make_job(client), make_job(client)
    client.put(f"/api/actions/{first}", json={"title": "Review offer", "due_date": "2026-09-26"})
    client.put(f"/api/actions/{second}", json={"title": "Request feedback", "due_date": "2026-09-24"})
    client.patch(f"/api/jobs/{second}", json={"status": "Rejected"})
    result = client.get("/api/actions").json()
    assert [item["job_id"] for item in result] == [second, first]
    assert result[0]["status"] == "Rejected"

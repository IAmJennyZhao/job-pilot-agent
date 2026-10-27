from test_api import create_profile


def test_study_progress_survives_reload_and_rename(client):
    create_profile(client)
    saved = client.post('/api/study-plans', json={
        'title': 'Practice', 'timeframe': '1 week',
        'plan': {'top_gaps': [], 'priority_order': [], 'study_plan': [
            {'period': 'Week 1', 'focus': 'Python', 'tasks': ['Build an API']}
        ], 'project_ideas': ['Build a demo']},
    }).json()
    url = f"/api/study-plans/{saved['id']}"
    result = client.patch(url, json={'completed_tasks': ['task:0:0', 'project:0']})
    assert result.status_code == 200
    assert result.json()['plan']['completed_tasks'] == ['task:0:0', 'project:0']
    client.patch(url, json={'title': 'Renamed'})
    assert client.get('/api/study-plans').json()[0]['plan']['completed_tasks'] == ['task:0:0', 'project:0']
    assert client.patch(url, json={'completed_tasks': ['task:99:0']}).status_code == 400


def test_project_only_and_mixed_records_keep_index_identity_and_other_progress(client):
    create_profile(client)
    for mode in ["project_ideas", "both", "weekly_plan"]:
        plan = {
            "top_gaps": ["Python"], "priority_order": ["Python"],
            "project_ideas": [] if mode == "weekly_plan" else ["Same idea", "Same idea"],
            "study_plan": [] if mode == "project_ideas" else [
                {"period": "Week 1", "focus": "Practice", "tasks": ["Repeat", "Repeat"]},
                {"period": "Week 2", "focus": "Practice", "tasks": ["Repeat"]},
            ],
        }
        progress = (["project:1"] if mode != "weekly_plan" else []) + (["task:0:1", "task:1:0"] if mode != "project_ideas" else [])
        response = client.post("/api/study-plans", json={"title": mode, "timeframe": "2 weeks", "mode": mode, "plan": plan})
        assert response.status_code == 201
        saved = response.json()
        url = f"/api/study-plans/{saved['id']}"
        assert client.patch(url, json={"completed_tasks": progress}).status_code == 200
        renamed = client.patch(url, json={"title": "Renamed " + mode}).json()
        assert renamed["id"] == saved["id"]
        assert renamed["mode"] == mode
        assert renamed["plan"] == {**plan, "completed_tasks": progress}
        changed = client.patch(url, json={"completed_tasks": progress[1:] if progress else []}).json()
        assert changed["plan"] == {**plan, "completed_tasks": progress[1:] if progress else []}
        reloaded = next(record for record in client.get("/api/study-plans").json() if record["id"] == saved["id"])
        assert reloaded == changed

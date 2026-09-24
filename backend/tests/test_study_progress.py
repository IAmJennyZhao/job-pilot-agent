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

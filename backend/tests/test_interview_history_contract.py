from datetime import datetime, timedelta, timezone

from app import models, schemas
from app.database import get_db
from app.main import app


def test_trends_keep_overall_scores_with_tag_filters_and_the_recent_window(client):
    session_id = client.post("/api/interview/sessions", json={"mode": "live_practice", "target_role": "History contract"}).json()["id"]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expected = []
    with next(app.dependency_overrides[get_db]()) as db:
        for index in range(55):
            tags = ["technical_depth"] if index % 3 == 0 else ["answer_structure"] if index % 3 == 1 else ["technical_depth", "answer_structure"]
            score = index  # Deliberately different scores to detect averaging or subscores.
            db.add(models.InterviewMessage(session_id=session_id, role=models.MessageRole.ai, content=f"Question {index}", score=score, feedback={"weak_point_tags": tags, "submitted_answer": f"Answer {index}"}, created_at=start + timedelta(minutes=index)))
            if index >= 5:
                expected.append((score, tags))
        db.commit()
    result = client.get("/api/interview/insights").json()
    assert [point["score"] for point in result["trends"]["overall"]] == [score for score, _ in expected]
    assert [point["score"] for point in result["trends"]["knowledge"]] == [score for score, tags in expected if "technical_depth" in tags]
    assert [point["score"] for point in result["trends"]["interview_skills"]] == [score for score, tags in expected if "answer_structure" in tags]
    assert [entry["score"] for entry in result["recent_scores"]] == list(range(54, 44, -1))
    counts = {point["tag"]: point["count"] for point in result["weak_points"]}
    assert counts == {tag: sum(tag in tags for _, tags in expected) for tag in ["technical_depth", "answer_structure"]}
    assert all(len(point["examples"]) <= 3 for point in result["weak_points"])


def test_continue_excludes_answered_questions_and_does_not_rewrite_history(client, monkeypatch):
    def provider(output_model, *_):
        if output_model is schemas.InterviewQuestionsOutput:
            return schemas.InterviewQuestionsOutput(questions=[schemas.InterviewQuestion(question=f"Question {index}", type="technical", why_it_matters="Practice", strong_answer_should_include=[]) for index in range(2)])
        return schemas.InterviewAnswerFeedbackOutput(score=75, what_went_well=[], what_was_missing=[], suggested_better_answer="Add evidence", coaching_notes=[], evidence_to_add=[], weak_point_tags=[], missing_skill_names=[], follow_up_question="")
    monkeypatch.setattr("app.services.ai_service.get_structured_output", provider)
    practice = client.post("/api/interview/practice-sets", json={"target_role": "Engineer", "count": 2}).json()
    session_id = practice["session_id"]
    first, second = practice["questions"]
    for answer in ["First attempt", "Revised attempt"]:
        assert client.post("/api/interview/answers/evaluate", json={"session_id": session_id, "question_id": first["id"], "answer": answer}).status_code == 200
    before = client.get(f"/api/interview/sessions/{session_id}").json()
    resume = client.get(f"/api/interview/sessions/{session_id}/resume").json()
    assert [question["id"] for question in resume["questions"]] == [second["id"]]
    assert client.get(f"/api/interview/sessions/{session_id}").json() == before
    attempts = client.get(f"/api/interview/questions/{first['id']}/attempts").json()
    assert [entry["answer"] for entry in attempts] == ["First attempt", "Revised attempt"]
    assert client.post("/api/interview/answers/evaluate", json={"session_id": session_id, "question_id": second["id"], "answer": "Answered second"}).status_code == 200
    completed = client.get(f"/api/interview/sessions/{session_id}").json()
    assert client.get(f"/api/interview/sessions/{session_id}/resume").json()["questions"] == []
    assert client.get(f"/api/interview/sessions/{session_id}").json() == completed

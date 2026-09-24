from app import schemas


def test_revision_keeps_exact_answer_score_and_timing(client, monkeypatch):
    scores = iter([50, 85])

    def fake(output_model, *_args):
        if output_model is schemas.InterviewQuestionsOutput:
            return schemas.InterviewQuestionsOutput(questions=[schemas.InterviewQuestion(
                question="Explain an API you built", type="technical", why_it_matters="Experience",
                strong_answer_should_include=["Results"],
            )])
        return schemas.InterviewAnswerFeedbackOutput(score=next(scores), what_went_well=["Specific example"],
            what_was_missing=[], suggested_better_answer="Include the result", coaching_notes=[],
            evidence_to_add=[], weak_point_tags=[], missing_skill_names=[], follow_up_question="")

    monkeypatch.setattr("app.services.ai_service.get_structured_output", fake)
    practice = client.post("/api/interview/practice-sets", json={"target_role": "Engineer", "count": 1}).json()
    question_id = practice["questions"][0]["id"]
    base = {"session_id": practice["session_id"], "question_id": question_id}
    for answer, elapsed in [("Initial answer", 90), ("Revised answer with evidence", 110)]:
        result = client.post("/api/interview/answers/evaluate", json={**base, "answer": answer, "elapsed_seconds": elapsed, "time_limit_seconds": 120})
        assert result.status_code == 200
    attempts = client.get(f"/api/interview/questions/{question_id}/attempts").json()
    assert [attempt["answer"] for attempt in attempts] == ["Initial answer", "Revised answer with evidence"]
    assert [attempt["score"] for attempt in attempts] == [50, 85]
    assert [attempt["feedback"]["elapsed_seconds"] for attempt in attempts] == [90, 110]
    assert all(attempt["created_at"].endswith("Z") for attempt in attempts)
    assert client.post("/api/interview/answers/evaluate", json={**base, "answer": " "}).status_code == 422
    assert client.post("/api/interview/answers/evaluate", json={**base, "answer": "Valid", "elapsed_seconds": -1}).status_code == 422
    other = client.post("/api/interview/sessions", json={"mode": "live_practice", "target_role": "Other Engineer"}).json()
    assert client.post("/api/interview/answers/evaluate", json={**base, "session_id": other["id"], "answer": "Wrong session"}).status_code == 400

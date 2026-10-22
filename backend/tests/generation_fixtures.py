"""Fictional four-pass provider; no network or private source files."""
import json
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisedResume, PolishedResume


def fake_generation(output_model, system, payload, *, model, timeout):
    data = json.loads(payload)
    evidence = data["approved_evidence"]
    previous = data["prior_outputs"]
    if output_model is ResumeDraft:
        claim = evidence["claims"][0]
        output = ResumeDraft(requirements=[{"id": "REQ-1", "quote": "Python", "description": "Python development"}],
            bullets=[{"id": "B-1", "record_id": claim["record_id"], "evidence_ids": [claim["id"]], "requirement_ids": ["REQ-1"], "text": claim["text"]}],
            skills=[{"name": "Python", "source_ids": ["SK-1"]}], unmet_requirement_ids=[], change_summary=["Selected supported Python work."])
    elif output_model is CritiqueReport:
        output = CritiqueReport(issues=[{"issue_id": "I-1", "severity": "improvement", "field_path": "bullets.B-1",
            "requirement_ids": ["REQ-1"], "evidence_ids": [evidence["claims"][0]["id"]], "finding": "Keep wording direct.",
            "proposed_action": "Preserve the supported implementation detail.", "requires_user_fact_confirmation": False}])
    elif output_model is RevisedResume:
        output = RevisedResume(draft=previous["select"], decisions=[{"issue_id": "I-1", "action": "accepted", "reason": "The supported wording is already concise."}])
    elif output_model is PolishedResume:
        draft = ResumeDraft.model_validate(previous["revise"]["draft"])
        edits = []
        for bullet in draft.bullets:
            text = bullet.text.replace("Successfully ", "").replace("successfully ", "")
            if text != bullet.text:
                edits.append({"bullet_id": bullet.id, "before": bullet.text, "after": text})
                bullet.text = text
        output = PolishedResume(draft=draft, edits=edits)
    else:
        raise AssertionError("Unknown generation contract")
    return output, {"model": model, "usage": {"input_tokens": 100, "output_tokens": 50}, "latency_ms": 1}

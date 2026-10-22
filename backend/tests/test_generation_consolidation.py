"""Fictional regressions minimized from the live writing evaluation."""
import copy
import json
import pytest
from types import SimpleNamespace
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisionDecision
from app.services.resume_validation import validate_draft, validate_stage
from test_resume_generation import prepared, generate


def example():
    snapshot = {"generation_version": 2, "job": {"source_content": "Python workflows and recovery."}, "projection": {
        "claims": [{"id": "C1", "record_id": "R1", "text": "Built internal Python checks."},
                   {"id": "C2", "record_id": "R1", "text": "Reduced weekly alerts from 100 to 20."}],
        "records": [{"id": "R1"}], "skill_groups": [], "technology_catalog": [{"id": "T1", "name": "Python", "aliases": []}],
        "claim_overlap_groups": [{"id": "O1", "claim_ids": ["C1", "C2"], "rule": "Checks and alert reduction may be combined."}]}}
    draft = ResumeDraft(requirements=[{"id": "Q1", "quote": "Python workflows", "description": "Python workflows"}],
        bullets=[{"id": "B1", "record_id": "R1", "evidence_ids": ["C1", "C2"], "requirement_ids": ["Q1"],
                  "text": "Built internal Python checks. Reduced weekly alerts from 100 to 20."}],
        skills=[], unmet_requirement_ids=[], change_summary=[])
    return snapshot, draft


def test_complementary_overlap_combines_once_but_not_as_repetitive_bullets():
    snapshot, draft = example()
    assert validate_draft(draft, snapshot) == []
    other = draft.bullets[0].model_copy(deep=True)
    other.id = "B2"
    other.evidence_ids = ["C2"]
    other.text = snapshot["projection"]["claims"][1]["text"]
    draft.bullets[0].evidence_ids = ["C1"]
    draft.bullets[0].text = snapshot["projection"]["claims"][0]["text"]
    draft.bullets.append(other)
    assert any("Overlap" in e for e in validate_draft(draft, snapshot))


def test_critique_skill_sources_and_actionable_reference_errors():
    snapshot, draft = example()
    issue = {"issue_id": "I1", "severity": "improvement", "field_path": "skills", "requirement_ids": [],
             "evidence_ids": ["T1"], "finding": "Prioritize Python.", "proposed_action": "Select Python.", "requires_user_fact_confirmation": False}
    critique = CritiqueReport(issues=[issue])
    assert validate_stage("critique", critique, snapshot, {"select": draft.model_dump()})["valid"]
    critique.issues[0].field_path = "bullets.B1.text"
    errors = validate_stage("critique", critique, snapshot, {"select": draft.model_dump()})["blocking_issues"]
    assert any("bullets.B1.text" in e and "bullets.B1" in e and "Allowed" in e for e in errors)


def test_authorized_split_tracks_parent_and_issue_without_reusing_identity():
    snapshot, draft = example()
    snapshot["projection"]["claim_overlap_groups"] = []
    critique = CritiqueReport(issues=[{"issue_id": "I1", "severity": "improvement", "field_path": "bullets.B1",
        "requirement_ids": [], "evidence_ids": ["C1", "C2"], "finding": "Two accomplishments.",
        "proposed_action": "Split into focused bullets.", "requires_user_fact_confirmation": False}])
    revised = draft.model_copy(deep=True)
    revised.bullets = []
    for index, claim in enumerate(snapshot["projection"]["claims"], 2):
        b = draft.bullets[0].model_copy(deep=True)
        b.id, b.text, b.evidence_ids = f"B{index}", claim["text"], [claim["id"]]
        revised.bullets.append(b)
    output = SimpleNamespace(draft=revised, decisions=[RevisionDecision(issue_id="I1", action="accepted", reason="Split supported claims.")],
        lineage=[SimpleNamespace(bullet_id=b.id, parent_bullet_ids=["B1"], issue_ids=["I1"]) for b in revised.bullets])
    accepted = {"select": draft.model_dump(), "critique": critique.model_dump()}
    assert validate_stage("revise", output, snapshot, accepted)["valid"]
    output.lineage[0].parent_bullet_ids = ["UNKNOWN"]
    assert not validate_stage("revise", output, snapshot, accepted)["valid"]


def test_legacy_overlap_validation_is_preserved():
    snapshot, draft = example()
    snapshot.pop("generation_version")
    assert any("Overlap" in e for e in validate_draft(draft, snapshot))


def test_long_combinations_and_empty_coverage_are_rejected():
    snapshot, draft = example()
    snapshot["projection"]["claims"][0]["text"] = " ".join(["Internal"] * 46)
    draft.bullets[0].text = " ".join(c["text"] for c in snapshot["projection"]["claims"])
    assert any("45 words" in e for e in validate_draft(draft, snapshot))
    draft.requirements = []
    assert any("posting requirement" in e for e in validate_draft(draft, snapshot))


def test_new_facts_and_unrelated_critique_sources_still_fail():
    snapshot, draft = example()
    draft.bullets[0].text += " Deployed to production for 1000 customers."
    assert any("unverified paraphrase" in e for e in validate_draft(draft, snapshot))
    issue = {"issue_id": "I1", "severity": "improvement", "field_path": "bullets.B1", "requirement_ids": [],
             "evidence_ids": ["T1"], "finding": "Python.", "proposed_action": "Add Python.", "requires_user_fact_confirmation": False}
    report = validate_stage("critique", CritiqueReport(issues=[issue]), snapshot, {"select": draft.model_dump()})
    assert not report["valid"] and "T1" in report["blocking_issues"][0]


def test_v1_reviewed_history_restores_alongside_v2(client, prepared, monkeypatch, tmp_path):
    from app.config import get_settings
    from app.services import generation_inputs, resume_generation, ai_service
    from app.services.resume_validation import OUTPUT_MODELS
    from app.services.generation_v1.validation import PROMPT_VERSIONS
    from app.services.generation_v1.prompts import system_for
    from app.services.intake_preferences import digest
    from generation_fixtures import fake_generation
    from test_resume_review import save_payload, approval_payload
    job, _ = prepared
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    capture = generation_inputs.capture
    def legacy_capture(db, job):
        state = capture(db, job)
        snap = state["snapshot"]
        snap.pop("generation_version")
        snap["prompt_versions"] = PROMPT_VERSIONS
        snap["prompt_hashes"] = {s: digest(system_for(s)) for s in PROMPT_VERSIONS}
        state["input_hash"] = digest(snap)
        return state
    def legacy_provider(output_model, system, payload, **kwargs):
        stage = json.loads(payload)["stage"]
        output, meta = fake_generation(OUTPUT_MODELS[stage], system, payload, **kwargs)
        data = output.model_dump()
        if stage == "revise":
            data.pop("lineage")
        return output_model.model_validate(data), meta
    with monkeypatch.context() as patch:
        patch.setattr(generation_inputs, "capture", legacy_capture)
        patch.setattr(resume_generation, "capture", legacy_capture)
        patch.setattr(ai_service, "get_tailoring_output", legacy_provider)
        old = generate(client, job).json()
    assert old["state"] == "completed", old
    url = f"/api/tailoring/resumes/{old['revision']['id']}"
    view = client.get(url).json()
    edited = client.post(url + "/revisions", json=save_payload(view)).json()
    assert edited["revision"]["validation"]["validator_version"] == "resume-review-v1"
    reviewed = client.post(url + "/review", json=approval_payload(edited))
    assert reviewed.status_code == 201, reviewed.text
    current = generate(client, job).json()
    assert current["state"] == "completed", current
    assert current["revision"]["validation"]["validator_version"] == "resume-v2"
    archive = client.get("/api/data/backup").content
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", archive)})
    assert preview.status_code == 200, preview.text
    restored = client.post("/api/data/restore", files={"file": ("backup.json", archive)}, data={"sha256": preview.json()["sha256"], "confirmation": "RESTORE"})
    assert restored.status_code == 200, restored.text
    assert client.get(url).json() == reviewed.json()
    bad = json.loads(archive)
    bad["tables"]["tailoring_runs"][0]["snapshot"]["generation_version"] = 999
    assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(bad).encode())}).status_code == 400

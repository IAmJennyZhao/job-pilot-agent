"""Real persistence/render/export acceptance; only model output is fictional and deterministic."""
import hashlib
import pytest
from app.config import get_settings
from app.services import ai_service
from acceptance_fixtures import CASES, bundle, posting, provider
from test_resume_generation import request_for
from test_resume_review import approval_payload
from test_resume_exports import rendered, final


@pytest.mark.parametrize("family", CASES)
def test_distinct_role_full_document_workflow_and_restore(client, monkeypatch, tmp_path, family):
    monkeypatch.setattr(get_settings(), "openai_api_key", "fictional-acceptance-key")
    monkeypatch.setattr(get_settings(), "openai_model", "fictional-acceptance-model")
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path / "storage"))
    calls = []
    def checked_provider(*args, **kwargs):
        calls.append(args[0].__name__)
        assert "EXCLUDED_CLAIM_SECRET" not in args[2] and "ARCHIVE_ONLY_SECRET" not in args[2]
        return provider(*args, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", checked_provider)
    client.post("/api/profile", json={"name": "Synthetic Tester", "skills": []})
    source = client.post("/api/profile/tailoring-sources/import", json=bundle()).json()
    active = client.post(f"/api/profile/tailoring-sources/{source['id']}/activate", json={"expected_hash": source["bundle_hash"], "expected_active_id": None})
    assert active.status_code == 200, active.text
    case = CASES[family]
    job = client.post("/api/jobs", json={"company": case["company"], "role_title": case["title"], "source_content": posting(family), "status": "Saved"}).json()
    result = client.post(f"/api/jobs/{job['id']}/tailoring/resume", json=request_for(client, job["id"]))
    run = result.json()
    assert run["state"] == "completed", run
    draft = run["revision"]["content"]["draft"]
    assert [b["text"] for b in draft["bullets"]] == case["claims"]
    assert {e for b in draft["bullets"] for e in b["evidence_ids"]} == {f"C-{family}-1", f"C-{family}-2"}
    assert draft["unmet_requirement_ids"] == ["REQ-3"]
    url = f"/api/tailoring/resumes/{run['revision']['id']}"
    view, render = rendered(client, url)
    assert render["validation"]["valid"] and render["validation"]["pages"] == 1
    final(client, url, view, render)
    paths = [url+f"/renders/{render['id']}/download/{fmt}" for fmt in ("pdf", "tex", "txt")]
    request = {**request_for(client, job["id"]), "options": {"count": 3, "length": "standard"}}
    letter = client.post(f"/api/jobs/{job['id']}/cover-letters", json=request).json()
    assert letter["state"] == "completed", letter
    letter_url = f"/api/cover-letters/{letter['revision']['id']}"
    reviewed = client.get(letter_url).json()
    assert len({tuple(sorted({c for p in v["paragraphs"] for s in p["sentences"] for c in s["candidate_evidence_ids"]})) for v in reviewed["revision"]["edit"]["variants"]}) == 3
    assert client.post(letter_url + "/review", json=approval_payload(reviewed)).status_code == 201
    paths += [letter_url+f"/revisions/{reviewed['revision']['id']}/download/{i}/{fmt}" for i in range(3) for fmt in ("txt", "md")]
    original = {path: client.get(path).content for path in paths}
    assert calls == ["DraftV4", "CritiqueV4", "RevisedV4", "PolishedV4", "LetterDraft", "LetterAssessment"]
    monkeypatch.setattr(ai_service, "get_tailoring_output", lambda *a, **k: pytest.fail("Read/review/export/restore called a model"))
    archive = client.get("/api/data/backup").content
    restored = client.post("/api/data/restore", files={"file": ("acceptance.json", archive)}, data={"sha256": hashlib.sha256(archive).hexdigest(), "confirmation": "RESTORE"})
    assert restored.status_code == 200, restored.text
    for path, expected in original.items():
        downloaded = client.get(path)
        assert downloaded.status_code == 200 and downloaded.content == expected
    assert client.get(f"/api/jobs/{job['id']}").json() == job


def test_role_examples_are_different_in_inputs_evidence_gaps_and_letters():
    from acceptance_fixtures import letter
    assert len({posting(k) for k in CASES}) == 3
    assert len({tuple(c["claims"]) for c in CASES.values()}) == 3
    assert len({tuple(c["skills"]) for c in CASES.values()}) == 3
    assert len({c["gap"] for c in CASES.values()}) == 3
    for key, case in CASES.items():
        doc = letter(key)
        assert all(any(s.candidate_evidence_ids for p in v.paragraphs for s in p.sentences) for v in doc.variants)
        assert all(180 <= sum(len(s.text.split()) for p in v.paragraphs for s in p.sentences) <= 250 for v in doc.variants)

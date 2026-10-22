import copy
import json
import uuid
import pytest
from app.config import get_settings
from app.services import ai_service
from app.letter_schemas import LetterAssessment, LetterDraft
from app.services.tailoring_provider import ProviderFailure
from test_resume_generation import prepared, request_for
from test_resume_review import approval_payload, save_payload
from letter_fixtures import fake_letter


@pytest.fixture
def letter(client, prepared, monkeypatch):
    monkeypatch.setattr(ai_service, "get_tailoring_output", fake_letter)
    return prepared


def generate(client, job, **options):
    return client.post(f"/api/jobs/{job['id']}/cover-letters", json={**request_for(client, job["id"]), "options": options})


def completed(client, job, **options):
    result = generate(client, job, **options)
    assert result.status_code == 201, result.text
    run = result.json()
    assert run["state"] == "completed", [(a["error"], a["validation"]) for a in run["stages"]]
    return run, f"/api/cover-letters/{run['revision']['id']}"


def check_payload(view):
    return {"request_key": str(uuid.uuid4()), "expected_revision_id": view["current_revision_id"], "content_hash": view["revision"]["content_hash"]}


@pytest.mark.parametrize("count,length", [(1, "short"), (2, "standard"), (3, "short"), (3, "standard")])
def test_generate_variants_review_and_matching_exports(client, letter, count, length):
    job, _ = letter
    before = client.get(f"/api/jobs/{job['id']}").json()
    run, url = completed(client, job, count=count, length=length)
    view = client.get(url).json()
    assert len(view["revision"]["edit"]["variants"]) == count
    assert view["approval_eligible"] and view["sentence_assessment"]
    download = f"{url}/revisions/{view['revision']['id']}/download/0"
    assert client.get(download + "/txt").status_code == 409
    assert client.post(url + "/review", json=approval_payload(view)).json()["approved_current"]
    txt = client.get(download + "/txt")
    assert txt.status_code == 200 and "Dear Hiring Team," in txt.text
    assert "Synthetic Tester" in txt.text and "C-" not in txt.text
    import html
    assert html.unescape(client.get(download + "/md").text) == txt.text
    assert client.get(f"/api/jobs/{job['id']}/tailoring").json()["runs"] == []
    assert len(client.get(f"/api/jobs/{job['id']}/cover-letters").json()["runs"]) == 1
    assert client.get(f"/api/tailoring/resumes/{run['revision']['id']}").status_code == 404
    assert client.get(f"/api/jobs/{job['id']}").json() == before


def test_edit_check_restore_and_historical_review(client, letter, monkeypatch):
    job, _ = letter
    _, url = completed(client, job, count=1, length="short")
    original = client.get(url).json()
    client.post(url + "/review", json=approval_payload(original))
    payload = save_payload(original)
    payload["edit"]["variants"][0]["paragraphs"][0]["sentences"][0]["text"] += " Thank you."
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    edited = client.post(url + "/revisions", json=payload).json()
    assert not edited["approval_eligible"]
    assert client.post(url + "/check", json=check_payload(edited)).status_code == 422
    assert client.post(url + "/review", json=approval_payload(edited)).status_code == 409
    assert client.post(url + "/revisions", json=payload).json()["revision"]["id"] == edited["revision"]["id"]
    assert client.post(url + "/revisions", json=save_payload(original)).status_code == 409
    monkeypatch.setattr(get_settings(), "openai_api_key", "synthetic-key")
    checked = client.post(url + "/check", json=check_payload(edited)).json()
    assert checked["approval_eligible"], checked
    assert client.post(url + "/review", json=approval_payload(checked)).json()["approved_current"]
    assert client.post(url + "/check", json=check_payload(checked)).status_code == 409
    restored = client.post(url + "/restore", json={"request_key": str(uuid.uuid4()), "expected_revision_id": checked["current_revision_id"], "revision_id": original["revision"]["id"]}).json()
    assert restored["revision"]["plain_text"] == original["revision"]["plain_text"] and not restored["approval_eligible"]
    assert len(restored["history"]) == 3
    client.patch(f"/api/jobs/{job['id']}", json={"source_content": "Changed posting"})
    assert client.get(url).json()["source_problem"]
    assert client.get(f"{url}/revisions/{original['revision']['id']}/download/0/txt").status_code == 200


@pytest.mark.parametrize("text,kind,ids", [
    ("I deployed this prototype to production.", "candidate_claim", ["C-ALLOWED"]),
    ("I was referred by your director.", "motivation", []),
    ("I have followed your company for years.", "transition", []),
    ("I created a platform serving millions of customers.", "candidate_claim", ["C-ALLOWED"]),
    ("I created an internal prototype using Python.", "candidate_claim", ["C-BLOCKED"]),
])
def test_unsupported_edits_cannot_be_approved(client, letter, text, kind, ids):
    job, _ = letter
    _, url = completed(client, job, count=1, length="short")
    payload = save_payload(client.get(url).json())
    s = payload["edit"]["variants"][0]["paragraphs"][0]["sentences"][1]
    s.update(text=text, sentence_kind=kind, candidate_evidence_ids=ids)
    saved = client.post(url + "/revisions", json=payload).json()
    response = client.post(url + "/check", json=check_payload(saved))
    assert response.status_code in {200, 422}, response.text
    view = client.get(url).json()
    assert not view["approval_eligible"]
    assert client.post(url + "/review", json=approval_payload(view)).status_code == 409


def test_refusal_no_hidden_retry_and_idempotency(client, letter, monkeypatch):
    job, _ = letter
    calls = []
    def provider(output_model, system, payload, **kwargs):
        calls.append(output_model)
        if output_model is LetterAssessment:
            raise ProviderFailure("Synthetic refusal")
        return fake_letter(output_model, system, payload, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", provider)
    payload = {**request_for(client, job["id"]), "options": {"count": 1, "length": "short"}}
    run = client.post(f"/api/jobs/{job['id']}/cover-letters", json=payload).json()
    assert run["state"] == "failed" and run["revision"] is None and len(calls) == 2
    assert client.post(f"/api/jobs/{job['id']}/cover-letters", json=payload).json()["id"] == run["id"]
    client.get(f"/api/cover-letters/runs/{run['id']}")
    assert len(calls) == 2
    monkeypatch.setattr(ai_service, "get_tailoring_output", fake_letter)
    retried = client.post(f"/api/cover-letters/runs/{run['id']}/retry", json={**payload, "request_key": str(uuid.uuid4())}).json()
    assert retried["state"] == "completed" and retried["parent_run_id"] == run["id"]


def test_letter_backup_roundtrip_and_tampering(client, letter, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    job, _ = letter
    _, url = completed(client, job, count=1, length="short")
    saved = client.post(url + "/revisions", json=save_payload(client.get(url).json())).json()
    checked = client.post(url + "/check", json=check_payload(saved)).json()
    assert client.post(url + "/review", json=approval_payload(checked)).status_code == 201
    archive = client.get("/api/data/backup").json()
    content = json.dumps(archive).encode()
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", content)})
    assert preview.status_code == 200, preview.text
    restored = client.post("/api/data/restore", files={"file": ("backup.json", content)}, data={"sha256": preview.json()["sha256"], "confirmation": "RESTORE"})
    assert restored.status_code == 200, restored.text
    assert client.get(url).json()["approved_current"]
    bad = copy.deepcopy(archive)
    bad["tables"]["tailoring_stage_attempts"][-1]["input_data"]["content_hash"] = "0" * 64
    assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(bad).encode())}).status_code == 400

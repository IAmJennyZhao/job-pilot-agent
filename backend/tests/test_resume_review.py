import copy
import hashlib
import json
import uuid
import pytest
from app.config import get_settings
from app.services import ai_service
from test_resume_generation import prepared, generate


@pytest.fixture
def completed(client, prepared, monkeypatch):
    job, source = prepared
    run = generate(client, job).json()
    assert run["state"] == "completed"
    monkeypatch.setattr(ai_service, "get_tailoring_output", lambda *a, **k: pytest.fail("Review must not call a model"))
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    return job, source, run, f"/api/tailoring/resumes/{run['revision']['id']}"


def save_payload(view):
    return {"request_key": str(uuid.uuid4()), "expected_revision_id": view["current_revision_id"], "edit": copy.deepcopy(view["revision"]["edit"])}


def approval_payload(view):
    return {"revision_id": view["revision"]["id"], "content_hash": view["revision"]["content_hash"],
            "validation_hash": view["revision"]["validation_hash"], "input_hash": view["input_hash"]}


def test_edit_review_restore_history_and_job_unchanged(client, completed):
    job, _, run, url = completed
    original = client.get(url).json()
    assert original["history"][0]["origin"] == "generated" and original["approval"] is None
    assert client.post(url + "/review", json=approval_payload(original)).status_code == 201
    assert client.post(url + "/review", json=approval_payload(original)).status_code == 200
    payload = save_payload(original)
    payload["edit"]["bullets"][0]["text"] = "Successfully built an internal Python prototype."
    response = client.post(url + "/revisions", json=payload)
    assert response.status_code == 201, response.text
    edited = response.json()
    assert edited["revision"]["validation"]["valid"] and edited["approval"] is None
    assert edited["changes_from_baseline"][0]["before"]["text"] == original["revision"]["edit"]["bullets"][0]["text"]
    assert client.get(url, params={"revision_id": original["revision"]["id"]}).json()["approval"]
    assert client.post(url + "/review", json=approval_payload(original)).status_code == 409
    assert client.post(url + "/review", json=approval_payload(edited)).json()["approved_current"]
    restored = client.post(url + "/restore", json={"request_key": str(uuid.uuid4()), "expected_revision_id": edited["current_revision_id"], "revision_id": original["revision"]["id"]}).json()
    assert restored["revision"]["origin"] == "restored" and restored["approval"] is None
    assert restored["revision"]["plain_text"] == original["revision"]["plain_text"]
    assert len(restored["history"]) == 3 and not restored["changes_from_baseline"]
    assert client.post(url + "/review", json=approval_payload(restored)).json()["approved_current"]
    assert client.get(f"/api/tailoring/runs/{run['id']}").json()["revision"] == run["revision"]
    assert client.get(f"/api/jobs/{job['id']}").json() == job


@pytest.mark.parametrize("change", [
    lambda edit: edit["bullets"][0].update(text="Deployed to production and improved revenue by 90%."),
    lambda edit: edit["bullets"][0].update(evidence_ids=["C-BLOCKED"]),
    lambda edit: edit["bullets"][0].update(record_id="UNRELATED"),
    lambda edit: edit["skills"].append({"name": "Kubernetes", "source_ids": ["SK-1"]}),
    lambda edit: edit.update(bullets=[]),
    lambda edit: edit["bullets"][0].update(requirement_ids=["UNKNOWN"]),
    lambda edit: edit["bullets"].append(copy.deepcopy(edit["bullets"][0])),
])
def test_invalid_edits_are_saved_but_not_reviewable(client, completed, change):
    *_, url = completed
    payload = save_payload(client.get(url).json())
    change(payload["edit"])
    response = client.post(url + "/revisions", json=payload)
    assert response.status_code == 201, response.text
    view = response.json()
    assert not view["revision"]["validation"]["valid"] and view["revision"]["validation"]["issues"]
    assert not view["approval_eligible"]
    assert client.post(url + "/review", json=approval_payload(view)).status_code == 409
    assert client.get(url).json()["revision"]["edit"] == payload["edit"]


def test_protected_fields_rejected_and_gaps_recomputed(client, completed):
    *_, url = completed
    view = client.get(url).json()
    payload = save_payload(view)
    payload["edit"]["identity"] = {"name": "Invented"}
    assert client.post(url + "/revisions", json=payload).status_code == 422
    payload = save_payload(view)
    payload["edit"]["bullets"][0]["requirement_ids"] = []
    edited = client.post(url + "/revisions", json=payload).json()
    assert edited["revision"]["content"]["draft"]["unmet_requirement_ids"] == ["REQ-1"]
    assert edited["revision"]["content"]["identity"] == view["revision"]["content"]["identity"]


def test_conflict_deduplication_and_approval_hashes(client, completed):
    *_, url = completed
    old = client.get(url).json()
    payload = save_payload(old)
    first = client.post(url + "/revisions", json=payload).json()
    repeated = client.post(url + "/revisions", json=payload)
    assert repeated.status_code == 200 and repeated.json()["revision"]["id"] == first["revision"]["id"]
    changed = copy.deepcopy(payload); changed["edit"]["skills"] = []
    assert client.post(url + "/revisions", json=changed).status_code == 409
    assert client.post(url + "/revisions", json=save_payload(old)).status_code == 409
    for field in ("content_hash", "validation_hash", "input_hash"):
        assert client.post(url + "/review", json={**approval_payload(first), field: "0" * 64}).status_code == 409
    assert len(client.get(url).json()["history"]) == 2


@pytest.mark.parametrize("kind", ["description", "role", "revoked", "superseded"])
def test_source_changes_keep_historical_approval_but_block_new_review(client, completed, kind):
    from tailoring_fixtures import import_payload, bank_data
    job, source, _, url = completed
    view = client.get(url).json()
    assert client.post(url + "/review", json=approval_payload(view)).status_code == 201
    if kind in {"description", "role"}:
        client.patch(f"/api/jobs/{job['id']}", json={"source_content" if kind == "description" else "role_title": "Changed role context"})
    elif kind == "revoked":
        client.post(f"/api/profile/tailoring-sources/{source['id']}/revoke", json={"expected_hash": source["bundle_hash"], "expected_active_id": source["id"]})
    else:
        bank = bank_data(); bank["bank_version"] = "new.synthetic"
        new = client.post("/api/profile/tailoring-sources/import", json=import_payload(bank)).json()
        client.post(f"/api/profile/tailoring-sources/{new['id']}/activate", json={"expected_hash": new["bundle_hash"], "expected_active_id": source["id"]})
    historical = client.get(url).json()
    assert historical["source_problem"] and historical["approval"] and not historical["approved_current"]
    assert client.post(url + "/review", json=approval_payload(historical)).status_code == 409
    edited = client.post(url + "/revisions", json=save_payload(historical)).json()
    assert edited["revision"]["validation"]["valid"] and not edited["approval_eligible"]


def test_cross_profile_and_cross_resume_access(client, completed):
    *_, url = completed
    view = client.get(url).json()
    assert client.get(url, params={"revision_id": str(uuid.uuid4())}).status_code == 404
    assert client.post(url + "/restore", json={"request_key": str(uuid.uuid4()), "expected_revision_id": view["current_revision_id"], "revision_id": str(uuid.uuid4())}).status_code == 404
    client.post("/api/profile", json={"name": "Other profile"})
    assert client.get(url).status_code == 404
    assert client.post(url + "/revisions", json=save_payload(view)).status_code == 404
    assert client.post(url + "/review", json=approval_payload(view)).status_code == 404


def test_backup_roundtrip_legacy_v4_and_tamper_detection(client, completed, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    *_, url = completed
    view = client.get(url).json()
    client.post(url + "/review", json=approval_payload(view))
    edit = client.post(url + "/revisions", json=save_payload(view)).json()
    client.post(url + "/review", json=approval_payload(edit))
    archive = client.get("/api/data/backup").json()
    assert archive["version"] == 5
    content = json.dumps(archive).encode()
    for _ in range(2):
        response = client.post("/api/data/restore", files={"file": ("review.json", content)}, data={"sha256": hashlib.sha256(content).hexdigest(), "confirmation": "RESTORE"})
        assert response.status_code == 200, response.text
        assert client.get(url).json()["approved_current"]
    for table, field, value in (("resume_edit_revisions", "plain_text", "Invented"), ("resume_edit_revisions", "parent_id", "missing"),
                                ("resume_review_approvals", "content_hash", "0"*64), ("resume_review_approvals", "validation_hash", "0"*64)):
        bad = copy.deepcopy(archive); bad["tables"][table][0][field] = value
        assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(bad).encode())}).status_code == 400
    archive["version"] = 4
    del archive["tables"]["resume_edit_revisions"]; del archive["tables"]["resume_review_approvals"]
    content = json.dumps(archive).encode()
    assert client.post("/api/data/restore", files={"file": ("v4.json", content)}, data={"sha256": hashlib.sha256(content).hexdigest(), "confirmation": "RESTORE"}).status_code == 200
    legacy = client.get(url).json()
    assert len(legacy["history"]) == 1 and legacy["approval"] is None


def test_real_sqlite_concurrent_edits_and_immutable_history(client, completed, monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException
    from app.database import build_engine
    from app.migrations import run_migrations
    from app.review_schemas import SaveResumeEdit
    from app.services.resume_review import save
    from app.services.backup_service import restore
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path / "assets"))
    *_, url = completed
    view = client.get(url).json()
    client.post(url + "/review", json=approval_payload(view))
    archive = client.get("/api/data/backup").content
    db_url = "sqlite:///" + (tmp_path / "review.db").as_posix()
    run_migrations(db_url); engine = build_engine(db_url)
    with Session(engine) as db: restore(db, archive, hashlib.sha256(archive).hexdigest())
    barrier = Barrier(2)
    def write_one(_):
        barrier.wait()
        with Session(engine) as db:
            try: return save(db, view["baseline_id"], SaveResumeEdit(**save_payload(view)))[1]
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(write_one, range(2)))
    assert results.count(True) == 1 and results.count(409) == 1
    for table in ("resume_edit_revisions", "resume_review_approvals"):
        with engine.begin() as db:
            with pytest.raises(IntegrityError): db.execute(text(f"UPDATE {table} SET content_hash = 'changed'"))
    with Session(engine) as db:
        from app.services.backup_service import export_archive
        latest = export_archive(db); db.rollback()
        restore(db, latest, hashlib.sha256(latest).hexdigest())
        restore(db, latest, hashlib.sha256(latest).hexdigest())
    engine.dispose()


def test_invalid_provenance_cannot_be_laundered_and_original_can_be_restored(client, completed):
    *_, url = completed
    initial = client.get(url).json()
    payload = save_payload(initial)
    payload["edit"]["bullets"][0]["evidence_ids"] = ["C-BLOCKED"]
    invalid = client.post(url + "/revisions", json=payload).json()
    repeated = client.post(url + "/revisions", json=save_payload(invalid)).json()
    assert not repeated["revision"]["validation"]["valid"]
    restored = client.post(url + "/restore", json={"request_key": str(uuid.uuid4()), "expected_revision_id": repeated["current_revision_id"], "revision_id": initial["revision"]["id"]}).json()
    assert restored["revision"]["validation"]["valid"]
    assert client.post(url + "/review", json=approval_payload(restored)).status_code == 201


def test_select_order_and_remove_approved_content_preserves_record_metadata(client, prepared):
    from tailoring_fixtures import bank_data, import_payload
    job, source = prepared
    bank = bank_data(); bank["bank_version"] = "synthetic.extended"
    bank["records"] += [
        {"id": "R-OLD", "kind": "employment", "employer": "Earlier Co", "title_display": "Original title", "start": "2022-01", "end": "2023-01", "source_id": "S-1"},
        {"id": "P-1", "kind": "project", "name": "Project One", "source_id": "S-1"},
        {"id": "P-2", "kind": "project", "name": "Project Two", "source_id": "S-1"}]
    for rid in ("R-OLD", "P-1", "P-2"):
        cid = "C-" + rid
        bank["claims"].append({"id": cid, "record_id": rid, "source_id": "S-1", "text": f"Built a fictional internal prototype for {rid}.", "evidence_status": "source_supported", "generation_eligible": True})
        bank["approval"]["approved_claim_ids"].append(cid)
    imported = client.post("/api/profile/tailoring-sources/import", json=import_payload(bank))
    assert imported.status_code == 201, imported.text
    new = imported.json()
    assert client.post(f"/api/profile/tailoring-sources/{new['id']}/activate", json={"expected_hash": new["bundle_hash"], "expected_active_id": source["id"]}).status_code == 200
    run = generate(client, job).json(); url = f"/api/tailoring/resumes/{run['revision']['id']}"
    initial = client.get(url).json(); payload = save_payload(initial)
    added = [{"id": "B-" + c["id"], "record_id": c["record_id"], "evidence_ids": [c["id"]], "requirement_ids": [], "text": c["text"]} for c in initial["evidence"] if c["id"] != "C-ALLOWED"]
    payload["edit"]["bullets"] = added + payload["edit"]["bullets"]
    payload["edit"]["project_order"] = ["P-2", "P-1"]
    edited = client.post(url + "/revisions", json=payload)
    assert edited.status_code == 201, edited.text
    view = edited.json()
    assert view["revision"]["validation"]["valid"]
    records = view["revision"]["content"]["records"]
    assert [r["id"] for r in records] == ["R-1", "R-OLD", "P-2", "P-1"]
    assert records[1]["title_display"] == "Original title" and records[1]["end"] == "2023-01"
    reduced = save_payload(view); reduced["edit"]["bullets"] = reduced["edit"]["bullets"][-1:]; reduced["edit"]["project_order"] = []; reduced["edit"]["skills"] = []
    final = client.post(url + "/revisions", json=reduced).json()
    assert final["revision"]["validation"]["valid"] and len(final["revision"]["content"]["records"]) == 1
    assert final["revision"]["content"]["draft"]["skills"] == []

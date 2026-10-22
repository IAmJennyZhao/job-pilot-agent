import copy
import json
import uuid
import pytest
from sqlalchemy import select, update
from app import models
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisedResume, PolishedResume
from app.services import ai_service, resume_generation as service
from app.services.intake_preferences import digest
from app.services.tailoring_provider import ProviderFailure
from generation_fixtures import fake_generation
from tailoring_fixtures import import_payload, bank_data


@pytest.fixture
def prepared(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "synthetic-key")
    monkeypatch.setattr(get_settings(), "openai_model", "synthetic-model")
    monkeypatch.setattr(ai_service, "get_tailoring_output", fake_generation)
    client.post("/api/profile", json={"name": "Synthetic Tester", "skills": []})
    bank = bank_data(); bank["claims"][0]["text"] = "Successfully built an internal Python prototype."
    source = client.post("/api/profile/tailoring-sources/import", json=import_payload(bank)).json()
    response = client.post(f"/api/profile/tailoring-sources/{source['id']}/activate", json={"expected_hash": source["bundle_hash"], "expected_active_id": None})
    assert response.status_code == 200
    job = client.post("/api/jobs", json={"company": "Fictional Employer", "role_title": "Backend Engineer", "source_content": "Build Python services. Minimum 2 years.", "status": "Applied"}).json()
    return job, source


def request_for(client, job_id):
    response = client.get(f"/api/jobs/{job_id}/tailoring")
    assert response.status_code == 200, response.text
    ready = response.json()["readiness"]
    return {"request_key": str(uuid.uuid4()), "expected_input_hash": ready["input_hash"], "reviewed_description_hash": ready["description_hash"], "acknowledged_evaluation_hash": ready["evaluation"]["evaluation_hash"]}


def generate(client, job, payload=None):
    return client.post(f"/api/jobs/{job['id']}/tailoring/resume", json=payload or request_for(client, job["id"]))


@pytest.mark.parametrize("role", ["AI Engineer", "Backend Engineer", "Full Stack Engineer"])
def test_four_pass_generation_preserves_sources_and_job(client, monkeypatch, prepared, role):
    job, source = prepared
    client.patch(f"/api/jobs/{job['id']}", json={"role_title": role})
    before = client.get(f"/api/jobs/{job['id']}").json()
    calls = []
    def provider(*args, **kwargs):
        calls.append(args)
        assert kwargs["timeout"] <= 60
        assert all(secret not in args[2] for secret in ("EXCLUDED_CLAIM_SECRET", "ARCHIVE_ONLY_SECRET", "private@example.test", "Synthetic inert template", "MIXED_DEPENDENCY_SECRET"))
        return fake_generation(*args, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", provider)
    payload = request_for(client, job["id"])
    response = generate(client, job, payload)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["state"] == "completed", run
    assert [call[0] for call in calls] == [ResumeDraft, CritiqueReport, RevisedResume, PolishedResume]
    assert all(stage["state"] == "passed" for stage in run["stages"])
    assert run["revision"]["validation"]["human_review_required"]
    assert run["revision"]["validation"]["wording_changes"]
    assert run["revision"]["content"]["records"][0]["title_display"] == "Engineer"
    assert "Successfully" not in run["revision"]["plain_text"]
    assert generate(client, job, payload).json()["id"] == run["id"]
    assert client.get(f"/api/tailoring/runs/{run['id']}").json()["revision"] == run["revision"]
    assert len(calls) == 4
    assert client.get(f"/api/jobs/{job['id']}").json() == before
    client.patch(f"/api/jobs/{job['id']}", json={"source_content": "Different Python description"})
    assert client.get(f"/api/tailoring/runs/{run['id']}").json()["source_changed"]


def test_readiness_and_stale_request_do_not_call_provider(client, monkeypatch, prepared):
    job, source = prepared
    monkeypatch.setattr(ai_service, "get_tailoring_output", lambda *a, **k: pytest.fail("not ready"))
    payload = request_for(client, job["id"])
    wrong = {**payload, "reviewed_description_hash": "0" * 64}
    assert generate(client, job, wrong).status_code == 409
    client.patch(f"/api/jobs/{job['id']}", json={"source_content": ""})
    assert not client.get(f"/api/jobs/{job['id']}/tailoring").json()["readiness"]["ready"]
    assert generate(client, job, payload).status_code == 422
    client.patch(f"/api/jobs/{job['id']}", json={"source_content": "Changed Python source"})
    assert generate(client, job, payload).status_code == 409
    client.post(f"/api/profile/tailoring-sources/{source['id']}/revoke", json={"expected_hash": source["bundle_hash"], "expected_active_id": source["id"]})
    assert generate(client, job, payload).status_code == 422


def test_validation_repair_is_bounded_and_never_accepts_fake_facts(client, monkeypatch, prepared):
    job, _ = prepared
    calls = []
    def bad(*args, **kwargs):
        output, meta = fake_generation(*args, **kwargs)
        calls.append(args[0])
        if isinstance(output, ResumeDraft):
            output.bullets[0].text = "Deployed Python to production with 98% accuracy."
        return output, meta
    monkeypatch.setattr(ai_service, "get_tailoring_output", bad)
    run = generate(client, job).json()
    assert run["state"] == "failed" and run["revision"] is None
    assert len(calls) == 2 and len(run["stages"]) == 2
    assert "unverified paraphrase" in run["stages"][0]["validation"]["blocking_issues"][0]


def test_explicit_retry_reuses_passed_checkpoints(client, monkeypatch, prepared):
    job, _ = prepared
    calls = []
    def failing(output_model, *args, **kwargs):
        calls.append(output_model)
        if output_model is RevisedResume:
            raise ProviderFailure("Synthetic timeout; completion may be unknown.")
        return fake_generation(output_model, *args, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", failing)
    failed = generate(client, job).json()
    assert failed["state"] == "failed" and len(calls) == 3
    def succeeding(output_model, *args, **kwargs):
        calls.append(output_model)
        return fake_generation(output_model, *args, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", succeeding)
    retried = client.post(f"/api/tailoring/runs/{failed['id']}/retry", json=request_for(client, job["id"]))
    assert retried.status_code == 201, retried.text
    run = retried.json()
    assert run["state"] == "completed", run
    assert run["parent_run_id"] == failed["id"] and len(calls) == 5
    assert sum(bool(a["metadata"].get("reused_from_attempt")) for a in run["stages"]) == 2


def test_active_run_deduplication_deadline_and_late_executor(client, monkeypatch, prepared):
    from datetime import timedelta
    job, _ = prepared
    payload = request_for(client, job["id"])
    monkeypatch.setattr(service, "execute", lambda *args: None)
    pending = generate(client, job, payload).json()
    assert pending["state"] == "pending"
    assert generate(client, job, payload).json()["id"] == pending["id"]
    assert generate(client, job).status_code == 409
    altered = {**payload, "expected_input_hash": "0" * 64}
    assert generate(client, job, altered).status_code == 409
    with next(app.dependency_overrides[get_db]()) as db:
        db.execute(update(models.TailoringRun).where(models.TailoringRun.id == pending["id"]).values(deadline_at=service.now()-timedelta(seconds=1)))
        db.commit()
    assert client.get(f"/api/tailoring/runs/{pending['id']}").json()["state"] == "interrupted"


def test_generation_backup_and_v3_compatibility(client, monkeypatch, prepared, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    job, _ = prepared
    run = generate(client, job).json()
    assert run["state"] == "completed", run
    original = client.get("/api/data/backup").json()
    assert original["version"] == 4
    def restore(archive):
        content = json.dumps(archive).encode()
        response = client.post("/api/data/restore-preview", files={"file": ("archive.json", content)})
        assert response.status_code == 200, response.text
        return client.post("/api/data/restore", files={"file": ("archive.json", content)}, data={"sha256": response.json()["sha256"], "confirmation": "RESTORE"})
    assert restore(original).status_code == 200
    assert client.get(f"/api/tailoring/runs/{run['id']}").json()["revision"] == run["revision"]
    tampered = copy.deepcopy(original)
    tampered["tables"]["tailored_revisions"][0]["plain_text"] = "Invented achievement"
    assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(tampered).encode())}).status_code == 400
    legacy = copy.deepcopy(original); legacy["version"] = 3
    for name in ("tailoring_runs", "tailoring_stage_attempts", "tailored_revisions"):
        del legacy["tables"][name]
    assert restore(legacy).status_code == 200
    assert client.get(f"/api/jobs/{job['id']}/tailoring").json()["runs"] == []

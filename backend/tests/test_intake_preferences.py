import copy
import uuid
import yaml
import pytest
from app import schemas
from app.intake_facts import IntakeFacts, verified_facts
from app.intake_schemas import IntakeReview
from app.tailoring_preferences import Preferences
from app.services import ai_service, job_intake_service
from app.services.intake_preferences import flags_for
from tailoring_fixtures import import_payload


def activate_preferences(client):
    client.post("/api/profile", json={"name": "Synthetic Tester", "skills": []})
    bundle = import_payload()
    bundle["preferences_yaml"] = yaml.safe_dump(preferences().model_dump(by_alias=True))
    source = client.post("/api/profile/tailoring-sources/import", json=bundle).json()
    activated = client.post(f"/api/profile/tailoring-sources/{source['id']}/activate", json={"expected_hash": source["bundle_hash"], "expected_active_id": None})
    assert activated.status_code == 200, activated.text
    return source


def preferences():
    data = yaml.safe_load(import_payload()["preferences_yaml"])
    data["compensation"].update(currency="USD", minimum=135000)
    data["experience"]["preferred_required_years_max"] = 3
    data["company"]["large_enterprise_min_employees"] = 10000
    data["roles"].update(target_families=["software_engineer"], employment_types=["full_time"])
    data["work_life_balance"].update(ideal_hours_per_week=40, preferred_max_hours_per_week=50)
    return Preferences.model_validate(data)


def review(**job):
    return IntakeReview(job=schemas.JobCreate(company="Synthetic", role_title="Engineer", pay_min=130000, pay_max=160000, pay_currency="USD", pay_period="year", **job), facts=IntakeFacts(
        salary_component={"value": "base", "origin": "user"}, salary_band={"value": "applicable", "origin": "user"}))


@pytest.mark.parametrize("patch,expected", [({"pay_min": 135000}, "green"), ({"pay_max": 134999, "pay_min": 100000}, "red"), ({}, "amber"), ({"pay_min": 160000, "pay_max": None}, "green"), ({"pay_min": None}, "amber"), ({"pay_period": "hour"}, "amber"), ({"pay_currency": "CAD"}, "amber")])
def test_salary_boundaries(patch, expected):
    r = review(); r.job = r.job.model_copy(update=patch)
    assert flags_for(r, preferences())[0]["level"] == expected


def test_evidence_unknowns_and_required_not_preferred():
    r = review()
    r.facts = IntakeFacts(required_years={"value": 2, "origin": "posting", "quote": "invented"}, preferred_years={"value": 8, "origin": "user"}, nyc_compatible={"value": "yes", "origin": "user"}, employer_source={"value": "agency", "origin": "user"})
    flags = {f["key"]: f for f in flags_for(r, preferences())}
    assert flags["required_years"]["level"] == "amber"
    assert flags["nyc_compatible"]["level"] == "green"
    assert flags["employer_source"]["level"] == "red"
    assert verified_facts(r.facts, "", extraction=True).nyc_compatible.value is None


def test_pasted_text_preserved_no_fetch_single_extraction(client, monkeypatch):
    text = "  Synthetic Engineer\n\nRemote in NYC.\n  "
    calls = []
    def fake(model, system, prompt):
        calls.append(model)
        return schemas.JobExtractionOutput(company="Synthetic", role_title="Engineer", summary="Basics", confidence=90,
            preference_facts={"nyc_compatible": {"value": "yes", "origin": "posting", "quote": "Remote in NYC."}, "required_years": {"value": 4, "origin": "posting", "quote": "fabricated"}})
    monkeypatch.setattr(ai_service, "get_structured_output", fake)
    monkeypatch.setattr(job_intake_service, "fetch_job_page_text", lambda _: pytest.fail("must not fetch"))
    response = client.post("/api/jobs/extract-preview", json={"source_url": "https://example.test/job", "source_content": text})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source_content"] == text and len(calls) == 1
    assert data["preference_facts"]["required_years"]["value"] is None
    assert data["preference_facts"]["nyc_compatible"]["value"] == "yes"
    assert client.get("/api/jobs").json() == []


def test_save_retry_duplicates_stale_evaluation_and_preparation(client):
    payload = review(source_content="Complete fictional description").model_dump(mode="json")
    payload["full_description_reviewed"] = True
    evaluated = client.post("/api/jobs/intake/evaluate", json=payload).json()
    assert evaluated["available"] is False
    assert client.get("/api/jobs").json() == []
    request = {**payload, "request_key": str(uuid.uuid4()), "decision": "continue", "expected_evaluation_hash": evaluated["evaluation_hash"]}
    wrong = {**request, "expected_evaluation_hash": "0" * 64}
    assert client.post("/api/jobs/intake/save", json=wrong).status_code == 409
    first = client.post("/api/jobs/intake/save", json=request)
    assert first.status_code == 200, first.text
    job = first.json()
    assert job["status"] == "Saved"
    assert client.post("/api/jobs/intake/save", json=request).json()["id"] == job["id"]
    assert len(client.get("/api/jobs").json()) == 1
    changed = copy.deepcopy(request); changed["job"]["company"] = "Another"
    assert client.post("/api/jobs/intake/save", json=changed).status_code == 409
    assert client.post("/api/jobs/intake/save", json={**request, "request_key": str(uuid.uuid4())}).status_code == 409
    preparation = client.get(f"/api/jobs/{job['id']}/intake").json()
    assert preparation["full_description_ready"] and preparation["generation_available"]
    client.patch(f"/api/jobs/{job['id']}", json={"source_content": "Changed"})
    assert client.get(f"/api/jobs/{job['id']}/intake").json()["review_stale"]


def test_active_preferences_red_override_and_changed_preferences(client):
    source = activate_preferences(client)
    payload = review().model_dump(mode="json")
    payload["job"].update(pay_min=100000, pay_max=120000, status="Applied")
    evaluation = client.post("/api/jobs/intake/evaluate", json=payload).json()
    assert evaluation["flags"][0]["level"] == "red"
    request = {**payload, "request_key": str(uuid.uuid4()), "decision": "continue", "expected_evaluation_hash": evaluation["evaluation_hash"]}
    response = client.post("/api/jobs/intake/save", json=request)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Saved"
    client.post(f"/api/profile/tailoring-sources/{source['id']}/revoke", json={"expected_hash": source["bundle_hash"], "expected_active_id": source["id"]})
    request["request_key"] = str(uuid.uuid4())
    assert client.post("/api/jobs/intake/save", json=request).status_code == 409
    preparation = client.get(f"/api/jobs/{response.json()['id']}/intake").json()
    assert not preparation["sources_ready"] and preparation["saved_evaluation"]["available"]
    assert not preparation["current_evaluation"]["available"]


def test_intake_backup_roundtrip_and_legacy_v2(client, monkeypatch, tmp_path):
    import json
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    activate_preferences(client)
    payload = review().model_dump(mode="json")
    evaluation = client.post("/api/jobs/intake/evaluate", json=payload).json()
    response = client.post("/api/jobs/intake/save", json={**payload, "request_key": str(uuid.uuid4()), "decision": "save_later", "expected_evaluation_hash": evaluation["evaluation_hash"]})
    assert response.status_code == 200
    archive = client.get("/api/data/backup").json()
    for legacy in (False, True):
        candidate = copy.deepcopy(archive)
        if legacy:
            candidate["version"] = 2
            del candidate["tables"]["job_intake_reviews"]
            for name in ("tailoring_runs", "tailoring_stage_attempts", "tailored_revisions", "resume_edit_revisions", "resume_review_approvals"):
                del candidate["tables"][name]
        content = json.dumps(candidate).encode()
        preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", content)})
        assert preview.status_code == 200, preview.text
        restored = client.post("/api/data/restore", files={"file": ("backup.json", content)}, data={"sha256": preview.json()["sha256"], "confirmation": "RESTORE"})
        assert restored.status_code == 200, restored.text
        rows = client.get("/api/data/backup").json()["tables"]["job_intake_reviews"]
        assert len(rows) == (0 if legacy else 1)
    archive["tables"]["job_intake_reviews"][0]["evaluation"]["flags"][0]["level"] = "green"
    bad = client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(archive).encode())})
    assert bad.status_code == 400


def test_failed_intake_save_rolls_back_job_and_events(client, monkeypatch):
    from app import models
    from app.database import get_db
    from app.main import app
    from sqlalchemy import select, event
    from sqlalchemy.orm import Session
    payload = review().model_dump(mode="json")
    evaluation = client.post("/api/jobs/intake/evaluate", json=payload).json()
    request = {**payload, "request_key": str(uuid.uuid4()), "decision": "save_later", "expected_evaluation_hash": evaluation["evaluation_hash"]}
    def fail(session, _context, _instances):
        if any(isinstance(row, models.JobIntakeReview) for row in session.new):
            raise RuntimeError("Synthetic save interruption")
    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="Synthetic save interruption"):
            client.post("/api/jobs/intake/save", json=request)
    finally:
        event.remove(Session, "before_flush", fail)
    assert client.get("/api/jobs").json() == []
    with next(app.dependency_overrides[get_db]()) as db:
        assert list(db.scalars(select(models.JobStatusEvent))) == []
    assert client.post("/api/jobs/intake/save", json=request).status_code == 200


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///private.txt", "https://user:secret@example.test/job", "not-a-url"])
def test_intake_rejects_invalid_source_and_review_links(client, url):
    assert client.post("/api/jobs/extract-preview", json={"source_url": url}).status_code == 422
    payload = review().model_dump(mode="json")
    payload["job"]["links"] = [{"label": "Posting", "url": url}]
    assert client.post("/api/jobs/intake/evaluate", json=payload).status_code == 422


def test_extraction_provider_has_no_hidden_retries_and_safe_errors(monkeypatch, caplog):
    from types import SimpleNamespace
    from fastapi import HTTPException
    calls = []
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.responses = self
        def parse(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("PRIVATE_PROVIDER_DETAILS")
    monkeypatch.setattr(ai_service, "get_settings", lambda: SimpleNamespace(openai_api_key="synthetic", openai_model="synthetic"))
    monkeypatch.setattr(ai_service, "OpenAI", FakeClient)
    with pytest.raises(HTTPException) as error:
        ai_service.get_structured_output(schemas.JobExtractionOutput, "system", "synthetic posting")
    assert len(calls) == 1 and error.value.status_code == 502
    assert "PRIVATE_PROVIDER_DETAILS" not in error.value.detail + caplog.text

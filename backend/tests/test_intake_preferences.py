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
    assert preparation["full_description_ready"] and not preparation["generation_available"]
    client.patch(f"/api/jobs/{job['id']}", json={"source_content": "Changed"})
    assert client.get(f"/api/jobs/{job['id']}/intake").json()["review_stale"]

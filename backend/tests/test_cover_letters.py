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


def test_templates_supply_style_only_and_company_context_requires_approval(client, letter, monkeypatch):
    job, _ = letter
    template = client.post("/api/profile/cover-letter-templates", json={"title": "Fictional style", "body": "REFERRAL_SECRET: my friend is your CEO. I built UNAPPROVED_PLATFORM."}).json()
    calls = []
    def provider(output_model, system, payload, **kwargs):
        calls.append(json.loads(payload))
        assert all(secret not in payload for secret in ("REFERRAL_SECRET", "UNAPPROVED_PLATFORM", "EXCLUDED_CLAIM_SECRET", "ARCHIVE_ONLY_SECRET", "private@example.test"))
        return fake_letter(output_model, system, payload, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", provider)
    context = {"text": "The company develops educational software.", "source_url": "https://example.test/about", "confirmed": True}
    rejected = generate(client, job, count=1, length="short", company_context={**context, "confirmed": False})
    assert rejected.status_code == 422 and not calls
    assert generate(client, job, company_context={**context, "source_url": "javascript:alert(1)"}).status_code == 422
    _, url = completed(client, job, count=1, length="short", template_id=template["id"], company_context=context)
    assert calls[0]["style"]["word_count"] > 0
    assert client.get(url).json()["job_evidence"][-1]["text"] == context["text"]
    assert client.delete(f"/api/profile/cover-letter-templates/{template['id']}").status_code == 204
    archive = client.get("/api/data/backup").content
    assert client.post("/api/data/restore-preview", files={"file": ("archive.json", archive)}).status_code == 200


def test_unrelated_valid_claim_and_incomplete_assessments_fail_closed(client, letter, monkeypatch):
    from app.services import letter_validation as policy
    from app.database import get_db
    from app.main import app
    from app import models
    job, _ = letter
    run, _ = completed(client, job, count=1, length="short")
    with next(app.dependency_overrides[get_db]()) as db:
        snapshot = copy.deepcopy(db.get(models.TailoringRun, run["id"]).snapshot)
    content = copy.deepcopy(run["revision"]["content"])
    # An existing, eligible source about documentation cannot entail building a prototype.
    unrelated = copy.deepcopy(snapshot["projection"]["claims"][0])
    unrelated.update(id="C-UNRELATED", text="Documented internal operating procedures.", technologies=[], technology_ids=[])
    snapshot["projection"]["claims"].append(unrelated)
    sentence = content["variants"][0]["paragraphs"][0]["sentences"][1]
    sentence.update(text="I created an internal prototype.", candidate_evidence_ids=["C-UNRELATED"])
    assessment = fake_letter(LetterAssessment, "", json.dumps(policy.assessment_payload(content, snapshot)))[0].model_dump()
    assert not policy.validate(content, snapshot, assessment)["valid"]
    assert any("Unsupported" in i["message"] for i in policy.validate(content, snapshot, assessment)["issues"])
    # Faithful paraphrases with low word overlap are accepted, independently of resume rules.
    original = run["revision"]["content"]
    valid = fake_letter(LetterAssessment, "", json.dumps(policy.assessment_payload(original, snapshot)))[0].model_dump()
    assert policy.validate(original, snapshot, valid)["valid"]
    for transform in (
        lambda a: a["sentences"].pop(),
        lambda a: a["sentences"].append(copy.deepcopy(a["sentences"][0])),
        lambda a: a["sentences"][1]["supports"][0].update(quote="Fabricated supporting quote"),
        lambda a: a["sentences"][1].update(actual_kind="transition"),
    ):
        changed = copy.deepcopy(valid); transform(changed)
        assert not policy.validate(original, snapshot, changed)["valid"]


def test_manual_check_failure_deduplication_and_historical_approval(client, letter, monkeypatch):
    job, _ = letter
    _, url = completed(client, job, count=1, length="short")
    original = client.get(url).json()
    client.post(url + "/review", json=approval_payload(original))
    saved = client.post(url + "/revisions", json=save_payload(original)).json()
    calls = []
    def failure(*args, **kwargs):
        calls.append(1)
        raise ProviderFailure("Synthetic timeout; completion may be unknown.")
    monkeypatch.setattr(ai_service, "get_tailoring_output", failure)
    payload = check_payload(saved)
    failed = client.post(url + "/check", json=payload).json()
    assert failed["checks"][0]["state"] == "failed" and not failed["approval_eligible"]
    assert client.post(url + "/check", json=payload).status_code == 200 and len(calls) == 1
    assert client.post(url + "/check", json={**payload, "content_hash": "0"*64}).status_code == 409
    client.get(url)
    assert len(calls) == 1
    assert client.get(f"{url}/revisions/{original['revision']['id']}/download/0/txt").status_code == 200
    monkeypatch.setattr(ai_service, "get_tailoring_output", fake_letter)
    checked = client.post(url + "/check", json=check_payload(saved)).json()
    assert checked["approval_eligible"]
    assert client.post(url + "/review", json={**approval_payload(checked), "validation_hash": saved["revision"]["validation_hash"]}).status_code == 409


def test_generation_repair_is_bounded_and_does_not_replace_reviewed_history(client, letter, monkeypatch):
    job, _ = letter
    original, url = completed(client, job, count=1, length="short")
    client.post(url + "/review", json=approval_payload(client.get(url).json()))
    calls = []
    def unsupported(output_model, system, payload, **kwargs):
        calls.append(output_model)
        result, metadata = fake_letter(output_model, system, payload, **kwargs)
        if output_model is LetterDraft:
            result.variants[0].paragraphs[0].sentences[1].text = "I deployed this internal Python prototype to production."
        return result, metadata
    monkeypatch.setattr(ai_service, "get_tailoring_output", unsupported)
    failed = generate(client, job, count=1, length="short").json()
    assert failed["state"] == "failed" and failed["revision"] is None
    assert calls == [LetterDraft, LetterAssessment, LetterDraft, LetterAssessment]
    assert client.get(url).json()["approved_current"]
    assert client.get(f"/api/cover-letters/runs/{original['id']}").json()["state"] == "completed"


def test_pending_checks_recover_without_automatic_calls(client, letter, monkeypatch):
    from datetime import timedelta
    from sqlalchemy import select, update
    from app import models
    from app.database import get_db
    from app.main import app
    from app.services import cover_letters, resume_generation
    job, _ = letter
    run, url = completed(client, job, count=1, length="short")
    saved = client.post(url + "/revisions", json=save_payload(client.get(url).json())).json()
    monkeypatch.setattr(cover_letters, "stage_call", lambda *a, **kw: None)
    pending = client.post(url + "/check", json=check_payload(saved)).json()
    assert pending["checks"][0]["state"] == "running"
    assert client.post(url + "/check", json=check_payload(saved)).status_code == 409
    with next(app.dependency_overrides[get_db]()) as db:
        db.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run["id"], models.TailoringStageAttempt.stage == "letter_check")
            .values(started_at=resume_generation.now()-timedelta(seconds=71)))
        db.commit()
    monkeypatch.setattr(ai_service, "get_tailoring_output", lambda *a, **kw: pytest.fail("Read called provider"))
    expired = client.get(url).json()
    assert expired["checks"][0]["state"] == "interrupted" and not expired["approval_eligible"]
    archive = client.get("/api/data/backup").content
    assert client.post("/api/data/restore-preview", files={"file": ("archive.json", archive)}).status_code == 200


def test_migrated_sqlite_serializes_checks_and_preserves_immutable_approval(client, letter, monkeypatch, tmp_path):
    import hashlib
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    from threading import Barrier, Event
    from fastapi import HTTPException
    from sqlalchemy import select, update
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from app import models
    from app.database import build_engine
    from app.migrations import run_migrations
    from app.letter_schemas import GenerateLetter, SaveLetterEdit, CheckLetter
    from app.review_schemas import ReviewResume
    from app.services import resume_generation, resume_review, cover_letters
    from app.services.backup_service import restore, export_archive, validate_archive
    job, _ = letter
    payload = {**request_for(client, job["id"]), "options": {"count": 1, "length": "short"}}
    archive = client.get("/api/data/backup").content
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path / "assets"))
    db_url = "sqlite:///" + (tmp_path / "letters.db").as_posix()
    run_migrations(db_url)
    engine = build_engine(db_url)
    with Session(engine) as db:
        restore(db, archive, hashlib.sha256(archive).hexdigest())
        run_id, _ = resume_generation.start(db, db.get(models.Job, job["id"]), GenerateLetter.model_validate(payload), document_kind="cover_letter")
    cover_letters.execute(engine, run_id)
    with Session(engine) as db:
        assert db.get(models.TailoringRun, run_id).state == "completed"
        base = db.scalar(select(models.TailoredRevision).where(models.TailoredRevision.run_id == run_id))
        baseline_id = base.id
        view = cover_letters.view(db, baseline_id)
        resume_review.save(db, baseline_id, SaveLetterEdit.model_validate(save_payload(view)))
        saved = cover_letters.view(db, baseline_id)
    barrier, release = Barrier(2), Event()
    calls = []
    def provider(*args, **kwargs):
        calls.append(1)
        assert release.wait(10), "Concurrent second check did not return"
        return fake_letter(*args, **kwargs)
    monkeypatch.setattr(ai_service, "get_tailoring_output", provider)
    def check_one(_):
        barrier.wait()
        with Session(engine) as db:
            try:
                cover_letters.check(db, baseline_id, CheckLetter.model_validate(check_payload(saved)))
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(check_one, i) for i in range(2)]
        try:
            done, _ = wait(futures, timeout=8, return_when=FIRST_COMPLETED)
            assert done and next(iter(done)).result() == 409
        finally:
            release.set()
        assert sorted(f.result() for f in futures) == [200, 409]
    assert len(calls) == 1
    with Session(engine) as db:
        checked = cover_letters.view(db, baseline_id)
        resume_review.approve(db, baseline_id, ReviewResume.model_validate(approval_payload(checked)))
        data = cover_letters.download(db, baseline_id, checked["revision"]["id"], 0, "txt")
        assert b"Dear Hiring Team," in data
        exported = export_archive(db)
        validate_archive(exported)
        attempt = db.scalar(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run_id, models.TailoringStageAttempt.stage == "letter_check"))
        with pytest.raises(IntegrityError):
            db.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.id == attempt.id).values(output_data={}))
        db.rollback()
        restore(db, exported, hashlib.sha256(exported).hexdigest())
        assert cover_letters.download(db, baseline_id, checked["revision"]["id"], 0, "txt") == data
    engine.dispose()


def test_v6_resume_archive_remains_compatible(client, letter, monkeypatch):
    from generation_fixtures import fake_generation
    from test_resume_generation import generate as generate_resume
    monkeypatch.setattr(ai_service, "get_tailoring_output", fake_generation)
    job, _ = letter
    assert generate_resume(client, job).json()["state"] == "completed"
    archive = client.get("/api/data/backup").json()
    archive["version"] = 6
    assert client.post("/api/data/restore-preview", files={"file": ("v6.json", json.dumps(archive).encode())}).status_code == 200


@pytest.mark.parametrize("source_value,letter_value,valid", [("-10%", "10%", False), ("−10%", "10%", False), ("$10", "10", False), ("10%", "10%", True)])
def test_numeric_signs_and_metric_constraints_are_preserved(client, letter, source_value, letter_value, valid):
    from app import models
    from app.database import get_db
    from app.main import app
    from app.services import letter_validation as policy
    job, _ = letter
    run, _ = completed(client, job, count=1, length="short")
    with next(app.dependency_overrides[get_db]()) as db:
        snapshot = copy.deepcopy(db.get(models.TailoringRun, run["id"]).snapshot)
    claim = snapshot["projection"]["claims"][0]
    claim["text"] = f"Built an internal Python prototype with a measured {source_value} change."
    metric = {"id": "M-TEST", "claim_id": claim["id"], "display": source_value, "unit": "test change", "constraints": ["Internal experiment only"], "derived_percentages_allowed": False}
    snapshot["projection"]["protected_metrics"].append(metric)
    content = copy.deepcopy(run["revision"]["content"])
    content["variants"][0]["paragraphs"][0]["sentences"][1]["text"] = f"I measured a {letter_value} change in the internal Python prototype."
    data = policy.assessment_payload(content, snapshot)
    assert data["sentences"][1]["protected_metrics"] == [metric]
    assessed = fake_letter(LetterAssessment, "", json.dumps(data))[0].model_dump()
    assert policy.validate(content, snapshot, assessed)["valid"] == valid

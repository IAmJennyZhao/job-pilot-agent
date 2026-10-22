import json

import pytest
from sqlalchemy import select, text

from app import models
from app.database import get_db
from app.main import app
from app.services import tailoring_source_service as service
from app.services.backup_service import TAILORING_TABLES, INTAKE_TABLES, GENERATION_TABLES, REVIEW_TABLES, RENDER_TABLES, V1_TABLES
from tailoring_fixtures import bank_data, import_payload

URL = "/api/profile/tailoring-sources"


def setup(client):
    profile = client.post("/api/profile", json={"name": "Fictional Tester", "skills": ["Python"]}).json()
    job = client.post("/api/jobs", json={"company": "Fictional Employer", "role_title": "Engineer"}).json()
    return profile, job


def imported(client, bank=None):
    response = client.post(URL + "/import", json=import_payload(bank))
    assert response.status_code in {200, 201}, response.text
    return response.json()


def activate(client, source, active_id=None, action="activate"):
    return client.post(f"{URL}/{source['id']}/{action}", json={
        "expected_hash": source["bundle_hash"], "expected_active_id": active_id})


def test_import_preview_activate_revoke_and_no_job_side_effects(client):
    _, job = setup(client)
    before = client.get(f"/api/jobs/{job['id']}").json()
    source = imported(client)
    assert source["status"] == "pending"
    assert client.get(URL).json()["active_id"] is None
    assert source["eligible_count"] == 1 and source["excluded_count"] == 1
    duplicate = client.post(URL + "/import", json=import_payload())
    assert duplicate.status_code == 200 and duplicate.json()["id"] == source["id"]
    assert len(client.get(URL).json()["versions"]) == 1
    assert activate(client, source).json()["status"] == "active"
    assert activate(client, source, source["id"]).status_code == 200
    assert len(client.get(f"{URL}/{source['id']}").json()["events"]) == 1
    with next(app.dependency_overrides[get_db]()) as db:
        assert len(service.active_projection(db)["claims"]) == 1
    assert activate(client, source, source["id"], "revoke").json()["status"] == "revoked"
    assert client.get(URL).json()["active_id"] is None
    assert activate(client, source).status_code == 409
    assert client.get(f"/api/jobs/{job['id']}").json() == before


def test_changes_require_new_bank_version_and_reactivation(client):
    setup(client)
    first = imported(client)
    activate(client, first)
    bank = bank_data(); bank["claims"][0]["text"] = "A revised supported accomplishment."
    assert client.post(URL + "/import", json=import_payload(bank)).status_code == 409
    bank["bank_version"] = "synthetic.2"
    second = imported(client, bank)
    assert activate(client, second).status_code == 409  # stale expected-active pointer
    response = activate(client, second, first["id"])
    assert response.status_code == 200
    assert client.get(f"{URL}/{first['id']}").json()["status"] == "superseded"
    assert client.get(f"{URL}/{first['id']}").json()["claims"][0]["text"] == first["claims"][0]["text"]
    assert client.get(URL).json()["active_id"] == second["id"]


def test_bad_hash_unapproved_and_cross_profile_activation_blocked(client):
    setup(client)
    source = imported(client)
    assert client.post(f"{URL}/{source['id']}/activate", json={"expected_hash": "0" * 64, "expected_active_id": None}).status_code == 409
    draft = bank_data(); draft["bank_version"] = "draft.1"; draft["approval"]["status"] = "draft"
    assert activate(client, imported(client, draft)).status_code == 409
    client.post("/api/profile", json={"name": "Another Fictional Profile"})
    assert client.get(f"{URL}/{source['id']}").status_code == 404
    assert activate(client, source).status_code == 404
    assert client.get(URL).json()["versions"] == []


def test_invalid_import_and_no_profile_have_no_writes(client):
    assert client.post(URL + "/import", json=import_payload()).status_code == 409
    setup(client)
    payload = import_payload(); payload["bank_markdown"] = "Not a bank"
    assert client.post(URL + "/import", json=payload).status_code == 422
    assert client.get(URL).json()["versions"] == []


def test_tampered_stored_projection_cannot_be_activated(client):
    setup(client)
    source = imported(client)
    # Fixture create_all has no migration triggers: exercise the service's independent check.
    with next(app.dependency_overrides[get_db]()) as db:
        row = db.get(models.TailoringSourceVersion, source["id"])
        row.projection = {**row.projection, "claims": []}
        db.commit()
    assert activate(client, source).status_code == 409


def test_backup_v2_roundtrip_includes_sources_and_activation(client, monkeypatch, tmp_path):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    setup(client)
    source = imported(client); activate(client, source)
    original = client.get("/api/data/backup").json()
    assert original["version"] == 6
    assert original["tables"]["tailoring_source_versions"][0]["template_tex"] == "Synthetic inert template"
    content = json.dumps(original).encode()
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", content)}).json()
    activate(client, source, source["id"], "revoke")
    restored = client.post("/api/data/restore", files={"file": ("backup.json", content)},
                           data={"sha256": preview["sha256"], "confirmation": "RESTORE"})
    assert restored.status_code == 200, restored.text
    assert client.get(URL).json()["active_id"] == source["id"]
    assert client.get("/api/data/backup").json()["tables"] == original["tables"]
    with next(app.dependency_overrides[get_db]()) as db:
        assert service.active_projection(db)["claims"][0]["id"] == "C-ALLOWED"


def test_legacy_v1_archive_upgrades_with_empty_sources(client, monkeypatch, tmp_path):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    _, job = setup(client)
    legacy = client.get("/api/data/backup").json()
    legacy["version"] = 1
    for name in TAILORING_TABLES | INTAKE_TABLES | GENERATION_TABLES | REVIEW_TABLES | RENDER_TABLES: del legacy["tables"][name]
    assert set(legacy["tables"]) == V1_TABLES
    source = imported(client); activate(client, source)
    content = json.dumps(legacy).encode()
    preview = client.post("/api/data/restore-preview", files={"file": ("legacy.json", content)})
    assert preview.status_code == 200, preview.text
    assert preview.json()["counts"]["tailoring_source_versions"] == 0
    result = client.post("/api/data/restore", files={"file": ("legacy.json", content)},
                         data={"sha256": preview.json()["sha256"], "confirmation": "RESTORE"})
    assert result.status_code == 200, result.text
    assert client.get(URL).json()["versions"] == []
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200
    recovery = client.get(f"/api/data/recovery/{result.json()['recovery_id']}").json()
    assert len(recovery["tables"]["tailoring_source_versions"]) == 1


@pytest.mark.parametrize("tamper", [
    lambda t: t["tailoring_source_versions"][0]["projection"].update(claims=[]),
    lambda t: t["tailoring_source_versions"][0].update(bundle_hash="0" * 64),
    lambda t: t["tailoring_source_events"][0].update(action="revoked"),
    lambda t: t["tailoring_source_events"][0].update(sequence=2),
    lambda t: t["tailoring_profile_states"][0].update(active_source_id=None),
])
def test_restore_rejects_corrupted_sources_before_touching_data(client, tamper):
    setup(client); source = imported(client); activate(client, source)
    archive = client.get("/api/data/backup").json()
    tamper(archive["tables"])
    result = client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(archive).encode())})
    assert result.status_code == 400
    assert client.get(URL).json()["active_id"] == source["id"]


def test_migration_protects_source_and_event_updates(tmp_path):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    from app.database import build_engine
    from app.migrations import run_migrations
    url = f"sqlite:///{(tmp_path / 'sources.db').as_posix()}"
    run_migrations(url)
    engine = build_engine(url)
    with Session(engine) as db:
        db.add(models.ResumeProfile(name="Fictional", is_active=True)); db.commit()
        from app.tailoring_schemas import SourceImport, ActivateSource
        source, _ = service.import_source(db, SourceImport(**import_payload()))
        service.change_activation(db, source, ActivateSource(expected_hash=source.bundle_hash, expected_active_id=None))
        for table, column in [("tailoring_source_versions", "bank_version"), ("tailoring_source_events", "action")]:
            with pytest.raises(IntegrityError):
                db.execute(text(f"UPDATE {table} SET {column}='tampered'"))
            db.rollback()
    engine.dispose()

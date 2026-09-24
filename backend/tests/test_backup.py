import base64
import json
import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main import app
from app import models


def setup_data(client):
    client.post("/api/profile", json={"name": "Backup Tester", "skills": ["Python"]})
    resume = client.post("/api/profile/resume-options", json={"title": "Resume", "parsed_text": "Saved resume text"}).json()
    job = client.post("/api/jobs", json={"company": "=SUM(A1)", "role_title": "Engineer", "notes": "Comma, newline\nand quotes \"here\""}).json()
    client.put(f"/api/actions/{job['id']}", json={"title": "Follow up", "due_date": "2026-10-01"})
    return job, resume


def test_backup_roundtrip_restores_pdf_and_keeps_recovery(client, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    job, resume = setup_data(client)
    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsynthetic attachment")
    db = next(app.dependency_overrides[get_db]())
    with db:
        row = db.get(models.ResumeOption, resume["id"])
        row.file_path = str(pdf)
        row.source_filename = "original.pdf"
        db.commit()
    archive = client.get("/api/data/backup")
    assert archive.status_code == 200
    content = archive.content
    payload = archive.json()
    assert payload["tables"]["resume_options"][0]["file_path"] is None
    assert base64.b64decode(payload["files"][resume["id"]]) == pdf.read_bytes()
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", content)}).json()
    assert preview["counts"]["jobs"] == 1 and preview["files"] == 1
    client.post("/api/jobs", json={"company": "New data", "role_title": "Later"})
    restore = client.post("/api/data/restore", files={"file": ("backup.json", content)}, data={"sha256": preview["sha256"], "confirmation": "RESTORE"})
    assert restore.status_code == 200, restore.text
    assert len(client.get("/api/jobs").json()) == 1
    assert client.get(f"/api/actions/{job['id']}").json()["title"] == "Follow up"
    assert client.get(f"/api/profile/resume-options/{resume['id']}/download").content == pdf.read_bytes()
    recovery = client.get(f"/api/data/recovery/{restore.json()['recovery_id']}").json()
    assert client.get("/api/data/recoveries").json()[0]["id"] == restore.json()["recovery_id"]
    assert len(recovery["tables"]["jobs"]) == 2
    after = client.get("/api/data/backup").json()
    assert after["tables"] == payload["tables"]
    assert after["files"] == payload["files"]
    csv = client.get("/api/data/jobs.csv").content.decode("utf-8-sig")
    assert "'=SUM(A1)" in csv and '"Comma, newline\nand quotes ""here"""' in csv


def test_invalid_restore_never_replaces_data(client, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    job, _ = setup_data(client)
    content = client.get("/api/data/backup").content
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", content)}).json()
    for data, status in [({"sha256": "wrong", "confirmation": "RESTORE"}, 409), ({"sha256": preview["sha256"], "confirmation": "no"}, 400)]:
        assert client.post("/api/data/restore", files={"file": ("backup.json", content)}, data=data).status_code == status
    archive = json.loads(content)
    archive["tables"]["job_actions"][0]["job_id"] = "missing"
    assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(archive).encode())}).status_code == 400
    archive = json.loads(content)
    archive["tables"]["resume_options"][0]["file_path"] = "../../outside.pdf"
    assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(archive).encode())}).status_code == 400
    archive = json.loads(content)
    archive["tables"]["jobs"][0]["required_skills"] = "not a list"
    assert client.post("/api/data/restore-preview", files={"file": ("bad.json", json.dumps(archive).encode())}).status_code == 400
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200
    assert not (tmp_path / "backups").exists()


def test_restore_commit_failure_rolls_back_replacement(client, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    setup_data(client)
    content = client.get("/api/data/backup").content
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", content)}).json()
    extra = client.post("/api/jobs", json={"company": "Must survive rollback", "role_title": "Engineer"}).json()
    with monkeypatch.context() as context:
        def fail_commit(_self):
            raise RuntimeError("Simulated commit failure")
        context.setattr(Session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="Simulated commit failure"):
            client.post("/api/data/restore", files={"file": ("backup.json", content)}, data={"sha256": preview["sha256"], "confirmation": "RESTORE"})
    assert client.get(f"/api/jobs/{extra['id']}").status_code == 200
    assert len(client.get("/api/jobs").json()) == 2
    assert len(client.get("/api/data/recoveries").json()) == 1


def test_missing_pdf_is_disclosed_and_text_is_retained(client, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    _, resume = setup_data(client)
    with next(app.dependency_overrides[get_db]()) as db:
        row = db.get(models.ResumeOption, resume["id"])
        row.file_path = str(tmp_path / "missing.pdf")
        row.source_filename = "missing.pdf"
        db.commit()
    archive = client.get("/api/data/backup")
    assert archive.json()["missing_files"] == ["missing.pdf"]
    preview = client.post("/api/data/restore-preview", files={"file": ("backup.json", archive.content)}).json()
    assert preview["missing_files"] == ["missing.pdf"]
    response = client.post("/api/data/restore", files={"file": ("backup.json", archive.content)}, data={"sha256": preview["sha256"], "confirmation": "RESTORE"})
    assert response.status_code == 200
    restored = client.get("/api/data/backup").json()
    assert restored["missing_files"] == ["missing.pdf"]
    assert restored["tables"]["resume_options"][0]["parsed_text"] == "Saved resume text"

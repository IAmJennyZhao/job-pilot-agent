import base64
import copy
import hashlib
import json
import pytest
from app import models
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.services import resume_compiler
from test_resume_generation import prepared
from test_resume_review import completed, approval_payload, save_payload


def test_malformed_pdf_reports_validation_failure():
    with pytest.raises(ValueError, match="Invalid or unreadable PDF"):
        resume_compiler.inspect_pdf(b"%PDF-1.7\ntruncated artifact", "Resume")


def test_unreadable_compiler_output_preserves_review_without_publishing(client, completed, monkeypatch):
    *_, url = completed
    view = client.get(url).json()
    monkeypatch.setattr(resume_compiler, "compile_pdf", lambda *a: (b"%PDF-1.7\ntruncated artifact", []))
    response = client.post(url + "/renders", json=approval_payload(view))
    assert response.status_code == 422 and "Invalid or unreadable PDF" in response.text
    assert client.get(url).json() == view
    assert client.get(url + "/renders", params={"revision_id": view["revision"]["id"]}).json() == []


def rendered(client, url):
    view = client.get(url).json()
    response = client.post(url + "/renders", json=approval_payload(view))
    assert response.status_code == 200, response.text
    return view, response.json()


def final(client, url, view, render):
    assert client.post(url + "/review", json=approval_payload(view)).status_code in {200, 201}
    preview = client.post(url + f"/renders/{render['id']}/preview").json()
    payload = {k: preview[k] for k in ("preview_receipt_id", "manifest_hash")}
    payload["layout_reviewed"] = True
    response = client.post(url + f"/renders/{render['id']}/approve", json=payload)
    assert response.status_code == 200, response.text
    return preview, payload


def test_preview_final_downloads_historical_sources_and_no_job_mutation(client, completed, monkeypatch):
    job, source, _, url = completed
    view, render = rendered(client, url)
    path = url + f"/renders/{render['id']}"
    assert render["validation"]["valid"], render
    for format in ("pdf", "tex", "txt"):
        assert client.get(path + "/download/" + format).status_code == 409
    assert client.post(path + "/approve", json={"preview_receipt_id": "0"*36, "manifest_hash": render["manifest_hash"], "layout_reviewed": True}).status_code == 409
    # An imported inert/placeholder template is never compiled.
    assert "Synthetic inert template" not in base64.b64decode(client.get("/api/data/backup").json()["tables"]["resume_renders"][0]["bundle"]["files"]["tex"]).decode()
    preview, approval = final(client, url, view, render)
    assert preview["page_images"] and base64.b64decode(preview["page_images"][0]).startswith(b"\x89PNG")
    files = {format: client.get(path + "/download/" + format).content for format in ("pdf", "tex", "txt")}
    assert files["pdf"] == base64.b64decode(preview["pdf_base64"])
    assert view["revision"]["edit"]["bullets"][0]["text"] in files["txt"].decode()
    for format, data in files.items():
        assert hashlib.sha256(data).hexdigest() == render["hashes"][format]
    assert client.post(path + "/approve", json=approval).status_code == 200
    monkeypatch.setattr(resume_compiler, "compile_pdf", lambda *args: pytest.fail("Downloads/cache must never compile"))
    assert client.post(url + "/renders", json=approval_payload(view)).json()["id"] == render["id"]
    newer = client.post(url + "/revisions", json=save_payload(view)).json()
    assert not newer["approved_current"]
    assert client.post(path + "/approve", json=approval).status_code == 409
    assert client.post(f"/api/profile/tailoring-sources/{source['id']}/revoke", json={"expected_hash": source["bundle_hash"], "expected_active_id": source["id"]}).status_code == 200
    assert client.get(url).json()["source_problem"]
    for format, data in files.items():
        assert client.get(path + "/download/" + format).content == data
    assert client.get(f"/api/jobs/{job['id']}").json() == job
    assert client.delete(path).status_code == 409


def test_backup_exact_artifact_restore_and_legacy_content_approval(client, completed, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    *_, url = completed
    view, render = rendered(client, url)
    final(client, url, view, render)
    archive = client.get("/api/data/backup").json()
    assert archive["version"] == 7
    path = url + f"/renders/{render['id']}/download/pdf"
    original = client.get(path).content
    monkeypatch.setattr(resume_compiler, "compiler", lambda: pytest.fail("Restore/download must work without a compiler"))
    def restore(data):
        content = json.dumps(data).encode()
        return client.post("/api/data/restore", files={"file": ("backup.json", content)}, data={"sha256": hashlib.sha256(content).hexdigest(), "confirmation": "RESTORE"})
    assert restore(archive).status_code == 200
    assert client.get(path).content == original
    for change in (lambda t: t["resume_renders"][0]["bundle"]["files"].pop("pdf"),
                   lambda t: t["resume_renders"][0]["bundle"]["files"].update(txt=base64.b64encode(b"Invented").decode()),
                   lambda t: t["resume_export_approvals"][0].update(manifest_hash="0"*64),
                   lambda t: t["resume_preview_receipts"][0].update(render_id="missing")):
        bad = copy.deepcopy(archive); change(bad["tables"])
        assert restore(bad).status_code == 400
        assert client.get(path).content == original
    legacy = copy.deepcopy(archive); legacy["version"] = 5
    for table in ("resume_renders", "resume_preview_receipts", "resume_export_approvals"): del legacy["tables"][table]
    assert restore(legacy).status_code == 200
    assert client.get(url).json()["approved_current"]
    assert client.get(url + "/renders", params={"revision_id": view["revision"]["id"]}).json() == []
    assert client.get(path).status_code == 404  # A content review never becomes a PDF approval.


def test_draft_cleanup_scoped_and_approval_requires_review_preview_and_fit(client, completed):
    *_, url = completed
    view, render = rendered(client, url)
    path = url + f"/renders/{render['id']}"
    preview = client.post(path + "/preview").json()
    payload = {"preview_receipt_id": preview["preview_receipt_id"], "manifest_hash": preview["manifest_hash"], "layout_reviewed": True}
    assert client.post(path + "/approve", json=payload).status_code == 409
    assert client.post(path + "/approve", json={**payload, "layout_reviewed": False}).status_code == 422
    assert client.delete(path.replace(view["baseline_id"], "missing")).status_code == 404
    assert client.delete(path).status_code == 204
    assert client.get(url).json()["revision"]["id"] == view["revision"]["id"]
    assert client.get("/api/profile/tailoring-sources").json()["active_id"]
    with next(app.dependency_overrides[get_db]()) as db:
        assert not db.query(models.ResumePreviewReceipt).count()
        assert not db.query(models.ResumeRender).count()


def test_concurrent_save_during_compile_keeps_old_preview_but_blocks_final(client, completed, monkeypatch):
    *_, url = completed
    view = client.get(url).json()
    original = resume_compiler.compile_pdf
    def compile_and_save(*args):
        assert client.post(url + "/revisions", json=save_payload(view)).status_code == 201
        return original(*args)
    monkeypatch.setattr(resume_compiler, "compile_pdf", compile_and_save)
    _, render = rendered(client, url)
    assert render["revision_id"] == view["revision"]["id"]
    path = url + f"/renders/{render['id']}"
    preview = client.post(path + "/preview").json()
    assert client.post(path + "/approve", json={"preview_receipt_id": preview["preview_receipt_id"], "manifest_hash": render["manifest_hash"], "layout_reviewed": True}).status_code == 409


def test_missing_compiler_and_invalid_content_do_not_publish_artifacts(client, completed, monkeypatch):
    *_, url = completed
    view = client.get(url).json()
    monkeypatch.setattr(get_settings(), "resume_pdflatex", "missing-pdflatex-executable")
    response = client.post(url + "/renders", json=approval_payload(view))
    assert response.status_code == 422 and "compiler" in response.text
    assert client.get(url + "/renders", params={"revision_id": view["revision"]["id"]}).json() == []
    bad = save_payload(view); bad["edit"]["bullets"][0]["text"] = "Invented production scale of 500 million users."
    invalid = client.post(url + "/revisions", json=bad).json()
    assert client.post(url + "/renders", json=approval_payload(invalid)).status_code == 409


def test_multi_page_preview_is_saved_but_cannot_be_final_approved(client, completed, monkeypatch):
    import pymupdf
    *_, url = completed
    original = resume_compiler.compile_pdf
    def two_pages(*args):
        pdf, warnings = original(*args)
        with pymupdf.open(stream=pdf, filetype="pdf") as document:
            document.new_page(width=612, height=792)
            return document.tobytes(), warnings
    monkeypatch.setattr(resume_compiler, "compile_pdf", two_pages)
    view, render = rendered(client, url)
    assert render["validation"]["pages"] == 2 and not render["validation"]["valid"]
    assert client.post(url + "/review", json=approval_payload(view)).status_code == 201
    path = url + f"/renders/{render['id']}"
    preview = client.post(path + "/preview").json()
    assert len(preview["page_images"]) == 2
    response = client.post(path + "/approve", json={"preview_receipt_id": preview["preview_receipt_id"], "manifest_hash": render["manifest_hash"], "layout_reviewed": True})
    assert response.status_code == 409 and "page-fit" in response.text
    assert client.get(path + "/download/pdf").status_code == 409


def test_artifact_migration_and_immutable_rows(client, completed, tmp_path, monkeypatch):
    from app.migrations import run_migrations
    from app.database import build_engine
    from app.services.backup_service import restore
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    *_, url = completed
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path / "assets"))
    view, render = rendered(client, url); final(client, url, view, render)
    archive = client.get("/api/data/backup").content
    db_url = "sqlite:///" + (tmp_path / "migration.db").as_posix()
    run_migrations(db_url); run_migrations(db_url)
    engine = build_engine(db_url)
    with Session(engine) as db:
        restore(db, archive, hashlib.sha256(archive).hexdigest())
        for table in ("resume_renders", "resume_preview_receipts", "resume_export_approvals"):
            with pytest.raises(IntegrityError):
                db.execute(text(f"UPDATE {table} SET manifest_hash = 'changed'")); db.commit()
            db.rollback()
    engine.dispose()

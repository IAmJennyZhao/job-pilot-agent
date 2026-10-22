"""Explicit fixture maintenance, never invoked by tests.

Run from repo root: py -3 backend/tests/fixtures/freeze_compatibility.py
Executes tracked historical code in isolated directories with synthetic fixtures.
No live models, user database, source assets, or .env files are used.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

REVISIONS = [(1, "b1fcce6"), (2, "db65a31"), (3, "59b6b28"), (4, "552db84"),
             (5, "530138b"), (6, "b31d212"), (7, "7b20522")]


def worker(version, output):
    # These imports resolve against the historical checkout, not the current app.
    sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / "tests")]
    import pytest
    from conftest import client as client_fixture
    from app.config import get_settings
    from app.services import ai_service
    generator = client_fixture.__wrapped__()
    client = next(generator)
    metadata = {"version": version, "downloads": {}}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(get_settings(), "asset_storage_dir", str(Path.cwd() / "storage"))
        patch.setattr(get_settings(), "openai_api_key", "synthetic-frozen-key")
        patch.setattr(get_settings(), "openai_model", "synthetic-frozen-model")
        patch.setattr(ai_service, "get_structured_output", lambda *a, **k: pytest.fail("No live model allowed"))
        if version >= 4:
            from test_resume_generation import prepared, generate
            job, _ = prepared.__wrapped__(client, patch)
            run = generate(client, job).json()
            assert run["state"] == "completed", run
            metadata["baseline"] = run["revision"]["id"]
            url = f"/api/tailoring/resumes/{metadata['baseline']}"
            if version >= 5:
                from test_resume_review import approval_payload
                view = client.get(url).json()
                assert client.post(url + "/review", json=approval_payload(view)).status_code == 201
            if version >= 6:
                from test_resume_exports import rendered, final
                view, render = rendered(client, url)
                final(client, url, view, render)
                for fmt in ("pdf", "tex", "txt"):
                    route = url + f"/renders/{render['id']}/download/{fmt}"
                    data = client.get(route)
                    assert data.status_code == 200, data.text
                    metadata["downloads"][route] = hashlib.sha256(data.content).hexdigest()
            if version >= 7:
                from letter_fixtures import fake_letter
                from test_resume_generation import request_for
                patch.setattr(ai_service, "get_tailoring_output", fake_letter)
                request = {**request_for(client, job["id"]), "options": {"count": 3, "length": "short"}}
                letter = client.post(f"/api/jobs/{job['id']}/cover-letters", json=request).json()
                assert letter["state"] == "completed", letter
                letter_url = f"/api/cover-letters/{letter['revision']['id']}"
                view = client.get(letter_url).json()
                assert client.post(letter_url + "/review", json=approval_payload(view)).status_code == 201
                for index in range(3):
                    for fmt in ("txt", "md"):
                        route = letter_url + f"/revisions/{view['revision']['id']}/download/{index}/{fmt}"
                        data = client.get(route)
                        assert data.status_code == 200, data.text
                        metadata["downloads"][route] = hashlib.sha256(data.content).hexdigest()
        else:
            from test_backup import setup_data
            job, _ = setup_data(client)
            if version >= 2:
                from tailoring_fixtures import import_payload
                source = client.post("/api/profile/tailoring-sources/import", json=import_payload()).json()
                assert client.post(f"/api/profile/tailoring-sources/{source['id']}/activate", json={"expected_hash": source["bundle_hash"], "expected_active_id": None}).status_code == 200
        metadata["job"] = job["id"]
        archive = client.get("/api/data/backup")
        assert archive.status_code == 200 and archive.json()["version"] == version
        metadata["sha256"] = hashlib.sha256(archive.content).hexdigest()
        Path(output).write_bytes(gzip.compress(archive.content, mtime=0))
        Path(output + ".meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    generator.close()


def freeze():
    root = Path(__file__).resolve().parents[2]
    destination = Path(__file__).parent / "compatibility"
    destination.mkdir(exist_ok=True)
    staging = root / "storage" / "compatibility-freeze"
    staging.mkdir(parents=True, exist_ok=True)
    manifest = []
    for version, revision in REVISIONS:
        sha = subprocess.check_output(["git", "rev-parse", revision], text=True).strip()
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            checkout = Path(temporary)
            archive = checkout / "source.tar"
            subprocess.run(["git", "archive", "--format=tar", f"--output={archive}", sha, "backend"], check=True)
            with tarfile.open(archive) as tar:
                tar.extractall(checkout, filter="data")
            target = destination / f"v{version}.json.gz"
            env = {**os.environ, "AUTO_MIGRATE": "0", "DATABASE_URL": "sqlite://", "OPENAI_API_KEY": "synthetic-frozen-key", "OPENAI_MODEL": "synthetic-frozen-model", "PYTHONPATH": "",
                   "RESUME_PDFLATEX": str(root / "storage/texlive/bin/windows/pdflatex.exe")}
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(version), str(target)], cwd=checkout / "backend", env=env, check=True)
            metadata = json.loads(Path(str(target) + ".meta.json").read_text())
            Path(str(target) + ".meta.json").unlink()
            manifest.append({**metadata, "source_commit": sha, "file": target.name})
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(int(sys.argv[2]), sys.argv[3])
    else:
        freeze()

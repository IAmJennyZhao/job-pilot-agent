"""Portable data archives. Imported paths are never used as filesystem paths."""
import base64
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import get_args, get_type_hints
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy import Enum, JSON, String, insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, build_engine

MAX_BYTES = 50 * 1024 * 1024
FORMAT = "job-pilot-backup"
VERSION = 6
RENDER_TABLES = {"resume_renders", "resume_preview_receipts", "resume_export_approvals"}
REVIEW_TABLES = {"resume_edit_revisions", "resume_review_approvals"}
GENERATION_TABLES = {"tailoring_runs", "tailoring_stage_attempts", "tailored_revisions"}
INTAKE_TABLES = {"job_intake_reviews"}
TAILORING_TABLES = {"tailoring_source_versions", "tailoring_source_events", "tailoring_profile_states"}
V1_TABLES = {"application_attributions", "asset_recommendation_snapshots", "cover_letter_templates",
            "interview_messages", "interview_questions", "interview_sessions", "job_actions", "job_analyses",
            "job_links", "job_status_events", "jobs", "resume_options", "resume_profiles", "resume_suggestions",
            "saved_study_plans", "skill_gaps", "advanced_job_analyses", "company_research_snapshots"}


def validate_tailoring_tables(tables):
    """Restore cannot turn edited JSON or a stale activation pointer into trusted facts."""
    from app.services.tailoring_source_service import validate_stored
    versions = {row["id"]: row for row in tables["tailoring_source_versions"]}
    histories = {key: [] for key in versions}
    for row in versions.values():
        validate_stored(SimpleNamespace(**row))
    for event in tables["tailoring_source_events"]:
        source = versions.get(event["source_id"])
        if not source or event["content_hash"] != source["bundle_hash"]:
            raise ValueError("Invalid source activation reference")
        histories[source["id"]].append(event)
    statuses = {}
    for source_id, history in histories.items():
        state = "pending"
        for index, event in enumerate(sorted(history, key=lambda e: e["sequence"]), start=1):
            action = event["action"]
            allowed = {"pending": {"active", "revoked"}, "active": {"superseded", "revoked"},
                       "superseded": {"active", "revoked"}, "revoked": set()}
            if event["sequence"] != index or action not in allowed[state]:
                raise ValueError("Invalid source activation history")
            state = action
        statuses[source_id] = state
    seen_profiles = set()
    for state in tables["tailoring_profile_states"]:
        profile_id = state["profile_id"]
        if profile_id in seen_profiles or state["revision"] < 0:
            raise ValueError("Invalid source profile state")
        seen_profiles.add(profile_id)
        active = [key for key, row in versions.items() if row["profile_id"] == profile_id and statuses[key] == "active"]
        if active != ([state["active_source_id"]] if state["active_source_id"] else []):
            raise ValueError("Source activation pointer/history mismatch")
        if active and versions[active[0]]["bank"]["approval"]["status"] not in {"approved", "approved_with_exclusions"}:
            raise ValueError("Active bank lacks recorded approval")
    if any(row["profile_id"] not in seen_profiles for row in versions.values()):
        raise ValueError("Source has no profile state")


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"Cannot export {type(value).__name__}")


def validate_intake_tables(tables):
    from app.intake_schemas import IntakeReview
    from app.tailoring_preferences import Preferences
    from app.services.intake_preferences import digest, flags_for
    sources = {row["id"]: row for row in tables["tailoring_source_versions"]}
    for row in tables["job_intake_reviews"]:
        review = IntakeReview.model_validate(row["review"])
        evaluation = row["evaluation"]
        if row["decision"] not in {"save_later", "continue"} or evaluation["input_hash"] != digest(review.model_dump(mode="json")):
            raise ValueError("Invalid intake review snapshot")
        signed = {key: value for key, value in evaluation.items() if key not in {"evaluation_hash", "duplicate_candidates"}}
        if evaluation["evaluation_hash"] != digest(signed):
            raise ValueError("Invalid intake evaluation hash")
        source = sources.get(row["source_id"])
        if row["source_id"] != evaluation["source_id"] or bool(source) != evaluation["available"]:
            raise ValueError("Invalid intake preference source")
        if source:
            if row["preference_snapshot"] != source["preferences"] or evaluation["preference_hash"] != digest(source["preferences"]):
                raise ValueError("Invalid intake preference snapshot")
            expected = flags_for(review, Preferences.model_validate(row["preference_snapshot"]))
            if expected != evaluation["flags"]:
                raise ValueError("Invalid intake flags")
        elif row["preference_snapshot"] is not None or evaluation["flags"]:
            raise ValueError("Intake flags have no preference source")


def export_archive(db: Session) -> bytes:
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    tables = {table.name: [dict(row) for row in db.execute(select(table)).mappings()] for table in Base.metadata.sorted_tables}
    files, missing = {}, []
    root = Path(get_settings().asset_storage_dir).resolve()
    for row in tables["resume_options"]:
        original = row.get("file_path")
        row["file_path"] = None
        if not original:
            if row.get("source_filename"):
                missing.append(row["source_filename"])
            continue
        path = Path(original).resolve()
        if path.is_relative_to(root) and path.is_file():
            if path.stat().st_size > MAX_BYTES:
                raise HTTPException(413, "A resume file is too large for this backup")
            files[row["id"]] = base64.b64encode(path.read_bytes()).decode("ascii")
        else:
            missing.append(row.get("source_filename") or row["title"])
    result = json.dumps({"format": FORMAT, "version": VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables, "files": files, "missing_files": missing}, default=json_value, ensure_ascii=False).encode("utf-8")
    if len(result) > MAX_BYTES:
        raise HTTPException(413, "Backup exceeds the 50 MB archive limit")
    return result


def validate_archive(content: bytes):
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Backup exceeds the 50 MB archive limit")
    try:
        archive = json.loads(content)
        if archive.get("format") != FORMAT or archive.get("version") not in {1, 2, 3, 4, 5, VERSION}:
            raise ValueError("Unsupported backup format or version")
        if archive["version"] == 1:
            if set(archive["tables"]) != V1_TABLES:
                raise ValueError("Invalid legacy backup tables")
            archive["tables"].update({name: [] for name in TAILORING_TABLES})
        if archive["version"] in {1, 2}:
            if set(archive["tables"]) != V1_TABLES | TAILORING_TABLES:
                raise ValueError("Invalid legacy backup tables")
            archive["tables"].update({name: [] for name in INTAKE_TABLES})
        if archive["version"] in {1, 2, 3}:
            if set(archive["tables"]) != V1_TABLES | TAILORING_TABLES | INTAKE_TABLES:
                raise ValueError("Invalid legacy backup tables")
            archive["tables"].update({name: [] for name in GENERATION_TABLES})
        if archive["version"] in {1, 2, 3, 4}:
            if set(archive["tables"]) != V1_TABLES | TAILORING_TABLES | INTAKE_TABLES | GENERATION_TABLES:
                raise ValueError("Invalid legacy backup tables")
            archive["tables"].update({name: [] for name in REVIEW_TABLES})
        if archive["version"] in {1, 2, 3, 4, 5}:
            if set(archive["tables"]) != V1_TABLES | TAILORING_TABLES | INTAKE_TABLES | GENERATION_TABLES | REVIEW_TABLES:
                raise ValueError("Invalid legacy backup tables")
            archive["tables"].update({name: [] for name in RENDER_TABLES})
        if set(archive["tables"]) != set(Base.metadata.tables):
            raise ValueError("Backup tables do not match this app version")
        tables = {}
        for table in Base.metadata.sorted_tables:
            rows = archive["tables"][table.name]
            if not isinstance(rows, list):
                raise ValueError("Invalid table rows")
            tables[table.name] = []
            for row in rows:
                if set(row) != set(table.columns.keys()):
                    raise ValueError(f"Invalid columns in {table.name}")
                cleaned = {}
                for column in table.columns:
                    value = row[column.name]
                    if table.name == "resume_options" and column.name == "file_path":
                        if value is not None:
                            raise ValueError("Backup must not contain local file paths")
                    if value is None:
                        if not column.nullable:
                            raise ValueError(f"Missing {table.name}.{column.name}")
                    elif isinstance(column.type, Enum):
                        value = column.type.enum_class(value)
                    elif isinstance(column.type, JSON):
                        model = next(mapper.class_ for mapper in Base.registry.mappers if mapper.local_table is table)
                        annotation = get_args(get_type_hints(model)[column.name])[0]
                        value = TypeAdapter(annotation).validate_python(value)
                    else:
                        value = TypeAdapter(column.type.python_type).validate_python(value)
                        if isinstance(column.type, String) and column.type.length and len(value) > column.type.length:
                            raise ValueError("Text field exceeds maximum length")
                    cleaned[column.name] = value
                tables[table.name].append(cleaned)
        files = archive.get("files", {})
        if not isinstance(files, dict):
            raise ValueError("Invalid file manifest")
        resume_ids = {row["id"] for row in tables["resume_options"]}
        decoded = {}
        for key, value in files.items():
            if key not in resume_ids:
                raise ValueError("File has no matching resume")
            decoded[key] = base64.b64decode(value, validate=True)
            if not decoded[key].startswith(b"%PDF-"):
                raise ValueError("Resume attachment is not a PDF")
        missing = archive.get("missing_files", [])
        if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
            raise ValueError("Invalid missing-file manifest")
        validate_tailoring_tables(tables)
        validate_intake_tables(tables)
        from app.services.generation_backup import validate_generation_tables
        validate_generation_tables(tables)
        from app.services.resume_review_backup import validate_review_tables
        validate_review_tables(tables)
        from app.services.resume_render_backup import validate_render_tables
        validate_render_tables(tables)
        # Validate IDs, foreign keys and SQL types before touching live records.
        engine = build_engine("sqlite://")
        try:
            Base.metadata.create_all(engine)
            with engine.begin() as connection:
                for table in Base.metadata.sorted_tables:
                    if tables[table.name]:
                        connection.execute(insert(table), tables[table.name])
        finally:
            engine.dispose()
        return tables, decoded, missing
    except (HTTPException,):
        raise
    except Exception as exc:
        raise HTTPException(400, "Invalid backup: unsupported data, broken references, or malformed attachments") from exc


def preview(content: bytes):
    tables, files, missing = validate_archive(content)
    return {"sha256": hashlib.sha256(content).hexdigest(), "counts": {name: len(rows) for name, rows in tables.items()},
            "files": len(files), "missing_files": missing}


def restore(db: Session, content: bytes, expected_hash: str):
    if hashlib.sha256(content).hexdigest() != expected_hash:
        raise HTTPException(409, "Backup changed since preview; preview it again")
    tables, files, missing = validate_archive(content)
    root = Path(get_settings().asset_storage_dir).resolve()
    recovery_dir = root / "backups"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    recovery_id = uuid.uuid4().hex
    recovery = recovery_dir / f"{recovery_id}.json"
    recovery.write_bytes(export_archive(db))
    for run in tables["tailoring_runs"]:
        if run["state"] in {"pending", "running"}:
            run.update(state="interrupted", active_key=None, finished_at=datetime.now(timezone.utc), error="Restored in-flight run; resume only with an explicit retry.")
    for attempt in tables["tailoring_stage_attempts"]:
        if attempt["state"] == "running":
            attempt.update(state="interrupted", finished_at=datetime.now(timezone.utc), error="Restored in-flight stage; provider completion may be unknown.")
    restored_dir = root / "restores" / uuid.uuid4().hex
    staged = []
    try:
        if files:
            restored_dir.mkdir(parents=True)
        for row in tables["resume_options"]:
            if row["id"] in files:
                path = restored_dir / f"{uuid.uuid4().hex}.pdf"
                path.write_bytes(files[row["id"]])
                staged.append(path)
                row["file_path"] = str(path)
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in {"tailoring_runs", "resume_edit_revisions"}:
                parent_column = table.c.parent_run_id if table.name == "tailoring_runs" else table.c.parent_id
                remaining = {row[0]: row[1] for row in db.execute(select(table.c.id, parent_column))}
                while remaining:
                    leaves = set(remaining) - set(remaining.values())
                    if not leaves:
                        raise ValueError("Cannot restore over cyclic retry history")
                    db.execute(table.delete().where(table.c.id.in_(leaves)))
                    remaining = {key: parent for key, parent in remaining.items() if key not in leaves}
            else:
                db.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            if tables[table.name]:
                db.execute(insert(table), tables[table.name])
        db.commit()
    except Exception:
        db.rollback()
        for path in staged:
            path.unlink(missing_ok=True)
        raise
    return {"restored": True, "recovery_id": recovery_id, "missing_files": missing}

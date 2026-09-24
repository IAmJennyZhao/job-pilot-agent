"""Portable data archives. Imported paths are never used as filesystem paths."""
import base64
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import get_args, get_type_hints

from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy import Enum, JSON, String, insert, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, build_engine

MAX_BYTES = 50 * 1024 * 1024
FORMAT = "job-pilot-backup"
VERSION = 1


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"Cannot export {type(value).__name__}")


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
        if archive.get("format") != FORMAT or archive.get("version") != VERSION:
            raise ValueError("Unsupported backup format or version")
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

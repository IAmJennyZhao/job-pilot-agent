from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.migrations import alembic_config, run_migrations
from alembic import command


def _sqlite_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def _head_revision() -> str:
    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    return script.get_current_head()


def _current_revision(url: str) -> str:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()


def test_fresh_database_is_created_at_head(tmp_path):
    url = _sqlite_url(tmp_path, "fresh.db")
    run_migrations(url)

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert set(Base.metadata.tables) <= tables
    assert _current_revision(url) == _head_revision()


def test_baseline_upgrade_preserves_jobs_and_adds_actions(tmp_path):
    url = _sqlite_url(tmp_path, "baseline.db")
    command.upgrade(alembic_config(url), "0001")
    engine = create_engine(url)
    with Session(engine) as session:
        session.add(models.Job(id="kept", company="Kept company", role_title="Engineer"))
        session.commit()
    engine.dispose()
    run_migrations(url)
    engine = create_engine(url)
    with Session(engine) as session:
        assert session.get(models.Job, "kept").company == "Kept company"
        assert session.scalars(select(models.JobAction)).all() == []
    engine.dispose()


def test_migrated_schema_matches_models(tmp_path):
    url = _sqlite_url(tmp_path, "schema.db")
    run_migrations(url)

    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        migrated_tables = set(inspector.get_table_names()) - {"alembic_version"}
        assert migrated_tables == set(Base.metadata.tables)
        for table_name, table in Base.metadata.tables.items():
            migrated = {column["name"]: column for column in inspector.get_columns(table_name)}
            assert set(migrated) == {column.name for column in table.columns}, table_name
            for column in table.columns:
                assert migrated[column.name]["nullable"] == column.nullable, f"{table_name}.{column.name}"
    finally:
        engine.dispose()


def test_pre_alembic_database_is_stamped_and_keeps_data(tmp_path):
    url = _sqlite_url(tmp_path, "legacy.db")
    engine = create_engine(url)
    try:
        Base.metadata.create_all(bind=engine)
        with Session(engine) as session:
            session.add(models.Job(company="Acme AI", role_title="Applied AI Engineer"))
            session.commit()
    finally:
        engine.dispose()

    run_migrations(url)

    assert _current_revision(url) == _head_revision()
    engine = create_engine(url)
    try:
        assert "alembic_version" in inspect(engine).get_table_names()
        with Session(engine) as session:
            job = session.scalars(select(models.Job)).one()
            assert job.company == "Acme AI"
    finally:
        engine.dispose()

    # Re-running against an up-to-date database must be a no-op.
    run_migrations(url)
    assert _current_revision(url) == _head_revision()


def test_pre_alembic_database_with_empty_version_table_is_stamped(tmp_path):
    # The real dev DB had an empty alembic_version table from an aborted run.
    url = _sqlite_url(tmp_path, "empty_version.db")
    engine = create_engine(url)
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        with Session(engine) as session:
            session.add(models.Job(company="Acme AI", role_title="Applied AI Engineer"))
            session.commit()
    finally:
        engine.dispose()

    run_migrations(url)

    assert _current_revision(url) == _head_revision()
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            assert session.scalars(select(models.Job)).one().company == "Acme AI"
    finally:
        engine.dispose()


def test_stale_revision_from_collapsed_lineage_is_restamped(tmp_path):
    url = _sqlite_url(tmp_path, "stale_revision.db")
    engine = create_engine(url)
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(text("INSERT INTO alembic_version VALUES ('0004_interview_practice')"))
    finally:
        engine.dispose()

    run_migrations(url)

    assert _current_revision(url) == _head_revision()

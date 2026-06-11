import json
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def build_engine(database_url: str) -> Engine:
    engine = create_engine(
        database_url,
        connect_args=_connect_args(database_url),
        future=True,
    )

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


settings = get_settings()
engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_added_columns()


def _ensure_added_columns() -> None:
    patches = [
        (
            "company_research_snapshots",
            "highlight_phrases",
            "ALTER TABLE company_research_snapshots ADD COLUMN highlight_phrases JSON NOT NULL DEFAULT '[]'",
        ),
        (
            "advanced_job_analyses",
            "highlight_phrases",
            "ALTER TABLE advanced_job_analyses ADD COLUMN highlight_phrases JSON NOT NULL DEFAULT '{}'",
        ),
        (
            "resume_profiles",
            "skill_groups",
            "ALTER TABLE resume_profiles ADD COLUMN skill_groups JSON NOT NULL DEFAULT '[]'",
        ),
        (
            "jobs",
            "selected_resume_option_id",
            "ALTER TABLE jobs ADD COLUMN selected_resume_option_id VARCHAR(36)",
        ),
        (
            "jobs",
            "selected_cover_letter_template_id",
            "ALTER TABLE jobs ADD COLUMN selected_cover_letter_template_id VARCHAR(36)",
        ),
        (
            "interview_sessions",
            "target_category",
            "ALTER TABLE interview_sessions ADD COLUMN target_category VARCHAR(64)",
        ),
        (
            "interview_sessions",
            "target_role",
            "ALTER TABLE interview_sessions ADD COLUMN target_role VARCHAR(255)",
        ),
        (
            "interview_sessions",
            "stage",
            "ALTER TABLE interview_sessions ADD COLUMN stage VARCHAR(64) NOT NULL DEFAULT 'mixed'",
        ),
        (
            "interview_sessions",
            "question_type",
            "ALTER TABLE interview_sessions ADD COLUMN question_type VARCHAR(100) NOT NULL DEFAULT 'mixed'",
        ),
        (
            "interview_messages",
            "question_id",
            "ALTER TABLE interview_messages ADD COLUMN question_id VARCHAR(36)",
        ),
    ]
    with engine.begin() as connection:
        for table_name, column_name, ddl in patches:
            inspector = inspect(connection)
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if column_name not in columns:
                connection.execute(text(ddl))
        _ensure_interview_sessions_job_nullable(connection)
        _ensure_skill_gaps_merged(connection)


SKILL_GAP_SOURCE_PRECEDENCE = {"resume_match": 0, "interview_feedback": 1, "job_analysis": 2}
_USER_LEVEL_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}


def _skill_gap_priority_for_count(count: int) -> str:
    if count >= 3:
        return "high"
    if count == 2:
        return "medium"
    return "low"


def _ensure_skill_gaps_merged(connection) -> None:
    inspector = inspect(connection)
    if "skill_gaps" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("skill_gaps")}
    if "source" not in columns:
        return
    if connection.dialect.name != "sqlite":
        return

    rows = connection.execute(
        text(
            """
            SELECT id, resume_profile_id, skill_name, source, count, priority,
                   user_level, suggested_action, created_at, updated_at
            FROM skill_gaps
            ORDER BY created_at, id
            """
        )
    ).mappings().all()

    merged: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["resume_profile_id"], row["skill_name"].strip().casefold())
        entry = merged.get(key)
        if entry is None:
            merged[key] = {
                "id": row["id"],
                "resume_profile_id": row["resume_profile_id"],
                "skill_name": row["skill_name"],
                "sources": {row["source"]},
                "count": row["count"],
                "user_level": row["user_level"],
                "suggested_action": row["suggested_action"],
                "action_source": row["source"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            continue
        entry["count"] += row["count"]
        entry["sources"].add(row["source"])
        if _USER_LEVEL_RANK.get(row["user_level"], 0) > _USER_LEVEL_RANK.get(entry["user_level"], 0):
            entry["user_level"] = row["user_level"]
        if SKILL_GAP_SOURCE_PRECEDENCE.get(row["source"], 99) < SKILL_GAP_SOURCE_PRECEDENCE.get(entry["action_source"], 99):
            entry["suggested_action"] = row["suggested_action"]
            entry["action_source"] = row["source"]
        entry["created_at"] = min(entry["created_at"], row["created_at"])
        entry["updated_at"] = max(entry["updated_at"], row["updated_at"])

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("PRAGMA legacy_alter_table=ON"))
    connection.execute(text("ALTER TABLE skill_gaps RENAME TO skill_gaps_old"))
    connection.execute(
        text(
            """
            CREATE TABLE skill_gaps (
                id VARCHAR(36) NOT NULL,
                resume_profile_id VARCHAR(36) NOT NULL,
                skill_name VARCHAR(255) NOT NULL,
                sources JSON NOT NULL DEFAULT '[]',
                count INTEGER NOT NULL,
                priority VARCHAR(32) NOT NULL,
                user_level VARCHAR(32) NOT NULL,
                suggested_action TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(resume_profile_id) REFERENCES resume_profiles (id) ON DELETE CASCADE
            )
            """
        )
    )
    for entry in merged.values():
        connection.execute(
            text(
                """
                INSERT INTO skill_gaps (
                    id, resume_profile_id, skill_name, sources, count,
                    priority, user_level, suggested_action, created_at, updated_at
                )
                VALUES (
                    :id, :resume_profile_id, :skill_name, :sources, :count,
                    :priority, :user_level, :suggested_action, :created_at, :updated_at
                )
                """
            ),
            {
                "id": entry["id"],
                "resume_profile_id": entry["resume_profile_id"],
                "skill_name": entry["skill_name"],
                "sources": json.dumps(
                    sorted(entry["sources"], key=lambda source: SKILL_GAP_SOURCE_PRECEDENCE.get(source, 99))
                ),
                "count": entry["count"],
                "priority": _skill_gap_priority_for_count(entry["count"]),
                "user_level": entry["user_level"],
                "suggested_action": entry["suggested_action"],
                "created_at": entry["created_at"],
                "updated_at": entry["updated_at"],
            },
        )
    connection.execute(text("DROP TABLE skill_gaps_old"))
    connection.execute(text("CREATE INDEX ix_skill_gaps_resume_profile_id ON skill_gaps (resume_profile_id)"))
    connection.execute(text("CREATE INDEX ix_skill_gaps_skill_name ON skill_gaps (skill_name)"))
    connection.execute(text("PRAGMA legacy_alter_table=OFF"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_interview_sessions_job_nullable(connection) -> None:
    inspector = inspect(connection)
    if "interview_sessions" not in inspector.get_table_names():
        return
    columns = inspector.get_columns("interview_sessions")
    job_column = next((column for column in columns if column["name"] == "job_id"), None)
    if not job_column or job_column.get("nullable"):
        return
    if connection.dialect.name != "sqlite":
        return

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("PRAGMA legacy_alter_table=ON"))
    connection.execute(text("ALTER TABLE interview_sessions RENAME TO interview_sessions_old"))
    connection.execute(
        text(
            """
            CREATE TABLE interview_sessions (
                id VARCHAR(36) NOT NULL,
                job_id VARCHAR(36),
                resume_profile_id VARCHAR(36),
                mode VARCHAR(32) NOT NULL,
                title VARCHAR(255),
                target_category VARCHAR(64),
                target_role VARCHAR(255),
                stage VARCHAR(64) NOT NULL DEFAULT 'mixed',
                question_type VARCHAR(100) NOT NULL DEFAULT 'mixed',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE SET NULL,
                FOREIGN KEY(resume_profile_id) REFERENCES resume_profiles (id) ON DELETE SET NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO interview_sessions (
                id,
                job_id,
                resume_profile_id,
                mode,
                title,
                target_category,
                target_role,
                stage,
                question_type,
                created_at,
                updated_at
            )
            SELECT
                id,
                job_id,
                resume_profile_id,
                mode,
                title,
                target_category,
                target_role,
                COALESCE(stage, 'mixed'),
                COALESCE(question_type, 'mixed'),
                created_at,
                updated_at
            FROM interview_sessions_old
            """
        )
    )
    connection.execute(text("DROP TABLE interview_sessions_old"))
    connection.execute(text("CREATE INDEX ix_interview_sessions_job_id ON interview_sessions (job_id)"))
    connection.execute(text("CREATE INDEX ix_interview_sessions_resume_profile_id ON interview_sessions (resume_profile_id)"))
    connection.execute(text("CREATE INDEX ix_interview_sessions_target_category ON interview_sessions (target_category)"))
    connection.execute(text("CREATE INDEX ix_interview_sessions_stage ON interview_sessions (stage)"))
    connection.execute(text("CREATE INDEX ix_interview_sessions_question_type ON interview_sessions (question_type)"))
    connection.execute(text("PRAGMA legacy_alter_table=OFF"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


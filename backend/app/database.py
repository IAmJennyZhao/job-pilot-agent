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


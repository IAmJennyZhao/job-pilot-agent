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
    ]
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, column_name, ddl in patches:
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if column_name not in columns:
                connection.execute(text(ddl))


import logging

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.config import BACKEND_DIR, get_settings
from app.database import build_engine

logger = logging.getLogger(__name__)

# Any table from the pre-Alembic era; its presence without a current revision
# means the database was created by the old create_all + patch system.
_PRE_ALEMBIC_MARKER_TABLE = "jobs"


def alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url or get_settings().database_url)
    config.attributes["configure_logger"] = False
    return config


def run_migrations(database_url: str | None = None) -> None:
    url = database_url or get_settings().database_url
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
            has_legacy_tables = _PRE_ALEMBIC_MARKER_TABLE in inspect(connection).get_table_names()
    finally:
        engine.dispose()

    config = alembic_config(url)
    script = ScriptDirectory.from_config(config)
    known_revisions = {revision.revision for revision in script.walk_revisions()}

    if current is None and has_legacy_tables:
        # Schema was fully managed by the old startup patcher; adopt it as-is.
        logger.info("Pre-Alembic database detected; stamping baseline revision before upgrading.")
        command.stamp(config, "head")
    elif current is not None and current not in known_revisions:
        # Revision from the old migration lineage that was collapsed into the
        # baseline; the legacy startup patcher kept those databases current.
        logger.warning("Unknown revision %r in alembic_version; re-stamping to head.", current)
        command.stamp(config, "head", purge=True)
    command.upgrade(config, "head")
    logger.info("Database is at the latest schema revision.")

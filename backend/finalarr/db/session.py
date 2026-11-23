"""Engine, sessions and migrations for the SQLite database."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from finalarr.backup import backup

log = logging.getLogger(__name__)

MIGRATIONS = Path(__file__).parent / "migrations"
BUSY_TIMEOUT_MS = 5000
# Automatic copies taken before an upgrade migrates the database; manual ones stay.
PRE_MIGRATION_PREFIX = "finalarr-before-"
PRE_MIGRATION_KEEP = 5
STAMP_LENGTH = len("20260101-000000")


def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA synchronous=FULL")
    cursor.close()


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine: Engine = create_engine(f"sqlite:///{path}")
        event.listen(self.engine, "connect", _sqlite_pragmas)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    def _alembic(self) -> Config:
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS))
        config.attributes["engine"] = self.engine
        return config

    def migrate(self) -> None:
        """Bring the schema to the newest revision; copy the database first if it has
        data from an older one."""
        config = self._alembic()
        head = ScriptDirectory.from_config(config).get_current_head()
        with self.engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        if current is not None and current != head:
            self._backup_before(str(head))
        command.upgrade(config, "head")

    def _backup_before(self, head: str) -> None:
        folder = self.path.parent / "backups"
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        target = backup(self.path, folder / f"{PRE_MIGRATION_PREFIX}{head}-{stamp}.db")
        log.info("Database copied to %s before migrating to %s", target, head)
        old = sorted(
            folder.glob(f"{PRE_MIGRATION_PREFIX}*.db"), key=lambda p: p.stem[-STAMP_LENGTH:]
        )
        for path in old[:-PRE_MIGRATION_KEEP]:
            path.unlink()

    def downgrade(self, revision: str) -> None:
        command.downgrade(self._alembic(), revision)

    def ping(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
        except Exception:
            return False
        return True

    def dispose(self) -> None:
        self.engine.dispose()

"""Engine, sessions and migrations for the SQLite database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS = Path(__file__).parent / "migrations"
BUSY_TIMEOUT_MS = 5000


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
        command.upgrade(self._alembic(), "head")

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

"""Consistent database backup while Finalarr runs (SQLite's online backup, WAL-safe).

    docker exec finalarr python -m finalarr.backup            # /config/backups/finalarr-<time>.db
    docker exec finalarr python -m finalarr.backup /config/x.db

Copying finalarr.db with cp while the container runs can catch it mid-write.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

DB_NAME = "finalarr.db"


def backup(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target


def main(argv: list[str]) -> int:
    data = Path(os.environ.get("FINALARR_DATA", "/config"))
    source = data / DB_NAME
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = Path(argv[0]) if argv else data / "backups" / f"finalarr-{stamp}.db"
    if argv and not argv[0].endswith(".db"):
        target = target / f"finalarr-{stamp}.db"
    if not source.exists():
        print(f"Database not found: {source}", file=sys.stderr)
        return 1
    print(backup(source, target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

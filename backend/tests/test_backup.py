import sqlite3

import pytest

from finalarr.backup import backup, main
from finalarr.db import models as m
from finalarr.db.session import Database


@pytest.fixture
def data(tmp_path):
    db = Database(tmp_path / "finalarr.db")
    db.migrate()
    with db.session() as s:
        s.add(m.SonarrInstance(name="Home", url="http://s:1", api_key_enc="x", webhook_token="t"))
        s.commit()
    yield tmp_path, db
    db.dispose()


def test_backup_is_a_consistent_copy_while_the_database_is_open(data, tmp_path):
    folder, _db = data
    target = backup(folder / "finalarr.db", tmp_path / "out" / "copy.db")
    with sqlite3.connect(target) as copy:
        assert copy.execute("select name from sonarr_instances").fetchall() == [("Home",)]
        assert copy.execute("pragma integrity_check").fetchone() == ("ok",)


def test_cli_writes_a_dated_file_next_to_the_database(data, capsys, monkeypatch):
    folder, _db = data
    monkeypatch.setenv("FINALARR_DATA", str(folder))
    assert main([]) == 0
    written = capsys.readouterr().out.strip()
    assert written.startswith(str(folder / "backups" / "finalarr-"))
    assert written.endswith(".db")


def test_missing_database_is_an_error(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FINALARR_DATA", str(tmp_path / "empty"))
    assert main([str(tmp_path / "copy.db")]) == 1
    assert "not found" in capsys.readouterr().err

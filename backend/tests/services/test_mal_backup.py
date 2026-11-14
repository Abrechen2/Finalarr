import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.fribb import parse_fribb, parse_fribb_ids, store_fribb
from finalarr.services.mal_backup import MalSequelWatcher
from finalarr.services.season_sources import JsonCache
from finalarr.sources.jikan import JikanAnime, JikanError

NOW = datetime(2026, 11, 13, tzinfo=UTC)
FRIBB = Path(__file__).parents[1] / "fixtures" / "anilist" / "fribb_subset.json"


class FakeJikan:
    def __init__(self):
        self.sequels = {58789: [61234]}
        self.details = {
            61234: JikanAnime.model_validate(
                {
                    "mal_id": 61234,
                    "title": "Mushoku Tensei III Part 2",
                    "type": "TV",
                    "status": "Not yet aired",
                    "aired": {"from": "2027-01-01T00:00:00+00:00"},
                }
            )
        }
        self.calls = []
        self.error = None

    def sequel_ids(self, mal_id):
        self.calls.append(("rel", mal_id))
        if self.error:
            raise self.error
        return self.sequels.get(mal_id, [])

    def anime(self, mal_id):
        self.calls.append(("anime", mal_id))
        return self.details[mal_id]


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    raw = FRIBB.read_bytes()
    with database.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        s.add(
            m.Series(
                instance=instance,
                sonarr_id=2,
                tvdb_id=371310,
                title="Mushoku Tensei",
                followed=True,
            )
        )
        store_fribb(s, parse_fribb(raw), NOW, ids=parse_fribb_ids(raw))
        s.commit()
    yield database
    database.dispose()


def run(db, jikan):
    created = []
    MalSequelWatcher(
        db,
        jikan,
        JsonCache(db, clock=lambda: NOW),
        on_events=lambda s, e: created.extend(e),
        clock=lambda: NOW,
    ).run()
    return created


def test_fribb_ids_are_parsed():
    assert (217434, 61234) in parse_fribb_ids(FRIBB.read_bytes())


def test_mal_sequel_is_announced_under_the_anilist_key(db):
    from finalarr.core.fingerprint import fingerprint

    created = run(db, FakeJikan())
    assert len(created) == 1
    with db.session() as s:
        event = s.scalar(select(m.Event))
        payload = json.loads(event.payload_json)
    assert event.type == "sequel_announced"
    assert (payload["anilist_id"], payload["sequel_title"], payload["first_air"]) == (
        217434,
        "Mushoku Tensei III Part 2",
        "2027-01-01",
    )
    assert payload["sources"] == ["myanimelist"]
    assert event.fingerprint == fingerprint("sequel_announced", 1, 2, 0, "217434")
    assert run(db, FakeJikan()) == []


def test_unresolvable_or_finished_sequels_are_skipped(db):
    jikan = FakeJikan()
    jikan.sequels = {58789: [99999]}
    assert run(db, jikan) == []
    jikan = FakeJikan()
    jikan.details[61234] = jikan.details[61234].model_copy(update={"status": "Finished Airing"})
    assert run(db, jikan) == []


def test_jikan_down_is_quiet(db):
    jikan = FakeJikan()
    jikan.error = JikanError("down")
    assert run(db, jikan) == []


def test_results_are_cached(db):
    jikan = FakeJikan()
    run(db, jikan)
    calls = len(jikan.calls)
    run(db, jikan)
    assert len(jikan.calls) == calls


def test_switched_off_jikan_is_not_asked(db):
    from finalarr.services.source_catalog import set_source

    with db.session() as s:
        set_source(s, "jikan", False)
        s.commit()

    class Refusing:
        def __getattr__(self, name):
            raise AssertionError("Jikan must not be asked")

    assert run(db, Refusing()) == []

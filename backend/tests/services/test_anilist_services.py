import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.anilist_cache import CachedAnilist
from finalarr.services.enricher import AnimeEnricher
from finalarr.services.fribb import fribb_is_stale, parse_fribb, store_fribb
from finalarr.sources.anilist import AnilistMedia, AnilistRateLimited, _NextAiring

from ..fakes import FakeAnilist

NOW = datetime(2026, 6, 1, tzinfo=UTC)
FRIBB = Path(__file__).parents[1] / "fixtures" / "anilist" / "fribb_subset.json"
MUSHOKU_TVDB = 371310


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    yield database
    database.dispose()


def media(mid, status="FINISHED", episodes=12, start=(2026, 1, 1)):
    return AnilistMedia.model_validate(
        {
            "id": mid,
            "format": "TV",
            "status": status,
            "episodes": episodes,
            "title": {"romaji": f"M{mid}"},
            "startDate": {"year": start[0], "month": start[1], "day": start[2]},
            "nextAiringEpisode": None,
        }
    )


# --- Fribb mapping -------------------------------------------------------------


def test_parse_fribb_keeps_only_tvdb_seasons():
    rows = parse_fribb(FRIBB.read_bytes())
    assert (MUSHOKU_TVDB, 2, 166873) in rows
    assert all(tvdb and season is not None for tvdb, season, _ in rows)
    assert len(rows) == 9


def test_store_fribb_replaces_auto_rows_and_keeps_manual(db):
    with db.session() as s:
        s.add(m.AnilistMapping(tvdb_id=1, tvdb_season=1, anilist_id=5, source="manual"))
        s.add(m.AnilistMapping(tvdb_id=2, tvdb_season=1, anilist_id=6, source="fribb"))
        s.commit()
        store_fribb(s, [(MUSHOKU_TVDB, 1, 108465)], NOW)
        s.commit()
        rows = {(r.tvdb_id, r.anilist_id, r.source) for r in s.scalars(select(m.AnilistMapping))}
    assert rows == {(1, 5, "manual"), (MUSHOKU_TVDB, 108465, "fribb")}


def test_fribb_staleness(db):
    with db.session() as s:
        assert fribb_is_stale(s, NOW)
        store_fribb(s, [], NOW)
        s.commit()
        assert not fribb_is_stale(s, NOW + timedelta(days=6))
        assert fribb_is_stale(s, NOW + timedelta(days=8))


# --- Cache ---------------------------------------------------------------------


def test_cache_serves_repeats_and_respects_ttl(db):
    fake = FakeAnilist([media(1), media(2, status="RELEASING")])
    clock = {"now": NOW}
    cached = CachedAnilist(db, fake, clock=lambda: clock["now"])
    assert set(cached.media([1, 2, 3])) == {1, 2}
    assert cached.media([1, 2, 3]).keys() == {1, 2}
    assert fake.batches == [[1, 2, 3]]
    clock["now"] += timedelta(minutes=20)  # releasing entry expired, finished + miss still cached
    cached.media([1, 2, 3])
    assert fake.batches[-1] == [2]
    clock["now"] += timedelta(hours=2)  # miss expired too
    cached.media([1, 3])
    assert fake.batches[-1] == [3]


def test_releasing_entry_expires_right_after_its_next_airing(db):
    soon = media(7, status="RELEASING")
    soon = soon.model_copy(
        update={
            "next_airing": _NextAiring(
                episode=2, airingAt=int((NOW + timedelta(minutes=5)).timestamp())
            )
        }
    )
    fake = FakeAnilist([soon])
    clock = {"now": NOW}
    cached = CachedAnilist(db, fake, clock=lambda: clock["now"])
    cached.media([7])
    clock["now"] += timedelta(minutes=6)
    cached.media([7])
    assert len(fake.batches) == 2


# --- Enricher ------------------------------------------------------------------


@pytest.fixture
def mushoku(db):
    with db.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        series = m.Series(
            instance=instance,
            sonarr_id=2,
            tvdb_id=MUSHOKU_TVDB,
            title="Mushoku Tensei",
            series_type="anime",
            followed=True,
        )
        series.seasons += [m.Season(number=1), m.Season(number=2)]
        s.add(series)
        store_fribb(s, parse_fribb(FRIBB.read_bytes()), NOW)
        s.commit()
        return series.id


def run(db, fake, changed=None):
    calls = changed if changed is not None else []
    enricher = AnimeEnricher(
        db,
        CachedAnilist(db, fake, clock=lambda: NOW),
        on_change=lambda i, sid: calls.append((i, sid)),
    )
    enricher.run()
    return calls


def seasons(db, series_id):
    with db.session() as s:
        return {x.number: x for x in s.get(m.Series, series_id).seasons}


def test_split_cour_counts_are_summed_per_tvdb_season(db, mushoku):
    changed = run(db, FakeAnilist())
    rows = seasons(db, mushoku)
    assert (rows[1].anilist_count, rows[2].anilist_count) == (23, 25)
    assert changed == [(1, 2)]
    with db.session() as s:
        assert s.get(m.Series, mushoku).anilist_resolution == "auto"


def test_finished_unknown_season_is_not_created(db, mushoku):
    run(db, FakeAnilist())
    assert 3 not in seasons(db, mushoku)  # Mushoku III is FINISHED in the fixture: no announcement


def test_upcoming_season_is_created_for_the_announcement(db, mushoku):
    fake = FakeAnilist()
    fake.media[178789] = media(178789, status="NOT_YET_RELEASED", episodes=14, start=(2026, 7, 4))
    run(db, fake)
    third = seasons(db, mushoku)[3]
    assert (third.anilist_count, third.anilist_start) == (14, date(2026, 7, 4))


def test_unknown_episode_count_leaves_the_season_alone(db, mushoku):
    fake = FakeAnilist()
    fake.media[166873] = media(166873, episodes=None)
    run(db, fake)
    assert seasons(db, mushoku)[2].anilist_count is None


def test_second_run_without_changes_queues_nothing(db, mushoku):
    run(db, FakeAnilist())
    assert run(db, FakeAnilist()) == []


def test_manual_pin_wins_over_fribb(db, mushoku):
    with db.session() as s:
        s.add(
            m.AnilistMapping(
                tvdb_id=MUSHOKU_TVDB, tvdb_season=2, anilist_id=146065, source="manual"
            )
        )
        s.commit()
    run(db, FakeAnilist())
    assert seasons(db, mushoku)[2].anilist_count == 13
    with db.session() as s:
        assert s.get(m.Series, mushoku).anilist_resolution == "manual"


def test_anime_without_mapping_is_unresolved_and_others_are_skipped(db, mushoku):
    with db.session() as s:
        instance = s.scalar(select(m.SonarrInstance))
        s.add_all(
            [
                m.Series(
                    instance=instance,
                    sonarr_id=9,
                    tvdb_id=1,
                    title="Obscure",
                    series_type="anime",
                    followed=True,
                ),
                m.Series(
                    instance=instance,
                    sonarr_id=10,
                    tvdb_id=2,
                    title="Live",
                    series_type="standard",
                    followed=True,
                ),
            ]
        )
        s.commit()
    run(db, FakeAnilist())
    with db.session() as s:
        resolution = {x.title: x.anilist_resolution for x in s.scalars(select(m.Series))}
    assert resolution == {"Mushoku Tensei": "auto", "Obscure": "unresolved", "Live": "none"}


def test_rate_limit_stops_the_run_quietly(db, mushoku):
    fake = FakeAnilist()
    fake.error = AnilistRateLimited(30)
    assert run(db, fake) == []
    assert seasons(db, mushoku)[2].anilist_count is None


def test_parts_are_derived_for_split_cours(db, mushoku):
    run(db, FakeAnilist())
    with db.session() as s:
        parts = s.scalars(
            select(m.AnimePart).order_by(m.AnimePart.season_id, m.AnimePart.part_index)
        ).all()
        view = [
            (p.season.number, p.part_index, p.anilist_id, p.episode_from, p.episode_to)
            for p in parts
        ]
    assert view == [
        (1, 1, 108465, 1, 11),
        (1, 2, 127720, 12, 23),
        (2, 1, 146065, 1, 13),
        (2, 2, 166873, 14, 25),
    ]


def test_parts_disappear_when_the_mapping_becomes_single(db, mushoku):
    run(db, FakeAnilist())
    with db.session() as s:
        s.add(
            m.AnilistMapping(
                tvdb_id=MUSHOKU_TVDB, tvdb_season=2, anilist_id=146065, source="manual"
            )
        )
        s.commit()
    run(db, FakeAnilist())
    with db.session() as s:
        assert {p.season.number for p in s.scalars(select(m.AnimePart))} == {1}


def test_refresh_if_stale_downloads_once_and_survives_failures(db):
    from finalarr.services.fribb import refresh_if_stale

    calls = []

    def download():
        calls.append(1)
        return FRIBB.read_bytes()

    assert refresh_if_stale(db, download, NOW)
    assert not refresh_if_stale(db, download, NOW + timedelta(days=1))
    assert len(calls) == 1

    def broken():
        raise ValueError("bad json")

    assert not refresh_if_stale(db, broken, NOW + timedelta(days=8))
    with db.session() as s:
        assert len(s.scalars(select(m.AnilistMapping)).all()) == 9


def test_changed_part_titles_replace_parts_without_unique_errors(db, mushoku):
    run(db, FakeAnilist())
    fake = FakeAnilist()
    fake.media[146065] = fake.media[146065].model_copy(update={"episodes": 12})
    with db.session() as s:
        s.execute(m.AnilistCache.__table__.delete())  # finished entries are cached for days
        s.commit()
    run(db, fake)
    with db.session() as s:
        ranges = [
            (p.episode_from, p.episode_to)
            for p in s.scalars(select(m.AnimePart).order_by(m.AnimePart.id))
            if p.season.number == 2
        ]
    assert ranges == [(1, 12), (13, 24)]


def test_removed_mapping_clears_anilist_data(db, mushoku):
    run(db, FakeAnilist())
    with db.session() as s:
        s.execute(m.AnilistMapping.__table__.delete().where(m.AnilistMapping.tvdb_season == 2))
        s.commit()
    changed = run(db, FakeAnilist())
    second = seasons(db, mushoku)[2]
    assert (second.anilist_count, second.anilist_start) == (None, None)
    with db.session() as s:
        assert {p.season.number for p in s.scalars(select(m.AnimePart))} == {1}
    assert changed == [(1, 2)]


def test_series_deleted_during_the_request_is_skipped(db, mushoku):
    class Deleting(FakeAnilist):
        def media_batch(self, ids):
            with db.session() as s:
                series = s.get(m.Series, mushoku)
                if series is not None:
                    s.delete(series)
                    s.commit()
            return super().media_batch(ids)

    assert run(db, Deleting()) == []


def test_one_run_batches_all_series_into_one_request(db, mushoku):
    with db.session() as s:
        instance = s.scalar(select(m.SonarrInstance))
        s.add(
            m.Series(
                instance=instance,
                sonarr_id=7,
                tvdb_id=353712,
                title="Shield Hero",
                series_type="anime",
                followed=True,
            )
        )
        s.commit()
    fake = FakeAnilist()
    run(db, fake)
    # one request for every mapped entry, one for all their sequels
    assert len(fake.batches) == 2
    assert set(fake.batches[0]) >= {108465, 166873, 99263, 173780}
    assert set(fake.batches[1]) == {217434, 199185}


SEQUELS = Path(__file__).parents[1] / "fixtures" / "anilist" / "sequels_2027.json"


def with_2027_sequels():
    fake = FakeAnilist()
    for raw in json.loads(SEQUELS.read_text())["data"]["Page"]["media"]:
        fake.media[raw["id"]] = AnilistMedia.model_validate(raw)
    return fake


def run_with_events(db, fake, now=NOW):
    created = []
    enricher = AnimeEnricher(
        db,
        CachedAnilist(db, fake, clock=lambda: now),
        on_change=lambda *_: None,
        on_events=lambda s, events: created.extend(e.type for e in events),
        clock=lambda: now,
    )
    enricher.run()
    return created


def test_standard_typed_series_with_a_fribb_mapping_is_enriched(db, mushoku):
    with db.session() as s:
        s.get(m.Series, mushoku).series_type = "standard"
        s.commit()
    run(db, FakeAnilist())
    assert seasons(db, mushoku)[2].anilist_count == 25
    with db.session() as s:
        assert s.get(m.Series, mushoku).anilist_resolution == "auto"


def test_unmapped_upcoming_sequel_is_announced_once(db, mushoku):
    created = run_with_events(db, with_2027_sequels())
    assert created == ["sequel_announced"]
    with db.session() as s:
        event = s.scalar(select(m.Event))
        payload = json.loads(event.payload_json)
    assert (event.series_id, event.season_id) == (mushoku, None)
    assert payload["anilist_id"] == 217434
    assert payload["sequel_title"].startswith("Mushoku Tensei III")
    assert payload["first_air"] == "2027-01-01"
    assert payload["title"] == "Mushoku Tensei"
    assert run_with_events(db, with_2027_sequels()) == []


def test_finished_or_mapped_sequels_are_not_announced(db, mushoku):
    fake = with_2027_sequels()
    fake.media[217434] = fake.media[217434].model_copy(update={"status": "FINISHED"})
    assert run_with_events(db, fake) == []
    with db.session() as s:
        s.add(
            m.AnilistMapping(tvdb_id=MUSHOKU_TVDB, tvdb_season=3, anilist_id=217434, source="fribb")
        )
        s.commit()
    assert run_with_events(db, with_2027_sequels()) == []


def test_old_sequel_start_is_not_news(db, mushoku):
    later = datetime(2028, 6, 1, tzinfo=UTC)
    assert run_with_events(db, with_2027_sequels(), now=later) == []


def test_switched_off_fribb_is_not_downloaded(db):
    from finalarr.services.fribb import refresh_if_stale
    from finalarr.services.source_catalog import set_source

    with db.session() as s:
        set_source(s, "fribb", False)
        s.commit()

    def download():
        raise AssertionError("must not download")

    assert not refresh_if_stale(db, download, NOW)


def test_switched_off_anilist_is_not_asked(db, mushoku):
    from finalarr.services.source_catalog import set_source

    with db.session() as s:
        set_source(s, "anilist", False)
        s.commit()

    class Refusing:
        def __getattr__(self, name):
            raise AssertionError("AniList must not be asked")

    assert run(db, Refusing()) == []

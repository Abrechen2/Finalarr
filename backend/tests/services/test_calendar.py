import json
from datetime import UTC, date, datetime, timedelta

import pytest

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.calendar import CalendarOptions, build_entries, render_ics

NOW = datetime(2026, 11, 13, 12, tzinfo=UTC)


def ep(number, days, has_file=False, finale=None, monitored=True):
    return m.Episode(
        sonarr_episode_id=7000 + number,
        number=number,
        title=f"Ep {number}",
        has_file=has_file,
        air_date_utc=NOW + timedelta(days=days),
        finale_type=finale,
        monitored=monitored,
    )


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "f.db")
    database.migrate()
    with database.session() as s:
        instance = m.SonarrInstance(name="C", url="http://s:1", api_key_enc="x", webhook_token="t")
        slime = m.Series(
            instance=instance, sonarr_id=1, title="Slime", title_slug="slime", followed=True
        )
        season = m.Season(number=3, expected_count=4)
        season.episodes += [
            ep(1, -3, has_file=True),
            ep(2, 4),
            ep(3, 11),
            ep(4, 18, finale="season"),
        ]
        slime.seasons.append(season)
        andor = m.Series(
            instance=instance, sonarr_id=2, title="Andor", title_slug="andor", followed=True
        )
        a2 = m.Season(number=2, expected_count=3)
        a2.episodes += [ep(11, 30), ep(12, 30), ep(13, 30)]
        andor.seasons.append(a2)
        ignored = m.Series(instance=instance, sonarr_id=3, title="Not followed", followed=False)
        ignored.seasons.append(m.Season(number=1, episodes=[ep(21, 2)]))
        s.add_all([slime, andor, ignored])
        s.add(
            m.Event(
                type="season_announced",
                fingerprint="a1",
                series_id=None,
                payload_json=json.dumps(
                    {"title": "The Last of Us", "season": 3, "first_air": "2027-02-14"}
                ),
            )
        )
        s.add(
            m.Event(
                type="sequel_announced",
                fingerprint="a2",
                payload_json=json.dumps(
                    {
                        "title": "Mushoku",
                        "sequel_title": "Mushoku III Part 2",
                        "first_air": "2027-01-01",
                    }
                ),
            )
        )
        s.commit()
    yield database
    database.dispose()


def entries(db, **options):
    opts = CalendarOptions(**options)
    with db.session() as s:
        return build_entries(s, NOW.date() - timedelta(days=14), date(2027, 3, 1), opts)


def labels(found):
    return [(e.title, e.season, e.episode, e.kind) for e in found]


def test_milestones_by_default_without_downloaded_episodes(db):
    found = entries(db)
    assert labels(found) == [
        ("Slime", 3, 4, "finale"),
        ("Andor", 2, 11, "premiere"),
        ("Andor", 2, 13, "finale"),
        ("The Last of Us", 3, None, "announcement"),
    ]


def test_all_episodes_and_downloaded_on_request(db):
    found = entries(db, scope="all", hide_downloaded=False, announcements=False)
    assert [(e.title, e.episode) for e in found] == [
        ("Slime", 1),
        ("Slime", 2),
        ("Slime", 3),
        ("Slime", 4),
        ("Andor", 11),
        ("Andor", 12),
        ("Andor", 13),
    ]
    assert found[0].has_file is True


def test_finales_only(db):
    assert [e.kind for e in entries(db, scope="finales", announcements=False)] == [
        "finale",
        "finale",
    ]


def test_series_can_opt_out(db):
    with db.session() as s:
        s.query(m.Series).filter_by(title="Andor").one().calendar = False
        s.commit()
    assert {e.title for e in entries(db)} == {"Slime", "The Last of Us"}


def test_year_only_announcements_are_left_out(db):
    assert "Mushoku" not in {e.title for e in entries(db)}


def test_unmonitored_episodes_are_skipped_when_monitoring_is_respected(db):
    with db.session() as s:
        s.query(m.Episode).filter_by(number=11).one().monitored = False
        s.commit()
    assert ("Andor", 2, 12, "premiere") not in labels(entries(db))
    assert "premiere" not in {e.kind for e in entries(db) if e.title == "Andor"}


def test_ics_feed(db):
    found = entries(db)
    body = render_ics(found, language="de", public_url="https://f.lan")
    text = body.decode()
    assert text.startswith("BEGIN:VCALENDAR")
    assert "X-WR-CALNAME:Finalarr" in text
    assert "SUMMARY:Slime S03E04 – Finale" in text
    assert "SUMMARY:Andor S02E11 – Staffelstart" in text
    assert "SUMMARY:The Last of Us: Staffel 3 – Start angekündigt" in text
    assert "DTSTART;VALUE=DATE:20270214" in text
    assert "UID:finalarr-episode-7004@finalarr" in text
    assert "URL:https://f.lan/series/" in text
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    english = render_ics(found, language="en", public_url=None).decode()
    assert "SUMMARY:Andor S02E11 – Season premiere" in english

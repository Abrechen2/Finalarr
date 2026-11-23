"""Finalarr's media sync end to end against a real Jellyfin (temporary container)."""

import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import requests
from cryptography.fernet import Fernet
from finalarr.crypto import SecretBox
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.watch_sync import WatchSync
from finalarr.services.watch_tracker import tracker_series, tracker_stats
from sqlalchemy import select

U = "http://127.0.0.1:18096"
ids = json.load(open(sys.argv[1]))
box = SecretBox(Fernet.generate_key().decode())
db = Database(Path(tempfile.mkdtemp()) / "finalarr.db")
db.migrate()
with db.session() as s:
    inst = m.SonarrInstance(name="H", url="http://s", api_key_enc="x", webhook_token="t")

    def show(sid, title, tvdb, seasons, followed):
        se = m.Series(
            instance=inst, sonarr_id=sid, title=title, tvdb_id=tvdb, followed=followed, runtime=45
        )
        for number, count in seasons:
            season = m.Season(number=number)
            season.episodes += [
                m.Episode(sonarr_episode_id=sid * 1000 + number * 100 + e, number=e, has_file=True)
                for e in range(1, count + 1)
            ]
            se.seasons.append(season)
        return se

    s.add_all(
        [
            show(1, "Severance", 371980, [(1, 9), (2, 4)], True),
            show(2, "Frieren", 424536, [(0, 1), (1, 6)], False),
            m.MediaServer(
                kind="jellyfin",
                name="Jellyfin",
                url=U,
                token_enc=box.encrypt(ids["key"]),
                enabled=True,
            ),
        ]
    )
    s.commit()
followed_now = []
sync = WatchSync(db, box, on_follow=lambda s, series: followed_now.extend(x.title for x in series))


def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    globals().setdefault("fails", 0)
    if not cond:
        globals()["fails"] += 1


sync.run()
with db.session() as s:
    server = s.scalar(select(m.MediaServer))
    check(
        "users found, none selected yet",
        sorted((u.name, u.selected) for u in server.users) == [("anna", False), ("dennis", False)],
    )
    check("no error", server.last_error is None)
    for u in server.users:
        u.selected = True
    s.commit()
sync.run()
with db.session() as s:
    rows = s.execute(
        select(
            m.MediaUser.name,
            m.WatchedEpisode.series_id,
            m.WatchedEpisode.season_number,
            m.WatchedEpisode.episode_number,
        ).join(m.MediaUser)
    ).all()
    server = s.scalar(select(m.MediaServer))
    per = {(n, sid, se): 0 for n, sid, se, _ in rows}
    for n, sid, se, _ in rows:
        per[(n, sid, se)] += 1
    print("  watched:", per, "unmatched:", server.unmatched_json)
    check("dennis: Severance S1 complete (9)", per.get(("dennis", 1, 1)) == 9)
    check(
        "dennis: Frieren S1 3 + special",
        per.get(("dennis", 2, 1)) == 3 and per.get(("dennis", 2, 0)) == 1,
    )
    check("anna: Severance S2E1", per.get(("anna", 1, 2)) == 1)
    check("Unknown Show reported as unmatched", "Unknown Show" in server.unmatched_json)
    # Jellyfin reports a play date for every played episode, so even the first sync is dated.
    check(
        "play dates come from Jellyfin",
        all(w.watched_on == date.today() for w in s.scalars(select(m.WatchedEpisode))),
    )
check("auto-follow: Frieren (3 recent episodes) is followed", followed_now == ["Frieren"])
# Un-mark an episode in Jellyfin and mark a new one: the next sync follows both.
h = {
    "Authorization": 'MediaBrowser Client="t", Device="t", DeviceId="t", Version="1", '
    f'Token="{ids["key"]}"'
}
eps = requests.get(
    f"{U}/Items",
    headers=h,
    params={"userId": ids["me"], "Recursive": "true", "IncludeItemTypes": "Episode"},
).json()["Items"]


def ep(series, season, n):
    return next(
        e["Id"]
        for e in eps
        if e["SeriesName"].startswith(series)
        and e["ParentIndexNumber"] == season
        and e["IndexNumber"] == n
    )


r1 = requests.delete(
    f"{U}/UserPlayedItems/{ep('Severance', 1, 9)}", headers=h, params={"userId": ids["me"]}
)
r2 = requests.post(
    f"{U}/UserPlayedItems/{ep('Frieren', 1, 4)}", headers=h, params={"userId": ids["me"]}
)
r3 = requests.post(
    f"{U}/UserPlayedItems/{ep('Frieren', 1, 5)}", headers=h, params={"userId": ids["me"]}
)
print("  jellyfin changes:", r1.status_code, r2.status_code, r3.status_code)
sync.run()
with db.session() as s:
    me = s.scalar(select(m.MediaUser.id).where(m.MediaUser.name == "dennis"))
    mine = {
        (w.series_id, w.season_number, w.episode_number): w.watched_on
        for w in s.scalars(select(m.WatchedEpisode).where(m.WatchedEpisode.user_id == me))
    }
    check("unwatched in Jellyfin -> gone", (1, 1, 9) not in mine)
    check(
        "new plays dated today",
        mine.get((2, 1, 4)) == date.today() and mine.get((2, 1, 5)) == date.today(),
    )
check("followed once, not again", followed_now == ["Frieren"])
with db.session() as s:
    stats = tracker_stats(s, None, date.today(), weeks=2)
    rows = {r["title"]: r for r in tracker_series(s, None, date.today())}
    print(
        "  tracker:", {k: stats[k] for k in ("episodes", "this_week", "undated")}, stats["series"]
    )
    print("  rows:", {t: (r["state"], r["unwatched"], r["next"]) for t, r in rows.items()})
    # Furthest watched is S02E01 (anna), so S01E09 counts as skipped, not missing.
    check(
        "tracker: Severance next is S02E02",
        rows["Severance"]["next"] == {"season": 2, "episode": 2},
    )
    check("tracker: Frieren next is S01E06", rows["Frieren"]["next"] == {"season": 1, "episode": 6})
# Outage: pause Jellyfin (its config lives in tmpfs, a restart would wipe it).
subprocess.run(["docker", "pause", "finalarr-jf"], capture_output=True)
sync.run()
with db.session() as s:
    server = s.scalar(select(m.MediaServer))
    check(f"outage recorded: {server.last_error!r}", bool(server.last_error))
    check("outage keeps watch data", s.query(m.WatchedEpisode).count() >= 15)
subprocess.run(["docker", "unpause", "finalarr-jf"], capture_output=True)
fails = globals().get("fails", 0)
print("FAILS:", fails)
sys.exit(1 if fails else 0)

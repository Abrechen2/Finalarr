"""Reads what the selected media server users watched and follows those series.

Each server is read outside any transaction; its result replaces the stored state
of its selected users in one short transaction. A server that fails keeps its old
state. Users that are not selected keep no watch data at all.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from finalarr.crypto import SecretBox, SecretDecryptError
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.reconcile_queue import enqueue
from finalarr.services.settings_store import load_settings
from finalarr.sources.media import MediaClient, MediaError, WatchedItem, client_for

log = logging.getLogger(__name__)

MAX_UNMATCHED = 200
ClientFactory = Callable[[m.MediaServer], MediaClient]
OnFollow = Callable[[Session, list[m.Series]], None]
Key = tuple[int, int, int]  # series id, season, episode


def default_client_factory(box: SecretBox) -> ClientFactory:
    def build(server: m.MediaServer) -> MediaClient:
        return client_for(server.kind, server.url, box.decrypt(server.token_enc))

    return build


class WatchSync:
    def __init__(
        self,
        db: Database,
        box: SecretBox,
        client_factory: ClientFactory | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        on_follow: OnFollow | None = None,
    ) -> None:
        self._db = db
        self._client_factory = client_factory or default_client_factory(box)
        self._clock = clock
        self._on_follow = on_follow

    def run(self) -> None:
        with self._db.session() as s:
            servers = list(
                s.scalars(select(m.MediaServer.id).where(m.MediaServer.enabled.is_(True)))
            )
        for server_id in servers:
            self.sync_server(server_id)
        with self._db.session() as s:
            followed = auto_follow(s, self._clock())
            if followed and self._on_follow:
                self._on_follow(s, followed)
            s.commit()

    def sync_server(self, server_id: int) -> None:
        with self._db.session() as s:
            server = s.get_one(m.MediaServer, server_id)
            selected = {u.remote_id for u in server.users if u.selected}
        try:
            client = self._client_factory(server)
            users = client.users()
            watched = {
                u.remote_id: client.watched(u.remote_id) for u in users if u.remote_id in selected
            }
        except (MediaError, SecretDecryptError) as error:
            log.warning("Media server %s: %s", server_id, error)
            self._mark(server_id, str(error))
            return
        with self._db.session() as s:
            server = s.get_one(m.MediaServer, server_id)
            _store_users(server, {u.remote_id: u.name for u in users})
            s.flush()
            by_tvdb = _series_by_tvdb(s)
            unmatched: set[str] = set()
            today = self._clock().date()
            for user in server.users:
                previous = _stored(s, user.id)
                s.execute(delete(m.WatchedEpisode).where(m.WatchedEpisode.user_id == user.id))
                if user.remote_id in watched:
                    rows, missing = _rows(watched[user.remote_id], by_tvdb)
                    unmatched |= missing
                    first_seen = None if user.baseline_at is None else today
                    rows = {
                        key: on or previous.get(key) or (None if key in previous else first_seen)
                        for key, on in rows.items()
                    }
                    user.baseline_at = user.baseline_at or self._clock()
                    rows = _apply_overrides(s, user.id, rows)
                    s.add_all(
                        m.WatchedEpisode(
                            user_id=user.id,
                            series_id=sid,
                            season_number=season,
                            episode_number=episode,
                            watched_on=on,
                        )
                        for (sid, season, episode), on in rows.items()
                    )
            server.unmatched_json = json.dumps(sorted(unmatched)[:MAX_UNMATCHED])
            server.last_sync_at = self._clock()
            server.last_error = None
            s.commit()

    def _mark(self, server_id: int, error: str) -> None:
        with self._db.session() as s:
            s.get_one(m.MediaServer, server_id).last_error = error
            s.commit()


def _store_users(server: m.MediaServer, remote: dict[str, str]) -> None:
    known = {u.remote_id: u for u in server.users}
    for gone in known.keys() - remote.keys():
        server.users.remove(known[gone])
    for remote_id, name in remote.items():
        if remote_id in known:
            known[remote_id].name = name
        else:
            server.users.append(m.MediaUser(remote_id=remote_id, name=name, selected=False))


def _apply_overrides(
    s: Session, user_id: int, rows: dict[Key, date | None]
) -> dict[Key, date | None]:
    """Manual corrections win; a "watched" one ends once the server agrees."""
    result = dict(rows)
    for override in s.scalars(select(m.WatchOverride).where(m.WatchOverride.user_id == user_id)):
        key = (override.series_id, override.season_number, override.episode_number)
        if not override.watched:
            result.pop(key, None)
        elif key in rows:
            s.delete(override)
        else:
            result[key] = override.created_at.date()
    return result


def _stored(s: Session, user_id: int) -> dict[Key, date | None]:
    return {
        (sid, season, episode): on
        for sid, season, episode, on in s.execute(
            select(
                m.WatchedEpisode.series_id,
                m.WatchedEpisode.season_number,
                m.WatchedEpisode.episode_number,
                m.WatchedEpisode.watched_on,
            ).where(m.WatchedEpisode.user_id == user_id)
        )
    }


def _series_by_tvdb(s: Session) -> dict[int, list[int]]:
    found: dict[int, list[int]] = {}
    rows = s.execute(select(m.Series.id, m.Series.tvdb_id).where(m.Series.tvdb_id.is_not(None)))
    for sid, tvdb in rows:
        if tvdb is not None:
            found.setdefault(tvdb, []).append(sid)
    return found


def _rows(
    items: list[WatchedItem], by_tvdb: dict[int, list[int]]
) -> tuple[dict[Key, date | None], set[str]]:
    """Distinct episodes per Sonarr series (the newest date wins) and unmatched titles."""
    rows: dict[Key, date | None] = {}
    unmatched: set[str] = set()
    for item in items:
        series_ids = by_tvdb.get(item.series_tvdb) if item.series_tvdb else None
        if not series_ids:
            if item.series_title:
                unmatched.add(item.series_title)
            continue
        for sid in series_ids:
            key = (sid, item.season, item.episode)
            dates = [d for d in (rows.get(key), item.watched_on) if d is not None]
            rows[key] = max(dates) if dates else None
    return rows, unmatched


def auto_follow(s: Session, now: datetime) -> list[m.Series]:
    """Follow ``auto`` series that some selected user watched enough of lately.
    It never unfollows: dropping abandoned series is a later, separate rule."""
    values: dict[str, Any] = load_settings(s)
    if not values["auto_follow"]:
        return []
    since = now.date() - timedelta(days=int(values["auto_follow_days"]))
    recent = (
        select(m.WatchedEpisode.series_id)
        .where(m.WatchedEpisode.season_number > 0, m.WatchedEpisode.watched_on >= since)
        .group_by(m.WatchedEpisode.series_id, m.WatchedEpisode.user_id)
        .having(func.count() >= int(values["auto_follow_min_episodes"]))
    )
    newly = list(
        s.scalars(
            select(m.Series).where(
                m.Series.follow_mode == "auto",
                m.Series.followed.is_(False),
                m.Series.id.in_(recent),
            )
        )
    )
    for series in newly:
        series.followed = True
        enqueue(s, series.instance_id, series.sonarr_id)
    return newly

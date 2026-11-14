"""Flask application factory."""

import os
from datetime import UTC, tzinfo
from functools import partial
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, abort, jsonify, send_from_directory
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from finalarr.api import (
    anilist,
    calendar,
    channels,
    dashboard,
    events,
    instances,
    rules,
    series,
    system,
    webhook,
)
from finalarr.api.common import register_error_handler
from finalarr.auth import init_auth
from finalarr.config import Settings, load_settings
from finalarr.crypto import SecretBox
from finalarr.db.session import Database
from finalarr.logging_setup import configure_logging
from finalarr.notify.sender import AppriseSender
from finalarr.ratelimit import RateLimiter
from finalarr.scheduler import SchedulerService
from finalarr.services.anilist_cache import CachedAnilist
from finalarr.services.announcements import AnnouncementWatcher, SeasonSource
from finalarr.services.delivery import DeliveryWorker, create_deliveries
from finalarr.services.enricher import AnimeEnricher
from finalarr.services.fribb import refresh_if_stale
from finalarr.services.mal_backup import MalSequelWatcher
from finalarr.services.news import NewsWatcher, anilist_titles
from finalarr.services.reconcile_queue import enqueue
from finalarr.services.reconciler import Reconciler
from finalarr.services.season_sources import JsonCache, TmdbSource, TraktSource, TvmazeSource
from finalarr.services.series_extras import ExtrasSources
from finalarr.sources.anilist import AnilistClient
from finalarr.sources.animeschedule import AnimeScheduleClient
from finalarr.sources.feeds import FEEDS, fetch_feed
from finalarr.sources.jikan import JikanClient
from finalarr.sources.tmdb import TmdbClient
from finalarr.sources.trakt import TraktClient
from finalarr.sources.tvmaze import TvmazeClient
from finalarr.version import get_version

_DEFAULT_STATIC_DIR = Path("/app/static")
_API_PREFIXES = ("api/", "webhook/", "ical/")
MAX_REQUEST_BYTES = 1024 * 1024
ANILIST_EVERY_SECONDS = 30 * 60
FEED_READS_PER_MINUTE = 30
ANNOUNCEMENTS_EVERY_SECONDS = 6 * 60 * 60
NEWS_EVERY_SECONDS = 30 * 60
DELIVER_EVERY_SECONDS = 10


def extras_sources(settings: Settings, cache: JsonCache, anilist: CachedAnilist) -> ExtrasSources:
    """Series page extras; TMDB and AnimeSchedule only with a key."""
    tmdb = settings.tmdb_api_key
    token = settings.animeschedule_token
    return ExtrasSources(
        cache=cache,
        tvmaze=TvmazeClient(),
        anilist=anilist,
        tmdb=TmdbClient(tmdb.get_secret_value()) if tmdb else None,
        animeschedule=AnimeScheduleClient(token.get_secret_value()) if token else None,
        region=settings.watch_region,
    )


def season_sources(settings: Settings, cache: JsonCache) -> list[SeasonSource]:
    """TVmaze always; TMDB and Trakt only with a key."""
    sources: list[SeasonSource] = [TvmazeSource(TvmazeClient(), cache)]
    if settings.tmdb_api_key:
        sources.append(TmdbSource(TmdbClient(settings.tmdb_api_key.get_secret_value()), cache))
    if settings.trakt_client_id:
        sources.append(TraktSource(TraktClient(settings.trakt_client_id.get_secret_value()), cache))
    return sources


def local_zone() -> tzinfo:
    """Container time zone (TZ) for quiet hours; UTC when unset or unknown."""
    try:
        return ZoneInfo(os.environ.get("TZ") or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def create_app(settings: Settings | None = None, static_dir: Path | None = None) -> Flask:
    """Build the app; without ``settings`` they come from the environment (fail closed)."""
    settings = settings or load_settings()
    configure_logging(settings.log_level, settings.data)
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    app.extensions["finalarr.settings"] = settings
    if settings.trusted_proxies:
        hops = settings.trusted_proxies
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops)  # type: ignore[method-assign]
    init_auth(app, settings)
    database = Database(settings.data / "finalarr.db")
    database.migrate()
    app.extensions["finalarr.db"] = database
    app.extensions["finalarr.secrets"] = SecretBox(settings.secret_key.get_secret_value())
    app.extensions["finalarr.webhook_allow"] = webhook.parse_allowlist(settings.webhook_allow)
    app.extensions["finalarr.webhook_limiter"] = RateLimiter(webhook.TRIGGERS_PER_MINUTE, 60)
    register_error_handler(app)
    box = app.extensions["finalarr.secrets"]
    delivery = DeliveryWorker(
        database, box, AppriseSender(), public_url=settings.public_url, zone=local_zone()
    )
    reconciler = Reconciler(database, box, on_events=lambda s, events: create_deliveries(s, events))
    cached_anilist = CachedAnilist(database, AnilistClient())

    def queue_series(instance_id: int, sonarr_id: int) -> None:
        with database.session() as s:
            enqueue(s, instance_id, sonarr_id)
            s.commit()

    enricher = AnimeEnricher(
        database,
        cached_anilist,
        on_change=queue_series,
        on_events=lambda s, events: create_deliveries(s, events),
    )

    def anilist_cycle() -> None:
        # The mapping must exist before the first enrichment can resolve anything.
        refresh_if_stale(database)
        enricher.run()

    json_cache = JsonCache(database)
    app.extensions["finalarr.json_cache"] = json_cache
    app.extensions["finalarr.extras"] = extras_sources(settings, json_cache, cached_anilist)
    watcher = AnnouncementWatcher(
        database,
        season_sources(settings, json_cache),
        on_events=lambda s, events: create_deliveries(s, events),
    )
    mal_watcher = MalSequelWatcher(
        database,
        JikanClient(),
        json_cache,
        on_events=lambda s, events: create_deliveries(s, events),
    )

    news = NewsWatcher(
        database,
        [(name, partial(fetch_feed, url)) for name, url in FEEDS.items()],
        on_events=lambda s, events: create_deliveries(s, events),
        extra_titles=anilist_titles,
    )

    def announcement_cycle() -> None:
        watcher.run()
        mal_watcher.run()

    scheduler = SchedulerService(
        database,
        reconciler,
        lock_path=settings.data / "scheduler.lock",
        extra_jobs=[
            ("anilist", anilist_cycle, ANILIST_EVERY_SECONDS),
            ("announcements", announcement_cycle, ANNOUNCEMENTS_EVERY_SECONDS),
            ("news", news.run, NEWS_EVERY_SECONDS),
            ("deliver", delivery.run, DELIVER_EVERY_SECONDS),
        ],
    )
    app.extensions["finalarr.anilist"] = cached_anilist
    app.extensions["finalarr.enricher"] = enricher
    app.extensions["finalarr.delivery"] = delivery
    app.extensions["finalarr.reconciler"] = reconciler
    app.extensions["finalarr.scheduler"] = scheduler
    app.extensions["finalarr.nudge"] = scheduler.nudge

    def nudge_sources() -> None:
        scheduler.run_soon("anilist")
        scheduler.run_soon("announcements")

    app.extensions["finalarr.nudge_anilist"] = nudge_sources
    app.extensions["finalarr.watcher"] = watcher
    app.register_blueprint(instances.bp)
    app.register_blueprint(webhook.bp)
    app.register_blueprint(series.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(rules.bp)
    app.register_blueprint(anilist.bp)
    app.register_blueprint(channels.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(system.bp)
    app.register_blueprint(calendar.bp)
    app.extensions["finalarr.feed_limiter"] = RateLimiter(FEED_READS_PER_MINUTE, 60)
    spa_dir = static_dir or Path(os.environ.get("FINALARR_STATIC_DIR", _DEFAULT_STATIC_DIR))

    @app.get("/health")
    def health() -> ResponseReturnValue:
        db_ok = database.ping()
        return jsonify(
            status="ok" if db_ok else "degraded",
            version=get_version(),
            db="ok" if db_ok else "error",
        ), (200 if db_ok else 503)

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path: str) -> ResponseReturnValue:
        if path.startswith(_API_PREFIXES) or not (spa_dir / "index.html").is_file():
            abort(404)
        asset = safe_join(str(spa_dir), path) if path else None
        if asset and Path(asset).is_file():
            return send_from_directory(spa_dir, path)
        return send_from_directory(spa_dir, "index.html")

    @app.errorhandler(NotFound)
    def not_found(_error: NotFound) -> ResponseReturnValue:
        return jsonify(error={"code": "not_found", "message": "Not found"}), 404

    return app

"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from finalarr.api import anilist, events, instances, rules, series, webhook
from finalarr.api.common import register_error_handler
from finalarr.auth import init_auth
from finalarr.config import Settings, load_settings
from finalarr.crypto import SecretBox
from finalarr.db.session import Database
from finalarr.logging_setup import configure_logging
from finalarr.ratelimit import RateLimiter
from finalarr.scheduler import SchedulerService
from finalarr.services.anilist_cache import CachedAnilist
from finalarr.services.enricher import AnimeEnricher
from finalarr.services.fribb import refresh_if_stale
from finalarr.services.reconcile_queue import enqueue
from finalarr.services.reconciler import Reconciler
from finalarr.sources.anilist import AnilistClient
from finalarr.version import get_version

_DEFAULT_STATIC_DIR = Path("/app/static")
_API_PREFIXES = ("api/", "webhook/")
MAX_REQUEST_BYTES = 1024 * 1024
ANILIST_EVERY_SECONDS = 30 * 60


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
    reconciler = Reconciler(database, app.extensions["finalarr.secrets"])
    cached_anilist = CachedAnilist(database, AnilistClient())

    def queue_series(instance_id: int, sonarr_id: int) -> None:
        with database.session() as s:
            enqueue(s, instance_id, sonarr_id)
            s.commit()

    enricher = AnimeEnricher(database, cached_anilist, on_change=queue_series)

    def anilist_cycle() -> None:
        # The mapping must exist before the first enrichment can resolve anything.
        refresh_if_stale(database)
        enricher.run()

    scheduler = SchedulerService(
        database,
        reconciler,
        lock_path=settings.data / "scheduler.lock",
        extra_jobs=[("anilist", anilist_cycle, ANILIST_EVERY_SECONDS)],
    )
    app.extensions["finalarr.anilist"] = cached_anilist
    app.extensions["finalarr.enricher"] = enricher
    app.extensions["finalarr.reconciler"] = reconciler
    app.extensions["finalarr.scheduler"] = scheduler
    app.extensions["finalarr.nudge"] = scheduler.nudge
    app.extensions["finalarr.nudge_anilist"] = lambda: scheduler.run_soon("anilist")
    app.register_blueprint(instances.bp)
    app.register_blueprint(webhook.bp)
    app.register_blueprint(series.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(rules.bp)
    app.register_blueprint(anilist.bp)
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

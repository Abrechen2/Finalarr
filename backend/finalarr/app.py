"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from finalarr.auth import init_auth
from finalarr.config import Settings, load_settings
from finalarr.db.session import Database
from finalarr.version import get_version

_DEFAULT_STATIC_DIR = Path("/app/static")
_API_PREFIXES = ("api/", "webhook/")


def create_app(settings: Settings | None = None, static_dir: Path | None = None) -> Flask:
    """Build the app; without ``settings`` they come from the environment (fail closed)."""
    settings = settings or load_settings()
    app = Flask(__name__, static_folder=None)
    app.extensions["finalarr.settings"] = settings
    if settings.trusted_proxies:
        hops = settings.trusted_proxies
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops)  # type: ignore[method-assign]
    init_auth(app, settings)
    database = Database(settings.data / "finalarr.db")
    database.migrate()
    app.extensions["finalarr.db"] = database
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

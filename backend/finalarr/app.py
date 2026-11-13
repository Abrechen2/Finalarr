"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import NotFound
from werkzeug.security import safe_join

from finalarr.auth import init_auth
from finalarr.config import Settings, load_settings
from finalarr.version import get_version

_DEFAULT_STATIC_DIR = Path("/app/static")
_API_PREFIXES = ("api/", "webhook/")


def create_app(settings: Settings | None = None, static_dir: Path | None = None) -> Flask:
    """Build the app; without ``settings`` they come from the environment (fail closed)."""
    settings = settings or load_settings()
    app = Flask(__name__, static_folder=None)
    app.extensions["finalarr.settings"] = settings
    init_auth(app, settings)
    spa_dir = static_dir or Path(os.environ.get("FINALARR_STATIC_DIR", _DEFAULT_STATIC_DIR))

    @app.get("/health")
    def health() -> ResponseReturnValue:
        return jsonify(status="ok", version=get_version())

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

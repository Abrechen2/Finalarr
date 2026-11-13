"""Single source of the running version."""

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


def get_version() -> str:
    """Image tag (e.g. ``0.1.0-rc.2``) if set at build time, else ``backend/VERSION``."""
    override = os.environ.get("FINALARR_VERSION", "").strip()
    if override:
        return override
    if _VERSION_FILE.is_file():
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    try:
        return version("finalarr")
    except PackageNotFoundError:
        return "0.0.0+unknown"

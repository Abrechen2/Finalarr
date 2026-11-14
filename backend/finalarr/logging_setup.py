"""Logging to stdout and /config/finalarr.log, with secrets stripped."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_BYTES = 2 * 1024 * 1024
LOG_BACKUPS = 3
_PATTERNS = [
    (re.compile(r"[0-9a-f]{64}"), "***"),
    (re.compile(r"(?i)(api[_-]?key[\"']?\s*[=:]\s*[\"']?)[^\s&\"',]+"), r"\1***"),
    # Apprise URLs carry their credentials inline.
    (re.compile(r"\b(tgram|discord|pover|json|jsons|apprise)://[^\s\"']+"), r"\1://***"),
    # Credentials inside plain HTTP(S) URLs, as Apprise logs them when it sends.
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1***@"),
    (re.compile(r"(/bot)\d+:[\w-]+"), r"\1***"),
    (re.compile(r"(/api/webhooks/\d+/)[\w-]+"), r"\1***"),
    (re.compile(r"(?i)([?&](?:token|key|secret|password|auth)=)[^&\s\"']+"), r"\1***"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = redact(record.getMessage()), None
        return True


class RedactingFormatter(logging.Formatter):
    """Redacts the whole formatted record, tracebacks included."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(level: str, data_dir: Path) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for handler in [h for h in root.handlers if getattr(h, "finalarr", False)]:
        root.removeHandler(handler)
        handler.close()
    data_dir.mkdir(parents=True, exist_ok=True)
    formatter = RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        RotatingFileHandler(data_dir / "finalarr.log", maxBytes=LOG_BYTES, backupCount=LOG_BACKUPS),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(RedactingFilter())
        handler.finalarr = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    # The drain job runs every few seconds; its INFO lines and "skipped: maximum
    # number of running instances" warnings during a long sync are noise.
    logging.getLogger("apscheduler").setLevel(logging.ERROR)

"""Channel presets → Apprise URLs. The stored URL is never shown again."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import apprise

_TELEGRAM_TOKEN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
_TELEGRAM_CHAT = re.compile(r"^(-?\d{1,20}|@[A-Za-z0-9_]{5,})$")
_DISCORD = re.compile(r"^https://(?:discord|discordapp)\.com/api/webhooks/(\d+)/([A-Za-z0-9_-]+)$")
_PUSHOVER_KEY = re.compile(r"^[A-Za-z0-9]{30}$")
KINDS = ("telegram", "discord", "pushover", "webhook", "apprise")


class PresetError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _field(fields: dict[str, str], name: str) -> str:
    return str(fields.get(name, "")).strip()


def _telegram(fields: dict[str, str]) -> str:
    token, chat = _field(fields, "bot_token"), _field(fields, "chat_id")
    if not _TELEGRAM_TOKEN.match(token):
        raise PresetError(
            "bot_token", "Telegram bot token looks like 123456:ABC… (from @BotFather)"
        )
    if not _TELEGRAM_CHAT.match(chat):
        raise PresetError("chat_id", "Chat id is a number (e.g. -100123…) or @channelname")
    return f"tgram://{token}/{chat}"


def _discord(fields: dict[str, str]) -> str:
    match = _DISCORD.match(_field(fields, "webhook_url"))
    if not match:
        raise PresetError(
            "webhook_url", "Paste the Discord webhook URL (discord.com/api/webhooks/…)"
        )
    return f"discord://{match[1]}/{match[2]}"


def _pushover(fields: dict[str, str]) -> str:
    user, token = _field(fields, "user_key"), _field(fields, "app_token")
    if not _PUSHOVER_KEY.match(user):
        raise PresetError("user_key", "Pushover user key has 30 letters and digits")
    if not _PUSHOVER_KEY.match(token):
        raise PresetError("app_token", "Pushover app token has 30 letters and digits")
    return f"pover://{user}@{token}"


def _webhook(fields: dict[str, str]) -> str:
    url = _field(fields, "url")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PresetError("url", "Webhook URL must start with http:// or https://")
    scheme = "jsons" if parts.scheme == "https" else "json"
    return f"{scheme}://{url.split('://', 1)[1]}"


def _raw(fields: dict[str, str]) -> str:
    return _field(fields, "url")


_BUILDERS = {
    "telegram": _telegram,
    "discord": _discord,
    "pushover": _pushover,
    "webhook": _webhook,
    "apprise": _raw,
}


def build_url(kind: str, fields: dict[str, str]) -> str:
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise PresetError("kind", f"Unknown channel kind; use one of {', '.join(KINDS)}")
    url = builder(fields)
    if not apprise.Apprise().add(url):
        raise PresetError(
            "url" if kind in ("apprise", "webhook") else "kind", "Apprise does not accept this URL"
        )
    return url


def describe(url: str) -> str:
    """Scheme only: Apprise URLs carry their credentials inline."""
    return f"{url.split('://', 1)[0]}://***"

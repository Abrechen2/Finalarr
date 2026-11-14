"""Bootstrap configuration from the environment.

Fails closed: without a usable API key and Fernet secret key the app refuses to
start. Everything else lives in the database and the UI.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "FINALARR_"
MIN_API_KEY_LENGTH = 20


class ConfigError(RuntimeError):
    """Startup configuration is missing or invalid. Messages never carry secret values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore", frozen=True)

    api_key: SecretStr
    secret_key: SecretStr
    port: int = Field(default=5790, ge=1, le=65535)
    base_path: str = "/"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    language: Literal["de", "en"] = "de"
    data: Path = Path("/config")
    cookie_secure: bool = False
    # "required": API key/login for everyone. "local": no login from private networks.
    auth: Literal["required", "local"] = "required"
    # Reverse proxies in front of Finalarr (e.g. 1 behind NPM). Only then is
    # X-Forwarded-For trusted for the client address.
    trusted_proxies: int = Field(default=0, ge=0, le=5)
    # Optional extra announcement sources (free keys); unset = source off.
    tmdb_api_key: SecretStr | None = None
    trakt_client_id: SecretStr | None = None
    # Optional AnimeSchedule.net app token: English dub dates and delay notes.
    animeschedule_token: SecretStr | None = None
    # Country for TMDB's "where to watch" (ISO 3166-1, e.g. DE, US, GB).
    watch_region: str = Field(default="DE", pattern=r"^[A-Z]{2}$")
    # Base URL users open Finalarr at; enables "open in Finalarr" links in messages.
    public_url: str | None = None
    # Public base URL that serves only /ical/ (e.g. through a reverse proxy), shown as
    # the subscription address so Google/Outlook can reach the feed.
    feed_url: str | None = None
    # Optional comma list of IPs/CIDRs allowed to call the Sonarr webhook.
    webhook_allow: str = ""

    @field_validator("public_url", "feed_url")
    @classmethod
    def _public_url_is_http(cls, value: str | None) -> str | None:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return value.rstrip("/") if value else None

    @field_validator("webhook_allow")
    @classmethod
    def _allowlist_parses(cls, value: str) -> str:
        import ipaddress

        for part in filter(None, (p.strip() for p in value.split(","))):
            try:
                ipaddress.ip_network(part, strict=False)
            except ValueError:
                raise ValueError(f"not an IP address or network: {part}") from None
        return value

    @field_validator("api_key")
    @classmethod
    def _api_key_strong_enough(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if not key:
            raise ValueError("must not be empty")
        if len(key) < MIN_API_KEY_LENGTH:
            raise ValueError(f"must be at least {MIN_API_KEY_LENGTH} characters")
        return SecretStr(key)

    @field_validator("secret_key")
    @classmethod
    def _secret_key_is_fernet(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value().strip().encode())
        except (ValueError, TypeError):
            raise ValueError(
                "must be a Fernet key (generate one with `openssl rand -base64 32 | tr '+/' '-_'`)"
            ) from None
        return SecretStr(value.get_secret_value().strip())


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read settings from ``environ`` (default: the process environment)."""
    source = os.environ if environ is None else environ
    values = {
        key[len(ENV_PREFIX) :].lower(): value
        for key, value in source.items()
        if key.startswith(ENV_PREFIX) and key != f"{ENV_PREFIX}VERSION"
    }
    try:
        return Settings.model_validate(values)
    except ValidationError as error:
        problems = [
            f"{ENV_PREFIX}{'.'.join(str(p) for p in issue['loc']).upper()}: {_reason(issue)}"
            for issue in error.errors(include_input=False)
        ]
        raise ConfigError("Invalid configuration — " + "; ".join(problems)) from None


def _reason(issue: Mapping[str, object]) -> str:
    if issue.get("type") == "missing":
        return "required, not set"
    message = str(issue.get("msg", "invalid"))
    return message.removeprefix("Value error, ")

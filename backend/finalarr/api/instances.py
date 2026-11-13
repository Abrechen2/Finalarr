"""Sonarr instances: CRUD, connection test, webhook token, manual sync (PLAN.md section 7)."""

from __future__ import annotations

import secrets as token_source
from typing import Any

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from finalarr.api.common import ApiProblem, database, not_found, parse_body, secrets
from finalarr.crypto import mask
from finalarr.db.models import SonarrInstance
from finalarr.services.reconcile_queue import enqueue
from finalarr.sources.sonarr import (
    SonarrAuthError,
    SonarrClient,
    SonarrError,
    validate_base_url,
)

bp = Blueprint("instances", __name__, url_prefix="/api/v1/instances")
WEBHOOK_TOKEN_BYTES = 32


class _UrlMixin(BaseModel):
    @field_validator("url", check_fields=False)
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return None if value is None else validate_base_url(value)


class ConnectionIn(_UrlMixin):
    url: str
    api_key: str = Field(min_length=1, max_length=200)


class InstanceIn(ConnectionIn):
    name: str = Field(min_length=1, max_length=100)
    basic_user: str | None = Field(default=None, max_length=100)
    basic_password: str | None = Field(default=None, max_length=200)


class InstancePatch(_UrlMixin):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    basic_user: str | None = Field(default=None, max_length=100)
    basic_password: str | None = Field(default=None, max_length=200)


def serialize(instance: SonarrInstance) -> dict[str, Any]:
    return {
        "id": instance.id,
        "name": instance.name,
        "url": instance.url,
        "api_key": mask(secrets().decrypt(instance.api_key_enc)),
        "enabled": instance.enabled,
        "basic_user": instance.basic_user,
        "basic_password_set": bool(instance.basic_pass_enc),
        "webhook_token": instance.webhook_token,
        "webhook_path": f"/webhook/sonarr/{instance.webhook_token}",
        "last_sync_at": instance.last_sync_at.isoformat() if instance.last_sync_at else None,
        "last_error": instance.last_error,
    }


def _load(session: Any, instance_id: int) -> SonarrInstance:
    instance = session.get(SonarrInstance, instance_id)
    if instance is None:
        raise not_found("Instance")
    return instance  # type: ignore[no-any-return]


def _commit(session: Any) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiProblem(409, "conflict", "An instance with this name exists already") from None


def _apply_basic(instance: SonarrInstance, user: str | None, password: str | None) -> None:
    if user is not None:
        instance.basic_user = user or None
    if password is not None:
        instance.basic_pass_enc = secrets().encrypt(password) if password else None


def connection_check(url: str, api_key: str) -> ResponseReturnValue:
    try:
        status = SonarrClient(url, api_key).system_status()
    except SonarrAuthError as error:
        raise ApiProblem(502, "sonarr_auth", str(error)) from None
    except SonarrError as error:
        raise ApiProblem(502, "sonarr_unreachable", str(error)) from None
    return {"ok": True, "version": status.version}


@bp.get("")
def list_instances() -> ResponseReturnValue:
    with database().session() as s:
        rows = s.scalars(select(SonarrInstance).order_by(SonarrInstance.name))
        return [serialize(i) for i in rows]


@bp.post("")
def create_instance() -> ResponseReturnValue:
    body = parse_body(InstanceIn)
    with database().session() as s:
        instance = SonarrInstance(
            name=body.name.strip(),
            url=body.url,
            api_key_enc=secrets().encrypt(body.api_key),
            webhook_token=token_source.token_hex(WEBHOOK_TOKEN_BYTES),
        )
        _apply_basic(instance, body.basic_user, body.basic_password)
        s.add(instance)
        _commit(s)
        return serialize(instance), 201


@bp.post("/test")
def test_unsaved() -> ResponseReturnValue:
    body = parse_body(ConnectionIn)
    return connection_check(body.url, body.api_key)


@bp.get("/<int:instance_id>")
def get_instance(instance_id: int) -> ResponseReturnValue:
    with database().session() as s:
        return serialize(_load(s, instance_id))


@bp.patch("/<int:instance_id>")
def patch_instance(instance_id: int) -> ResponseReturnValue:
    body = parse_body(InstancePatch)
    with database().session() as s:
        instance = _load(s, instance_id)
        if body.name is not None:
            instance.name = body.name.strip()
        if body.url is not None:
            instance.url = body.url
        if body.api_key is not None:
            instance.api_key_enc = secrets().encrypt(body.api_key)
        if body.enabled is not None:
            instance.enabled = body.enabled
        _apply_basic(instance, body.basic_user, body.basic_password)
        _commit(s)
        return serialize(instance)


@bp.delete("/<int:instance_id>")
def delete_instance(instance_id: int) -> ResponseReturnValue:
    with database().session() as s:
        s.delete(_load(s, instance_id))
        s.commit()
    return "", 204


@bp.post("/<int:instance_id>/test")
def test_instance(instance_id: int) -> ResponseReturnValue:
    with database().session() as s:
        instance = _load(s, instance_id)
        url, key = instance.url, secrets().decrypt(instance.api_key_enc)
    return connection_check(url, key)


@bp.post("/<int:instance_id>/rotate-token")
def rotate_token(instance_id: int) -> ResponseReturnValue:
    with database().session() as s:
        instance = _load(s, instance_id)
        instance.webhook_token = token_source.token_hex(WEBHOOK_TOKEN_BYTES)
        s.commit()
        return serialize(instance)


@bp.post("/<int:instance_id>/sync")
def sync_instance(instance_id: int) -> ResponseReturnValue:
    with database().session() as s:
        _load(s, instance_id)
        enqueue(s, instance_id)
        s.commit()
    nudge = current_app.extensions.get("finalarr.nudge")
    if nudge:
        nudge()
    return {"queued": True}, 202

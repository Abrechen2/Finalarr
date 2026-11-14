"""Media servers (Emby, Jellyfin, Plex): connect, pick users, see sync status."""

from __future__ import annotations

import json
from typing import Any, Literal

from flask import Blueprint, current_app
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finalarr.api.common import ApiProblem, database, not_found, parse_body, secrets
from finalarr.crypto import mask
from finalarr.db.models import MediaServer, MediaUser, WatchedEpisode
from finalarr.sources.media import MediaClient, MediaError, client_for
from finalarr.sources.sonarr import validate_base_url

bp = Blueprint("media_servers", __name__, url_prefix="/api/v1/media-servers")
Kind = Literal["emby", "jellyfin", "plex"]


class _Url(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("url", check_fields=False)
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return None if value is None else validate_base_url(value)


class ConnectionIn(_Url):
    kind: Kind
    url: str
    token: str = Field(min_length=1, max_length=500)


class ServerIn(ConnectionIn):
    name: str = Field(min_length=1, max_length=100)


class ServerTest(ConnectionIn):
    """The add-server form; testing it before saving sends the same body."""

    name: str | None = Field(default=None, max_length=100)


class ServerPatch(_Url):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = None
    token: str | None = Field(default=None, min_length=1, max_length=500)
    enabled: StrictBool | None = None


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected: StrictBool


def _client(kind: str, url: str, token: str) -> MediaClient:
    factory = current_app.extensions.get("finalarr.media_client", client_for)
    client: MediaClient = factory(kind, url, token)
    return client


def _check(client: MediaClient) -> str:
    try:
        return client.test()
    except MediaError as error:
        raise ApiProblem(502, "media_unreachable", str(error)) from None


def serialize(s: Session, server: MediaServer, version: str | None = None) -> dict[str, Any]:
    counts = dict(
        s.execute(
            select(WatchedEpisode.user_id, func.count())
            .join(MediaUser)
            .where(MediaUser.server_id == server.id)
            .group_by(WatchedEpisode.user_id)
        ).all()
    )
    return {
        "id": server.id,
        "kind": server.kind,
        "name": server.name,
        "url": server.url,
        "token": mask(secrets().decrypt(server.token_enc)),
        "enabled": server.enabled,
        "version": version,
        "last_sync_at": server.last_sync_at.isoformat() if server.last_sync_at else None,
        "last_error": server.last_error,
        "unmatched": json.loads(server.unmatched_json or "[]"),
        "users": [
            {
                "id": u.id,
                "name": u.name,
                "selected": u.selected,
                "watched_episodes": counts.get(u.id, 0),
            }
            for u in server.users
        ],
    }


def _load(s: Session, server_id: int) -> MediaServer:
    server = s.get(MediaServer, server_id)
    if server is None:
        raise not_found("Media server")
    return server


def _commit(s: Session) -> None:
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise ApiProblem(409, "conflict", "A media server with this name exists already") from None


def _nudge() -> None:
    nudge = current_app.extensions.get("finalarr.nudge_media")
    if nudge:
        nudge()


@bp.get("")
def list_servers() -> ResponseReturnValue:
    with database().session() as s:
        return [serialize(s, server) for server in s.scalars(select(MediaServer))]


@bp.post("/test")
def test_unsaved() -> ResponseReturnValue:
    body = parse_body(ServerTest)
    return {"version": _check(_client(body.kind, body.url, body.token))}


@bp.post("")
def create_server() -> ResponseReturnValue:
    body = parse_body(ServerIn)
    client = _client(body.kind, body.url, body.token)
    version = _check(client)
    try:
        users = client.users()
    except MediaError as error:
        raise ApiProblem(502, "media_unreachable", str(error)) from None
    with database().session() as s:
        server = MediaServer(
            kind=body.kind,
            name=body.name,
            url=body.url,
            token_enc=secrets().encrypt(body.token),
            users=[MediaUser(remote_id=u.remote_id, name=u.name, selected=False) for u in users],
        )
        s.add(server)
        _commit(s)
        return serialize(s, server, version), 201


@bp.patch("/<int:server_id>")
def patch_server(server_id: int) -> ResponseReturnValue:
    body = parse_body(ServerPatch)
    with database().session() as s:
        server = _load(s, server_id)
        if body.url is not None and body.url != server.url and body.token is None:
            # The stored token must never go to an address it was not given for.
            # "token" names the form field (Bandit B105 false positive).
            missing = {"token": "required when the URL changes"}  # nosec B105
            raise ApiProblem(400, "validation", "Invalid input", missing)
        if body.token is not None:
            _check(_client(server.kind, body.url or server.url, body.token))
        if body.name is not None:
            server.name = body.name
        if body.url is not None:
            server.url = body.url
        if body.token is not None:
            server.token_enc = secrets().encrypt(body.token)
        if body.enabled is not None:
            server.enabled = body.enabled
        _commit(s)
        return serialize(s, server)


@bp.delete("/<int:server_id>")
def delete_server(server_id: int) -> ResponseReturnValue:
    with database().session() as s:
        s.delete(_load(s, server_id))
        s.commit()
    return "", 204


@bp.patch("/<int:server_id>/users/<int:user_id>")
def patch_user(server_id: int, user_id: int) -> ResponseReturnValue:
    body = parse_body(UserPatch)
    with database().session() as s:
        user = s.get(MediaUser, user_id)
        if user is None or user.server_id != server_id:
            raise not_found("Media server user")
        user.selected = body.selected
        if not body.selected:
            # Nothing is kept about people who are not selected.
            s.execute(delete(WatchedEpisode).where(WatchedEpisode.user_id == user.id))
        s.commit()
        result = {"id": user.id, "name": user.name, "selected": user.selected}
    if body.selected:
        _nudge()
    return result


@bp.post("/<int:server_id>/sync")
def sync_server(server_id: int) -> ResponseReturnValue:
    with database().session() as s:
        _load(s, server_id)
    _nudge()
    return {"queued": True}, 202

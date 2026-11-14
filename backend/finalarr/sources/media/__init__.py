"""Media server clients (Emby, Jellyfin, Plex), normalised to users and watched episodes."""

from __future__ import annotations

from finalarr.sources.media.base import MediaClient, MediaError, MediaUserInfo, WatchedItem


def client_for(kind: str, url: str, token: str) -> MediaClient:
    from finalarr.sources.media.emby import EmbyClient, JellyfinClient
    from finalarr.sources.media.plex import PlexClient

    clients: dict[str, type[MediaClient]] = {
        "emby": EmbyClient,
        "jellyfin": JellyfinClient,
        "plex": PlexClient,
    }
    if kind not in clients:
        raise ValueError(f"unknown media server kind: {kind}")
    return clients[kind](url, token)


__all__ = ["MediaClient", "MediaError", "MediaUserInfo", "WatchedItem", "client_for"]

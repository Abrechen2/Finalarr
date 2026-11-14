"""Sending through Apprise, with errors captured and redacted."""

from __future__ import annotations

import logging
from typing import Protocol

import apprise

from finalarr.logging_setup import redact

TITLE = "Finalarr"


class SendError(RuntimeError):
    pass


class Sender(Protocol):
    def send(self, url: str, body: str) -> None: ...


class AppriseSender:
    def send(self, url: str, body: str) -> None:
        client = apprise.Apprise()
        if not client.add(url):
            raise SendError("Channel URL is not accepted by Apprise")
        with apprise.LogCapture(level=logging.WARNING) as captured:  # type: ignore[no-untyped-call]
            ok = client.notify(title=TITLE, body=body, body_format=apprise.NotifyFormat.HTML)
            detail = captured.getvalue().strip().splitlines()
        if not ok:
            raise SendError(redact(detail[-1] if detail else "Sending failed"))

"""Delivery queue: one row per (event, channel), retried with backoff (PLAN.md 4.3).

Deliveries are created in the same transaction as their events (outbox). A
send is at-least-once: a crash between the provider's OK and the commit can
repeat one message; that window is accepted and documented.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.crypto import SecretBox, SecretDecryptError
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.notify.messages import render
from finalarr.notify.sender import Sender, SendError

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF = (timedelta(minutes=1), timedelta(minutes=5))
BATCH = 50


def channel_accepts(channel: m.Channel, event_type: str) -> bool:
    wanted = json.loads(channel.event_filter_json or "[]")
    return channel.enabled and (not wanted or event_type in wanted)


def create_deliveries(session: Session, events: list[m.Event], now: datetime | None = None) -> None:
    due = now or datetime.now(UTC)
    channels = session.scalars(select(m.Channel).where(m.Channel.enabled.is_(True))).all()
    for event in events:
        for channel in channels:
            if channel_accepts(channel, event.type):
                session.add(
                    m.Delivery(event_id=event.id, channel_id=channel.id, next_attempt_at=due)
                )


def resend(
    session: Session, event_id: int, channel_id: int | None = None, now: datetime | None = None
) -> int:
    """Reset deliveries to pending; adds rows for enabled channels that had none."""
    event = session.get_one(m.Event, event_id)
    existing = {d.channel_id: d for d in event.deliveries}
    query = select(m.Channel).where(m.Channel.enabled.is_(True))
    if channel_id is not None:
        query = query.where(m.Channel.id == channel_id)
    count = 0
    for channel in session.scalars(query):
        delivery = existing.get(channel.id)
        if delivery is None:
            delivery = m.Delivery(event_id=event.id, channel_id=channel.id)
            session.add(delivery)
        delivery.status, delivery.attempts, delivery.last_error = "pending", 0, None
        delivery.next_attempt_at = now or datetime.now(UTC)
        count += 1
    return count


class DeliveryWorker:
    def __init__(
        self,
        db: Database,
        box: SecretBox,
        sender: Sender,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        public_url: str | None = None,
    ) -> None:
        self._db = db
        self._box = box
        self.sender = sender
        self._clock = clock
        self._public_url = public_url.rstrip("/") if public_url else None

    def run(self) -> None:
        now = self._clock()
        with self._db.session() as s:
            due = s.scalars(
                select(m.Delivery)
                .where(m.Delivery.status == "pending", m.Delivery.next_attempt_at <= now)
                .order_by(m.Delivery.id)
                .limit(BATCH)
            ).all()
            for delivery in due:
                self._attempt(delivery, now)
                s.commit()

    def _attempt(self, delivery: m.Delivery, now: datetime) -> None:
        event, channel = delivery.event, delivery.channel
        link = (
            f"{self._public_url}/series/{event.series_id}"
            if self._public_url and event.series_id
            else None
        )
        body = render(event.type, json.loads(event.payload_json), channel.language, link)
        delivery.attempts += 1
        try:
            self.sender.send(self._box.decrypt(channel.apprise_url_enc), body)
        except SecretDecryptError as error:
            delivery.status, delivery.last_error = "failed", str(error)
            return
        except SendError as error:
            delivery.last_error = str(error)[:500]
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.status = "failed"
                log.warning(
                    "Delivery %s to %s failed for good: %s", delivery.id, channel.name, error
                )
            else:
                delivery.next_attempt_at = now + BACKOFF[delivery.attempts - 1]
            return
        delivery.status, delivery.sent_at, delivery.last_error = "sent", now, None

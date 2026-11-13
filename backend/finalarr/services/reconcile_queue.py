"""Durable reconcile requests, coalesced per (instance, series). Series 0 = full sync."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from finalarr.db.models import ReconcileRequest, utcnow

FULL_SYNC = 0


def enqueue(session: Session, instance_id: int, sonarr_series_id: int = FULL_SYNC) -> None:
    statement = insert(ReconcileRequest).values(
        instance_id=instance_id, sonarr_series_id=sonarr_series_id, requested_at=utcnow()
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["instance_id", "sonarr_series_id"],
            set_={"requested_at": statement.excluded.requested_at},
        )
    )


def take_all(session: Session) -> list[tuple[int, int]]:
    """Remove and return every pending request as (instance_id, sonarr_series_id)."""
    rows = session.execute(
        select(ReconcileRequest.instance_id, ReconcileRequest.sonarr_series_id).order_by(
            ReconcileRequest.requested_at
        )
    ).all()
    session.execute(delete(ReconcileRequest))
    return [(r.instance_id, r.sonarr_series_id) for r in rows]

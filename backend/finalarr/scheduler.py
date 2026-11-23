"""Background jobs with a singleton guarantee.

The scheduler only runs in the process that holds an exclusive ``flock`` on
``/config/scheduler.lock``. A second process (e.g. an overlapping worker during
a restart) retries the lock instead of starting its own scheduler. Work itself
is durable (``reconcile_requests``), so a crash loses latency, not data.
"""

from __future__ import annotations

import fcntl
import functools
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Any, Protocol

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from finalarr.db.models import SonarrInstance
from finalarr.db.session import Database
from finalarr.memory import tracked
from finalarr.services.reconcile_queue import FULL_SYNC, enqueue, take_all
from finalarr.services.settings_store import load_settings

log = logging.getLogger(__name__)

DRAIN_SECONDS = 5
JOB_TIMEOUT_GRACE = 60
EXTRA_JOB_DELAY_SECONDS = 20


class _Reconciler(Protocol):
    def reconcile(self, instance_id: int, sonarr_series_id: int = FULL_SYNC) -> None: ...


class SchedulerService:
    def __init__(
        self,
        db: Database,
        reconciler: _Reconciler,
        lock_path: Path,
        retry_seconds: float = 10.0,
        extra_jobs: list[tuple[str, Callable[[], object], float]] | None = None,
    ) -> None:
        self._db = db
        self._reconciler = reconciler
        self._lock_path = lock_path
        self._retry_seconds = retry_seconds
        self._extra_jobs = extra_jobs or []
        self._lock_file: IO[str] | None = None
        self._scheduler: BackgroundScheduler | None = None
        self._retry: threading.Timer | None = None
        self._stopped = False
        # Extra jobs running now, and those asked to run again once they finish.
        self._jobs_lock = threading.Lock()
        self._busy: set[str] = set()
        self._again: set[str] = set()

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def start(self, retry: bool = True) -> bool:
        """Start if the lock is free; otherwise keep retrying in the background."""
        self._stopped = False
        if not self._acquire():
            log.info(
                "Scheduler lock is held elsewhere; %s", "retrying" if retry else "not starting"
            )
            if retry:
                self._schedule_retry()
            return False
        interval = self._interval_minutes()
        scheduler = BackgroundScheduler(
            timezone=UTC,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": JOB_TIMEOUT_GRACE,
            },
        )
        scheduler.add_job(
            tracked("drain", self.drain),
            "interval",
            seconds=DRAIN_SECONDS,
            id="drain",
            replace_existing=True,
        )
        scheduler.add_job(
            self.queue_full_syncs,
            "interval",
            minutes=interval,
            id="full_sync",
            replace_existing=True,
        )
        first_run = datetime.now(UTC) + timedelta(seconds=EXTRA_JOB_DELAY_SECONDS)
        for job_id, func, seconds in self._extra_jobs:
            scheduler.add_job(
                self._repeatable(job_id, tracked(job_id, func)),
                "interval",
                seconds=seconds,
                id=job_id,
                replace_existing=True,
                next_run_time=first_run,
            )
        scheduler.start()
        self._scheduler = scheduler
        self.queue_full_syncs()
        self.nudge()
        log.info("Scheduler started (full sync every %s min)", interval)
        return True

    def nudge(self) -> None:
        """Run the drain job now instead of waiting for its next tick."""
        if self.running and self._scheduler is not None:
            self._scheduler.modify_job("drain", next_run_time=datetime.now(UTC))

    def _repeatable(self, job_id: str, job: Callable[[], None]) -> Callable[[], None]:
        @functools.wraps(job)
        def run() -> None:
            with self._jobs_lock:
                self._busy.add(job_id)
            try:
                job()
            finally:
                with self._jobs_lock:
                    self._busy.discard(job_id)
                    again = job_id in self._again
                    self._again.discard(job_id)
                if again:
                    self.run_soon(job_id)

        return run

    def run_soon(self, job_id: str) -> None:
        """Run a job now instead of waiting for its interval (no-op when stopped). Asked
        while it runs, it runs once more afterwards: the running pass may have missed
        the change that asked."""
        if not self.running or self._scheduler is None:
            return
        with self._jobs_lock:
            if job_id in self._busy:
                self._again.add(job_id)
                return
        self._scheduler.modify_job(job_id, next_run_time=datetime.now(UTC))

    def shutdown(self) -> None:
        self._stopped = True
        if self._retry is not None:
            self._retry.cancel()
            self._retry = None
        if self._scheduler is not None:
            if self._scheduler.running:
                self._scheduler.shutdown(wait=True)
            self._scheduler = None
        self._release()

    def drain(self) -> None:
        with self._db.session() as s:
            requests = take_all(s)
            s.commit()
        full = {instance for instance, series in requests if series == FULL_SYNC}
        work = sorted({(i, sid) for i, sid in requests if sid == FULL_SYNC or i not in full})
        for instance_id, series_id in work:
            try:
                self._reconciler.reconcile(instance_id, series_id)
            except Exception:  # one broken series must not stop the rest
                log.exception("Reconcile %s/%s failed", instance_id, series_id)

    def queue_full_syncs(self) -> None:
        with self._db.session() as s:
            for instance_id in s.scalars(
                select(SonarrInstance.id).where(SonarrInstance.enabled.is_(True))
            ):
                enqueue(s, instance_id)
            s.commit()

    def _interval_minutes(self) -> int:
        with self._db.session() as s:
            return int(load_settings(s)["reconcile_interval_minutes"])

    def _acquire(self) -> bool:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._lock_path.open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._lock_file = handle
        return True

    def _release(self) -> None:
        if self._lock_file is not None:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    def _schedule_retry(self) -> None:
        def attempt() -> None:
            if not self._stopped and not self.running:
                self.start(retry=True)

        self._retry = threading.Timer(self._retry_seconds, attempt)
        self._retry.daemon = True
        self._retry.start()


def describe_jobs(service: SchedulerService | None) -> list[dict[str, Any]]:
    """Job list for the system status endpoint."""
    if service is None or not service.running or service._scheduler is None:
        return []
    return [
        {"id": job.id, "next_run": job.next_run_time.isoformat() if job.next_run_time else None}
        for job in service._scheduler.get_jobs()
    ]

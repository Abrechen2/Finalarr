import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from apscheduler.executors.base import BaseExecutor

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.scheduler import SchedulerService, describe_jobs, overdue
from finalarr.services.reconcile_queue import enqueue


class FakeReconciler:
    def __init__(self):
        self.calls = []
        self.done = threading.Event()

    def reconcile(self, instance_id, sonarr_series_id=0):
        self.calls.append((instance_id, sonarr_series_id))
        self.done.set()


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "f.db")
    db.migrate()
    with db.session() as s:
        s.add_all(
            [
                m.SonarrInstance(name="A", url="http://a:1", api_key_enc="x", webhook_token="a"),
                m.SonarrInstance(
                    name="B", url="http://b:1", api_key_enc="x", webhook_token="b", enabled=False
                ),
            ]
        )
        s.commit()
    reconciler = FakeReconciler()
    service = SchedulerService(db, reconciler, lock_path=tmp_path / "scheduler.lock")
    yield db, reconciler, service, tmp_path
    service.shutdown()
    db.dispose()


def test_drain_runs_each_request_once_and_full_sync_wins(env):
    db, reconciler, service, _ = env
    with db.session() as s:
        enqueue(s, 1, 5)
        enqueue(s, 1, 0)
        enqueue(s, 2, 7)
        s.commit()
    service.drain()
    assert sorted(reconciler.calls) == [(1, 0), (2, 7)]
    service.drain()
    assert len(reconciler.calls) == 2


def test_periodic_job_queues_full_syncs_for_enabled_instances(env):
    db, _, service, _ = env
    service.queue_full_syncs()
    from finalarr.services.reconcile_queue import take_all

    with db.session() as s:
        assert take_all(s) == [(1, 0)]


def test_a_failing_reconcile_does_not_stop_the_others(env):
    db, reconciler, service, _ = env

    def boom(instance_id, sonarr_series_id=0):
        reconciler.calls.append((instance_id, sonarr_series_id))
        if sonarr_series_id == 5:
            raise RuntimeError("bug")

    reconciler.reconcile = boom
    with db.session() as s:
        enqueue(s, 1, 5)
        enqueue(s, 1, 6)
        s.commit()
    service.drain()
    assert sorted(reconciler.calls) == [(1, 5), (1, 6)]


def test_only_one_scheduler_holds_the_lock(env):
    db, reconciler, service, tmp_path = env
    other = SchedulerService(db, reconciler, lock_path=tmp_path / "scheduler.lock")
    assert service.start(retry=False)
    assert not other.start(retry=False)
    assert not other.running
    service.shutdown()
    assert other.start(retry=False)
    other.shutdown()


def test_start_queues_an_initial_full_sync_and_nudge_drains_quickly(env):
    db, reconciler, service, _ = env
    assert service.start(retry=False)
    assert service.running
    assert reconciler.done.wait(10)
    assert (1, 0) in reconciler.calls
    reconciler.done.clear()
    with db.session() as s:
        enqueue(s, 1, 42)
        s.commit()
    service.nudge()
    assert reconciler.done.wait(5)
    assert (1, 42) in reconciler.calls


def test_nudge_and_shutdown_are_safe_when_not_running(env):
    _, _, service, _ = env
    service.nudge()
    service.shutdown()


def test_retry_takes_over_once_the_lock_frees(env):
    db, reconciler, service, tmp_path = env
    other = SchedulerService(
        db, reconciler, lock_path=tmp_path / "scheduler.lock", retry_seconds=0.05
    )
    assert service.start(retry=False)
    assert not other.start(retry=True)
    service.shutdown()
    for _ in range(100):
        if other.running:
            break
        threading.Event().wait(0.05)
    assert other.running
    other.shutdown()


def test_run_soon_triggers_an_extra_job(env):
    db, reconciler, _, tmp_path = env
    ran = threading.Event()
    service = SchedulerService(
        db, reconciler, lock_path=tmp_path / "other.lock", extra_jobs=[("anilist", ran.set, 3600)]
    )
    service.run_soon("anilist")  # not running: no-op
    assert service.start(retry=False)
    service.run_soon("anilist")
    assert ran.wait(5)
    service.shutdown()


def test_jobs_run_with_memory_tracking(env, tmp_path):
    db, reconciler, _service, _ = env
    service = SchedulerService(
        db,
        reconciler,
        lock_path=tmp_path / "other.lock",
        extra_jobs=[("news", lambda: None, 3600)],
    )
    try:
        assert service.start(retry=False)
        jobs = {job.id: job.func for job in service._scheduler.get_jobs()}
        assert hasattr(jobs["news"], "__wrapped__")
        assert hasattr(jobs["drain"], "__wrapped__")
    finally:
        service.shutdown()


def test_run_soon_during_a_run_runs_again_afterwards(env, monkeypatch):
    # Selecting a second media-server user while the sync for the first one runs must
    # not wait for the next interval (30 minutes).
    db, reconciler, _, tmp_path = env
    # APScheduler frees the job's only slot after the function returned; a rerun asked
    # for before that is skipped. Widen that gap so the test does not depend on timing.
    release_slot = BaseExecutor._run_job_success

    def slow_release(self, job_id, events):
        time.sleep(0.3)
        release_slot(self, job_id, events)

    monkeypatch.setattr(BaseExecutor, "_run_job_success", slow_release)
    started, release, runs = threading.Event(), threading.Event(), []

    def job():
        runs.append(1)
        started.set()
        release.wait(5)

    service = SchedulerService(
        db, reconciler, lock_path=tmp_path / "again.lock", extra_jobs=[("media", job, 3600)]
    )
    assert service.start(retry=False)
    service.run_soon("media")
    assert started.wait(5)
    service.run_soon("media")  # while it runs
    release.set()
    for _ in range(50):
        if len(runs) >= 2:
            break
        time.sleep(0.1)
    service.shutdown()
    assert len(runs) == 2


def test_jobs_report_their_last_run_and_error(env):
    db, reconciler, _, tmp_path = env
    done = threading.Event()

    def broken():
        done.set()
        raise RuntimeError("AniList is down")

    service = SchedulerService(
        db, reconciler, lock_path=tmp_path / "jobs.lock", extra_jobs=[("anilist", broken, 3600)]
    )
    assert service.start(retry=False)
    service.run_soon("anilist")
    assert done.wait(5)
    for _ in range(50):
        jobs = {job["id"]: job for job in describe_jobs(service)}
        if jobs["anilist"]["last_run"]:
            break
        time.sleep(0.1)
    service.shutdown()
    assert jobs["anilist"]["error"] == "RuntimeError: AniList is down"
    assert jobs["anilist"]["overdue"] is False
    assert jobs["drain"]["error"] is None


def test_a_job_without_a_good_run_for_two_intervals_is_overdue():
    now = datetime(2026, 11, 23, 12, tzinfo=UTC)
    started = now - timedelta(hours=5)
    assert overdue(None, started, timedelta(hours=1), now) is True
    assert overdue(now - timedelta(minutes=30), started, timedelta(hours=1), now) is False
    assert overdue(now - timedelta(hours=3), started, timedelta(hours=1), now) is True
    # Freshly started: no run yet is fine.
    assert overdue(None, now - timedelta(minutes=10), timedelta(hours=1), now) is False

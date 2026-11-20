import threading

import pytest

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.scheduler import SchedulerService
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

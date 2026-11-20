import logging

import pytest

from finalarr import memory


def test_rss_reads_the_process_size():
    value = memory.rss_mb()
    assert value is None or value > 0


def test_tracked_job_trims_and_logs_big_growth(monkeypatch, caplog):
    sizes = iter([100, 140])
    trims = []
    monkeypatch.setattr(memory, "rss_mb", lambda: next(sizes))
    monkeypatch.setattr(memory, "trim", lambda: trims.append(1))
    ran = []
    job = memory.tracked("news", lambda: ran.append(1))
    with caplog.at_level(logging.INFO, logger="finalarr.memory"):
        job()
    assert ran == [1] and trims == [1]
    assert "news raised memory by 40 MB (100 -> 140 MB)" in caplog.text


def test_small_growth_stays_quiet_and_errors_still_trim(monkeypatch, caplog):
    sizes = iter([100, 105])
    trims = []
    monkeypatch.setattr(memory, "rss_mb", lambda: next(sizes))
    monkeypatch.setattr(memory, "trim", lambda: trims.append(1))

    def broken():
        raise RuntimeError("boom")

    with caplog.at_level(logging.INFO, logger="finalarr.memory"), pytest.raises(RuntimeError):
        memory.tracked("anilist", broken)()
    assert trims == [1]
    assert "raised memory" not in caplog.text


def test_trim_is_safe_everywhere():
    memory.trim()  # glibc returns memory; elsewhere it is a no-op

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from finalarr.notify.quiet import QuietHours, quiet_until

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.mark.parametrize(
    ("now_local", "expected_local"),
    [
        ((23, 30), (7, 0)),  # inside, before midnight → next morning
        ((3, 0), (7, 0)),  # inside, after midnight → same morning
        ((7, 0), None),  # end is exclusive
        ((12, 0), None),
        ((22, 0), (7, 0)),  # start is inclusive
    ],
)
def test_overnight_window(now_local, expected_local):
    day = 13 if now_local[0] >= 12 else 14
    now = datetime(2026, 11, day, *now_local, tzinfo=BERLIN).astimezone(UTC)
    until = quiet_until(QuietHours("22:00", "07:00"), now, BERLIN)
    if expected_local is None:
        assert until is None
    else:
        assert until.astimezone(BERLIN).hour == expected_local[0]
        assert until > now
        assert until.tzinfo is not None


def test_same_day_window():
    now = datetime(2026, 11, 13, 13, 0, tzinfo=BERLIN).astimezone(UTC)
    until = quiet_until(QuietHours("12:00", "14:00"), now, BERLIN)
    assert until.astimezone(BERLIN).replace(tzinfo=None) == datetime(2026, 11, 13, 14, 0)


def test_equal_start_and_end_means_off():
    now = datetime(2026, 11, 13, 13, 0, tzinfo=UTC)
    assert quiet_until(QuietHours("08:00", "08:00"), now, BERLIN) is None


@pytest.mark.parametrize("value", ["24:00", "7:00", "aa:bb", ""])
def test_invalid_times(value):
    with pytest.raises(ValueError):
        QuietHours(value, "07:00")

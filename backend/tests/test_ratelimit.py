from finalarr.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    clock = Clock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)
    assert limiter.hit("a")
    assert limiter.hit("a")
    assert not limiter.hit("a")


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window_seconds=60, clock=Clock())
    assert limiter.hit("a")
    assert limiter.hit("b")


def test_window_slides():
    clock = Clock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.hit("a")
    clock.now += 61
    assert limiter.hit("a")

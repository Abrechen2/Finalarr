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


def test_forgive_returns_the_latest_slot():
    limiter = RateLimiter(limit=1, window_seconds=60, clock=Clock())
    assert limiter.hit("a")
    limiter.forgive("a")
    assert limiter.hit("a")
    limiter.forgive("unknown-key")


def test_concurrent_hits_never_exceed_the_limit():
    import threading

    limiter = RateLimiter(limit=5, window_seconds=60)
    results = []
    barrier = threading.Barrier(20)

    def attempt():
        barrier.wait()
        results.append(limiter.hit("a"))

    threads = [threading.Thread(target=attempt) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 5

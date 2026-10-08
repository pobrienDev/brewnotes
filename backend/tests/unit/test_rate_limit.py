from app.security.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_allows_limit_then_blocks_then_recovers() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=3, window_s=60, clock=clock)
    assert [limiter.hit("ip")[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = limiter.hit("ip")
    assert allowed is False
    assert retry_after == 60
    clock.now += 30
    allowed, retry_after = limiter.hit("ip")
    assert allowed is False
    assert retry_after == 30
    clock.now += 31
    assert limiter.hit("ip") == (True, 0)


def test_keys_are_independent() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_s=60, clock=FakeClock())
    assert limiter.hit("a") == (True, 0)
    assert limiter.hit("b") == (True, 0)
    assert limiter.hit("a")[0] is False


def test_stale_keys_are_purged() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=5, window_s=60, clock=clock)
    for i in range(10_001):
        limiter.hit(f"ip-{i}")
    clock.now += 61
    limiter.hit("fresh")
    assert len(limiter._hits) < 100

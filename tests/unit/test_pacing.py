from hangar.pacing import RateLimiter


class FakeTime:
    """A clock that moves only when the code under test sleeps, or a test says so."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def limiter(time: FakeTime, interval: float = 1.0) -> RateLimiter:
    return RateLimiter(interval, sleep=time.sleep, clock=time.clock)


def test_the_first_turn_never_waits() -> None:
    time = FakeTime()

    limiter(time).wait_for_turn()

    assert time.sleeps == []


def test_a_turn_taken_at_once_waits_the_whole_interval() -> None:
    time = FakeTime()
    pacer = limiter(time, interval=1.0)

    pacer.wait_for_turn()
    pacer.wait_for_turn()

    assert time.sleeps == [1.0]


def test_a_turn_waits_only_for_what_is_left_of_the_interval() -> None:
    time = FakeTime()
    pacer = limiter(time, interval=1.0)

    pacer.wait_for_turn()
    time.now += 0.75
    pacer.wait_for_turn()

    assert time.sleeps == [0.25]


def test_a_turn_after_the_interval_does_not_wait() -> None:
    time = FakeTime()
    pacer = limiter(time, interval=1.0)

    pacer.wait_for_turn()
    time.now += 3.0
    pacer.wait_for_turn()

    assert time.sleeps == []


def test_each_turn_counts_from_the_end_of_the_previous_wait() -> None:
    time = FakeTime()
    pacer = limiter(time, interval=1.0)

    pacer.wait_for_turn()
    pacer.wait_for_turn()
    pacer.wait_for_turn()

    assert time.sleeps == [1.0, 1.0]

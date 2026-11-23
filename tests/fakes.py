"""Fakes that more than one test module uses."""


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

"""
Spacing out and retrying requests to a remote service.

The fetch stage and the Mistral client both send requests to services that
limit how often they may be called, and both retry the same answers with
the same growing wait. They share this module, which sits above ``core``
and below the stages, so neither keeps its own copy.
"""

import time
from collections.abc import Callable

# Statuses that mean "try again later" rather than "this will never work".
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def backoff_delay(first_delay_seconds: float, retry: int) -> float:
    """
    Give the wait before a retry, doubling with each one.

    Args:
        first_delay_seconds: The wait before the first retry.
        retry: Which retry is next: 1 for the first, 2 for the second.

    Returns:
        The wait in seconds.
    """
    return first_delay_seconds * 2.0 ** (retry - 1)


class RateLimiter:
    """
    Leaves at least a set time between two turns.

    The first turn never waits. Each later turn waits until the interval has
    passed since the previous turn began.
    """

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Create the limiter.

        Args:
            min_interval_seconds: The shortest time between two turns.
            sleep: Waits a number of seconds. Tests replace it.
            clock: Gives the current time in seconds. Tests replace it.
        """
        self._min_interval = min_interval_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_turn: float | None = None

    def wait_for_turn(self) -> None:
        """
        Wait until the next request may be sent, then mark the turn as taken.
        """
        if self._last_turn is not None:
            wait = self._last_turn + self._min_interval - self._clock()

            if wait > 0:
                self._sleep(wait)

        self._last_turn = self._clock()

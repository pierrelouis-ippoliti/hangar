from collections.abc import Iterator

import pytest

from hangar.observability.logs import close_logging


@pytest.fixture(autouse=True)
def no_logging_left_behind() -> Iterator[None]:
    """Remove the log handlers a test installed, so the next test starts clean."""
    yield
    close_logging()

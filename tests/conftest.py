import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hangar.observability.logs import close_logging


@pytest.fixture(autouse=True)
def no_logging_left_behind() -> Iterator[None]:
    """Remove the log handlers a test installed, so the next test starts clean."""
    yield
    close_logging()


@dataclass
class FakeQdrant:
    """A fake Qdrant on 127.0.0.1. Set status to change what /readyz answers."""

    url: str
    status: int = 200


@pytest.fixture
def fake_qdrant() -> Iterator[FakeQdrant]:
    fake = FakeQdrant(url="")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(fake.status if self.path == "/readyz" else 404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()

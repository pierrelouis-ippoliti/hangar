import ipaddress
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from hangar.observability.logs import close_logging
from tests.fixture_corpus import FixtureCorpus, write_fixture_corpus


@pytest.fixture(autouse=True)
def no_logging_left_behind() -> Iterator[None]:
    """Remove the log handlers a test installed, so the next test starts clean."""
    yield
    close_logging()


# Tests with these markers use the network on purpose and run only locally.
NETWORK_MARKERS = ("model", "llm", "corpus")


def is_loopback(address: object) -> bool:
    """
    Whether a socket address stays on this machine.

    A Unix socket address is a path, so it is local. An IP address is local
    when it is a loopback address. Any other host name would need a lookup,
    so it counts as leaving the machine.
    """
    if not isinstance(address, tuple):
        return True

    host = address[0]

    if host == "localhost":
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Refuse every connection that leaves the machine, so CI never needs the network.

    Loopback stays open for the fake servers. Tests marked model, llm or
    corpus are left alone.
    """
    if any(request.node.get_closest_marker(name) for name in NETWORK_MARKERS):
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refuse_outside(address: object) -> None:
        if not is_loopback(address):
            raise RuntimeError(
                f"a test tried to connect to {address}, but tests may not use the "
                "network; mark it model, llm or corpus if it must"
            )

    def guarded_connect(sock: socket.socket, address: Any) -> None:
        refuse_outside(address)
        real_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: Any) -> int:
        refuse_outside(address)

        return real_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


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
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()


@pytest.fixture
def fixture_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FixtureCorpus:
    """
    The fixture corpus in the test's temporary folder, with real hashes.

    ``HANGAR_DATA_DIR`` points at the ``data`` subfolder.
    """
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))

    return write_fixture_corpus(tmp_path)

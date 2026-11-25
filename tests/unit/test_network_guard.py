import socket
import urllib.request
from typing import Any

import pytest

# 192.0.2.1 is reserved for documentation (RFC 5737), so nothing answers there.
OUTSIDE = ("192.0.2.1", 80)


def test_a_connection_that_leaves_the_machine_is_refused() -> None:
    with socket.socket() as sock:
        sock.settimeout(0.5)

        with pytest.raises(RuntimeError, match=r"192\.0\.2\.1.*network"):
            sock.connect(OUTSIDE)


def test_connect_ex_is_refused_too() -> None:
    with socket.socket() as sock:
        sock.settimeout(0.5)

        with pytest.raises(RuntimeError, match=r"192\.0\.2\.1.*network"):
            sock.connect_ex(OUTSIDE)


def test_loopback_connections_still_work(fake_qdrant: Any) -> None:
    with urllib.request.urlopen(fake_qdrant.url + "readyz", timeout=2) as response:
        assert response.status == 200

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hangar.core.prompts import Message
from hangar.generation.llm import LlmError
from hangar.generation.mistral import MistralClient
from tests.fakes import FakeTime

FAKE_KEY = "fake-mistral-key-0123456789"
MODEL = "mistral-small-2603"

MESSAGES = (
    Message(role="system", content="Answer from the sources only."),
    Message(role="user", content="How often is the ELT battery replaced?"),
)


def reply(
    text: str = "Replace it at half its useful life [1].",
    *,
    finish_reason: str = "stop",
    prompt_tokens: int = 812,
    completion_tokens: int = 14,
) -> dict[str, object]:
    """A chat completion as the Mistral API sends it."""
    return {
        "id": "cmpl-0123",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@dataclass
class FakeMistral:
    """A Mistral API on 127.0.0.1 that answers from a list of set replies."""

    time: FakeTime
    url: str = ""
    # (status, body) pairs, answered in order. A successful reply is
    # answered once the list is empty.
    answers: list[tuple[int, object]] = field(default_factory=list)
    # How long the server takes to answer, in fake seconds.
    latency: float = 0.0
    requests: list[tuple[str, dict[str, str], dict[str, object]]] = field(
        default_factory=list
    )


@pytest.fixture
def mistral() -> Iterator[FakeMistral]:
    fake = FakeMistral(time=FakeTime())

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            fake.requests.append((self.path, dict(self.headers), body))

            fake.time.now += fake.latency
            status, answer = fake.answers.pop(0) if fake.answers else (200, reply())
            data = json.dumps(answer).encode()

            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()

    yield fake

    server.shutdown()
    server.server_close()


def client(fake: FakeMistral, attempts: int = 3) -> MistralClient:
    return MistralClient(
        MODEL,
        FAKE_KEY,
        base_url=fake.url,
        min_interval_seconds=1.0,
        attempts=attempts,
        backoff_seconds=2.0,
        sleep=fake.time.sleep,
        clock=fake.time.clock,
    )


def test_complete_sends_the_messages_and_parameters_with_the_key(
    mistral: FakeMistral,
) -> None:
    client(mistral).complete(MESSAGES, temperature=0.0, max_output_tokens=512)

    path, headers, body = mistral.requests[0]
    assert path == "/v1/chat/completions"
    assert headers["Authorization"] == f"Bearer {FAKE_KEY}"
    assert body == {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Answer from the sources only."},
            {"role": "user", "content": "How often is the ELT battery replaced?"},
        ],
        "temperature": 0.0,
        "max_tokens": 512,
    }


def test_complete_returns_the_text_tokens_latency_and_finish_reason(
    mistral: FakeMistral,
) -> None:
    mistral.latency = 1.5
    mistral.answers = [(200, reply("Cut off", finish_reason="length"))]

    completion = client(mistral).complete(
        MESSAGES, temperature=0.0, max_output_tokens=512
    )

    assert completion.text == "Cut off"
    assert completion.model_id == MODEL
    assert (completion.input_tokens, completion.output_tokens) == (812, 14)
    assert completion.latency_seconds == 1.5
    assert completion.finish_reason == "length"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_complete_retries_busy_or_failing_answers_with_a_growing_wait(
    mistral: FakeMistral, status: int
) -> None:
    mistral.answers = [(status, {"message": "busy"}), (status, {"message": "busy"})]

    completion = client(mistral, attempts=3).complete(
        MESSAGES, temperature=0.0, max_output_tokens=512
    )

    assert completion.text == "Replace it at half its useful life [1]."
    assert len(mistral.requests) == 3
    assert mistral.time.sleeps == [2.0, 4.0]


@pytest.mark.parametrize("status", [400, 401, 422, 501])
def test_complete_fails_at_once_on_a_refused_request(
    mistral: FakeMistral, status: int
) -> None:
    mistral.answers = [(status, {"message": "Unauthorized"})]

    with pytest.raises(LlmError, match=rf"{status}.*Unauthorized"):
        client(mistral).complete(MESSAGES, temperature=0.0, max_output_tokens=512)

    assert len(mistral.requests) == 1


def test_complete_gives_up_after_the_last_attempt(mistral: FakeMistral) -> None:
    mistral.answers = [(429, {"message": "busy"})] * 3

    with pytest.raises(LlmError, match="429.*after 3 attempts"):
        client(mistral, attempts=3).complete(
            MESSAGES, temperature=0.0, max_output_tokens=512
        )

    assert len(mistral.requests) == 3


def test_two_completions_are_at_least_the_interval_apart(
    mistral: FakeMistral,
) -> None:
    llm = client(mistral)

    llm.complete(MESSAGES, temperature=0.0, max_output_tokens=512)
    llm.complete(MESSAGES, temperature=0.0, max_output_tokens=512)

    assert mistral.time.sleeps == [1.0]


def test_complete_fails_on_a_reply_it_cannot_read(mistral: FakeMistral) -> None:
    mistral.answers = [(200, {"choices": []})]

    with pytest.raises(LlmError, match="can't read"):
        client(mistral).complete(MESSAGES, temperature=0.0, max_output_tokens=512)


def test_complete_retries_network_errors_then_gives_up() -> None:
    # Bind a port, then close it, so nothing listens there.
    server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    closed_url = f"http://127.0.0.1:{server.server_port}"
    server.server_close()
    fake = FakeMistral(time=FakeTime(), url=closed_url)

    with pytest.raises(LlmError, match="after 3 attempts"):
        client(fake, attempts=3).complete(
            MESSAGES, temperature=0.0, max_output_tokens=512
        )

    assert fake.time.sleeps == [2.0, 4.0]

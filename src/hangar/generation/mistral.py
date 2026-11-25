"""
The Mistral adapter: chat completions over HTTP, spaced out and retried.

It calls the chat completions endpoint with the standard library, so Hangar
needs no Mistral SDK, and owns its rate limit and retries alone
(ADR-0007). Only ``pipelines`` constructs it.
"""

import http.client
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence

from pydantic import BaseModel, Field, ValidationError

from hangar.core.completions import Completion
from hangar.core.prompts import Message
from hangar.generation.llm import LlmError
from hangar.pacing import RETRYABLE_STATUSES, RateLimiter, backoff_delay

MISTRAL_BASE_URL = "https://api.mistral.ai"
CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

# The longest piece of an error body quoted in an error message.
MAX_DETAIL_CHARACTERS = 300


class MistralClient:
    """
    Gets completions from the Mistral API.

    Requests are at least ``min_interval_seconds`` apart, retries included:
    the free tier allows one request per second. Busy or failing answers
    (429, 500, 502, 503 and 504) and network errors are retried, waiting
    ``backoff_seconds``, then twice that, and so on. Other statuses, such as
    401 for a wrong key, fail at once.

    Attributes:
        model_id: The dated model ID the client asks for.
    """

    def __init__(
        self,
        model_id: str,
        api_key: str,
        *,
        base_url: str = MISTRAL_BASE_URL,
        min_interval_seconds: float = 1.0,
        attempts: int = 4,
        backoff_seconds: float = 2.0,
        timeout_seconds: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Create the client.

        Args:
            model_id: The dated model ID, such as ``mistral-small-2603``.
            api_key: The Mistral API key, from the environment settings.
            base_url: The API's address. Tests point it at a local server.
            min_interval_seconds: The shortest time between two requests.
            attempts: How many times a request is tried before giving up.
            backoff_seconds: The wait before the first retry. It doubles
                with each retry.
            timeout_seconds: How long to wait for the API to answer.
            sleep: Waits a number of seconds. Tests replace it.
            clock: Gives the current time in seconds. Tests replace it.
        """
        self.model_id = model_id
        self._api_key = api_key
        self._url = base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
        self._limiter = RateLimiter(min_interval_seconds, sleep=sleep, clock=clock)
        self._attempts = attempts
        self._backoff = backoff_seconds
        self._timeout = timeout_seconds
        self._sleep = sleep
        self._clock = clock

    def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_output_tokens: int,
    ) -> Completion:
        """
        Ask the model to answer the messages.

        Args:
            messages: The messages to send, in order.
            temperature: The sampling temperature.
            max_output_tokens: The most tokens the answer may use.

        Returns:
            The model's completion. Its latency is that of the request that
            succeeded.

        Raises:
            LlmError: If the API refuses the request, every attempt fails,
                or the reply can't be read.
        """
        body = {
            "model": self.model_id,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        reason = ""

        for attempt in range(1, self._attempts + 1):
            if attempt > 1:
                self._sleep(backoff_delay(self._backoff, attempt - 1))

            self._limiter.wait_for_turn()
            started = self._clock()

            try:
                data = self._post(body)
            except urllib.error.HTTPError as error:
                if error.code not in RETRYABLE_STATUSES:
                    raise LlmError(
                        f"Mistral answered {error.code}: {_detail(error)}"
                    ) from error

                reason = f"it answered {error.code}"
            except (OSError, http.client.HTTPException) as error:
                reason = str(getattr(error, "reason", error))
            else:
                return _read_completion(data, latency=self._clock() - started)

        raise LlmError(
            f"can't get a completion from Mistral: {reason}, "
            f"after {self._attempts} attempts"
        )

    def _post(self, body: dict[str, object]) -> bytes:
        request = urllib.request.Request(
            self._url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            data: bytes = response.read()

            return data


class _ReplyMessage(BaseModel):
    content: str


class _Choice(BaseModel):
    message: _ReplyMessage
    finish_reason: str


class _Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class _Reply(BaseModel):
    """The parts of a chat completion that Hangar keeps; the rest is ignored."""

    model: str
    choices: list[_Choice] = Field(min_length=1)
    usage: _Usage


def _detail(error: urllib.error.HTTPError) -> str:
    # Mistral explains a refusal in the body, usually as {"message": ...}.
    text = error.read().decode("utf-8", errors="replace")

    try:
        message = json.loads(text).get("message")
    except (ValueError, AttributeError):
        message = None

    detail = str(message) if message else text

    return detail[:MAX_DETAIL_CHARACTERS]


def _read_completion(data: bytes, latency: float) -> Completion:
    try:
        reply = _Reply.model_validate_json(data)
    except ValidationError as error:
        raise LlmError(f"can't read Mistral's reply: {error}") from error

    choice = reply.choices[0]

    return Completion(
        text=choice.message.content,
        model_id=reply.model,
        input_tokens=reply.usage.prompt_tokens,
        output_tokens=reply.usage.completion_tokens,
        latency_seconds=latency,
        finish_reason=choice.finish_reason,
    )

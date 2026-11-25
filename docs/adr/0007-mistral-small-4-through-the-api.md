# ADR-0007: Mistral Small 4 through the API, pinned and rate-limited

- **Status:** accepted
- **Date:** 2026-11-23
- **Issue:** #25

## Context

The answering path needs a language model to write a cited answer from five retrieved chunks. Hangar is measured version by version, so the model must stay the same between runs, and v0 runs on a laptop with no budget for model calls.

The constraints that shaped the choice:

- **Cost.** Mistral's free tier allows one request per second per workspace, which is enough for one question at a time and for a seed run of a few dozen questions.
- **Reproducibility.** An alias such as `mistral-small-latest` moves to a new model without notice. A dated model ID does not.
- **A like-for-like comparison later.** v9 moves models to self-hosted servers. If the v0 model's weights are open, v9 can serve the same model and measure what self-hosting changes, with the model held fixed.
- **The laptop.** Its GPU (an NVIDIA T600) already holds BGE-M3 for embedding and search.

## Decision

v0 answers with Mistral Small 4, version 26.03, called through Mistral's chat completions API. Its weights are open under Apache 2.0.

- **Pinned.** The pipeline file names the dated ID `mistral-small-2603`, and the configuration rejects undated IDs. Every completion records the model ID the API reports.
- **Deterministic settings.** Temperature 0, and at most 512 output tokens per answer.
- **Rate-limited on the client.** `MistralClient` leaves at least one second between requests, retries included, through the same `pacing.RateLimiter` as the downloader. The free tier would refuse faster requests anyway; spacing them on the client avoids the refusals.
- **Retried.** A 429, 500, 502, 503 or 504 answer, or a network error, is retried up to four attempts in all, waiting 2, 4, then 8 seconds. The downloader retries the same statuses, from the same list in `pacing`. Any other status, such as 401 for a wrong key or 400 for a bad request, fails at once with Mistral's explanation.
- **Plain HTTP.** The client sends one POST with the standard library, like the downloader, instead of using the `mistralai` SDK. Hangar needs one endpoint and no streaming, and owning the HTTP call means the rate limit and the retries live in one place.
- **The key comes from the environment only.** `MISTRAL_API_KEY` is read from the environment or `.env`, never from the pipeline file, and the logs redact it.

## Alternatives

- **A larger Mistral model.**
  - It would likely write better answers.
  - But each question would use more of the free tier's token budget and take longer, and v9 would need far more GPU memory to self-host it for the comparison. v0 is the baseline: a better generator is a later, measured change.
- **A local model on the laptop.**
  - No network, no key and no rate limit.
  - But Mistral Small 4 doesn't fit on the T600, so a local model would have to be a much smaller one that shares the GPU with BGE-M3. Answers would be slow and weaker, and the model would differ from the one v9 self-hosts.
- **The `mistralai` SDK instead of plain HTTP.**
  - Typed requests and replies, and streaming for free.
  - But it adds a dependency with its own retry logic, which would have to be switched off so it doesn't stack with Hangar's. The chat completions call is one JSON POST, and a unit test against a local server covers the reply Hangar reads.

## Consequences

- Runs are reproducible as far as the API allows: same model ID, temperature 0, same prompt file. A provider-side change to a dated model would still show up in the results, not in the configuration.
- A seed run takes at least one second per question, plus the model's own time. A failing request can add up to 14 seconds of waits before the run stops.
- A request that timed out after the model began to answer is sent again, so its tokens may be counted twice. On the free tier that costs nothing.
- The live test (`uv run pytest -m llm tests/llm`) makes one real call with the v0 prompt. If Mistral changes the shape of its reply, that test fails before a seed run does.
- v9 adds a second `LlmClient` for the self-hosted copy of the same model. Answers and records don't change, since the rest of Hangar sees only the interface.

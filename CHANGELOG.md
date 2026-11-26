# Changelog

Each Hangar version has one section, with one subsection per tag. A milestone ends with a pre-release tag (`v0.0.0a0` for M0), and a version ends with its release (`v0.0.0` for v0).

## v0 · Baseline (in progress)

### 0.0.0a4 · M4 Answering (2026-11-26)

The answering path: `hangar ask` retrieves the top 5 chunks, renders the v0 prompt, asks Mistral Small 4 and prints an answer whose numbered citations name a document and its pages or sections, ending with the study-aid notice. `--record` writes the answer and run records with their cost.

Added:

- The v0 prompt `prompts/answer-v0.md`, which asks for a numbered citation after every claim and labels each source with its authority, type and content date, and the prompt renderer, which returns the messages and the numbered source map. A test pins each prompt file's hash, so prompts are never edited in place (#24).
- The language model client interface, the Mistral client for `mistral-small-2603` with a limit of one request per second and retries on 429 and 5xx answers, the fake client for tests, a live test marked `llm`, and ADR-0007 on Mistral Small 4 through the API. The downloader's request spacing, retryable statuses and backoff moved to `hangar.pacing`, which both now share (#25).
- The citation parser, which turns each marker such as `[2]` in an answer into a citation with its chunk, document and pages or sections, and flags a marker outside the source map as invalid (#26).
- Firmer tests and checks: shared test builders in `tests/builders.py`, a guard that refuses network connections in tests not marked `model`, `llm` or `corpus`, a ban on `while True` in `make check` and pre-commit, ruff's `DTZ` rules, and an import-linter contract that keeps I/O modules out of `hangar.core` (#81).
- Answer and run records, the run recorder that writes them to `results/` as JSON lines and `run.json`, and cost tracking from the configuration's price table, with the free-tier cost and the list-price cost of every answer. A release run refuses a checkout with changes. Run IDs are now the start time plus a short configuration hash, shared by the log file and the run record, and every command that succeeds logs its duration (#27).
- The answer pipeline and `hangar ask`, which answers a question from the top 5 chunks and prints each cited source with its document, pages or sections, authority and type, content date and attribution from `NOTICE.md`, flags invalid citation markers, and ends every answer with the study-aid notice. `--record` writes the answer record and the run record under the command's run ID (#28).
- A tighter agent setup: `make fix` formats the code and applies ruff's safe fixes, a shared `.claude/settings.json` refuses `git commit` and `git push` with `--no-verify`, the pull request template drops its CI checkbox, and CLAUDE.md matches the code again (#86).
- An end-to-end test that runs fetch, parse, chunk, embed, index and ask on the fixture corpus with no network, model or secret, and checks that each citation names the pages or sections of its chunk. The stage tests now share one fixture corpus, whose manifest gets real hashes when the tests run (#29).

### 0.0.0a3 · M3 Chunk, embed, index (2026-11-18)

The last three build stages: `hangar chunk`, `hangar embed` and `hangar index` turn the parsed C1 text into 3,627 chunks of up to 512 BGE-M3 tokens, embed them with BGE-M3 and load them into Qdrant. `hangar search` returns the top 5 chunks for a question.

Added:

- The fixed-token chunker with BGE-M3's tokenizer, `hangar chunk` and its DVC stage, and ADR-0006 on counting tokens with the embedder's tokenizer (#20).
- The BGE-M3 dense embedder through sentence-transformers, the hash embedder for tests, `hangar embed` with its Parquet vectors file and its DVC stage, and how to run it on a notebook GPU (#21).
- The Qdrant vector index, collection naming, `hangar index` with the committed index manifest `results/v0/index-manifest.json` and its DVC stage, and ADR-0008 on rebuilding the collection on every run (#22).
- The retriever interface, the dense retriever, the fixed retriever for tests, and `hangar search`, which prints the top 5 chunks for a question with their scores, documents, pages or sections (#23).

### 0.0.0a2 · M2 Parsing (2026-11-14)

The second build stage: `hangar parse` turns the 18 documents of C1 into one canonical text each, split into passages by page or section, and checks the results against thresholds.

Added:

- The parsed document and passage models, text normalisation, the mapping from character ranges to pages or sections, and ADR-0005 on locations and identifiers (#15).
- The PDF parser: one passage per page with its printed label, warnings for empty and garbled pages, the rule that only `parsing` and `pipelines` import pypdfium2, and ADR-0004 on pypdfium2 (#16).
- The CAR parser: one passage per section of Subparts 571 and 573, with its heading path, read from the Justice Canada XML with lxml (#17).
- The Transport Canada HTML parser: a front-matter passage, then one passage per numbered section of the standards and ACs. The content selectors are now XPath expressions, and `corpus/c1-scope.md` records Standard 571's appendices as left out of C1 (#18).
- `hangar parse` and its DVC stage: every document of the snapshot parsed into `data/parsed/c1`, the committed parse report `results/v0/parse-report.json`, and data checks with thresholds in `parsing.checks` (#19).

### 0.0.0a1 · M1 Corpus C1 (2026-11-05)

Corpus C1 and the first build stage: `hangar fetch` downloads its 18 documents and checks each one against the manifest's SHA-256.

Added:

- Environment settings, the pipeline configuration schema with `configs/pipelines/v0.yaml`, and the configuration hash (#9).
- One `hangar` subcommand per stage, structured logs that carry the run ID, stage and document and redact the API key, and `hangar doctor` (#10).
- The C1 corpus manifest with 18 documents, the list in `configs/corpus/c1.yaml`, and a record of how the scope rule was applied (#11).
- Validation of the corpus manifest, and a loader that returns the active documents of a snapshot (#12).
- `hangar fetch` and its DVC stage: the downloader, the hash checks and the fetch log. The Transport Canada pages now come from fixed Wayback Machine snapshots, and each manifest entry gains an `official_url` for citations (#13).
- `NOTICE.md` with each source's reuse terms and attribution, the C1 data card draft, and ADR-0003 on licences (#14).

### 0.0.0a0 · M0 Repository and tooling (2026-11-04)

The repository, its tooling and CI, before the first pipeline feature. No pipeline code yet.

Added:

- The uv project for Python 3.12, with locked dependencies and the `hangar` command, which prints its version (#2).
- Ruff, mypy in strict mode, and import-linter contracts for the package layers (#3).
- Pre-commit hooks with the gitleaks secret scanner, and ignore rules for data, secrets and caches (#4).
- CI on every pull request, Dependabot, and the pull request template. `main` now requires a passing CI run and squash merges (#5).
- Docker Compose for Qdrant v1.20.0, the Makefile and an empty DVC pipeline (#6).
- The README, the MIT licence, this changelog, the architecture page, the ADR template and the backlog (#7).
- ADR-0001 (Qdrant as the vector store) and ADR-0002 (reproduction through DVC stages) (#8).

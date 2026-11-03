# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Hangar is a RAG system over the FAA maintenance technician handbooks and Transport Canada's maintenance rules (CAR Subparts 571 and 573, Standards 571 and 573, ACs 571-xxx and 573-xxx). It is rebuilt in public, one measured version at a time (v0 to v12).

**No code exists yet.** The plan lives in the GitHub milestones and issues of `pierrelouis-ippoliti/hangar`. Each issue states its scope and acceptance criteria; read the relevant issue (`gh issue view <n>`) before starting work, and reference it in commits and pull requests. Once written, `docs/architecture.md` and `docs/adr/` record the design.

The PDF library is pypdfium2, not PyMuPDF: PyMuPDF is AGPL-3.0, which would bind Hangar's own licence.

## Commands (planned in M0, not yet in place)

The stack is Python 3.12 managed with uv; ruff, mypy (strict on `src/`), import-linter and pytest.

- `make setup`: install from `uv.lock` and the pre-commit hooks.
- `make check`: lint, format check, types, import rules and tests, exactly as CI runs them.
- `make qdrant-up` / `make qdrant-down`: start and stop Qdrant through Docker Compose.
- `make reproduce`: setup, Qdrant, then every DVC stage from a clean clone.
- `make clean-data`: delete `data/` and the Qdrant volume (asks for confirmation).
- Single test: `uv run pytest tests/unit/test_file.py::test_name`.
- Tests marked `model` (real BGE-M3) and `llm` (real Mistral call, needs the API key) run only locally, never in CI.

The `hangar` CLI has one subcommand per stage, each taking a pipeline config (default `configs/pipelines/v0.yaml`): `doctor`, `fetch`, `parse`, `chunk`, `embed`, `index`, `search` (retrieval only, no LLM), `ask`, `seed run`, `seed summarize`. DVC stages in `dvc.yaml` mirror the build commands, so DVC reruns only what a parameter change affects.

## Architecture

The build is five stages, each a function from one artifact to the next: fetch → parse → chunk → embed → index. The answering path reads the index: retrieve top 5 → render prompt → Mistral → parse citations → answer record. Because stages only exchange files, `embed` can run on a borrowed notebook GPU and hand back a vectors file.

One package, `src/hangar/`, split by stage. Dependency rules, enforced by import-linter in CI:

- `core` (domain types, config models, identifiers, provenance, errors) imports nothing else from hangar and does no I/O.
- Stage packages (`corpus`, `parsing`, `chunking`, `embedding`, `indexing`, `retrieval`, `generation`, `evaluation`) import `core` only. The one exception: `retrieval` may import the embedding and indexing interfaces.
- Adapters (Qdrant, Mistral, sentence-transformers, pypdfium2) live inside their stage package. Only `pipelines` constructs them, through a registry keyed by type names in the config.
- `pipelines` imports stages and `core`; `cli` imports `pipelines` only. `observability` imports `core` only and may be used everywhere.

Rules that cut across files:

- **Stages never modify their inputs**, so a rerun gives the same result.
- **A variant is a config file, not a code branch.** Nothing in the code asks which version it is running.
- **Every artifact and run record carries provenance:** config hash (SHA-256 of the resolved pipeline file), commit and dirty flag, input hashes, model revisions.
- **Identifiers derive from content and location**, never from run order. Passages look like `faa-h-8083-31b#p142` or `car-sor-96-433#s571.10`. Chunk IDs are a short hash of document ID, chunker ID and offsets.
- **Positions are character offsets into one canonical text per document.** A chunk's pages or sections are computed from offsets, never guessed. Passages must cover the canonical text exactly once. PDF pages use the 1-based page index as canonical, with the printed label stored alongside.
- **Only add an interface where a named later version needs it:** v1 evaluation and a W&B run sink; v2 Docling parser and structure-aware chunker; v3 multi-output embedder, sparse and BM25 search, hybrid retriever; v4 reranker; v5 LoRA adapters; v6 query transforms and parent-child chunks; v7 structured answers and citation checking; v9 remote embedder and LLM clients.
- Config has two layers. Environment settings (pydantic-settings, `.env`) say *where* things run and are not hashed. The pipeline YAML says *what* runs and is hashed.
- Pin everything: model revisions by commit hash, the LLM by dated model ID, the Qdrant image by tag.
- Prompts in `prompts/` are never edited in place. A new version gets a new file.

## v0 constraints

- **Keep v0 naive.** No header cleaning, table handling, hybrid search or reranking. Note improvement ideas in `docs/backlog.md`; each becomes a measured later version.
- Chunks are 512 tokens counted with BGE-M3's own tokenizer, no overlap. Embeddings use BGE-M3 dense output.
- Mistral Small 4 at temperature 0, with a client-side limit of 1 request per second and backoff on 429 errors.
- CI never touches the network, a real model or a secret. Tests use a fixture corpus, the hash embedder, Qdrant local in-memory mode and a fake LLM.
- Corpus documents are never committed. `corpus/manifest.yaml` holds URLs and SHA-256 hashes, and a hash mismatch stops the run. Transport Canada text is quoted word for word, never modified or translated.
- Every answer must cite a document and a page or section, and end with the study-aid notice: Hangar is not approved maintenance data.
- The seed questions (`eval/seed/questions.jsonl`) must be committed before the first seed run.
- Notebooks are for exploration only and never write artifacts.

## Git workflow

- Claude writes the code; the maintainer reviews every pull request. Explain each change in clear, plain language in the PR description.
- One short branch per issue, named `v<version>/<issue>-<slug>` (for example `v0/2-uv-skeleton`), squash-merged into `main` through a pull request. One pull request per issue.
- Conventional Commits: `feat`, `fix`, `docs`, `test`, `chore`.
- Decision records (ADR-0001 to ADR-0007) go in `docs/adr/`, each written in the milestone whose issue asks for it.

## Versions, tags and releases

The tag is always `v` followed by the version in `pyproject.toml`. Bump the version and tag `main` after the last pull request of a milestone is merged.

- Milestone M*k* of Hangar version *N* is the pre-release `N.0.0ak`: M0 of v0 is `0.0.0a0` (tag `v0.0.0a0`), M5 is `0.0.0a5`.
- The final milestone of a version is the release `N.0.0`: v0 is `0.0.0` (tag `v0.0.0`), v1 is `1.0.0`.
- Milestone tags get no GitHub release. Each version gets one GitHub release, titled like "Hangar v0 · Baseline", carrying its CHANGELOG notes and results files.
- `CHANGELOG.md` gets one section per tag.

# Changelog

Each Hangar version has one section, with one subsection per tag. A milestone ends with a pre-release tag (`v0.0.0a0` for M0), and a version ends with its release (`v0.0.0` for v0).

## v0 · Baseline (in progress)

### Unreleased · M1 Corpus C1

Added:

- Environment settings, the pipeline configuration schema with `configs/pipelines/v0.yaml`, and the configuration hash (#9).
- Validation of the corpus manifest, and a loader that returns the active documents of a snapshot (#12).
- The C1 corpus manifest with 18 documents, the list in `configs/corpus/c1.yaml`, and a record of how the scope rule was applied (#11).
- One `hangar` subcommand per stage, structured logs that carry the run ID, stage and document and redact the API key, and `hangar doctor` (#10).
- `hangar fetch` and its DVC stage: the downloader, the hash checks and the fetch log. The Transport Canada pages now come from fixed Wayback Machine snapshots, and each manifest entry gains an `official_url` for citations (#13).

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

# Changelog

Each Hangar version has one section, with one subsection per tag. A milestone ends with a pre-release tag (`v0.0.0a0` for M0), and a version ends with its release (`v0.0.0` for v0).

## v0 · Baseline (in progress)

### Unreleased · M1 Corpus C1

Added:

- Environment settings, the pipeline configuration schema with `configs/pipelines/v0.yaml`, and the configuration hash (#9).

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

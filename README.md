# Hangar - cited answers from aircraft maintenance documents

Hangar answers aircraft maintenance questions from the FAA handbooks and Transport Canada's rules. It cites the page it used, and says when the documents don't cover a question. Each release changes one thing and publishes what it measured.

**Status:** in progress. v0, the baseline, is being built.

> [!WARNING]
> **Hangar is a study and lookup aid, not approved maintenance data.** Its answers can be wrong or incomplete. Always check the current official documents and follow your organisation's approved procedures.

## What it reads

- The FAA Aviation Maintenance Technician Handbooks.
- Transport Canada's maintenance rules: CAR Subparts 571 and 573, Standards 571 and 573, and the advisory circulars numbered 571 and 573.

The documents are not stored in this repository. Hangar downloads them from their official sources and checks each file against a SHA-256 hash in `corpus/manifest.yaml`.

## Quick start

You need [uv](https://docs.astral.sh/uv/), Docker with Compose, `make` and `git`.

```bash
git clone https://github.com/pierrelouis-ippoliti/hangar.git
cd hangar
make setup          # install Python 3.12, the locked dependencies and the git hooks
make check          # lint, format check, types, import rules and tests, as CI runs them
cp .env.example .env  # then fill in the values
make qdrant-up      # start Qdrant on 127.0.0.1:6333
make qdrant-down    # stop it; its data is kept in a Docker volume
```

The pipeline commands (`hangar fetch`, `hangar parse`, …, `hangar ask`) arrive in the next milestones. `make reproduce` will then rebuild everything from a clean clone.

## Versions

Each version asks one question, changes one thing and is measured before it is adopted.

| Version | Question | Status | Post |
| --- | --- | --- | --- |
| v0 · Baseline | How far does the simplest pipeline get, and where does it fail first? | In progress | Coming soon |

## Documentation

- [Architecture](docs/architecture.md): principles, data flow and package rules.
- [Decision records](docs/adr/): why the main choices were made.
- [Backlog](docs/backlog.md): ideas parked for later versions.
- [Changelog](CHANGELOG.md): what each tag changed.

## Licence

The code is released under the [MIT licence](LICENSE). The corpus documents are not part of this repository and stay under their publishers' terms.

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
uv run hangar doctor  # check Python, Qdrant, the API key, disk space and the model cache
make qdrant-down    # stop it; its data is kept in a Docker volume
```

`hangar --help` lists one subcommand per stage. `doctor`, `fetch`, `parse`, `chunk`, `embed`, `index` and `search` work so far: `uv run hangar fetch` downloads the documents into `data/raw` and checks their hashes, `uv run hangar parse` turns them into passages in `data/parsed/c1` and writes `results/v0/parse-report.json`, `uv run hangar chunk` splits them into chunks of 512 tokens in `data/chunks/c1/fixed512`, `uv run hangar embed` turns each chunk into a BGE-M3 vector in `data/vectors/c1/fixed512/bge-m3-dense`, `uv run hangar index` loads them into the Qdrant collection `c1__fixed512__bge-m3-dense` (start Qdrant first with `make qdrant-up`), and `uv run hangar search "What must a maintenance release contain?"` prints the five chunks closest to a question. `uv run hangar ask "What must a maintenance release contain?"` answers it through Mistral with a citation after every claim (it needs `MISTRAL_API_KEY`); it will give its first real answers once the seed questions are committed. The seed commands arrive in the next milestone. `make reproduce` will then rebuild everything from a clean clone.

## Versions

Each version asks one question, changes one thing and is measured before it is adopted.

| Version | Question | Status | Post |
| --- | --- | --- | --- |
| v0 · Baseline | How far does the simplest pipeline get, and where does it fail first? | In progress | Coming soon |

## Documentation

- [Architecture](docs/architecture.md): principles, data flow and package rules.
- [Data card](docs/data-card.md): what corpus C1 holds, its sizes and its known gaps.
- [Decision records](docs/adr/): why the main choices were made.
- [Backlog](docs/backlog.md): ideas parked for later versions.
- [Changelog](CHANGELOG.md): what each tag changed.

## Licence

The code is released under the [MIT licence](LICENSE). The corpus documents are not part of this repository and stay under their publishers' terms. [`NOTICE.md`](NOTICE.md) gives each source's terms and how Hangar quotes it, and [ADR-0003](docs/adr/0003-licences.md) explains the choices.

Hangar is an independent project. It is not affiliated with or endorsed by the Federal Aviation Administration or Transport Canada.

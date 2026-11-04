# ADR-0002: Reproduction through DVC stages and local run records, with Weights & Biases from v1

- **Status:** accepted
- **Date:** 2026-11-04
- **Issue:** #8

## Context

Every number Hangar publishes must trace back to a tagged run, and anyone must be able to rebuild that run from a clean clone with one command.

- The build is five stages that only exchange files: fetch, parse, chunk, embed and index.
- Some stages are slow: downloading about 0.4 GB of PDFs, and embedding on a laptop. A parameter change should therefore rerun only the stages it affects.
- In v0 there is a single seed run, scored by hand. From v1, every change is judged on an evaluation set, run after run.

## Decision

- **DVC pipeline:** each build command is a DVC stage in `dvc.yaml`, with its parameters read from `configs/pipelines/v0.yaml`.
  - `dvc.lock` records the hashes of each stage's inputs and outputs, so `dvc repro` reruns only what changed.
  - `make reproduce` runs setup, starts Qdrant, then runs `dvc repro`.
- **Local run records:** every run writes a JSON record under `results/` with its provenance: the configuration hash, the commit and dirty flag, the input hashes and the model revisions.
- **Weights & Biases from v1:** v1 adds it as a second destination for the same run records, through a run sink interface. It then gives a public run history that posts can link to.

DVC joined lakeFS in November 2025 and stays open source under the same licence, Apache 2.0 ([announcement](https://dvc.org/blog/dvc-joins-lakefs-your-questions-answered/)).

## Alternatives

- **Scripts only:** a Makefile that calls each command in order.
  - Simpler, with no extra tool.
  - Every rebuild reruns every stage, unless the caching is written by hand.
  - Nothing records which inputs produced which outputs.
- **Weights & Biases from day one.**
  - It would track one hand-scored run in v0.
  - It adds an account, an API key and a network dependency to every run, and CI could not use it anyway.

## Consequences

- A parameter change reruns only the affected stages, and `dvc.lock` shows what was built from what.
- There is no DVC remote. The corpus documents are not Hangar's to redistribute, so every clone rebuilds from the official sources and checks their hashes.
- The Qdrant collection lives in a Docker volume, outside DVC's view. The index stage therefore writes an index manifest file for DVC to track.
- DVC sits in the `pipeline` dependency group, so CI, which never runs the pipeline, doesn't install it. Its anonymous usage analytics are turned off.
- v1 must add the run sink interface, and no v0 code may write to W&B.

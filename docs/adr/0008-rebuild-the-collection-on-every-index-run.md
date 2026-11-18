# ADR-0008: Rebuild the Qdrant collection on every index run

- **Status:** accepted
- **Date:** 2026-11-18
- **Issue:** #22

## Context

Every other stage writes files, and replaces its output folder whole, so its output always matches its inputs. The index stage is different: its output is a Qdrant collection, state that lives in a Docker volume, outside the files that DVC and git track.

Two facts make a collection drift from its inputs if it is only added to:

- **Chunk IDs change with the parse.** A chunk's ID is a hash of its document, its chunker and its offsets ([ADR-0005](0005-locations-and-identifiers.md)). A new parser, a normalisation change or a new chunk size moves the offsets, so the new chunks get new IDs. Upserting them adds new points, but the old points stay, and a search can return text the documents no longer contain.
- **The volume can be wiped or changed outside Hangar,** by `make clean-data`, a Docker clean-up, or a test run against the wrong collection. DVC can't see that.

`hangar index` must also meet issue #22's criterion: running it twice leaves the collection unchanged. On C1, the collection holds 3,627 points, and Qdrant builds it in about a second.

## Decision

`hangar index` deletes the collection if it exists, creates it empty, uploads every chunk with its vector, and checks that the point count equals the chunk count. It never updates a collection in place.

- The collection then holds exactly the chunks and vectors on disk, whatever was in it before.
- Point IDs come from chunk IDs, so the same inputs give the same points, and two runs leave the same collection.
- The DVC stage has `always_changed: true`, so every `dvc repro` rebuilds the collection, even when DVC sees no change in the files. A wiped volume is rebuilt by the next repro.
- The index manifest (`results/v0/index-manifest.json`) holds no time, so a rebuild from the same inputs writes the same file, and the stages after `index` don't rerun.

## Alternatives

- **Keep the collection, check it, and upsert.**
  - It does less work when nothing has changed.
  - But points from an earlier parse stay behind, so the collection holds more than its inputs, and the point count no longer matches the chunk count. Removing them would mean listing every point ID in the collection and deleting the ones that are no longer chunks. That is more code and more failure modes, for a saving of about a second.
- **Skip the build when the manifest already matches.**
  - It also saves the second.
  - But a matching manifest says nothing about what is in the volume now: the collection could be empty, wiped, or changed by hand.
- **Build a new collection under a versioned name, then switch an alias to it.**
  - Qdrant aliases switch at once, so a search running during the rebuild never sees an empty collection, and the old collection stays until the new one is ready.
  - But it needs names with a version, clean-up of old collections, and alias handling in the retriever. That pays off for a server that answers questions while it is rebuilt. v0 runs on one laptop, where nothing searches during a rebuild.

## Consequences

- The collection always matches the chunks and vectors on disk, and no stale chunk can reach an answer.
- Each `dvc repro` spends a few seconds on the index stage, mostly starting Python: about a second of it is Qdrant building C1.
- The collection is empty for that second. A search at the same moment finds nothing; on a laptop, nothing searches then.
- A run that stops in the middle leaves an empty or partial collection. The point count check stops the run before the manifest is written, and the next run rebuilds the collection.
- The rebuild grows with the corpus. If a later snapshot takes minutes to index, or a version serves questions while it rebuilds (v9's remote clients), the alias switch above becomes worth its cost, through a new ADR.

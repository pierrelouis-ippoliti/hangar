# ADR-0001: Qdrant as the vector store

- **Status:** accepted
- **Date:** 2026-11-04
- **Issue:** #8

## Context

v0 only needs dense search: BGE-M3 vectors, top 5 by cosine similarity. Later versions need more from the same store:

- **v3 (hybrid search):** dense, sparse and BM25 retrieval side by side, fused with RRF, weighted RRF and DBSF.
- **v6 (advanced retrieval):** parent-child chunks and several query variants per question.

Two constraints apply from day one. CI never touches the network, so tests need a store that runs without a server. And real runs happen on a laptop with Docker.

## Decision

Use **Qdrant**:

- **Real runs:** a Qdrant server in Docker Compose, pinned to `qdrant/qdrant:v1.20.0` and bound to `127.0.0.1`.
- **Tests:** `qdrant-client`'s in-memory mode, `QdrantClient(":memory:")`, which uses the same client calls.
- **In the code:** Qdrant sits behind the vector index interface in `hangar.indexing`, and only `pipelines` constructs the adapter.

What Qdrant offers for the versions ahead, according to its documentation:

- **One collection, several vector types:** a single collection holds named dense and sparse vectors, and multi-vectors are available since v1.10.
- **Fusion:** the Query API combines several prefetch queries with `rrf` (with per-prefetch weights) or `dbsf`.
- **BM25 on the server:** a full-text index can rank points with BM25 scoring, and the `qdrant/bm25` model builds sparse vectors from text.

The in-memory mode was checked with `qdrant-client` 1.20.0. A collection with named dense and sparse vectors, an upsert and a hybrid query fused with RRF all ran with the same calls as against the server.

## Alternatives

- **Weaviate,** which the maintainer has used professionally.
  - It offers hybrid search, combining BM25F and vectors with `Ranked` and `RelativeScore` fusion, and it supports named vectors.
  - Its option without a server, Embedded Weaviate, is documented as experimental, and it downloads a Weaviate binary on first use. That would break the rule that CI never touches the network.
- **pgvector.**
  - It stores dense and sparse vectors (`sparsevec`, limited to 1,000 non-zero values in an HNSW index), and its documentation suggests combining it with Postgres full-text search for hybrid search.
  - Fusion is left to the user: RRF has to be written by hand in SQL, and full-text ranking uses `ts_rank_cd`, not BM25.
  - Tests would also need a Postgres server.

## Consequences

- v3 can add sparse vectors, BM25 and fusion without changing the store.
- Tests run in memory, with no server, network or Docker, which suits CI.
- The in-memory mode is a separate implementation from the server. A feature it doesn't support needs a test marked to run only locally, against the Docker server.
- The image is pinned by tag, so a Qdrant upgrade is a deliberate pull request.
- Changing store later means writing one adapter, plus one registry entry and one configuration value.

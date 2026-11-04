# Backlog

v0 is deliberately naive, so its scores give later versions an honest baseline. Improvement ideas are parked here instead of being slipped into v0. Each one becomes a measured change in a later version, and is kept only if its metric improves.

| Idea | Why it might help | Planned version |
| --- | --- | --- |
| Remove repeated page headers and footers | They add noise to chunks and their embeddings | v2 · Parsing and chunking |
| Read tables as tables | v0 flattens them into text, which breaks rows apart | v2 · Parsing and chunking |
| Compare pypdfium2 with Docling | Docling recovers layout, headings and tables | v2 · Parsing and chunking |
| Chunks that follow section structure | Fixed 512-token windows cut sections in the middle | v2 · Parsing and chunking |
| Sweep chunk size and overlap | 512 tokens without overlap is a starting point, not a measured choice | v2 · Parsing and chunking |
| BM25 and BGE-M3 sparse vectors next to dense search | Exact matching should help questions that quote section, AC or part numbers | v3 · Hybrid search |
| Rerank the top candidates with a cross-encoder | It should push the right passage higher, at some cost in latency | v4 · Reranking |
| LoRA fine-tuning of the embedder and the reranker | Maintenance vocabulary is narrow and specialised | v5 · Domain fine-tuning |
| Query rewriting, HyDE, parent-child chunks, contextual enrichment | Vague or multi-part questions are hard to match | v6 · Advanced retrieval |
| Structured answers, citation checking and an abstention policy | Every claim should trace to a passage, and the system should say when it has no answer | v7 · Grounded answers |

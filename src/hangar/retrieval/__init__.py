"""
The retrieval step: from a question to the chunks that answer it, best first.

v0 has one retriever, dense search with BGE-M3 in Qdrant. It combines the
embedding and indexing interfaces, which is why ``retrieval`` is the one
stage package allowed to import other stages. v3 adds sparse, BM25 and
hybrid retrievers behind the same interface.
"""

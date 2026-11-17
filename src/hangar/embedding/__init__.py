"""
The embed stage: from chunks to one vector per chunk.

v0 uses the dense output of BGE-M3 through sentence-transformers. The model
sits behind the embedder interface, so tests use a hash embedder that needs
no model, and v3 can add an embedder with several outputs.
"""

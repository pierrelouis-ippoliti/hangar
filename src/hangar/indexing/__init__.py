"""
The index stage: from vectors to a searchable Qdrant collection.

The vector store sits behind the vector index interface, so tests use
Qdrant's in-memory mode through the same adapter, and changing the store
later means writing one adapter.
"""

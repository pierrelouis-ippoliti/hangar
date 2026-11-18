"""Collection names: one collection per snapshot, chunker and embedder."""

SEPARATOR = "__"


def collection_name(snapshot: str, chunker_id: str, embedder_id: str) -> str:
    """
    Name the collection that holds one vector set.

    Args:
        snapshot: The corpus snapshot, such as ``c1``.
        chunker_id: The chunker, such as ``fixed512``.
        embedder_id: The embedder, such as ``bge-m3-dense``.

    Returns:
        The three parts joined by ``__``, such as
        ``c1__fixed512__bge-m3-dense``.

    Raises:
        ValueError: If a part is empty or contains ``__``, which would make
            the name ambiguous.
    """
    parts = (snapshot, chunker_id, embedder_id)

    for part in parts:
        if not part or SEPARATOR in part:
            raise ValueError(f"collection name part {part!r} is empty or contains '__'")

    return SEPARATOR.join(parts)

import pytest

from hangar.indexing.naming import collection_name


def test_the_name_joins_snapshot_chunker_and_embedder() -> None:
    assert (
        collection_name("c1", "fixed512", "bge-m3-dense")
        == "c1__fixed512__bge-m3-dense"
    )


def test_each_part_changes_the_name() -> None:
    names = {
        collection_name("c1", "fixed512", "bge-m3-dense"),
        collection_name("c2", "fixed512", "bge-m3-dense"),
        collection_name("c1", "fixed256-o32", "bge-m3-dense"),
        collection_name("c1", "fixed512", "e5-large-dense"),
    }

    assert len(names) == 4


@pytest.mark.parametrize("parts", [("", "fixed512", "x"), ("c1", "a__b", "x")])
def test_a_part_that_would_make_the_name_ambiguous_is_refused(
    parts: tuple[str, str, str],
) -> None:
    with pytest.raises(ValueError, match="empty or contains '__'"):
        collection_name(*parts)

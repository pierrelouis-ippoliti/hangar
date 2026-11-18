from pathlib import Path

from hangar.parsing.car import CarXmlParser
from hangar.parsing.pdf import PdfPageParser
from hangar.parsing.tc_html import TcHtmlParser
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_parsers, build_retriever

V0_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "pipelines" / "v0.yaml"


def test_each_format_gets_its_parser() -> None:
    parsers = build_parsers(load_pipeline_config(V0_CONFIG).parsing)

    assert set(parsers) == {"pdf", "xml", "html"}
    assert isinstance(parsers["pdf"], PdfPageParser)
    assert isinstance(parsers["xml"], CarXmlParser)
    assert isinstance(parsers["html"], TcHtmlParser)


def test_the_retriever_returns_the_configured_top_k() -> None:
    from qdrant_client import QdrantClient

    from hangar.core.chunks import Chunk, PassageRef, chunk_id
    from hangar.core.parsed import PageLocation
    from hangar.embedding.embedder import HashEmbedder
    from hangar.indexing.qdrant import QdrantIndex

    chunks = [
        Chunk(
            id=chunk_id("example-handbook", "fixed512", n, n + 1),
            document_id="example-handbook",
            chunker_id="fixed512",
            start=n,
            end=n + 1,
            text=str(n),
            token_count=1,
            passages=[
                PassageRef(
                    id="example-handbook#p1",
                    location=PageLocation(page_index=1, page_label=None),
                )
            ],
        )
        for n in range(7)
    ]
    embedder = HashEmbedder()
    index = QdrantIndex(QdrantClient(":memory:"), "c1__fixed512__test")
    index.recreate(dimension=embedder.dimension)
    index.upsert(chunks, embedder.embed_documents([c.text for c in chunks]))
    config = load_pipeline_config(V0_CONFIG)

    results = build_retriever(config.retrieval, embedder, index).retrieve("3")

    assert len(results) == config.retrieval.top_k == 5
    assert results[0].chunk == chunks[3]
    assert {r.retriever_id for r in results} == {"dense"}

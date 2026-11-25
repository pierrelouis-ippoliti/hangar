from pathlib import Path

import pytest
from pydantic import SecretStr

from hangar.core.errors import ConfigError
from hangar.generation.mistral import MistralClient
from hangar.parsing.car import CarXmlParser
from hangar.parsing.pdf import PdfPageParser
from hangar.parsing.tc_html import TcHtmlParser
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_llm_client, build_parsers, build_retriever
from tests.builders import consecutive_chunks

V0_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "pipelines" / "v0.yaml"


def test_each_format_gets_its_parser() -> None:
    parsers = build_parsers(load_pipeline_config(V0_CONFIG).parsing)

    assert set(parsers) == {"pdf", "xml", "html"}
    assert isinstance(parsers["pdf"], PdfPageParser)
    assert isinstance(parsers["xml"], CarXmlParser)
    assert isinstance(parsers["html"], TcHtmlParser)


def test_the_retriever_returns_the_configured_top_k() -> None:
    from qdrant_client import QdrantClient

    from hangar.embedding.embedder import HashEmbedder
    from hangar.indexing.qdrant import QdrantIndex

    chunks = consecutive_chunks([str(n) for n in range(7)])
    embedder = HashEmbedder()
    index = QdrantIndex(QdrantClient(":memory:"), "c1__fixed512__test")
    index.recreate(dimension=embedder.dimension)
    index.upsert(chunks, embedder.embed_documents([c.text for c in chunks]))
    config = load_pipeline_config(V0_CONFIG)

    results = build_retriever(config.retrieval, embedder, index).retrieve("3")

    assert len(results) == config.retrieval.top_k == 5
    assert results[0].chunk == chunks[3]
    assert {r.retriever_id for r in results} == {"dense"}


def test_the_llm_client_asks_for_the_configured_model() -> None:
    config = load_pipeline_config(V0_CONFIG)

    client = build_llm_client(config.generation, SecretStr("fake-key"))

    assert isinstance(client, MistralClient)
    assert client.model_id == "mistral-small-2603"


def test_the_llm_client_needs_the_api_key() -> None:
    config = load_pipeline_config(V0_CONFIG)

    with pytest.raises(ConfigError, match="MISTRAL_API_KEY"):
        build_llm_client(config.generation, None)

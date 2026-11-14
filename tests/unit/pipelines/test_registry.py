from pathlib import Path

from hangar.parsing.car import CarXmlParser
from hangar.parsing.pdf import PdfPageParser
from hangar.parsing.tc_html import TcHtmlParser
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_parsers

V0_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "pipelines" / "v0.yaml"


def test_each_format_gets_its_parser() -> None:
    parsers = build_parsers(load_pipeline_config(V0_CONFIG).parsing)

    assert set(parsers) == {"pdf", "xml", "html"}
    assert isinstance(parsers["pdf"], PdfPageParser)
    assert isinstance(parsers["xml"], CarXmlParser)
    assert isinstance(parsers["html"], TcHtmlParser)

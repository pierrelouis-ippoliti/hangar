import hashlib
from pathlib import Path

import pytest
from lxml import etree

from hangar.core.config import ContentSelectors, NormalisationConfig
from hangar.core.parsed import ParsedDocument
from hangar.parsing.parser import ParseError
from hangar.parsing.tc_html import TcHtmlParser
from tests.builders import document_spec

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tc_html"
STANDARD = FIXTURES / "tc-standard-example.html"
AC = FIXTURES / "tc-ac-example.html"
NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)
SELECTORS = ContentSelectors(standard="//main", advisory_circular="//main")
TITLE = "Advisory Circular (AC) No. 571-999"


def parse(
    path: Path,
    document_type: str = "standard",
    selectors: ContentSelectors = SELECTORS,
) -> ParsedDocument:
    document = document_spec(
        id="tc-example", authority="TC", type=document_type, format="html"
    )

    return TcHtmlParser(NORMALISATION, selectors).parse(document, path)


def texts(parsed: ParsedDocument) -> dict[str, str]:
    return {
        p.id.split("#")[1]: parsed.text[p.start : p.end].rstrip("\n")
        for p in parsed.passages
    }


def test_numbered_headings_start_passages_after_a_front_matter_passage() -> None:
    parsed = parse(STANDARD)

    assert [p.id for p in parsed.passages] == [
        "tc-example#front",
        "tc-example#s571.01",
        "tc-example#s571.02",
    ]


def test_front_matter_holds_the_title_contents_and_preamble() -> None:
    assert texts(parse(STANDARD))["front"] == (
        "Example Standard 571 - Example Maintenance\n"
        "Table of contents\n"
        "571.01 Example Application\n"
        "571.02 Example Rules\n"
        "Preamble\n"
        "This example standard sets out made-up rules."
    )


def test_unnumbered_headings_stay_in_the_section_before_them() -> None:
    assert texts(parse(STANDARD))["s571.01"] == (
        "571.01 Example Application\n"
        "(1) The first example rule.\n"
        "Types of Example Work\n"
        "Kind Example\n"
        "Light Cleaning"
    )


def test_blocks_and_line_breaks_become_lines_and_hidden_content_is_left_out() -> None:
    assert texts(parse(STANDARD))["s571.02"] == (
        "571.02 Example Rules\n"
        "A line\n"
        "broken in two.\n"
        "(a) first item;\n"
        "(b) second item.\n"
        "Date modified:\n"
        "2024-01-01"
    )


def test_only_the_selected_content_is_read() -> None:
    text = parse(STANDARD).text

    assert "Example site menu" not in text
    assert "Example site footer" not in text
    assert "not page text" not in text
    assert "editor's note" not in text


def test_advisory_circular_sections_follow_their_numbers_at_any_heading_level() -> None:
    parsed = parse(AC, "advisory_circular")

    assert [p.id.split("#")[1] for p in parsed.passages] == [
        "front",
        "s1.0",
        "s1.1",
        "s1.2",
        "s2.0",
        "s2.1",
        "s2.1.1",
        "s3.0",
    ]


def test_heading_path_is_the_title_then_the_numbered_headings_above() -> None:
    paths = {
        p.id.split("#")[1]: p.location.heading_path
        for p in parse(AC, "advisory_circular").passages
    }

    assert paths["front"] == (TITLE,)
    assert paths["s1.1"] == (TITLE, "1.0 Introduction", "1.1 Purpose")
    assert paths["s2.1.1"] == (
        TITLE,
        "2.0 Guidance",
        "2.1 Example Records",
        "2.1.1 Example Entries",
    )
    assert paths["s3.0"] == (TITLE, "3.0 Contact Office")


def test_an_unnumbered_appendix_stays_in_the_last_section() -> None:
    assert texts(parse(AC, "advisory_circular"))["s3.0"] == (
        "3.0 Contact Office\n"
        "Example office.\n"
        "Appendix A — Example Form\n"
        "An example appendix."
    )


def test_the_selector_follows_the_document_type(tmp_path: Path) -> None:
    selectors = ContentSelectors(standard="//main", advisory_circular="//article")
    path = tmp_path / "page.html"
    path.write_text(
        "<html><body><main><h1>Ignored</h1></main>"
        "<article><h1>Kept</h1><h2>1.0 Only</h2><p>Text.</p></article></body></html>",
        encoding="utf-8",
    )

    parsed = parse(path, "advisory_circular", selectors)

    assert parsed.text == "Kept\n\n1.0 Only\nText."


def test_a_page_without_sections_gives_a_front_passage_and_a_warning(
    tmp_path: Path,
) -> None:
    path = tmp_path / "page.html"
    path.write_text(
        "<html><body><main><h1>Example Notice</h1><p>No sections here.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    parsed = parse(path)

    assert [p.id for p in parsed.passages] == ["tc-example#front"]
    assert parsed.text == "Example Notice\nNo sections here."
    assert [(w.code, w.passage_id) for w in parsed.warnings] == [
        ("no_sections", "tc-example#front")
    ]


def test_parser_records_lxml_and_the_hash_of_the_file_it_read() -> None:
    parsed = parse(STANDARD)

    assert parsed.source_sha256 == hashlib.sha256(STANDARD.read_bytes()).hexdigest()
    assert parsed.parser.name == "tc-html"
    assert parsed.parser.version.startswith(etree.__version__)
    assert parsed.warnings == ()


def test_a_selector_that_matches_no_element_is_an_error() -> None:
    selectors = ContentSelectors(standard="//article", advisory_circular="//main")

    with pytest.raises(ParseError, match="tc-example.*//article.*0 elements"):
        parse(STANDARD, selectors=selectors)


def test_an_invalid_selector_is_an_error() -> None:
    selectors = ContentSelectors(standard="//main[", advisory_circular="//main")

    with pytest.raises(ParseError, match="tc-example.*//main\\["):
        parse(STANDARD, selectors=selectors)


def test_a_document_type_without_a_selector_is_an_error() -> None:
    with pytest.raises(ParseError, match="tc-example.*handbook"):
        parse(STANDARD, document_type="handbook")


def test_two_sections_with_the_same_number_are_an_error(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text(
        "<html><body><main><h2>1.0 First</h2><h2>1.0 Again</h2></main></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(ParseError, match="tc-example.*1.0"):
        parse(path)


def test_an_empty_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_bytes(b"")

    with pytest.raises(ParseError, match="tc-example"):
        parse(path)


def test_a_missing_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="tc-example.*can't read"):
        parse(tmp_path / "missing.html")

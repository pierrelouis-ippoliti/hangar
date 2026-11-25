import hashlib
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from hangar.core.config import NormalisationConfig
from hangar.core.parsed import PageLocation, Passage, passage_id
from hangar.parsing.parser import ParseError
from hangar.parsing.pdf import PdfPageParser, page_warnings
from tests.builders import document_spec

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "pdf"
    / "faa-h-8083-30b-p34-36.pdf"
)
NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)


def test_each_page_becomes_one_passage_with_its_printed_label() -> None:
    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), FIXTURE)

    assert [p.id for p in parsed.passages] == [
        "faa-h-8083-30b#p1",
        "faa-h-8083-30b#p2",
        "faa-h-8083-30b#p3",
    ]
    assert [p.location for p in parsed.passages] == [
        PageLocation(page_index=1, page_label="1-13"),
        PageLocation(page_index=2, page_label="1-14"),
        PageLocation(page_index=3, page_label="1-15"),
    ]


def test_passages_cover_the_canonical_text_in_page_order() -> None:
    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), FIXTURE)
    pages = [parsed.text[p.start : p.end] for p in parsed.passages]

    assert "".join(pages) == parsed.text
    assert pages[0].startswith("1-13\n")
    assert pages[1].startswith("1-14\n")
    assert pages[2].startswith("1-15\n")


def test_text_is_normalised() -> None:
    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), FIXTURE)

    assert "\r" not in parsed.text
    assert "  " not in parsed.text


def test_hyphens_that_pdfium_marks_as_u_fffe_are_kept_as_hyphens() -> None:
    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), FIXTURE)

    assert "\ufffe" not in parsed.text
    assert "self-sustaining" in parsed.text


def test_parser_records_its_library_and_the_hash_of_the_file_it_read() -> None:
    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), FIXTURE)

    assert parsed.document_id == "faa-h-8083-30b"
    assert parsed.source_sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert parsed.parser.name == "pypdfium2"
    assert parsed.parser.version.startswith(pdfium.version.PYPDFIUM_INFO.version)


def test_the_fixture_has_no_warnings() -> None:
    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), FIXTURE)

    assert parsed.warnings == ()


def test_blank_page_keeps_an_empty_passage_and_a_warning(tmp_path: Path) -> None:
    # Page 1 of the fixture, a blank page, then page 3. The new file has no
    # page labels.
    path = tmp_path / "with-blank-page.pdf"
    source = pdfium.PdfDocument(FIXTURE)
    pdf = pdfium.PdfDocument.new()
    pdf.import_pages(source, [0])
    pdf.new_page(612, 792)
    pdf.import_pages(source, [2])
    pdf.save(path)
    pdf.close()
    source.close()

    parsed = PdfPageParser(NORMALISATION).parse(document_spec(), path)
    blank = parsed.passages[1]

    assert blank.start == blank.end
    assert [p.location.page_label for p in parsed.passages] == [None, None, None]
    assert [(w.code, w.passage_id) for w in parsed.warnings] == [
        ("empty_page", "faa-h-8083-30b#p2")
    ]


def test_page_with_unreadable_characters_gets_a_garbled_page_warning() -> None:
    text = "readable page\n\nFigure 8-9. \x01\x08\x01\x05 echo"
    locations = [PageLocation(page_index=i, page_label=None) for i in (1, 2)]
    passages = [
        Passage(
            id=passage_id("doc", locations[0]), location=locations[0], start=0, end=15
        ),
        Passage(
            id=passage_id("doc", locations[1]),
            location=locations[1],
            start=15,
            end=len(text),
        ),
    ]

    warnings = page_warnings(text, passages)

    assert [(w.code, w.passage_id) for w in warnings] == [("garbled_page", "doc#p2")]
    assert "4 unreadable characters" in warnings[0].message


def test_a_file_that_is_not_a_pdf_raises_an_error_naming_the_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(ParseError, match="faa-h-8083-30b"):
        PdfPageParser(NORMALISATION).parse(document_spec(), path)


def test_one_unreadable_character_is_named_in_the_singular() -> None:
    location = PageLocation(page_index=7, page_label="1-3")
    passage = Passage(id=passage_id("doc", location), location=location, start=0, end=5)

    warnings = page_warnings("ab\x01cd", [passage])

    assert warnings[0].message == "page 7 (printed 1-3) has 1 unreadable character"

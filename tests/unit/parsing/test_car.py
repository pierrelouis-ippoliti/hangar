import hashlib
from pathlib import Path

import pytest
from lxml import etree

from hangar.core.config import NormalisationConfig
from hangar.core.parsed import ParsedDocument, SectionLocation
from hangar.parsing.car import CarXmlParser
from hangar.parsing.parser import ParseError
from tests.builders import document_spec

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "car" / "car-example.xml"
NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)


def parse(
    subparts: tuple[str, ...] = ("571", "573"), path: Path = FIXTURE
) -> ParsedDocument:
    document = document_spec(
        id="car-example", authority="TC", type="regulation", format="xml"
    )

    return CarXmlParser(NORMALISATION, subparts).parse(document, path)


def section_texts(parsed: ParsedDocument) -> dict[str, str]:
    return {
        p.id.split("#s")[1]: parsed.text[p.start : p.end].rstrip("\n")
        for p in parsed.passages
    }


def test_only_the_sections_of_the_chosen_subparts_are_kept() -> None:
    parsed = parse()

    assert [p.id for p in parsed.passages] == [
        "car-example#s571.01",
        "car-example#s571.02",
        "car-example#s573.01",
    ]


def test_subparts_come_from_the_configuration() -> None:
    parsed = parse(subparts=("573",))

    assert [p.id for p in parsed.passages] == ["car-example#s573.01"]


def test_heading_path_takes_the_latest_heading_at_each_level() -> None:
    paths = [p.location.heading_path for p in parse().passages]

    assert paths == [
        (
            "PART V Example Airworthiness",
            "Subpart 71 — Example Maintenance Requirements",
            "Application",
        ),
        (
            "PART V Example Airworthiness",
            "Subpart 71 — Example Maintenance Requirements",
            "Example Performance Rules",
        ),
        (
            "PART V Example Airworthiness",
            "Subpart 73 — Example Maintenance Organizations",
            "Division I — General",
            "Example Duties",
        ),
    ]


def test_section_text_starts_with_the_headings_since_the_previous_section() -> None:
    texts = section_texts(parse())

    assert texts["571.01"] == (
        "Subpart 71 — Example Maintenance Requirements\n"
        "Application\n"
        "571.01 This Subpart applies to\n"
        "(a) example aircraft; and\n"
        "(b) example parts.\n"
        "SOR/2000-1, s. 1; SOR/2019-2, s. 3"
    )


def test_nested_labels_lead_their_text_and_cross_references_stay_inline() -> None:
    texts = section_texts(parse())

    assert texts["571.02"] == (
        "Example Performance Rules\n"
        "571.02 (1) A person shall use the methods set out in Example Standard 571"
        " that are\n"
        "(a) specified by the manufacturer; or\n"
        "(i) equivalent to them.\n"
        "(2) [Repealed, SOR/2019-2, s. 4]"
    )


def test_repealed_sections_keep_their_passage() -> None:
    texts = section_texts(parse())

    assert texts["573.01"].endswith("573.01 [Repealed, SOR/2022-3, s. 1]")


def test_reserved_ranges_and_other_subparts_stay_out_of_the_text() -> None:
    text = parse().text

    assert "reserved" not in text
    assert "not kept" not in text
    assert "Example Operating Rules" not in text


def test_section_locations_carry_the_label() -> None:
    location = parse().passages[0].location

    assert isinstance(location, SectionLocation)
    assert location.label == "571.01"


def test_parser_records_lxml_and_the_hash_of_the_file_it_read() -> None:
    parsed = parse()

    assert parsed.source_sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert parsed.parser.name == "car-xml"
    assert parsed.parser.version.startswith(etree.__version__)
    assert parsed.warnings == ()


def test_a_subpart_with_no_sections_is_an_error() -> None:
    with pytest.raises(ParseError, match="car-example.*Subpart 999"):
        parse(subparts=("571", "999"))


def test_a_file_that_is_not_xml_raises_an_error_naming_the_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.xml"
    path.write_text("<Regulation><Body>", encoding="utf-8")

    with pytest.raises(ParseError, match="car-example"):
        parse(path=path)


def test_entities_are_not_resolved(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("do not read", encoding="utf-8")
    path = tmp_path / "entity.xml"
    path.write_text(
        f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file://{secret}">]>'
        "<Regulation><Body><Section><Label>571.01</Label><Text>&x;</Text>"
        "</Section></Body></Regulation>",
        encoding="utf-8",
    )

    assert "do not read" not in parse(subparts=("571",), path=path).text


def write_body(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "regulations.xml"
    path.write_text(f"<Regulation><Body>{body}</Body></Regulation>", encoding="utf-8")

    return path


def test_comments_inside_a_section_are_ignored(tmp_path: Path) -> None:
    path = write_body(
        tmp_path,
        "<Section><Label>571.01</Label><!-- a note -->"
        "<Text>Some text.</Text></Section>",
    )

    assert parse(subparts=("571",), path=path).text == "571.01 Some text."


def test_a_label_with_no_text_still_gets_its_line(tmp_path: Path) -> None:
    path = write_body(tmp_path, "<Section><Label>571.01</Label></Section>")

    assert parse(subparts=("571",), path=path).text == "571.01"


def test_sections_without_a_label_are_skipped(tmp_path: Path) -> None:
    path = write_body(
        tmp_path,
        "<Section><Text>No label.</Text></Section>"
        "<Section><Label>571.01</Label><Text>Kept.</Text></Section>",
    )

    assert parse(subparts=("571",), path=path).text == "571.01 Kept."


def test_a_file_with_no_body_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "regulations.xml"
    path.write_text("<Regulation><Order/></Regulation>", encoding="utf-8")

    with pytest.raises(ParseError, match="car-example.*no Body"):
        parse(path=path)

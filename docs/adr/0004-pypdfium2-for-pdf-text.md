# ADR-0004: pypdfium2 for PDF text

- **Status:** accepted
- **Date:** 2026-11-14
- **Issue:** #16

## Context

The three FAA handbooks of C1 are PDFs of 500 to 1,052 pages, 2,229 pages in all. v0 needs the text of each page and the printed page label, such as `1-13`, because citations name a page ([ADR-0005](0005-locations-and-identifiers.md)). It needs nothing else: no layout, no tables, no images.

Hangar's code is MIT ([ADR-0003](0003-licences.md)). A library under a licence that reaches network use would bind Hangar's own licence as soon as Hangar answers questions over a network.

## Decision

Hangar reads PDFs with **pypdfium2**, the Python binding for PDFium, the PDF engine of Chromium.

- **Licence:** pypdfium2 is Apache-2.0 or BSD-3-Clause, PDFium is BSD-3-Clause, and the libraries bundled in its wheels are permissive too.
- **Version:** 5.14 or later, for `PdfDocument.get_page_label`. The parser records the pypdfium2 version and the PDFium build, such as `5.15.2 (PDFium 8149)`, because a new PDFium can extract different text.
- **One passage per page,** from `get_text_range()`. A page with no text keeps an empty passage and an `empty_page` warning. A page with control, private-use or unassigned characters gets a `garbled_page` warning. Both are known parse losses (P1), left for v2.
- **One correction:** PDFium returns a hyphen it joins across a line break as `U+FFFE`, which is not a character, as in `self\ufffesustaining`. The parser turns it back into the hyphen the page prints. Nothing else is cleaned.
- **Only `parsing` and `pipelines` import pypdfium2,** as an import-linter contract checks. pypdfium2 ships no type information, so mypy treats its objects as untyped, and the parser turns what it reads into `str` at once.

## Alternatives

- **PyMuPDF.**
  - Fast, with good text extraction and page labels.
  - But it is AGPL-3.0 or a paid licence. The AGPL reaches network use, so it would bind Hangar's own licence.
- **pdfplumber,** on top of pdfminer.six.
  - MIT, with detailed layout and table analysis.
  - But v0 needs neither, and pure Python is slower than PDFium's C++ engine on 2,229 pages. Layout and tables come back in v2, with Docling.
- **pypdf.**
  - BSD, pure Python, with page labels.
  - But it is pure Python too, and offers v0 nothing that pypdfium2 lacks. PDFium is also the engine Chromium relies on, so it has met far more PDFs.

## Consequences

- Parsing the three handbooks takes about 10 seconds on a laptop. They give 3 blank covers and 2 garbled pages: a figure on page 404 of FAA-H-8083-30B, and one character on page 570 of FAA-H-8083-31B.
- Each page's text keeps its running header and printed page number. Removing them is a backlog item for v2.
- pypdfium2 ships PDFium as a binary in platform wheels, so Hangar installs simply only where a wheel exists: Linux, macOS and Windows on common processors.
- Upgrading pypdfium2 can change the text, and so the offsets. The recorded version shows when that happened, and the DVC parse stage (#19) reruns.
- The v2 Docling parser follows the same `Parser` interface and is chosen in the pipeline file.

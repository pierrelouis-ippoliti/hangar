# ADR-0005: Locations and identifiers for passages and chunks

- **Status:** accepted
- **Date:** 2026-11-14
- **Issue:** #15

## Context

Every answer must cite a document and a page or section, so each piece of text needs a location that a reader can check. The corpus gives two kinds:

- **The FAA handbooks are PDFs.** Each page has a position in the file, and most pages also have a printed number, such as `7-12`. Printed numbers aren't unique: chapters restart them, the front matter uses `i`, `ii`, and one handbook (FAA-H-8083-31B) has no page labels at all.
- **The Transport Canada documents are divided into numbered sections:** `571.10` in the regulations and standards, `4.1.1` in the advisory circulars. A standard or circular page also starts with text before its first numbered section: a title, a table of contents, sometimes a preamble.

Chunks (M3) are cut by token count, not by page or section, so a chunk can cross a page break. Its locations have to come from somewhere reliable.

## Decision

- **Each document has one canonical text,** the parser's output after normalisation: Unicode NFKC, one kind of line ending, and runs of spaces and tabs collapsed.
- **Passages are character ranges of that text,** one per PDF page or per numbered section. Together they cover the text exactly once. The model rejects gaps, overlaps and passages that don't reach both ends.
- **A PDF page is located by its 1-based index in the file,** which is canonical. The printed label is stored next to it when the PDF provides one, because that is what technicians cite.
- **A section is located by its label,** such as `571.10`, with its heading path. The text before the first numbered section becomes a front-matter passage, with no label.
- **IDs derive from the document and the location:** `faa-h-8083-31b#p142`, `car-sor-96-433#s571.10`, `tc-std-571#front`. They never depend on the order of a run.
- **Chunks store offsets.** The pages or sections a chunk covers are computed from its offsets (`ParsedDocument.passages_in_range`), never guessed.
- **Offsets belong to one parse.** A new parser gives new offsets. Evidence labels in the evaluation sets use quotes, which survive a change of parser.

## Alternatives

- **Printed page numbers only.**
  - They are what readers know.
  - But they repeat within a handbook, one handbook has none, and they don't say where a page is in the file. Citations would sometimes be ambiguous, and a link couldn't go straight to the page.
- **Labels stored on each chunk, with no passages.**
  - Simpler for v0, since the chunker would record the page it starts on.
  - But a chunk that crosses a page break would cite only one page. Each chunker would also have to work out locations again, including the structure-aware chunker of v2.
- **Dropping the front matter of Transport Canada pages.**
  - It would leave the table of contents out of the index.
  - But some front matter holds real content, such as the preamble of Standard 571, and a page with no numbered section would then have no text at all.

## Consequences

- Every parser builds its passages through one function (`parsing.assemble`), so the coverage rule holds for every format.
- The chunker (M3) and the citation parser (M4) work with offsets, and use `passages_in_range` for locations.
- NFKC changes some characters: `m²` becomes `m2`, and `½` becomes `1⁄2`. The canonical text is therefore not always a word-for-word copy of the source. Quotes shown to readers must say they come from the normalised text, or be taken from the source itself. The backlog records NFC, which keeps these characters, as a measured change for v2.
- An empty page keeps a zero-length passage, so page numbers stay continuous. No range ever covers it.
- Parsed documents from different parsers can't share offsets. The v2 comparison between pypdfium2 and Docling has to match evidence by quote.

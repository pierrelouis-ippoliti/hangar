# Data card: corpus snapshot C1

- **Status:** draft. The page and section counts below come from the downloaded files. Token counts arrive with the chunker (#20), and exact counts of the text kept come with the parsers (M2).
- **Snapshot:** C1, the corpus of every version up to v9.
- **Downloaded:** 2026-11-05, by `hangar fetch`. The FAA and CAR hashes were first computed on 2026-11-04.

## What C1 holds

C1 follows a rule rather than a hand-picked list: **the three FAA maintenance technician handbooks, plus everything Transport Canada numbers 571 or 573.** [`corpus/c1-scope.md`](../corpus/c1-scope.md) records how the rule was applied and what it left out. [`corpus/manifest.yaml`](../corpus/manifest.yaml) lists each document with its source, dates and SHA-256.

All 18 documents are in English. Their files take 424,663,275 bytes.

| Group | Documents | Format | Downloaded from |
| --- | --- | --- | --- |
| FAA handbooks | 3 | PDF | faa.gov |
| Canadian Aviation Regulations | 1 (Subparts 571 and 573 kept) | XML | GitHub, `justicecanada/laws-lois-xml`, at a pinned commit |
| Transport Canada standards | 2 | HTML | Wayback Machine snapshots of tc.canada.ca |
| Transport Canada advisory circulars | 12 | HTML | Wayback Machine snapshots of tc.canada.ca |

## Measured sizes

**FAA handbooks**, all 2023 editions:

| ID | Pages | Bytes |
| --- | ---: | ---: |
| `faa-h-8083-30b` (General) | 677 | 92,539,602 |
| `faa-h-8083-31b` (Airframe) | 1,052 | 111,959,636 |
| `faa-h-8083-32b` (Powerplant) | 500 | 214,668,861 |

The page counts are those of the PDF files, as reported by `pdfinfo`, front matter included.

**Canadian Aviation Regulations:** `car-sor-96-433`, 4,495,496 bytes, consolidated to 2026-06-18. The file holds all the regulations. The 31 sections kept are 571.01 to 571.13, 573.01 to 573.15, and 573.30 to 573.32.

**Transport Canada pages:** the words are those inside each page's `<main>` element. That count includes a few navigation words, such as the "Date modified" line, so it is slightly above the text the parser will keep.

| ID | Words | Bytes |
| --- | ---: | ---: |
| `tc-std-571` | 7,577 | 105,205 |
| `tc-std-573` | 7,912 | 107,663 |
| `tc-ac-571-002` | 4,040 | 76,790 |
| `tc-ac-571-004` | 1,647 | 52,058 |
| `tc-ac-571-006` | 2,855 | 73,882 |
| `tc-ac-571-024` | 4,604 | 75,758 |
| `tc-ac-571-025` | 4,413 | 70,466 |
| `tc-ac-571-026` | 3,002 | 66,586 |
| `tc-ac-573-002` | 2,012 | 55,541 |
| `tc-ac-573-003` | 1,662 | 56,685 |
| `tc-ac-573-006` | 1,958 | 55,920 |
| `tc-ac-573-008` | 5,002 | 82,564 |
| `tc-ac-573-009` | 1,852 | 54,332 |
| `tc-ac-573-010` | 3,397 | 66,230 |

**Tokens:** to be measured with BGE-M3's tokenizer in #20.

## Known gaps

- **Only English.** The French versions of the Transport Canada documents are left out, and nothing is translated.
- **Documents the rule leaves out.** Subparts 571 and 573 refer to other standards, such as Standard 625 (Aircraft Equipment and Maintenance), and to other parts of the CARs. None of them are in C1, so a question that depends on them can't be fully answered.
- **A cancelled circular.** AC 571-005 (Major Repair After Substantial Damage) was cancelled on 2024-11-15 for "misleading information". It stays in the manifest on record but is never fetched. Questions on that subject are candidates for the unanswerable part of the seed set.
- **Fixed points in time.** The CARs are consolidated to 2026-06-18. Each Transport Canada page is the latest Wayback Machine capture made after its last change, taken between 2026-03-11 and 2026-08-13. A later change to any document reaches Hangar only in a new snapshot, C2.
- **Figures and tables.** v0 reads text only. The handbooks' diagrams and photos are not searchable, tables lose their layout, and text inside images is lost.
- **Images credited to other people.** Some handbook figures come from outside contributors under their own terms. See [`NOTICE.md`](../NOTICE.md).

## Licences

See [`NOTICE.md`](../NOTICE.md) for each source's terms and attribution, and [ADR-0003](adr/0003-licences.md) for Hangar's own licences.

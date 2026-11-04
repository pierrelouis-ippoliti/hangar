# Snapshot C1: how the scope rule was applied

C1 is defined by a rule, not a hand-picked list: **the three FAA maintenance technician handbooks, plus everything Transport Canada numbers 571 or 573.** This page records how the rule was applied on 2026-11-04, so that anyone can check it or apply it again. The documents are listed in [`manifest.yaml`](manifest.yaml) and [`configs/corpus/c1.yaml`](../configs/corpus/c1.yaml).

## What C1 holds

18 documents, all in English.

| Group | Documents | Source |
| --- | --- | --- |
| FAA handbooks | FAA-H-8083-30B General, FAA-H-8083-31B Airframe, FAA-H-8083-32B Powerplant, all 2023 | One PDF each, from the [FAA handbooks page](https://www.faa.gov/regulations_policies/handbooks_manuals/aviation) |
| Regulations | Canadian Aviation Regulations, SOR/96-433, consolidated to 2026-06-18 | `eng/regulations/SOR-96-433.xml` in [justicecanada/laws-lois-xml](https://github.com/justicecanada/laws-lois-xml), at commit `076f5b3c`, the latest that changed the file (2026-08-06) |
| Standards | Standard 571 (Maintenance), Standard 573 (Approved Maintenance Organizations) | Transport Canada web pages |
| Advisory circulars | The 12 active ACs numbered 571-xxx or 573-xxx | Transport Canada web pages |

The XML holds all the regulations. The parser keeps only Subparts 571 and 573. The pinned file contains exactly the expected sections: 571.01 to 571.13, 573.01 to 573.15, and 573.30 to 573.32.

## Advisory circulars

The [AC index](https://tc.canada.ca/en/aviation/reference-centre/advisory-circulars) listed 13 ACs numbered 571-xxx or 573-xxx on 2026-11-04.

| AC | Subject | Effective | In C1 |
| --- | --- | --- | --- |
| 571-002 | Maintenance Implementation Procedures – Bilateral Aviation Safety Agreement Between Canada and United States | 2019-05-01 | Yes |
| 571-004 | Installation Eligibility of Substitute or Replacement Bearings | 2009-08-26 | Yes |
| 571-005 | Major Repair After Substantial Damage | 2011-07-14 | **No: cancelled on 2024-11-15** |
| 571-006 | Electronic Signatures and Electronic Exchange of the Authorized Release Certificate – Form One | 2012-03-26 | Yes |
| 571-024 | Documentation Required for the Installation of Parts onto Canadian Registered Aircraft | 2024-06-13 | Yes |
| 571-025 | Maintenance of Emergency Locator Transmitters (ELTs) | 2020-03-09 | Yes |
| 571-026 | Parts Removed from an Aircraft No Longer in Service and Disposal of Scrapped Parts | 2025-07-09 | Yes |
| 573-002 | Aircraft Certification Authority Based on Foreign Qualifications | 2025-12-31 | Yes |
| 573-003 | Trade Standards for Personnel Working in Approved Maintenance Organizations | 2013-10-31 | Yes |
| 573-006 | Maintenance and Operations in Accordance with the Technical Arrangement – Maintenance Between Canada and the United Kingdom | 2025-03-28 | Yes |
| 573-008 | Approved Maintenance Organization Certificate: Application and Amendment Procedures | 2026-02-11 | Yes |
| 573-009 | Technical Arrangement – Maintenance Between Canada and Brazil | 2024-02-14 | Yes |
| 573-010 | Maintenance Annex Guidance – Bilateral Aviation Safety Agreement between Canada and the European Union | 2024-11-15 | Yes |

**AC 571-005** was cancelled because it "has been found to contain misleading information". Its page now holds only the cancellation notice. The manifest keeps it with the status `cancelled`, so it is on record but stays out of the snapshot. A question about major repairs after substantial damage is a candidate for the unanswerable questions in the seed set.

## What the rule leaves out

- **Other standards**, such as Standard 625 (Aircraft Equipment and Maintenance), even though Subparts 571 and 573 refer to them.
- **Other parts of the CARs.** The XML is downloaded whole, but the parser keeps only Subparts 571 and 573.
- **French versions** of the Transport Canada documents, and translations of any kind.
- **Cancelled ACs**, as above.

## How each field was filled in

All the documents were downloaded on 2026-11-04, and each SHA-256 was computed from the downloaded file.

| Field | FAA handbooks | CAR XML | Standards | ACs |
| --- | --- | --- | --- | --- |
| Edition | "B (2023)", as printed on the cover | The consolidation date | The latest amendment date | The issue number on the page |
| Content date | The PDF's creation date (only the year is printed) | The `ConsolidationDate` in the XML | The latest "(amended …)" date in the text | The effective date on the page |
| Page-modified date | The `Last-Modified` header of the PDF | The date of the pinned commit | The page's "Date modified" | The page's "Date modified" |

**Two of these dates differ from what the page says:**

- Standard 571 says "Content last revised: 2010/12/01", but its text contains an amendment dated 2010/12/30.
- Standard 573 says "Content last revised: 2012/06/01", but its text contains an amendment dated 2022/12/07.

In both cases, the content date is the latest amendment in the text.

**Stable hashes.** Each Transport Canada page gave the same SHA-256 when it was fetched twice, about 30 seconds apart. The hash covers the whole page, including the site's menus and footer, so a change to the site's layout would change it even if the text didn't.

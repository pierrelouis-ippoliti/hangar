# Notice

**Hangar - cited answers from aircraft maintenance documents.** Its code is released under the [MIT licence](LICENSE). This file covers the documents Hangar reads and quotes: they are not Hangar's, they are not stored in this repository, and each stays under its publisher's terms. [ADR-0003](docs/adr/0003-licences.md) records why.

## What Hangar does with the documents

- **It never redistributes them.** The documents are not in this repository, there is no DVC remote, and no release carries them. Each clone downloads them from the sources in [`corpus/manifest.yaml`](corpus/manifest.yaml) and checks each file's SHA-256.
- **It quotes them word for word.** Excerpts are never modified, summarised as if quoted, or translated. Each one carries the document's full title, its publisher and the address of the official version (`official_url` in the manifest).
- **It is not approved maintenance data.** Every answer ends with that notice.
- **It is an independent project.** Hangar is not affiliated with or endorsed by the Federal Aviation Administration, Transport Canada, the Department of Justice Canada or the Internet Archive.

## FAA Aviation Maintenance Technician Handbooks

| ID | Document |
| --- | --- |
| `faa-h-8083-30b` | FAA-H-8083-30B, Aviation Maintenance Technician Handbook – General |
| `faa-h-8083-31b` | FAA-H-8083-31B, Aviation Maintenance Technician Handbook – Airframe |
| `faa-h-8083-32b` | FAA-H-8083-32B, Aviation Maintenance Technician Handbook – Powerplant |

**Terms.** These handbooks are works of the United States Government. [17 U.S.C. §105(a)](https://www.law.cornell.edu/uscode/text/17/105):

> Copyright protection under this title is not available for any work of the United States Government, but the United States Government is not precluded from receiving and holding copyrights transferred to it by assignment, bequest, or otherwise.

**Figures from other people.** Each handbook's "Acknowledgments" page credits outside contributors for some of its images, a few of them under their own licences. The General handbook, for example, credits imagery from Wikimedia Commons under CC BY-SA 2.0 FR. §105 doesn't make those images free to reuse: **check a figure's credit line before republishing it.** Hangar v0 quotes text only, never figures.

**Attribution:** *FAA-H-8083-31B, Aviation Maintenance Technician Handbook – Airframe*, Federal Aviation Administration, with the official URL.

## Canadian Aviation Regulations

| ID | Document |
| --- | --- |
| `car-sor-96-433` | Canadian Aviation Regulations (SOR/96-433), consolidated to 2026-06-18 |

Hangar reads Subparts 571 and 573 only, from the XML in the Department of Justice's [justicecanada/laws-lois-xml](https://github.com/justicecanada/laws-lois-xml) repository, at a pinned commit. That repository is released under the Open Government Licence – Canada, as stated in its `LICENSE.md`.

**Terms.** The [Reproduction of Federal Law Order (SI/97-5)](https://laws-lois.justice.gc.ca/eng/regulations/SI-97-5/FullText.html):

> Anyone may, without charge or request for permission, reproduce enactments and consolidations of enactments of the Government of Canada, and decisions and reasons for decisions of federally-constituted courts and administrative tribunals, provided due diligence is exercised in ensuring the accuracy of the materials reproduced and the reproduction is not represented as an official version.

Hangar quotes the regulations exactly as the XML holds them and never presents a quote as the official version. The official version is on the [Justice Laws website](https://laws-lois.justice.gc.ca/eng/regulations/SOR-96-433/).

**Attribution:** *Canadian Aviation Regulations (SOR/96-433)*, consolidated to 2026-06-18, Department of Justice Canada. Not the official version; the official version is at <https://laws-lois.justice.gc.ca/eng/regulations/SOR-96-433/>.

## Transport Canada standards and advisory circulars

| ID | Document |
| --- | --- |
| `tc-std-571` | Standard 571 – Maintenance |
| `tc-std-573` | Standard 573 – Approved Maintenance Organizations |
| `tc-ac-571-002` | AC 571-002, Maintenance Implementation Procedures – Bilateral Aviation Safety Agreement Between Canada and United States |
| `tc-ac-571-004` | AC 571-004, Installation Eligibility of Substitute or Replacement Bearings |
| `tc-ac-571-005` | AC 571-005, Major Repair After Substantial Damage (cancelled; kept on record, never fetched) |
| `tc-ac-571-006` | AC 571-006, Electronic Signatures and Electronic Exchange of the Authorized Release Certificate – Form One |
| `tc-ac-571-024` | AC 571-024, Documentation Required for the Installation of Parts onto Canadian Registered Aircraft |
| `tc-ac-571-025` | AC 571-025, Maintenance of Emergency Locator Transmitters (ELTs) |
| `tc-ac-571-026` | AC 571-026, Parts Removed from an Aircraft No Longer in Service and Disposal of Scrapped Parts |
| `tc-ac-573-002` | AC 573-002, Aircraft Certification Authority Based on Foreign Qualifications |
| `tc-ac-573-003` | AC 573-003, Trade Standards for Personnel Working in Approved Maintenance Organizations |
| `tc-ac-573-006` | AC 573-006, Maintenance and Operations in Accordance with the Technical Arrangement – Maintenance Between Canada and the United Kingdom |
| `tc-ac-573-008` | AC 573-008, Approved Maintenance Organization Certificate: Application and Amendment Procedures |
| `tc-ac-573-009` | AC 573-009, Technical Arrangement – Maintenance Between Canada and Brazil |
| `tc-ac-573-010` | AC 573-010, Maintenance Annex Guidance – Bilateral Aviation Safety Agreement between Canada and the European Union |

**Terms.** Transport Canada's pages link to the [Canada.ca terms and conditions](https://www.canada.ca/en/transparency/terms.html), read on 2026-11-05:

> **Non-commercial reproduction**
>
> Unless otherwise specified you may reproduce the materials in whole or in part for non-commercial purposes, and in any format, without charge or further permission, provided you do the following:
>
> - exercise due diligence in ensuring the accuracy of the materials reproduced
> - indicate both the complete title of the materials reproduced, as well as the author (where available)
> - indicate that the reproduction is a copy of the version available at [URL where original document is available]
>
> **Commercial reproduction**
>
> Unless otherwise specified, you may not reproduce materials on this site, in whole or in part, for the purposes of commercial redistribution without prior written permission from the copyright administrator.

How Hangar meets them:

- **Non-commercial use.** Hangar is a non-commercial project. Any commercial use of the quotes would need Transport Canada's written permission first.
- **Accuracy.** Quotes are word for word, never modified or translated.
- **Title, author and source.** Each quote gives the complete title, names Transport Canada as the author, and says it is a copy of the version at the page's official URL.
- **No endorsement.** Each quote also states that Hangar is not affiliated with or endorsed by Transport Canada.

**Where the copies come from.** The live pages change their bytes whenever the site rebuilds its cache, even when the text doesn't. So `hangar fetch` downloads each page from a fixed snapshot in the Internet Archive's [Wayback Machine](https://web.archive.org/) ([why](corpus/c1-scope.md#where-the-transport-canada-pages-come-from)). The content is still Transport Canada's, and citations point to the official page, never to the snapshot.

**Attribution:** *AC 571-025, Maintenance of Emergency Locator Transmitters (ELTs)*, Transport Canada. A copy of the version available at the official URL. Hangar is not affiliated with or endorsed by Transport Canada.

## Hangar's own annotations

The questions, reference answers and labels written for Hangar's evaluation sets will be released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with a licence file in their folder when the first set is committed. A quote inside an annotation stays under its source's terms above.

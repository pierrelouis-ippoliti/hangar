# ADR-0003: Licences for the code, the annotations and the documents

- **Status:** accepted
- **Date:** 2026-11-05
- **Issue:** #14

## Context

Hangar publishes four kinds of material, and each has its own owner:

- **The code**, written for Hangar.
- **The annotations:** the questions, reference answers and labels of the evaluation sets, also written for Hangar. The first set is the v0 seed set.
- **Quotes** from the documents, in answers, evaluation sets, docs and posts.
- **The documents themselves:** the FAA handbooks, the CARs, and Transport Canada's standards and advisory circulars.

The documents' terms, quoted in [`NOTICE.md`](../../NOTICE.md), set the limits:

- **FAA handbooks:** works of the United States Government, with no copyright under 17 U.S.C. §105. Some figures, though, are credited to outside contributors under their own terms.
- **CARs:** anyone may reproduce them if the reproduction is accurate and not presented as the official version (SI/97-5).
- **Transport Canada pages:** non-commercial reproduction is allowed with the complete title, the author and the address of the original. Commercial redistribution needs written permission.

## Decision

- **Code:** MIT, as in `LICENSE` since M0.
- **Annotations:** CC BY 4.0. Each evaluation set's folder gets a licence file when the set is first committed.
- **Quotes:** stay under their source's terms. They are reproduced word for word, never modified or translated, with the attribution that `NOTICE.md` gives for each source.
- **Documents:** never redistributed. They are not committed, there is no DVC remote, and no release carries them. Every clone downloads them from the sources in `corpus/manifest.yaml` and checks their SHA-256.

## Alternatives

- **Apache 2.0 for the code.**
  - It adds an explicit patent grant, and asks every distribution to carry a NOTICE file.
  - Hangar holds no patents, and the patent grant would add nothing.
  - MIT is shorter, already in place, and asks only that the licence text stays with the code.
- **Committing the corpus to the repository.**
  - Every clone would rebuild without the network, and would never depend on a source staying online.
  - But Hangar's MIT licence allows commercial use, and a clone could then redistribute Transport Canada's pages commercially. Transport Canada's terms forbid that without permission.
  - Some FAA figures are not the US Government's to give away.
  - The files take 425 MB, which git handles badly.

## Consequences

- Anyone can reuse, fork or sell Hangar's code and annotations. Reusing the quotes stays bound by their sources' terms, which `NOTICE.md` spells out.
- Rebuilding needs the network, and depends on the sources staying online. If a source disappears or changes, its hash no longer matches, the fetch stops, and the corpus moves to a new snapshot. The Wayback snapshots of the Transport Canada pages make that less likely.
- The generation stage (M4) must attach each source's attribution to every quote it shows: the full title, the publisher and the official URL. For Transport Canada, that includes "a copy of the version available at" and the statement that Hangar is not affiliated with or endorsed by Transport Canada.
- The issue that commits the seed set (`eval/seed/questions.jsonl`) must add the CC BY 4.0 licence file next to it.
- Any commercial use of Transport Canada quotes would first need Transport Canada's written permission.

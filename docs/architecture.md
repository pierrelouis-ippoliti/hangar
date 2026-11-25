# Architecture

Hangar's code is a set of small stages that read files and write files, with every external service behind an interface. This page describes the rules the code follows and how data moves through it. Each stage section is filled in by the issue that builds the stage.

## Principles

1. **Stages are functions over artifacts.** Each stage reads its inputs, writes new outputs and never modifies its inputs, so a rerun gives the same result.
2. **Domain types sit at the centre and do no I/O.** Documents, passages, chunks and answers are validated data objects.
3. **External systems sit behind small interfaces.** Qdrant, Mistral, Hugging Face and HTTP downloads are reached through interfaces, and tests swap them for fakes.
4. **A variant is a configuration file, not a code branch.** Nothing in the code asks which version it is running.
5. **Every artifact records where it came from:** the configuration hash, the commit, the input hashes and the model revisions.
6. **Identifiers derive from content and location,** never from the order of a run.
7. **Validation happens at every boundary,** with error messages that name the file and the field.
8. **An interface exists only where a named later version needs it.** Notebooks never write artifacts.

## Data flow

v0 has five build stages, each writing one artifact, and one answering path that reads the index. The build runs once per corpus snapshot. The answering path runs once per question.

```mermaid
flowchart LR
    subgraph build ["Build: once per corpus snapshot"]
        direction LR
        manifest["corpus/manifest.yaml"] --> fetch(["fetch"])
        fetch --> raw["data/raw/"]
        raw --> parse(["parse"])
        parse --> parsed["data/parsed/"]
        parsed --> chunk(["chunk"])
        chunk --> chunks["data/chunks/"]
        chunks --> embed(["embed"])
        embed --> vectors["data/vectors/"]
        vectors --> indexer(["index"])
        indexer --> collection[("Qdrant collection")]
    end

    subgraph answering ["Answer: once per question"]
        direction LR
        question["question"] --> retrieve(["retrieve top 5"])
        retrieve --> render(["render prompt"])
        render --> llm(["Mistral"])
        llm --> cite(["parse citations"])
        cite --> record["answer record"]
    end

    collection --> retrieve
```

Rounded boxes are steps; square boxes are the files they read and write. Each build stage reads only the previous artifact, so the embed stage can run on a borrowed notebook GPU and hand back its vectors file, while the other stages stay on the laptop.

## Package layout and dependency rules

All the code lives in one package, `src/hangar/`, split by stage. A package folder is created when its first real file arrives, so most of the folders below don't exist yet.

| Package | Holds |
| --- | --- |
| `core` | Domain types, configuration models, identifiers, provenance, run and answer records, costs, errors |
| `observability` | Logging set-up, run recorder |
| `files` | Reading the YAML files that configure Hangar, such as the manifest and the pipeline file, file hashes, and replacing a stage's output folder whole |
| `pacing` | The rate limiter, the retryable statuses and the backoff that the downloader and the Mistral client share |
| `corpus` | Manifest loading and validation, downloader, hash checks |
| `parsing` | FAA PDF pages, CAR XML, Transport Canada HTML, normalisation, parse report |
| `chunking` | Chunker interface, fixed-token chunker, token counter |
| `embedding` | Embedder interface, sentence-transformers adapter, hash embedder for tests |
| `indexing` | Vector index interface, Qdrant adapter, collection naming, index manifest |
| `retrieval` | Retriever interface, dense retriever |
| `generation` | Prompt rendering, LLM client interface, Mistral adapter, rate limiter, citations |
| `evaluation` | Seed set loading, scoring sheet export, summary |
| `pipelines` | The build, answer and seed-run pipelines, and the registry that turns configuration into objects |
| `cli` | The `hangar` command |

Dependencies point one way, from top to bottom:

```text
cli
└── pipelines
    └── retrieval
        └── corpus | parsing | chunking | embedding | indexing | generation | evaluation
            └── observability | files | pacing
                └── core
```

- `core` imports nothing else from `hangar` and does no I/O.
- `files` imports only `core`. It reads YAML files for the stages and `pipelines`, which then pass the content to `core` to validate.
- `pacing` imports nothing else from `hangar`. It only waits, so it needs no domain type.
- The stage packages import `core`, `observability`, `files` and `pacing`, never each other. The one exception is `retrieval`, which may use the embedding and indexing interfaces because it combines them.
- Adapters for Qdrant, Mistral, sentence-transformers and pypdfium2 live inside their stage package. Only `pipelines` constructs them, through a registry keyed by the type names in the configuration. Swapping one of them therefore touches one registry entry and one configuration file.
- `pipelines` imports the stages and `core`. `cli` imports only `pipelines` and `observability`.
- Every layer may use `observability`.

import-linter checks these rules in CI, through the contracts in `pyproject.toml`:

- **Layers:** the order above. Packages that don't exist yet are optional, so the contract already holds and starts checking each package as soon as it appears.
- **cli:** `cli` imports nothing but `pipelines` and `observability`.
- **Adapter libraries:** only `parsing` and `pipelines` import pypdfium2 and lxml, only `chunking` and `pipelines` import tokenizers and huggingface_hub, only `embedding` and `pipelines` import sentence-transformers, transformers and torch, and only `indexing` and `pipelines` import qdrant-client. Each contract checks every module of `hangar` and exempts the allowed packages, so a new package is checked from its first file.
- **retrieval:** `retrieval` may use the embedding and indexing interfaces, but no other stage and neither adapter module (`embedding.st_embedder`, `indexing.qdrant`). `pipelines` builds the adapters and passes them in.
- **Mistral adapter:** the Mistral client calls the API with the standard library, so there is no library to fence in. Instead, only `pipelines` may import the adapter module, `generation.mistral`; the rest of the code sees the `LlmClient` interface.

## Commands and logs

`hangar` has one subcommand per stage, plus `doctor`. Each takes `--config`, the pipeline file (`configs/pipelines/v0.yaml` by default). `cli` only parses the command line; `pipelines.commands` runs the command:

1. It reads the environment settings and the pipeline file. An unusable file of either kind is reported on the screen, since no run has started yet.
2. It starts a run with its own ID, such as `20261105T142233Z-1a2b3c4d`: the start time in UTC and the first eight characters of the configuration hash. The log file and the run record of an answering run share this ID. Two runs of the same configuration started in the same second get the same ID, and their logs go to one file.
3. It logs the pipeline file's path and configuration hash, runs the command and returns the exit code: 0 on success, 1 on failure. A command that succeeds ends its log with its duration, so every stage records how long it ran.

Every record goes to two places: a JSON lines file, `<data folder>/logs/<run ID>.jsonl`, and the screen, as readable lines. Each record carries the run ID, the stage and the document being worked on. Code logs through the standard library (`logging.getLogger(__name__)`), and a `log_context` block in `observability.logs` supplies those three values, so the code that logs never passes them along.

The Mistral API key is replaced by `[REDACTED]` before any record is written, in messages, arguments and tracebacks alike, and in records from other libraries too. Errors are logged rather than left to print their own traceback, so they go through the same redaction.

`hangar doctor` checks Python 3.12 or later, Qdrant's `/readyz` endpoint, that `MISTRAL_API_KEY` is set (without calling the API), 2 GB of free space for the data folder, and that the pinned embedding model is in the Hugging Face cache or can be downloaded there. It reports each check as pass or fail, and exits with 1 if any fails.

## Run records

The language model's output can vary even at temperature 0, so every answer is stored rather than assumed reproducible. An answering run, such as `hangar ask` or `hangar seed run`, keeps two kinds of record, both defined in `core.records`:

- **Answer record**, one per question: the run ID, the seed question's ID (none for `hangar ask`), the question, a reference to each retrieved chunk (its ID, score, document ID and pages or sections, never its text), the prompt version, the completion with its token counts, the citations (invalid ones included), the retrieval and generation times, and the cost.
- **Run record**, one per run: the run ID, the configuration hash, the git commit and dirty flag (none outside a git checkout), whether it was a release run, the snapshot, the embedding model and its revision, the language model's dated ID, the start and end times, and the totals over its answers: the number of answers, the input and output tokens, the cost, and the retrieval and generation times.

Answer records are committed, and the documents are never redistributed ([ADR-0003](adr/0003-licences.md)), so a record keeps where each chunk is, not what it says; the chunk ID finds the text again in the chunks file.

Times are in seconds. Retrieval time includes embedding the question. Generation time is the whole language model call, waits for the rate limit and retries included, so it can be longer than the completion's latency, which counts only the request that succeeded.

**Cost** (`core.costs`). Tokens are priced from the `prices` table of the pipeline file, in US dollars per million tokens, keyed by model ID. Every cost has two figures: the free tier, which is zero in v0, and the list price, what the same tokens would cost at Mistral's published price. v9 compares the list price with the cost of a self-hosted model.

**The recorder** (`observability.recorder`). `RunRecorder` is the interface, so v1 can add a recorder that sends the records to Weights & Biases. `FileRunRecorder` writes both kinds into a new folder of the run's own: each answer is appended to a JSON lines file, such as `seed-run.jsonl`, as soon as it is made, and the run record goes to `run.json` at the end. It refuses a folder that already exists, naming it in the error, so two runs that got the same ID in the same second can't overwrite each other. Tests point it at a temporary folder.

**The run** (`pipelines.runs.AnsweringRun`) ties these together: it records each answer, then builds the run record from the configuration and the answers. A release run refuses to start when the checkout has changed or untracked files, or isn't a git checkout, so the commit it records is exactly the code that ran.

**The code version** (`pipelines.provenance`). `code_version` returns the commit and the dirty flag as a `core.provenance.CodeVersion`. The build stages only log it: their committed reports leave it out, since a report written before its own commit would always say dirty.

## Stages

### Fetch

`hangar fetch` makes sure every active document of the snapshot is in `<data folder>/raw`, with the SHA-256 the manifest gives. It downloads only from the manifest's URLs.

1. It reads the manifest named by `corpus.manifest` and keeps the active documents of `corpus.snapshot`. Cancelled documents stay in the manifest but are never fetched. Each document is downloaded from its `source_url`. For Transport Canada pages, that is a fixed Wayback Machine snapshot, because the live pages' bytes change with the site's cache ([why](../corpus/c1-scope.md#where-the-transport-canada-pages-come-from)). `official_url` keeps the live page for citations.
2. Each document's file is named by its raw artifact ID, the document ID plus its format: `faa-h-8083-31b.pdf`, `car-sor-96-433.xml`, `tc-ac-571-002.html`.
3. A file already there with the right hash is kept, so a second run downloads nothing.
4. Otherwise the file is downloaded to `<ID>.part`, hashed as it streams to disk, and renamed only if its hash matches. A mismatch or a failed download stops the run, with an error that starts with the document ID. The files fetched before it are kept.
5. Each download is added to `data/logs/fetch-log.jsonl` as a raw artifact record: path, SHA-256, size, fetch time, and the server's `ETag` and `Last-Modified` headers. The log stays out of `data/raw`, so that folder holds only the documents and its hash in `dvc.lock` is the same on every machine.

The downloader is an interface with two versions:

- **`HttpDownloader`:** uses the standard library, with no extra dependency. It reads and hashes 1 MiB at a time, so the 205 MB Powerplant handbook never sits in memory. It sends a `User-Agent` that names Hangar and its repository, leaves at least one second between requests, and retries 429 and 5xx answers and network errors up to three times, waiting 2 then 4 seconds. Other answers, such as 404, fail at once.
  - It decodes gzip-encoded answers while they stream, at most 1 MiB at a time, so the file and its hash are those of the document itself. The Wayback Machine sends gzip even when asked for none.
  - It refuses any file larger than 1 GB once decoded. The largest C1 file is 215 MB.
- **`LocalCopyDownloader`:** copies local files instead, so tests never touch the network.

The `fetch` DVC stage depends on `corpus/manifest.yaml` and on the `corpus` section of the pipeline file. Its output, `data/raw`, has `cache: false`, because the documents are not Hangar's to store, and `persist: true`, so DVC doesn't delete the files before a rerun and fetch can skip them.

### Parse

The parse stage turns each downloaded file into one canonical text, split into passages: one per PDF page, or one per numbered section of a regulation, standard or advisory circular. [ADR-0005](adr/0005-locations-and-identifiers.md) explains these choices.

- **Canonical text.** `parsing.normalise` applies Unicode NFKC, turns every line ending into a plain newline, and collapses runs of spaces and tabs into one space, as `parsing.normalisation` in the pipeline file sets. Newlines stay, so paragraphs and list items stay apart.
- **Passages** (`core.parsed`) are character ranges of the canonical text, and cover it exactly once. `ParsedDocument` rejects gaps, overlaps, duplicate IDs, and passages that don't start at 0 or don't reach the end of the text.
- **Locations.** A page passage holds its 1-based index in the PDF, which is canonical, and the printed page label when the PDF has one. A section passage holds its label, such as `571.10`, and its heading path. The text before the first numbered section is a front-matter passage with no label.
- **IDs** derive from the document and the location: `faa-h-8083-31b#p142`, `car-sor-96-433#s571.10`, `tc-std-571#front`.
- **Assembly.** Every parser cuts its document into parts and hands them to `parsing.assemble`. It normalises and trims each part, then joins them with a blank line. Each passage includes the blank line that follows it, so the passages cover the text by construction. An empty page keeps a zero-length passage, so page numbers stay continuous.
- **From offsets to locations.** `ParsedDocument.passages_in_range(start, end)` returns the passages a range of the text covers. The chunker uses it to find a chunk's pages or sections. Empty passages hold no text, so no range covers them.
- **Parsers** follow the `parsing.parser.Parser` interface: a manifest entry and a downloaded file in, a parsed document out. Each records its name, the version of its library, the SHA-256 of the file it read, and its warnings, such as empty pages.

**PDF pages.** `parsing.pdf.PdfPageParser` reads the FAA handbooks with pypdfium2 ([ADR-0004](adr/0004-pypdfium2-for-pdf-text.md)):

- Each page gives one passage, with the text PDFium extracts, its 1-based index, and its printed label when the PDF has page labels. FAA-H-8083-31B has none.
- The text is kept as extracted, running headers and page numbers included. The only correction: PDFium returns a hyphen it joins across a line break as `U+FFFE`, and the parser puts the hyphen back.
- A page with no text gets an `empty_page` warning. A page with control, private-use or unassigned characters, such as a figure whose font has no Unicode mapping, gets a `garbled_page` warning. C1 gives 3 empty covers and 2 garbled pages.
- A file PDFium can't open raises a `ParseError` that starts with the document ID.

**CAR sections.** `parsing.car.CarXmlParser` reads the Justice Canada XML of the regulations with lxml:

- It keeps the sections whose label starts with one of `parsing.car.subparts`, 571 and 573 in v0, in document order: 31 sections, the partly repealed ones included. A configured subpart with no section is an error.
- Headings don't wrap their sections in this XML: `Heading` elements with a level from 1 to 5 sit next to the `Section` elements. A section's heading path is the latest heading at each level before it, such as `Part V — Airworthiness › Subpart 71 — Aircraft Maintenance Requirements › Maintenance Release`. A heading's history note stays out of it.
- A section's text starts with the headings that came after the previous section, so the canonical text keeps them in order. Then each `Text` becomes one line, led by the labels above it: `571.02 (1) …`, `(a) …`, `(i) …`. Cross-references stay inline, and the history note becomes a last line, as the consolidation prints it. Reserved ranges, such as 573.16 to 573.29, have no section and stay out.
- Entities are never resolved and nothing is fetched from the network, so a downloaded file can't make the parser read other files.

**Transport Canada sections.** `parsing.tc_html.TcHtmlParser` reads the standards and advisory circulars with lxml:

- The content is the one element that the document type's selector in `parsing.tc_html.content_selectors` picks. Selectors are XPath expressions, `//main` for every C1 page, so no CSS selector library is needed. A selector that picks no element or several is an error.
- A heading from `h2` to `h6` whose text starts with a section number, such as `571.10` or `4.1.1`, starts a passage labelled with that number. Heading levels differ from page to page, so the number decides, not the level. Unnumbered headings, such as "Types of Work" or an appendix after the last section, stay in the section before them. Two sections with the same number are an error.
- The text before the first numbered section, the title, table of contents and preamble, is the front-matter passage. A page with no numbered section is one front-matter passage with a `no_sections` warning.
- A section's heading path is the page title, then the numbered headings above it: `Advisory Circular (AC) No. 571-024 › 4.0 … › 4.2 …`.
- Each block element, such as a paragraph, list item, table row or heading, becomes one line. Table cells are separated by a space, scripts and styles are left out, and the page details at the end of `<main>` ("Date modified") stay in the last section.

**The command.** `hangar parse` runs the stage:

1. It reads the active documents of the snapshot from the manifest, and logs the git commit and whether the checkout has changes. These go in the log, not in the results, because a report written before its own commit would always say it has changes.
2. The registry in `pipelines.registry` builds one parser per format: PDF, XML and HTML. Each document is read from `<data folder>/raw/<document ID>.<format>`. A missing file, or one its parser can't read, stops the run with an error that starts with the document ID.
3. It writes the parse report to `results/<run name>/parse-report.json`, which is committed. For each document, the report holds:
   - the format, the SHA-256 of the file read, and the parser and library versions;
   - the number of characters and passages;
   - pages, empty pages and garbled pages for PDFs, or numbered sections for the other formats;
   - the parser's warnings.

   It holds the configuration hash, but no time, run ID or commit, so the same files, configuration and code give the same report.
4. It checks each document against `parsing.checks`: a minimum number of characters, a minimum number of numbered sections, and a maximum share of empty and of garbled PDF pages. Every failing document is listed, one line each, and the run stops. The report is still written, so the failure can be read.
5. Only when every check passes does it write `<data folder>/parsed/<snapshot>/<document ID>.json`: the parsed document with the configuration hash (`core.parsed.ParsedFile`). The folder is written next to the old one, then replaces it whole, so it never mixes two runs.

The `parse` DVC stage depends on the manifest, `data/raw`, the parsing code, and the `corpus`, `parsing` and `run.name` settings. Like `data/raw`, its outputs have `cache: false`: the parsed files hold the documents' text, and the report is in git.

### Chunk

The chunk stage splits each canonical text into chunks of at most 512 tokens, with no overlap, as `chunking` in the pipeline file sets. Tokens are counted with the embedder's own tokenizer, so "512 tokens" means what BGE-M3 sees ([ADR-0006](adr/0006-tokens-counted-with-the-embedder-tokenizer.md)).

- **Chunks** (`core.chunks.Chunk`) hold their document ID, chunker ID, start and end offsets into the canonical text, their text, their token count, and the passages they cover, each with its ID and location. A chunk that crosses a page break lists both pages. Empty pages hold no text, so no chunk lists them.
- **IDs.** The chunker ID names the configuration: `fixed512`, or `fixed256-o32` when chunks overlap. A chunk's ID is the first 16 hex characters of the SHA-256 of `<document>|<chunker>|<start>|<end>`, so it stays the same from run to run and changes when the parse or the chunker changes. The model rejects an ID that doesn't match, an empty range, and a text whose length doesn't match the offsets.
- **Token counter** (`chunking.tokens.TokenCounter`): counts a text's tokens, and lists where each token starts. Both leave out the special tokens the model adds. `chunking.hf_tokenizer.HfTokenCounter` reads BGE-M3's `tokenizer.json` at the pinned revision, with truncation turned off. `WhitespaceCounter`, which counts words, stands in for it in tests.
- **Fixed-token chunker** (`chunking.fixed.FixedTokenChunker`), behind the `chunking.chunker.Chunker` interface, so v2 can add a structure-aware chunker:
  1. It tokenizes the whole text once.
  2. It cuts where token 512 starts, then counts that chunk's text again on its own. A tokenizer can split a piece of text a little differently on its own, so while the count is over 512 the cut moves back one token. On C1, 282 of the 3,627 chunks count 510 or 511 on their own.
  3. The next chunk starts at the cut. The first chunk starts at 0 and the last ends at the end of the text, so the chunks cover the text exactly once.
  4. A text with no tokens, or a single token that counts over 512 on its own, stops the run with an error that starts with the document ID.

**The command.** `hangar chunk` runs the stage:

1. It reads every file in `<data folder>/parsed/<snapshot>/`, in file name order. No parsed file stops the run and asks for `hangar parse`.
2. The registry builds the chunker, with the tokenizer of the model named in `embedding`. The tokenizer, about 17 MB, is downloaded the first time, then read from the Hugging Face cache. The model weights aren't needed.
3. It writes `<data folder>/chunks/<snapshot>/<chunker ID>/chunks.jsonl`, one chunk per line, in document ID order, then in text order.
4. Next to it, `meta.json` (`core.chunks.ChunksMeta`) records the configuration hash, the tokenizer's model and revision, the SHA-256 of each parsed file read, and the numbers of chunks and tokens. Like the parse report, it holds no time, run ID or commit, so the same inputs give the same file.

The folder is written next to the old one, then replaces it whole (`files.replace_folder`). On C1, the stage takes about 6 seconds and gives 3,627 chunks and 1,851,452 tokens from 18 documents.

The `chunk` DVC stage depends on `data/parsed/c1`, the chunk model and the chunking code, and on `corpus.snapshot`, `chunking`, `embedding.model` and `embedding.revision`: a new embedder means a new tokenizer. Its output has `cache: false`, because the chunks hold the documents' text.

### Embed

The embed stage turns each chunk into one vector with the dense output of BGE-M3, through sentence-transformers. Its sparse and multi-vector outputs wait for v3.

- **Embedder interface** (`embedding.embedder.Embedder`): `embed_documents` for chunks and `embed_query` for questions, because some models encode them differently. BGE-M3 encodes both the same way. An embedder reports its model ID, revision, dimension, and whether its vectors are normalised.
- **BGE-M3** (`embedding.st_embedder.SentenceTransformerEmbedder`): `BAAI/bge-m3` loaded at the commit hash in `embedding.revision`, with unit-length vectors of 1,024 values. The batch size comes from `embedding.batch_size`, and the device from the `HANGAR_DEVICE` setting (`cpu`, `cuda` or `mps`). The registry imports this module only when it builds the embedder, because sentence-transformers loads torch, which takes seconds; the other commands start without it.
- **Only the pinned weights are fetched.** The pinned revision has only `pytorch_model.bin`. After loading such a file, transformers starts a thread that downloads a safetensors copy (2.3 GB) from a bot's pull request on the model page, an unpinned branch. The model never loads that copy, so the adapter turns this off with `DISABLE_SAFETENSORS_CONVERSION`, and a model test checks it.
- **Hash embedder** (`embedding.embedder.HashEmbedder`), for tests: a unit-length vector derived from the text's SHA-256. The same text always gives the same vector, and no model is loaded.
- **Model contract test** (`tests/corpus/test_bge_m3_embedder.py`, marked `model`): 1,024 dimensions, unit length, and a match with a reference vector in `tests/fixtures/embedding/`, made once on the CPU. The match is close, not exact, because the CPU and the GPU round floats differently.

**The command.** `hangar embed` runs the stage:

1. It reads `<data folder>/chunks/<snapshot>/<chunker ID>/chunks.jsonl` and nothing else. A missing file asks for `hangar chunk`, and a chunk listed twice stops the run.
2. It sends the chunks to the model 20 batches at a time, and logs its progress after each group.
3. It checks that there is one vector per chunk and that every vector has the model's dimension.
4. It writes `<data folder>/vectors/<snapshot>/<chunker ID>/<embedder ID>/vectors.parquet`, such as `vectors/c1/fixed512/bge-m3-dense/`. Each row (`core.vectors.VectorRecord`) holds the chunk ID, the model ID, its revision, and the vector as 32-bit floats: 4 KB per chunk. The embedder ID is the model name and its output, `bge-m3-dense`.
5. Next to it, `meta.json` (`core.vectors.VectorsMeta`) records the configuration hash, the model, its revision, the dimension, normalisation, the SHA-256 of the chunks file, and the number of vectors. Like the other `meta.json` files, it holds no time, run ID or commit.

The folder replaces the old one whole, like the other stages' outputs. On C1, the stage took 25 minutes on the laptop's NVIDIA T600 (4 GB) for the 3,627 chunks, with GPU memory at about 2.5 GiB for batch 16, and writes a 15.6 MB file. On the CPU, it would take about an hour.

The `embed` DVC stage depends on the chunks file, the vector models, the embedding code and the `embedding` settings. Unlike the other stages, its output uses DVC's cache: the vectors hold no document text, and they are slow to rebuild.

**Running it on a notebook GPU.** The stage reads only the chunks file and writes only the vectors folder, so it can run on a borrowed GPU, such as a Kaggle or Modal notebook, while the other stages stay on the laptop:

1. On the laptop, run `uv run hangar chunk`, then upload `data/chunks/c1/fixed512/chunks.jsonl` to the notebook, for example as a private Kaggle dataset. The chunks hold the documents' text, so keep it private.
2. In the notebook, with a GPU and internet access turned on, install Hangar at the commit the laptop uses, with the locked dependency versions:

   ```bash
   git clone https://github.com/pierrelouis-ippoliti/hangar.git
   cd hangar
   git checkout <commit>
   pip install uv
   uv sync --locked --no-dev
   ```

   `uv sync --locked` installs the versions in `uv.lock`. `pip install` would ignore the lock file and could pick other versions of torch and sentence-transformers.
3. Copy the chunks file to `data/chunks/c1/fixed512/chunks.jsonl` inside the clone, then run `HANGAR_DEVICE=cuda uv run hangar embed`.
4. Download the folder `data/vectors/c1/fixed512/bge-m3-dense/` and put it at the same place on the laptop.
5. Check that `chunks_sha256` in its `meta.json` equals `sha256sum data/chunks/c1/fixed512/chunks.jsonl` on the laptop, so the vectors belong to these chunks.
6. Run `uv run dvc commit embed`. DVC records the folder as the stage's output, so `dvc repro` doesn't run the stage again.

### Index

The index stage loads the chunks and their vectors into one Qdrant collection, which the answering path searches ([ADR-0001](adr/0001-qdrant-vector-store.md)).

- **Collection name** (`indexing.naming.collection_name`): the snapshot, the chunker and the embedder, joined by `__`: `c1__fixed512__bge-m3-dense`. Vectors from two chunkers or two models never share a collection. A part that is empty or contains `__` is refused, so a name always splits back into its parts.
- **Vector index interface** (`indexing.index.VectorIndex`): `recreate` deletes the collection and creates it empty, `check` verifies that it exists with the right dimension, `upsert` stores chunks with their vectors, `search` returns the k closest chunks with their scores, optionally filtered on payload fields, and `count` counts the points.
- **Qdrant adapter** (`indexing.qdrant.QdrantIndex`), with cosine distance:
  - A point's ID is its chunk ID read as a 64-bit number, so the same chunk always lands on the same point.
  - Its payload is the whole chunk, text and passages included, so a search returns chunks without reading the chunk files.
  - Filters are equalities on payload fields, such as `{"document_id": "tc-std-571"}`.
  - Points are uploaded 256 at a time.
  - Tests use `QdrantClient(":memory:")`, which runs the same client calls without a server.
- **The registry** imports qdrant-client only when it builds the index, because it takes half a second to import.

**The command.** `hangar index` runs the stage:

1. It reads `chunks.jsonl` and the vectors folder. A missing file asks for `hangar chunk` or `hangar embed`.
2. It checks that the vectors' `meta.json` names the SHA-256 of this chunks file. Otherwise the vectors were made from other chunks, such as an older chunking or a vectors folder copied from a notebook, and the run stops.
3. It checks that chunks and vectors match one to one: the same number, no chunk with two vectors, no vector without its chunk.
4. It deletes the collection and builds it again, then checks that the point count equals the chunk count ([ADR-0008](adr/0008-rebuild-the-collection-on-every-index-run.md)). Running it twice leaves the same points.
5. It writes `results/<run name>/index-manifest.json`, which is committed (`indexing.manifest.IndexManifest`). The manifest records the collection, the snapshot, the chunker, the embedder with its revision and dimension, the distance, the point count, the Qdrant version, the configuration hash, and the SHA-256 of the chunks and vectors files. Like the parse report, it holds no time, run ID or commit; the build time is in the run's log.

On C1, Qdrant builds the 3,627 points in about a second.

The `index` DVC stage depends on the chunks file, the vectors folder, the indexing code, and the `index` and `run.name` settings. The collection lives in a Docker volume that DVC can't see, so the stage has `always_changed: true`: every `dvc repro` rebuilds it, and a wiped volume comes back. The manifest is the same on every run with the same inputs, so later stages don't rerun. It is in git, so DVC doesn't cache it. The stage needs Qdrant running (`make qdrant-up`).

### Retrieve

Retrieval finds the chunks for a question. It is the first step of the answering path, and `hangar search` runs it alone, without the language model.

- **Scored chunk** (`core.retrieval.ScoredChunk`): the chunk, its score, its rank from 1, and the ID of the retriever that found it, so later evaluations can compare retrievers on the same questions.
- **Retriever interface** (`retrieval.retriever.Retriever`): a question in, scored chunks out, best first. v3's sparse, BM25 and hybrid retrievers will follow it.
- **Dense retriever** (`retrieval.dense.DenseRetriever`): it embeds the question with `embed_query`, searches the vector index, and returns the top `retrieval.top_k` chunks, 5 in v0. The score is the cosine similarity of the two vectors.
- **Fixed retriever** (`retrieval.retriever.FixedRetriever`), for tests: it returns the same chunks for every question, so the generation tests of M4 need no embedder or index.

`retrieval` is the one stage package that uses other stages, because it combines the embedder and the vector index. It uses only their interfaces; `pipelines` builds the adapters and passes them in.

**The command.** `hangar search "question"`:

1. A blank question stops the command before anything is loaded.
2. It builds the Qdrant index of the configured collection and the BGE-M3 embedder, then checks that the collection exists with vectors of the model's dimension. If Qdrant isn't running, the error says to run `make qdrant-up`; if the collection is missing, to run `hangar index`.
3. It prints each chunk on standard output, apart from the log lines on standard error: the rank, the score, the document, the pages or sections, then a 160-character excerpt.

   ```text
   1. 0.737  faa-h-8083-30b, p. 323 (7-79)
      ens the nut on the plug. Turnbuckles After a turnbuckle has been properly adjusted, it must be safetied. There are several methods of safetying turnbuckles; how…
   ```

   A page shows its index, and its printed label in brackets when the PDF has one. A section shows `§` and its number, and the text before the first numbered section shows as `front matter`. A chunk that covers several passages shows its first and last: `p. 323 (7-79) to p. 324 (7-80)`.
4. The log records the chunk IDs and scores.

Each search loads the 2.3 GB model again, which takes most of its 9 seconds on the laptop. Keeping the model loaded between questions is in the backlog.

### Generate

Generation turns a question and its chunks into a cited answer. `hangar ask` is still to be written, in #28; the records it writes are described under [Run records](#run-records).

**The prompt.** A prompt file, such as `prompts/answer-v0.md`, has three parts, each starting with a level-1 heading on its own line:

- `# System`: the instructions, sent as the system message.
- `# User`: the user message, with the placeholders `$question` and `$sources`.
- `# Source`: how one source is written into `$sources`, with `$number`, `$label`, `$title`, `$date`, `$location` and `$text`.

The placeholders follow Python's `string.Template`, so a literal dollar sign is written `$$`. The prompt file holds the instructions and the layout of each source, so a new prompt with new wording or layout needs no code change. The values put into a source come from code: the authority and type labels, and the page or section wording. Each part must use all of its placeholders and no others, and a broken file stops the run with an error that names the file and the problem.

The v0 prompt asks for a numbered marker such as `[2]` after every claim, and for Transport Canada requirements to be quoted word for word. It also asks the model to say when the sources don't cover the question. Each source sits in a `<source>` element that the prompt calls quoted material, and the model is told to ignore any instruction inside it. The study-aid notice is not left to the model: `hangar ask` adds it after every answer (#28).

**Prompt files are never edited in place.** Every answer record names its prompt version, so a changed prompt is a new file, such as `answer-v1.md`. A unit test pins the SHA-256 of each prompt file, so an edit in place fails CI.

**The renderer** (`generation.prompt`). `load_prompt_template(folder, version)` reads and checks a prompt file. Its `render` method takes the question, the scored chunks and the manifest entries of their documents. It returns a `core.prompts.RenderedPrompt`:

- the prompt version;
- the messages: the system message, then the user message;
- the source map: one `Source` per chunk, numbered from 1 in rank order, with the chunk ID, the document ID and the passages the chunk covers. The citation parser (#26) uses it to turn a marker into a document and its pages or sections.

Each source is labelled with its authority and type, such as "FAA handbook guidance" or "Transport Canada advisory circular". It also shows the document's title, its content date and where the chunk sits, written the same way as in `hangar search`: `p. 323 (7-79)` or `§ 571.10`. A chunk whose document is missing from the manifest stops the run.

**The language model client** (`generation.llm`). `LlmClient` is the interface: its `complete` method takes the messages, the temperature and the output token limit, and returns a `core.completions.Completion` with the text, the model ID the provider reports, the input and output token counts, the latency and the finish reason (`stop`, or `length` for an answer cut off at the limit). The latency is that of the request that succeeded, without the waits for the rate limit or the failed attempts. There are two clients:

- **`MistralClient`** (`generation.mistral`) sends one POST to Mistral's chat completions endpoint with the standard library, asking for the dated model of the pipeline file, `mistral-small-2603`, at temperature 0 with at most 512 output tokens ([ADR-0007](adr/0007-mistral-small-4-through-the-api.md)).
  - It leaves at least one second between requests, retries included, through `pacing.RateLimiter`, the limiter the downloader uses. The free tier allows one request per second.
  - It retries 429, 500, 502, 503 and 504 answers and network errors, up to four attempts, waiting 2, 4, then 8 seconds, with the status list and backoff of `pacing` that the downloader uses too. Other answers, such as 401 for a wrong key, fail at once with Mistral's explanation.
  - The registry builds it with the key from the environment settings (`MISTRAL_API_KEY`), never from the pipeline file. A missing key stops the command with an error that names the variable.
- **`FakeLlmClient`**, for tests: it returns the same answer to every prompt, citing sources [1] and [2] by default, and counts words as tokens.

A live test (`uv run pytest -m llm tests/llm`, local only) sends the v0 prompt to Mistral once and checks the reply's shape and token counts.

**The citation parser** (`generation.citations`). `parse_citations(answer, sources)` takes the answer text and the source map of its prompt, and returns one `core.citations.Citation` per distinct marker number, in the order each number first appears:

- A number in the source map gives a valid citation, with the chunk ID, the document ID and the passages of that source, so the answer can show its document and pages or sections without another lookup.
- Any other number, such as `[7]` with five sources or `[0]`, gives an invalid citation, with no chunk, document or passages. The answer record keeps it, so wrong markers can be counted.
- An answer with no marker gives no citation.

Only a number in square brackets counts as a marker, as the v0 prompt asks: `[1][3]` gives two citations, while `[1, 3]` or `[OFF]` give none. Checking that a cited source supports its claim is left to v7.

### Evaluate

To be written in #30 to #33.

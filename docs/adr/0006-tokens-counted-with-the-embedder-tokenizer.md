# ADR-0006: Chunk tokens counted with the embedder's tokenizer

- **Status:** accepted
- **Date:** 2026-11-16
- **Issue:** #20

## Context

v0 splits each canonical text into chunks of 512 tokens with no overlap. A chunk's size matters for two reasons:

- **The embedder reads a limited number of tokens.** BGE-M3 accepts 8,192, but the size of a chunk changes what its vector captures, and later versions will compare chunk sizes. Those comparisons only mean something if "512 tokens" is the same quantity in every run.
- **A chunk must never be cut off silently.** If the chunker's count is lower than the embedder's, the end of a chunk could fall outside the model's window and its text would never be embedded.

There is no single "token": a word, a character and a BGE-M3 token are different units. On C1, the 7.97 million characters of the parsed texts make 1.85 million BGE-M3 tokens.

## Decision

Count tokens with the embedder's own tokenizer: BGE-M3's `tokenizer.json`, loaded with the `tokenizers` library at the model revision pinned in the pipeline file. The token counter is an interface (`chunking.tokens.TokenCounter`), so tests count words instead and never load the model.

The rules of the fixed-token chunker:

- **The 512 tokens leave out the special tokens.** BGE-M3 adds `<s>` and `</s>` around every text, so the model sees 514 tokens. That is far below its limit of 8,192, so nothing is cut off.
- **Chunks are cut where a token starts.** The whole text is tokenized once, and each cut falls at a token's first character, so no token is split. With BGE-M3, a token includes the space before it, so a cut falls just before that space.
- **Each chunk's count is its own text, counted again.** A tokenizer can split a piece of text on its own a little differently than the same piece inside the whole text. The chunker counts each chunk's text by itself and moves the cut back one token at a time until the count is at most 512. On C1, 282 of the 3,627 chunks count 510 or 511 on their own.
- **Chunks cover each document's text exactly once,** like passages: the first starts at 0, each ends where the next starts, and the last reaches the end of the text. Their pages or sections come from their offsets.
- **Truncation is off.** The tokenizer's truncation and padding are turned off when it is loaded, because truncation would silently drop the end of a long handbook.

## Alternatives

- **Words.**
  - Simple, with no model to load, and easy to explain.
  - But a word is not what the model reads. Section labels and document numbers split into many tokens: `571.10(a)` is one word but 7 BGE-M3 tokens, and `AC 43.13-1B` is two words but 5 tokens. A chunk of N words can hold far more tokens than expected. The size the experiments compare would drift with the content.
- **Characters.**
  - Exact and fast, with no tokenizer.
  - But the number of characters per token changes with the text: section numbers, references and tables use far more tokens per character than plain prose. A fixed number of characters gives chunks of very different token sizes.
- **Another model's tokenizer,** such as a generic one from `tiktoken`.
  - Fast and well known.
  - But it counts differently from BGE-M3, so it has the same drawback as words: the count isn't what the embedder sees.

## Consequences

- "512 tokens" means 512 BGE-M3 tokens, the same in every run, and no chunk can exceed the model's window.
- The chunk stage needs BGE-M3's tokenizer, about 17 MB, downloaded once into the Hugging Face cache. It never needs the model weights.
- Changing the embedder changes the tokenizer, so the chunks must be rebuilt. The DVC `chunk` stage depends on `embedding.model` and `embedding.revision` for this reason.
- A structure-aware chunker (v2) can follow the same interface and rules, with cuts at section boundaries instead of every 512 tokens.

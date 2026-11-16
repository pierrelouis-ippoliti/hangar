"""
The chunk stage: from canonical texts to chunks of a fixed number of tokens.

Tokens are counted with the embedder's own tokenizer, so "512 tokens" means
what the embedder sees. The tokenizer sits behind the token counter
interface, so tests can count words instead.
"""

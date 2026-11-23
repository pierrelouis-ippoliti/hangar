"""
The generation step: from a question and its chunks to a cited answer.

It renders the prompt from a versioned file in ``prompts/``, calls the
language model and parses the citation markers in its answer.
"""

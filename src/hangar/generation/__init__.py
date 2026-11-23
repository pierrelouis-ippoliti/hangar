"""
The generation step: from a question and its chunks to a cited answer.

It renders the prompt from a versioned file in ``prompts/`` and sends it to
the language model through a client. The citation parser joins it in #26.
"""

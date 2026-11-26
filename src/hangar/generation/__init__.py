"""
The generation step: from a question and its chunks to a cited answer.

It renders the prompt from a versioned file in ``prompts/``, sends it to
the language model through a client, parses the citations of the answer,
and shows the answer with its sources and the study-aid notice.
"""

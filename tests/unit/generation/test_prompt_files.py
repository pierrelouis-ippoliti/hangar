"""
Prompt files are never edited in place: a new version is a new file.

Every answer record names its prompt version, so editing a prompt file would
make two runs with the same version use different prompts. This test pins
each file's SHA-256. To change a prompt, add a new file, such as
``answer-v1.md``, and add its hash here.
"""

import hashlib
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"

PROMPT_SHA256 = {
    "answer-v0": "355d688c51208669425449addc293b757452aee4bea2fb810b64ba35029d6fb3",
}


def test_prompt_files_match_their_pinned_hashes() -> None:
    found = {
        path.stem: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(PROMPTS.glob("*.md"))
    }

    assert found == PROMPT_SHA256, (
        "a prompt file was edited or added: write a new version as a new file "
        "and pin its hash in PROMPT_SHA256"
    )

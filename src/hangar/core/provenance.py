"""
Provenance: which code produced a run.

A run record keeps the git commit and whether the checkout had changes, so
a result can be traced to the exact code behind it. A release run refuses a
checkout with changes, since its commit wouldn't describe the code that ran.
"""

from pydantic import BaseModel, ConfigDict

from hangar.core.config import CommitHash


class CodeVersion(BaseModel):
    """
    The git commit of a checkout, and whether the checkout had changes.

    Attributes:
        commit: The commit checked out, as 40 hex characters.
        dirty: Whether files were changed or untracked, so that the code
            that ran differs from the commit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    commit: CommitHash
    dirty: bool

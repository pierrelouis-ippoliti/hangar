"""
Retrieval results: the chunks found for a question, best first.

A retriever ranks chunks for a question. Each result keeps the retriever's
ID, so the evaluation of later versions can compare retrievers on the same
questions.
"""

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from hangar.core.chunks import Chunk


class ScoredChunk(BaseModel):
    """
    One chunk found for a question.

    Attributes:
        chunk: The chunk, with its text and the passages it covers.
        score: How well it matches the question, as the retriever measures
            it; for the dense retriever, the cosine similarity of the
            vectors. Higher is better.
        rank: Its position in the results, starting at 1.
        retriever_id: The retriever that found it, such as ``dense``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk: Chunk
    score: float
    rank: PositiveInt
    retriever_id: str = Field(min_length=1)

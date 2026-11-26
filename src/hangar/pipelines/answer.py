"""
The answer pipeline: a question in, an answer record out.

It retrieves the top chunks, renders the prompt, asks the language model,
parses the citations and builds the answer record. ``hangar ask`` answers
one question with it; ``hangar seed run`` will answer every seed question.
"""

import logging
import time
from collections.abc import Callable, Mapping

from hangar.core.config import PipelineConfig
from hangar.core.corpus import DocumentSpec
from hangar.core.costs import token_cost
from hangar.core.records import AnswerRecord, ScoredChunkRef, StageTimings
from hangar.generation.citations import parse_citations
from hangar.generation.llm import LlmClient
from hangar.generation.prompt import PromptTemplate
from hangar.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


class AnswerPipeline:
    """
    Answers questions from the documents, one answer record per question.
    """

    def __init__(
        self,
        retriever: Retriever,
        template: PromptTemplate,
        documents: Mapping[str, DocumentSpec],
        llm: LlmClient,
        config: PipelineConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Set up the pipeline.

        Args:
            retriever: Finds the chunks for a question.
            template: The prompt the chunks and the question are written
                into.
            documents: The manifest entry of each document of the snapshot,
                keyed by ID, for the source labels of the prompt.
            llm: The language model client.
            config: The pipeline configuration, for the temperature, the
                output token limit and the prices of the language model.
            clock: Gives the current time in seconds, to time each step.
        """
        self._retriever = retriever
        self._template = template
        self._documents = documents
        self._llm = llm
        self._generation = config.generation
        self._prices = config.prices[config.generation.model]
        self._clock = clock

    def answer(
        self, question: str, run_id: str, question_id: str | None = None
    ) -> AnswerRecord:
        """
        Answer one question.

        Args:
            question: The question, in plain words.
            run_id: The run the answer belongs to.
            question_id: The seed question's ID, or None for a question
                asked with ``hangar ask``.

        Returns:
            The answer record, with a reference to each retrieved chunk but
            never its text, and every citation, invalid ones included.

        Raises:
            PromptError: If a retrieved chunk's document is not in the
                manifest.
            LlmError: If the language model gives no completion.
        """
        started = self._clock()
        results = self._retriever.retrieve(question)
        retrieved = self._clock()

        prompt = self._template.render(question, results, self._documents)
        asked = self._clock()
        completion = self._llm.complete(
            prompt.messages,
            temperature=self._generation.temperature,
            max_output_tokens=self._generation.max_output_tokens,
        )
        generated = self._clock()

        citations = parse_citations(completion.text, prompt.sources)
        invalid = [citation.marker for citation in citations if not citation.valid]
        logger.info(
            "answered with %d chunks: %d citations, %d invalid",
            len(results),
            len(citations),
            len(invalid),
        )

        if invalid:
            logger.warning(
                "the answer cites sources that don't exist: %s",
                ", ".join(f"[{marker}]" for marker in invalid),
            )

        return AnswerRecord(
            run_id=run_id,
            question_id=question_id,
            question=question,
            scored_chunks=tuple(ScoredChunkRef.of(result) for result in results),
            prompt_version=prompt.prompt_version,
            completion=completion,
            citations=citations,
            timings=StageTimings(
                retrieval_seconds=retrieved - started,
                generation_seconds=generated - asked,
            ),
            cost=token_cost(
                self._prices, completion.input_tokens, completion.output_tokens
            ),
        )

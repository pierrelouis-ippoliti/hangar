"""The ask pipeline: one question answered from the documents, with citations."""

import logging
from pathlib import Path

from hangar.core.config import PipelineConfig
from hangar.corpus.manifest import load_snapshot
from hangar.generation.llm import LlmClient
from hangar.generation.presentation import format_answer
from hangar.generation.prompt import load_prompt_template
from hangar.observability.recorder import FileRunRecorder
from hangar.pipelines.answer import AnswerPipeline
from hangar.pipelines.provenance import code_version
from hangar.pipelines.registry import build_llm_client
from hangar.pipelines.runs import AnsweringRun
from hangar.pipelines.search import configured_retriever
from hangar.pipelines.settings import Settings
from hangar.retrieval.retriever import Retriever

PROMPTS_DIR = Path("prompts")
ANSWERS_FILE = "answers.jsonl"

logger = logging.getLogger(__name__)


def run_ask(
    settings: Settings,
    config: PipelineConfig,
    question: str,
    run_id: str,
    *,
    record: bool = False,
    retriever: Retriever | None = None,
    llm: LlmClient | None = None,
) -> str:
    """
    Answer a question, and optionally record the answer.

    The quick checks come first: the API key, the manifest, the prompt file
    and the record folder. Only then is the embedding model loaded and the
    language model called.

    Args:
        settings: Where Hangar runs: the data folder, the Qdrant server,
            the device and the Mistral API key.
        config: The pipeline configuration.
        question: The question, in plain words.
        run_id: The run's ID, shared with its log file.
        record: Whether to write the answer record and the run record to
            ``<data folder>/runs/<run ID>/``.
        retriever: The retriever to use instead of the configured one, for
            tests.
        llm: The language model client to use instead of the configured
            one, for tests.

    Returns:
        The answer for the screen: its text, each cited source with its
        attribution, and the study-aid notice.

    Raises:
        ConfigError: If the API key is not set, or the manifest can't be
            read.
        PromptError: If the prompt file is broken.
        RunFolderExistsError: If ``record`` is true and the run's folder
            already exists.
        VectorIndexError: If Qdrant or the collection can't be used.
        LlmError: If the language model gives no completion.
    """
    if llm is None:
        llm = build_llm_client(config.generation, settings.mistral_api_key)

    corpus = config.corpus
    documents = {d.id: d for d in load_snapshot(corpus.manifest, corpus.snapshot)}
    template = load_prompt_template(PROMPTS_DIR, config.generation.prompt)
    run = _start_run(settings, config, run_id) if record else None

    if retriever is None:
        retriever = configured_retriever(settings, config)

    pipeline = AnswerPipeline(retriever, template, documents, llm, config)
    answer = pipeline.answer(question, run_id)

    if run is not None:
        run.record_answer(answer)
        run.finish()

    return format_answer(answer, documents, corpus.snapshot)


def _start_run(settings: Settings, config: PipelineConfig, run_id: str) -> AnsweringRun:
    folder = settings.data_dir / "runs" / run_id
    recorder = FileRunRecorder(folder, ANSWERS_FILE)
    logger.info("recording the answer in %s", folder)

    return AnsweringRun(run_id, config, recorder, code_version(Path.cwd()))

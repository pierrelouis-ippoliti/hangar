import json
from pathlib import Path

import pytest

from hangar.core.errors import ConfigError
from hangar.core.records import AnswerRecord, RunRecord
from hangar.generation.llm import FakeLlmClient
from hangar.generation.presentation import STUDY_AID_NOTICE
from hangar.observability.recorder import RunFolderExistsError
from hangar.pipelines.ask import run_ask
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.settings import Settings, load_settings
from hangar.retrieval.retriever import FixedRetriever
from tests.builders import RUN_ID, chunk, page, section

ROOT = Path(__file__).resolve().parents[3]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")
QUESTION = "When is the ELT battery replaced?"

# Two chunks from real C1 documents, so the manifest knows them.
RETRIEVER = FixedRetriever(
    [
        chunk(
            "Replace the ELT battery.",
            passages=[page(142, "7-12", document_id="faa-h-8083-31b")],
        ),
        chunk("Record the date.", passages=[section("571.10")]),
    ]
)


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings with the data folder in a temporary folder and no API key."""
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    return load_settings(None)


def ask(
    settings: Settings, llm: FakeLlmClient | None = None, *, record: bool = False
) -> str:
    return run_ask(
        settings,
        CONFIG,
        QUESTION,
        RUN_ID,
        record=record,
        retriever=RETRIEVER,
        llm=llm or FakeLlmClient(),
    )


def test_the_answer_shows_the_document_and_page_or_section_of_each_citation(
    settings: Settings,
) -> None:
    text = ask(settings)

    assert "[1] faa-h-8083-31b, p. 142 (7-12)\n    FAA handbook guidance" in text
    assert "[2] tc-std-571, § 571.10\n    Transport Canada standard" in text
    assert "Hangar is not affiliated with or endorsed by Transport Canada." in text


def test_invalid_markers_are_flagged(settings: Settings) -> None:
    text = ask(settings, FakeLlmClient("Replace it [1]. Test it [8]."))

    assert "[8] invalid marker" in text


def test_the_study_aid_notice_ends_every_answer(settings: Settings) -> None:
    for llm in (FakeLlmClient(), FakeLlmClient("The sources don't say.")):
        assert ask(settings, llm).endswith(STUDY_AID_NOTICE)


def test_nothing_is_written_without_record(settings: Settings) -> None:
    ask(settings)

    assert not (settings.data_dir / "runs").exists()


def test_record_writes_the_answer_and_the_run_record_under_the_run_id(
    settings: Settings,
) -> None:
    ask(settings, record=True)

    folder = settings.data_dir / "runs" / RUN_ID
    (line,) = (folder / "answers.jsonl").read_text().splitlines()
    answer = AnswerRecord.model_validate_json(line)
    run = RunRecord.model_validate(json.loads((folder / "run.json").read_text()))
    assert answer.run_id == run.run_id == RUN_ID
    assert answer.question == QUESTION
    assert run.release is False
    assert run.totals.answers == 1


def test_record_refuses_the_folder_of_an_earlier_run(settings: Settings) -> None:
    (settings.data_dir / "runs" / RUN_ID).mkdir(parents=True)

    with pytest.raises(RunFolderExistsError):
        ask(settings, record=True)


def test_a_missing_api_key_stops_the_command_before_anything_is_loaded(
    settings: Settings,
) -> None:
    # No retriever is given, so loading anything would reach for Qdrant and
    # the embedding model.
    with pytest.raises(ConfigError, match="MISTRAL_API_KEY"):
        run_ask(settings, CONFIG, QUESTION, RUN_ID)

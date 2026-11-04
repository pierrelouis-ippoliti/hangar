import copy
import re
from typing import Any

import pydantic
import pytest

from hangar.core.config import config_hash, parse_pipeline_config
from hangar.core.errors import ConfigError

SOURCE = "configs/pipelines/test.yaml"


def valid_data() -> dict[str, Any]:
    return {
        "corpus": {"snapshot": "c1", "manifest": "corpus/manifest.yaml"},
        "parsing": {
            "pdf": {"type": "pypdfium2"},
            "normalisation": {"unicode_form": "NFKC", "collapse_whitespace": True},
            "car": {"subparts": ["571", "573"]},
            "tc_html": {
                "content_selectors": {"standard": "main", "advisory_circular": "main"}
            },
        },
        "chunking": {
            "type": "fixed_tokens",
            "size": 512,
            "overlap": 0,
            "tokenizer": "embedder",
        },
        "embedding": {
            "type": "sentence_transformers",
            "model": "BAAI/bge-m3",
            "revision": "5617a9f61b028005a4858fdac845db406aefb181",
            "output": "dense",
            "batch_size": 16,
            "normalize": True,
        },
        "index": {"type": "qdrant", "distance": "cosine"},
        "retrieval": {"type": "dense", "top_k": 5},
        "generation": {
            "type": "mistral",
            "model": "mistral-small-2603",
            "temperature": 0.0,
            "max_output_tokens": 512,
            "prompt": "answer-v0",
        },
        "run": {"name": "v0", "seed": 0, "notes": ""},
        "prices": {
            "mistral-small-2603": {
                "free_tier": {
                    "input_usd_per_million": 0.0,
                    "output_usd_per_million": 0.0,
                },
                "list_price": {
                    "input_usd_per_million": 0.15,
                    "output_usd_per_million": 0.6,
                },
            }
        },
    }


def with_value(
    data: dict[str, Any], path: tuple[str, ...], value: Any
) -> dict[str, Any]:
    changed = copy.deepcopy(data)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


def problem_fields(data: object) -> list[str | None]:
    with pytest.raises(ConfigError) as error_info:
        parse_pipeline_config(data, SOURCE)
    return [problem.field for problem in error_info.value.problems]


def test_valid_data_gives_a_config_with_its_values() -> None:
    config = parse_pipeline_config(valid_data(), SOURCE)

    assert config.corpus.snapshot == "c1"
    assert config.chunking.size == 512
    assert config.embedding.revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert config.generation.model == "mistral-small-2603"
    assert config.retrieval.top_k == 5


def test_config_cannot_be_changed_after_loading() -> None:
    config = parse_pipeline_config(valid_data(), SOURCE)

    with pytest.raises(pydantic.ValidationError):
        config.chunking.size = 256  # type: ignore[misc]


def test_error_message_names_the_file_and_the_field() -> None:
    data = with_value(valid_data(), ("chunking", "size"), 0)

    with pytest.raises(ConfigError) as error_info:
        parse_pipeline_config(data, SOURCE)

    assert str(error_info.value).startswith(f"{SOURCE}: chunking.size: ")


def test_missing_section_is_reported_by_name() -> None:
    data = valid_data()
    del data["embedding"]

    assert problem_fields(data) == ["embedding"]


def test_unknown_field_is_rejected_so_typos_are_caught() -> None:
    data = with_value(valid_data(), ("chunking", "sise"), 512)

    assert problem_fields(data) == ["chunking.sise"]


def test_list_items_are_named_by_their_position() -> None:
    data = with_value(valid_data(), ("parsing", "car", "subparts"), ["571", 573])

    assert problem_fields(data) == ["parsing.car.subparts[1]"]


def test_every_problem_in_the_file_is_reported() -> None:
    data = with_value(valid_data(), ("chunking", "size"), 0)
    data = with_value(data, ("retrieval", "top_k"), 0)

    assert problem_fields(data) == ["chunking.size", "retrieval.top_k"]


def test_top_level_must_be_a_mapping_of_sections() -> None:
    assert problem_fields(["corpus", "parsing"]) == [None]


def test_model_revision_must_be_a_commit_hash_not_a_branch() -> None:
    data = with_value(valid_data(), ("embedding", "revision"), "main")

    with pytest.raises(ConfigError) as error_info:
        parse_pipeline_config(data, SOURCE)

    problem = error_info.value.problems[0]
    assert problem.field == "embedding.revision"
    assert "commit hash" in problem.message


def test_llm_must_be_a_dated_id_not_a_latest_alias() -> None:
    data = with_value(valid_data(), ("generation", "model"), "mistral-small-latest")

    with pytest.raises(ConfigError) as error_info:
        parse_pipeline_config(data, SOURCE)

    problem = error_info.value.problems[0]
    assert problem.field == "generation.model"
    assert "dated model ID" in problem.message


def test_chunk_overlap_must_be_smaller_than_the_chunk_size() -> None:
    data = with_value(valid_data(), ("chunking", "overlap"), 512)

    assert problem_fields(data) == ["chunking"]


def test_generation_model_must_have_a_price() -> None:
    data = with_value(valid_data(), ("generation", "model"), "mistral-medium-2508")

    with pytest.raises(ConfigError) as error_info:
        parse_pipeline_config(data, SOURCE)

    assert "mistral-medium-2508" in error_info.value.problems[0].message
    assert "prices" in error_info.value.problems[0].message


def test_hash_is_a_sha256_hex_digest() -> None:
    config = parse_pipeline_config(valid_data(), SOURCE)

    assert re.fullmatch(r"[0-9a-f]{64}", config_hash(config))


def test_same_content_gives_the_same_hash_whatever_the_key_order() -> None:
    data = valid_data()
    reordered = dict(reversed(list(data.items())))

    assert config_hash(parse_pipeline_config(data, SOURCE)) == config_hash(
        parse_pipeline_config(reordered, SOURCE)
    )


def test_hash_covers_the_resolved_values_so_a_default_matches_its_explicit_value() -> (
    None
):
    explicit = valid_data()
    implicit = valid_data()
    del implicit["run"]["notes"]

    assert config_hash(parse_pipeline_config(explicit, SOURCE)) == config_hash(
        parse_pipeline_config(implicit, SOURCE)
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("corpus", "snapshot"), "c2"),
        (("corpus", "manifest"), "corpus/other.yaml"),
        (("parsing", "normalisation", "collapse_whitespace"), False),
        (("parsing", "car", "subparts"), ["571"]),
        (("parsing", "tc_html", "content_selectors", "standard"), "article"),
        (("chunking", "size"), 256),
        (("chunking", "overlap"), 64),
        (("embedding", "revision"), "0" * 40),
        (("embedding", "batch_size"), 32),
        (("embedding", "normalize"), False),
        (("retrieval", "top_k"), 10),
        (("generation", "temperature"), 0.5),
        (("generation", "max_output_tokens"), 256),
        (("generation", "prompt"), "answer-v1"),
        (("run", "name"), "v0-rerun"),
        (("run", "seed"), 1),
        (("run", "notes"), "a note"),
        (
            ("prices", "mistral-small-2603", "list_price", "input_usd_per_million"),
            0.2,
        ),
    ],
)
def test_changing_any_value_changes_the_hash(path: tuple[str, ...], value: Any) -> None:
    original = parse_pipeline_config(valid_data(), SOURCE)
    changed = parse_pipeline_config(with_value(valid_data(), path, value), SOURCE)

    assert config_hash(changed) != config_hash(original)

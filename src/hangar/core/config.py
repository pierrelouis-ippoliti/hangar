"""
The pipeline configuration: what a run does.

A pipeline file, such as ``configs/pipelines/v0.yaml``, chooses the corpus
snapshot, the parser, the chunker, the models and the prompt. Two runs with
the same resolved configuration are meant to give the same results, so its
hash identifies them. Settings that only say where things run, such as the
data folder or the API key, are kept out of it.

Each ``type`` field accepts only the implementations that v0 builds. A later
version adds its value when it adds the code behind it.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
    model_validator,
)

from hangar.core.errors import ConfigError, FieldProblem, field_problems


def _check_commit_hash(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(
            f"must be a 40-character commit hash, not a branch or tag: {value!r}"
        )
    return value


def _check_dated_model_id(value: str) -> str:
    if "latest" in value:
        raise ValueError(
            "must be a dated model ID, such as mistral-small-2603, "
            f"not the alias {value!r}"
        )
    return value


CommitHash = Annotated[str, AfterValidator(_check_commit_hash)]
DatedModelId = Annotated[
    str, Field(min_length=1), AfterValidator(_check_dated_model_id)
]


class ConfigSection(BaseModel):
    """A part of the pipeline configuration: frozen, and with no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CorpusConfig(ConfigSection):
    """
    Which documents a run uses.

    Attributes:
        snapshot: The corpus snapshot, such as ``c1``.
        manifest: The manifest listing the documents, relative to the
            repository root.
    """

    snapshot: str = Field(pattern=r"^c[0-9]+$")
    manifest: Path


class PdfParsingConfig(ConfigSection):
    """
    How PDF documents are read.

    Attributes:
        type: The PDF library.
    """

    type: Literal["pypdfium2"]


class NormalisationConfig(ConfigSection):
    """
    How extracted text is cleaned before it becomes the canonical text.

    Attributes:
        unicode_form: The Unicode normalisation form applied to the text.
        collapse_whitespace: Whether runs of spaces and tabs become one space.
    """

    unicode_form: Literal["NFKC"]
    collapse_whitespace: bool


class CarParsingConfig(ConfigSection):
    """
    Which parts of the Canadian Aviation Regulations are kept.

    Attributes:
        subparts: The subpart numbers to keep, such as ``571``.
    """

    subparts: tuple[str, ...] = Field(min_length=1)


class ContentSelectors(ConfigSection):
    """
    Where the content sits in a Transport Canada page, per document type.

    Attributes:
        standard: The CSS selector of a standard's content.
        advisory_circular: The CSS selector of an advisory circular's content.
    """

    standard: str = Field(min_length=1)
    advisory_circular: str = Field(min_length=1)


class TcHtmlParsingConfig(ConfigSection):
    """
    How Transport Canada HTML pages are read.

    Attributes:
        content_selectors: Where the content sits in each type of page.
    """

    content_selectors: ContentSelectors


class ParsingConfig(ConfigSection):
    """
    How each document format becomes a canonical text.

    Attributes:
        pdf: The settings for PDF documents.
        normalisation: The text clean-up applied to every format.
        car: The settings for the regulation XML.
        tc_html: The settings for Transport Canada pages.
    """

    pdf: PdfParsingConfig
    normalisation: NormalisationConfig
    car: CarParsingConfig
    tc_html: TcHtmlParsingConfig


class ChunkingConfig(ConfigSection):
    """
    How canonical texts are split into chunks.

    Attributes:
        type: The chunker.
        size: The chunk size, in tokens.
        overlap: How many tokens each chunk shares with the previous one.
        tokenizer: Where the tokenizer that counts the tokens comes from.
    """

    type: Literal["fixed_tokens"]
    size: PositiveInt
    overlap: NonNegativeInt
    tokenizer: Literal["embedder"]

    @model_validator(mode="after")
    def _check_overlap_is_smaller_than_size(self) -> Self:
        if self.overlap >= self.size:
            raise ValueError(
                f"overlap ({self.overlap}) must be smaller than size ({self.size})"
            )
        return self


class EmbeddingConfig(ConfigSection):
    """
    The model that turns chunks and questions into vectors.

    Attributes:
        type: The library that runs the model.
        model: The Hugging Face model ID.
        revision: The model's commit hash on Hugging Face.
        output: Which of the model's outputs is used.
        batch_size: How many chunks are encoded at once.
        normalize: Whether vectors are scaled to unit length.
    """

    type: Literal["sentence_transformers"]
    model: str = Field(min_length=1)
    revision: CommitHash
    output: Literal["dense"]
    batch_size: PositiveInt
    normalize: bool


class IndexConfig(ConfigSection):
    """
    Where the vectors are stored and searched.

    Attributes:
        type: The vector store.
        distance: How the store compares two vectors.
    """

    type: Literal["qdrant"]
    distance: Literal["cosine"]


class RetrievalConfig(ConfigSection):
    """
    How the passages for a question are found.

    Attributes:
        type: The retriever.
        top_k: How many chunks are passed to the language model.
    """

    type: Literal["dense"]
    top_k: PositiveInt


class GenerationConfig(ConfigSection):
    """
    How the answer is written.

    Attributes:
        type: The language model provider.
        model: The provider's dated model ID.
        temperature: The sampling temperature.
        max_output_tokens: The most tokens an answer may use.
        prompt: The prompt version, the name of a file in ``prompts/``.
    """

    type: Literal["mistral"]
    model: DatedModelId
    temperature: NonNegativeFloat
    max_output_tokens: PositiveInt
    prompt: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")


class RunConfig(ConfigSection):
    """
    How a run is labelled.

    Attributes:
        name: A short name for the run.
        seed: The random seed.
        notes: Free text kept with the run's records.
    """

    name: str = Field(min_length=1)
    seed: NonNegativeInt
    notes: str = ""


class TokenPrice(ConfigSection):
    """
    What a model's tokens cost, in US dollars per million tokens.

    Attributes:
        input_usd_per_million: The price of the prompt tokens.
        output_usd_per_million: The price of the answer tokens.
    """

    input_usd_per_million: NonNegativeFloat
    output_usd_per_million: NonNegativeFloat


class ModelPrices(ConfigSection):
    """
    A model's token prices.

    Attributes:
        free_tier: What the free tier charges, recorded as zero.
        list_price: What the same tokens cost at the published price.
    """

    free_tier: TokenPrice
    list_price: TokenPrice


class PipelineConfig(ConfigSection):
    """
    A whole pipeline file, validated.

    Attributes:
        corpus: Which documents are used.
        parsing: How documents become canonical texts.
        chunking: How texts are split into chunks.
        embedding: The embedding model.
        index: The vector store.
        retrieval: How passages are found.
        generation: How answers are written.
        run: How the run is labelled.
        prices: Token prices, keyed by model ID.
    """

    corpus: CorpusConfig
    parsing: ParsingConfig
    chunking: ChunkingConfig
    embedding: EmbeddingConfig
    index: IndexConfig
    retrieval: RetrievalConfig
    generation: GenerationConfig
    run: RunConfig
    prices: dict[str, ModelPrices]

    @model_validator(mode="after")
    def _check_generation_model_has_a_price(self) -> Self:
        if self.generation.model not in self.prices:
            raise ValueError(
                f"generation.model {self.generation.model!r} has no entry in prices"
            )
        return self


def parse_pipeline_config(data: object, source: str) -> PipelineConfig:
    """
    Validate the content of a pipeline file.

    Args:
        data: The file's content, as read from YAML.
        source: The file the content came from, used in error messages.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: If the content is not a valid pipeline configuration.
            The error lists every problem, each with its field.
    """
    if not isinstance(data, dict):
        raise ConfigError(
            source, [FieldProblem(None, "the file must be a mapping of sections")]
        )
    try:
        return PipelineConfig.model_validate(data)
    except ValidationError as error:
        raise ConfigError(source, field_problems(error)) from error


def config_hash(config: PipelineConfig) -> str:
    """
    Compute the configuration hash that identifies a run's results.

    The hash covers the resolved configuration: every value after
    validation, defaults included, written as JSON with sorted keys.
    Comments, formatting and key order in the file don't change it; any
    change of value does.

    Args:
        config: The validated configuration.

    Returns:
        The SHA-256 of the resolved configuration, as 64 hex characters.
    """
    resolved = config.model_dump(mode="json")
    canonical = json.dumps(
        resolved, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

"""
The embedder for sentence-transformers models, such as BGE-M3.

It loads the model at the revision pinned in the configuration, and uses
its dense output: one vector per text. BGE-M3's sparse and multi-vector
outputs wait for v3.
"""

import os
from collections.abc import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from hangar.core.config import EmbeddingConfig
from hangar.embedding.embedder import EmbedError


class SentenceTransformerEmbedder:
    """
    Turns texts into vectors with a sentence-transformers model.

    Attributes:
        model_id: The Hugging Face model ID, such as ``BAAI/bge-m3``.
        revision: The model's commit hash.
        dimension: How many values each vector has, 1,024 for BGE-M3.
        normalized: Whether the vectors are scaled to unit length.
    """

    def __init__(self, config: EmbeddingConfig, device: str) -> None:
        """
        Load the model, downloading it the first time.

        Args:
            config: The embedding section of the pipeline configuration: the
                model, its revision, the batch size and normalisation.
            device: Where the model runs: ``cpu``, ``cuda`` or ``mps``.

        Raises:
            EmbedError: If the model doesn't report its vector dimension.
        """
        # BGE-M3's pinned revision has only pytorch_model.bin. After loading
        # it, transformers would start a thread that downloads a safetensors
        # copy (2.3 GB) from a bot's pull request, an unpinned branch. The
        # model never uses that copy, so the download is turned off. This
        # setting applies to the whole process.
        os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "true"
        self._model = SentenceTransformer(
            config.model, revision=config.revision, device=device
        )
        dimension = self._model.get_embedding_dimension()

        if dimension is None:
            raise EmbedError(f"{config.model} doesn't report its vector dimension")

        self.model_id = config.model
        self.revision = config.revision
        self.dimension = dimension
        self.normalized = config.normalize
        self._batch_size = config.batch_size

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Turn document texts, such as chunks, into vectors.

        Args:
            texts: The texts to embed. They are sent to the model in batches
                of the configured size.

        Returns:
            One vector per text, in the same order.
        """
        vectors = self._model.encode_document(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=self.normalized,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return _as_lists(vectors)

    def embed_query(self, text: str) -> list[float]:
        """
        Turn a question into a vector.

        Args:
            text: The question.

        Returns:
            Its vector.
        """
        vectors = self._model.encode_query(
            [text],
            normalize_embeddings=self.normalized,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return _as_lists(vectors)[0]


def _as_lists(vectors: object) -> list[list[float]]:
    # With convert_to_numpy, encode returns a 2D NumPy array, but its type
    # covers every output format, so it is checked here.
    if not isinstance(vectors, np.ndarray) or vectors.ndim != 2:
        raise EmbedError(f"the model returned {type(vectors).__name__}, not a matrix")

    rows: list[list[float]] = vectors.astype(np.float32).tolist()

    return rows

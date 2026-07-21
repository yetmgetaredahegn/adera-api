"""Local embeddings — BGE-M3 via sentence-transformers (ADR-009, 06 §5).

Local and multilingual (critical for Amharic), 1024-dim, $0 marginal cost — which is
why unlimited eligibility verdicts on the paid tier are economically safe (02 §6).

The model is loaded ONCE per process (lru_cache singleton): reloading a 2GB model
per task would murder throughput. CPU is fine at our volume. In production this runs
on the Celery `cpu` queue; the CLI calls it directly.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-m3"
BATCH_SIZE = 32


@lru_cache
def _get_model() -> "SentenceTransformer":
    # Imported lazily: sentence-transformers pulls torch (~GBs). Nothing that
    # doesn't embed should pay that import.
    from sentence_transformers import SentenceTransformer

    model: SentenceTransformer = SentenceTransformer(MODEL_NAME)
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed. Normalized so cosine distance is well-behaved in pgvector."""
    model = _get_model()
    vectors = model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True)
    return [v.tolist() for v in vectors]

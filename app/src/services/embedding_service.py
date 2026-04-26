from __future__ import annotations

import logging

from etl.meilisearch.embedding_profiles import EmbeddingProfile, get_profile
from etl.meilisearch.vectorizer import SentenceTransformerVectorizer

logger = logging.getLogger("app.services.embedding")


class EmbeddingService:
    def __init__(
        self,
        embedding_profile: str,
        encode_batch_size: int = 256,
        cpu_threads: int | None = None,
    ) -> None:
        logger.info("ENTER init_embedding_service profile=%s", embedding_profile)
        self.profile: EmbeddingProfile = get_profile(embedding_profile)
        self.vectorizer = SentenceTransformerVectorizer(
            model_name=self.profile.model_name,
            encode_batch_size=encode_batch_size,
            cpu_threads=cpu_threads,
        )
        logger.info(
            "EXIT  init_embedding_service model=%s embedder=%s",
            self.profile.model_name,
            self.profile.embedder_name,
        )

    def embed_query(self, query: str) -> list[float]:
        logger.info("ENTER embed_query query_len=%s", len(query))
        vector = self.vectorizer.encode([query])[0]
        logger.info("EXIT  embed_query dimensions=%s", len(vector))
        return vector

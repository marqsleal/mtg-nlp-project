from __future__ import annotations

import logging
from collections.abc import Sequence

from sentence_transformers import CrossEncoder

logger = logging.getLogger("app.services.reranker")


class RerankerService:
    def __init__(self, model_name: str) -> None:
        logger.info("ENTER init_reranker_service model=%s", model_name)
        self.model_name = model_name
        self._model: CrossEncoder | None = None
        logger.info("EXIT  init_reranker_service")

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            logger.info("ENTER load_reranker_model model=%s", self.model_name)
            self._model = CrossEncoder(self.model_name)
            logger.info("EXIT  load_reranker_model")
        return self._model

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        logger.info("ENTER rerank_score query_len=%s docs=%s", len(query), len(documents))
        if not documents:
            logger.info("EXIT  rerank_score docs=0")
            return []
        model = self._get_model()
        pairs = [[query, doc] for doc in documents]
        scores = model.predict(pairs, show_progress_bar=False)
        normalized = [float(value) for value in scores]
        logger.info("EXIT  rerank_score docs=%s", len(normalized))
        return normalized

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.src.api.search import router as search_router
from app.src.config import Settings
from app.src.services.domain_semantic_layer_service import DomainSemanticLayerService
from app.src.services.embedding_service import EmbeddingService
from app.src.services.meilisearch_service import MeiliSearchService
from app.src.services.reranker_service import RerankerService
from etl.logging_utils import configure_logging

logger = logging.getLogger("app.main")


def _configure_third_party_log_levels() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    configure_logging(settings.log_level)
    _configure_third_party_log_levels()
    logger.info("ENTER app_lifespan")
    app.state.settings = settings
    app.state.embedding_service = EmbeddingService(
        embedding_profile=settings.embedding_model_profile,
        encode_batch_size=settings.embedding_encode_batch_size,
        cpu_threads=settings.embedding_cpu_threads,
    )
    app.state.meili_service = MeiliSearchService(
        base_url=settings.meilisearch_url,
        api_key=settings.meilisearch_api_key,
        index_uid=settings.meilisearch_index_uid,
    )
    app.state.domain_semantic_layer_service = DomainSemanticLayerService(
        base_url=settings.meilisearch_url,
        api_key=settings.meilisearch_api_key,
        index_uid=settings.query_semantic_layer_index_uid,
        cache_ttl_seconds=settings.query_expansion_cache_ttl_seconds,
    )
    app.state.reranker_service = RerankerService(model_name=settings.rerank_model_name)
    if settings.rerank_warmup_on_startup:
        app.state.reranker_service.warmup()
    try:
        logger.info("EXIT  app_lifespan_startup")
        yield
    finally:
        logger.info("ENTER app_lifespan_shutdown")
        app.state.domain_semantic_layer_service.close()
        app.state.meili_service.close()
        logger.info("EXIT  app_lifespan_shutdown")


app = FastAPI(title="MTG Semantic Search API", version="0.1.0", lifespan=lifespan)
app.include_router(search_router)


@app.get("/health")
def health() -> dict[str, str]:
    logger.info("ENTER endpoint=health")
    logger.info("EXIT  endpoint=health")
    return {"status": "ok"}


@app.get("/v1/ready")
def ready() -> dict[str, str]:
    logger.info("ENTER endpoint=v1_ready")
    app.state.meili_service.health()
    logger.info("EXIT  endpoint=v1_ready")
    return {"status": "ready"}

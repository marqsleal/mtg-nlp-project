from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "mtg-semantic-search-api"
    app_version: str = "0.1.0"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    meilisearch_url: str = Field(default="http://127.0.0.1:7700", alias="MEILISEARCH_URL")
    meilisearch_api_key: str | None = Field(default=None, alias="MEILISEARCH_API_KEY")
    meilisearch_index_uid: str = Field(default="mtg_cards", alias="MEILISEARCH_INDEX_UID")
    query_semantic_layer_index_uid: str = Field(
        default="mtg_domain_semantic_layer",
        alias="QUERY_SEMANTIC_LAYER_INDEX_UID",
    )
    query_expansion_enabled: bool = Field(default=True, alias="QUERY_EXPANSION_ENABLED")
    query_expansion_max_terms: int = Field(default=5, ge=1, alias="QUERY_EXPANSION_MAX_TERMS")
    query_expansion_min_score: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        alias="QUERY_EXPANSION_MIN_SCORE",
    )
    query_expansion_cache_ttl_seconds: int = Field(
        default=600,
        ge=0,
        alias="QUERY_EXPANSION_CACHE_TTL_SECONDS",
    )
    search_fusion_mode: Literal["hybrid", "rrf"] = Field(
        default="hybrid",
        alias="SEARCH_FUSION_MODE",
    )
    search_rrf_k: int = Field(default=60, ge=1, alias="SEARCH_RRF_K")
    search_rrf_window: int = Field(default=100, ge=1, alias="SEARCH_RRF_WINDOW")

    embedding_model_profile: str = Field(
        default="bge_small_en_v15",
        alias="EMBEDDING_MODEL_PROFILE",
    )
    embedding_encode_batch_size: int = Field(default=256, alias="EMBEDDING_ENCODE_BATCH_SIZE")
    embedding_cpu_threads: int | None = Field(default=None, alias="EMBEDDING_CPU_THREADS")

    search_default_limit: int = 20
    search_max_limit: int = 100
    search_default_offset: int = 0
    search_default_show_ranking_score: bool = True
    search_default_semantic_ratio: float = 0.7
    search_default_candidate_limit: int = 60
    search_max_candidate_limit: int = 200

    rerank_enabled_default: bool = True
    rerank_default_top_k: int = 40
    rerank_max_top_k: int = 100
    rerank_default_weight: float = 0.7
    rerank_model_name: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        alias="RERANK_MODEL_NAME",
    )

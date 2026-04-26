from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="User text query to embed and search semantically.",
    )
    limit: int | None = Field(default=None, ge=1, le=1000)
    offset: int | None = Field(default=None, ge=0)
    filter: str | list[str] | None = None
    attributes_to_retrieve: list[str] | None = None
    show_ranking_score: bool | None = None
    min_ranking_score: float | None = Field(default=None, ge=0.0)
    semantic_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Semantic weight for vector retrieval. Default is 1.0.",
    )
    candidate_limit: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Number of candidates retrieved before reranking.",
    )
    rerank: bool | None = Field(default=None, description="Enable cross-encoder reranking step.")
    rerank_top_k: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="How many candidates are reranked.",
    )
    rerank_weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Weight of reranker score in final blended score.",
    )
    retrieve_vectors: bool = False

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return value.strip()


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    lang: str | None = None
    set: str | None = None
    rarity: str | None = None
    score: float | None = None
    retrieval_score: float | None = None
    rerank_score: float | None = None
    document: dict[str, Any]


class SearchMeta(BaseModel):
    query: str
    limit: int
    offset: int
    estimated_total_hits: int
    processing_time_ms: int
    mode: str
    candidate_limit: int
    candidates_returned: int
    rerank_applied: bool
    embedder_name: str
    model_name: str


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    meta: SearchMeta

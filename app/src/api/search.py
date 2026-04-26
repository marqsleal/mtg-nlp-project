from __future__ import annotations

import logging
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.src.config import Settings
from app.src.models.search import SearchHit, SearchMeta, SearchRequest, SearchResponse
from app.src.services.embedding_service import EmbeddingService
from app.src.services.meilisearch_service import MeiliSearchService
from app.src.services.reranker_service import RerankerService

router = APIRouter(prefix="/v1", tags=["search"])
logger = logging.getLogger("app.api.search")


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def _get_meili_service(request: Request) -> MeiliSearchService:
    return request.app.state.meili_service


def _get_reranker_service(request: Request) -> RerankerService:
    return request.app.state.reranker_service


def _min_max_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [1.0 for _ in values]
    span = max_v - min_v
    return [(value - min_v) / span for value in values]


def _apply_rerank(
    hits: list[dict],
    query: str,
    reranker_service: RerankerService,
    rerank_top_k: int,
    rerank_weight: float,
) -> list[dict]:
    rerank_subset = hits[:rerank_top_k]
    texts = [
        str(item.get("search_text") or item.get("oracle_text") or item.get("name") or "")
        for item in rerank_subset
    ]
    rerank_scores = reranker_service.score(query, texts)

    retrieval_scores = [float(item.get("_rankingScore", 0.0)) for item in rerank_subset]
    normalized_retrieval = _min_max_normalize(retrieval_scores)
    normalized_rerank = _min_max_normalize(rerank_scores)

    blended: list[tuple[float, float, float, dict]] = []
    for item, retrieval_score, rerank_score in zip(
        rerank_subset,
        normalized_retrieval,
        normalized_rerank,
        strict=True,
    ):
        final_score = ((1.0 - rerank_weight) * retrieval_score) + (rerank_weight * rerank_score)
        blended.append((final_score, retrieval_score, rerank_score, item))

    blended.sort(key=lambda value: value[0], reverse=True)
    reranked_hits = []
    for final_score, retrieval_score, rerank_score, item in blended:
        enriched = dict(item)
        enriched["_finalScore"] = final_score
        enriched["_retrievalScoreNorm"] = retrieval_score
        enriched["_rerankScoreNorm"] = rerank_score
        reranked_hits.append(enriched)
    return reranked_hits + hits[rerank_top_k:]


@router.post("/search", response_model=SearchResponse)
def semantic_search(
    payload: SearchRequest,
    settings: Annotated[Settings, Depends(_get_settings)],
    embedding_service: Annotated[EmbeddingService, Depends(_get_embedding_service)],
    meili_service: Annotated[MeiliSearchService, Depends(_get_meili_service)],
    reranker_service: Annotated[RerankerService, Depends(_get_reranker_service)],
) -> SearchResponse:
    logger.info("ENTER endpoint=v1_search")
    start = perf_counter()
    query_vector = embedding_service.embed_query(payload.query)

    limit = min(payload.limit or settings.search_default_limit, settings.search_max_limit)
    offset = payload.offset if payload.offset is not None else settings.search_default_offset
    show_ranking_score = (
        payload.show_ranking_score
        if payload.show_ranking_score is not None
        else settings.search_default_show_ranking_score
    )
    semantic_ratio = (
        payload.semantic_ratio
        if payload.semantic_ratio is not None
        else settings.search_default_semantic_ratio
    )
    candidate_limit = payload.candidate_limit or settings.search_default_candidate_limit
    candidate_limit = max(limit, min(candidate_limit, settings.search_max_candidate_limit))
    rerank_enabled = (
        payload.rerank if payload.rerank is not None else settings.rerank_enabled_default
    )
    rerank_top_k = payload.rerank_top_k or settings.rerank_default_top_k
    rerank_top_k = min(rerank_top_k, settings.rerank_max_top_k, candidate_limit)
    rerank_weight = (
        payload.rerank_weight
        if payload.rerank_weight is not None
        else settings.rerank_default_weight
    )
    fusion_mode = (
        payload.fusion_mode if payload.fusion_mode is not None else settings.search_fusion_mode
    )
    rrf_k = payload.rrf_k if payload.rrf_k is not None else settings.search_rrf_k
    rrf_window = (
        payload.rrf_window if payload.rrf_window is not None else settings.search_rrf_window
    )
    query_expansion_enabled = (
        payload.query_expansion
        if payload.query_expansion is not None
        else settings.query_expansion_enabled
    )
    expansion_max_terms = (
        payload.expansion_max_terms
        if payload.expansion_max_terms is not None
        else settings.query_expansion_max_terms
    )
    expansion_min_score = (
        payload.expansion_min_score
        if payload.expansion_min_score is not None
        else settings.query_expansion_min_score
    )

    attributes_to_retrieve = payload.attributes_to_retrieve
    if not payload.retrieve_vectors and attributes_to_retrieve is None:
        attributes_to_retrieve = ["*"]

    search_result = meili_service.semantic_search(
        query=payload.query,
        vector=query_vector,
        embedder_name=embedding_service.profile.embedder_name,
        semantic_ratio=semantic_ratio,
        limit=candidate_limit,
        offset=offset,
        search_filter=payload.filter,
        attributes_to_retrieve=attributes_to_retrieve,
        show_ranking_score=show_ranking_score,
    )

    raw_hits = search_result.get("hits", [])

    rerank_applied = False
    mode = "hybrid"
    if rerank_enabled and raw_hits:
        raw_hits = _apply_rerank(
            hits=raw_hits,
            query=payload.query,
            reranker_service=reranker_service,
            rerank_top_k=rerank_top_k,
            rerank_weight=rerank_weight,
        )
        rerank_applied = True
        mode = "hybrid_reranked"

    if payload.min_ranking_score is not None:
        raw_hits = [
            item
            for item in raw_hits
            if float(item.get("_finalScore", item.get("_rankingScore", 0.0)))
            >= payload.min_ranking_score
        ]
    raw_hits = raw_hits[:limit]

    hits: list[SearchHit] = []
    for item in raw_hits:
        document = dict(item)
        if not payload.retrieve_vectors:
            document.pop("_vectors", None)
        hits.append(
            SearchHit(
                id=str(document.get("id", "")),
                name=str(document.get("name", "")),
                lang=document.get("lang"),
                set=document.get("set"),
                rarity=document.get("rarity"),
                score=document.get("_finalScore", document.get("_rankingScore")),
                retrieval_score=document.get("_retrievalScoreNorm", document.get("_rankingScore")),
                rerank_score=document.get("_rerankScoreNorm"),
                document=document,
            )
        )

    total_ms = int((perf_counter() - start) * 1000)
    meta = SearchMeta(
        query=payload.query,
        limit=limit,
        offset=offset,
        estimated_total_hits=int(search_result.get("estimatedTotalHits", 0)),
        processing_time_ms=total_ms,
        mode=mode,
        candidate_limit=candidate_limit,
        candidates_returned=len(raw_hits),
        rerank_applied=rerank_applied,
        embedder_name=embedding_service.profile.embedder_name,
        model_name=embedding_service.profile.model_name,
        fusion_mode=fusion_mode,
        rrf_k=rrf_k if fusion_mode == "rrf" else None,
        rrf_window=rrf_window if fusion_mode == "rrf" else None,
        query_expansion_applied=False,
        expanded_terms=[],
        expanded_query=None,
    )
    logger.info(
        "EXIT  endpoint=v1_search duration_ms=%s mode=%s fusion=%s query_expansion=%s "
        "query_expansion_max_terms=%s query_expansion_min_score=%.2f query_len=%s "
        "limit=%s candidate_limit=%s hits=%s rerank=%s",
        total_ms,
        mode,
        fusion_mode,
        query_expansion_enabled,
        expansion_max_terms,
        expansion_min_score,
        len(payload.query),
        limit,
        candidate_limit,
        len(hits),
        rerank_applied,
    )
    return SearchResponse(hits=hits, meta=meta)

from __future__ import annotations

from typing import Any


def fuse_rrf(
    *,
    fts_hits: list[dict[str, Any]],
    vector_hits: list[dict[str, Any]],
    k: int,
    window: int,
) -> list[dict[str, Any]]:
    if k <= 0:
        raise ValueError("k must be > 0")
    if window <= 0:
        raise ValueError("window must be > 0")

    fts_ranked = fts_hits[:window]
    vector_ranked = vector_hits[:window]

    aggregated: dict[str, dict[str, Any]] = {}
    for rank, hit in enumerate(fts_ranked, start=1):
        doc_id = str(hit.get("id") or "")
        if not doc_id:
            continue
        entry = aggregated.setdefault(
            doc_id,
            {
                "score": 0.0,
                "best_ranking_score": float(hit.get("_rankingScore", 0.0)),
                "fts_rank": None,
                "vector_rank": None,
                "document": dict(hit),
            },
        )
        entry["score"] += 1.0 / (k + rank)
        entry["fts_rank"] = rank
        entry["best_ranking_score"] = max(
            float(entry["best_ranking_score"]),
            float(hit.get("_rankingScore", 0.0)),
        )

    for rank, hit in enumerate(vector_ranked, start=1):
        doc_id = str(hit.get("id") or "")
        if not doc_id:
            continue
        entry = aggregated.setdefault(
            doc_id,
            {
                "score": 0.0,
                "best_ranking_score": float(hit.get("_rankingScore", 0.0)),
                "fts_rank": None,
                "vector_rank": None,
                "document": dict(hit),
            },
        )
        entry["score"] += 1.0 / (k + rank)
        entry["vector_rank"] = rank
        entry["best_ranking_score"] = max(
            float(entry["best_ranking_score"]),
            float(hit.get("_rankingScore", 0.0)),
        )

    fused: list[dict[str, Any]] = []
    for entry in aggregated.values():
        merged = dict(entry["document"])
        merged["_rrfScore"] = entry["score"]
        merged["_rankingScore"] = entry["best_ranking_score"]
        merged["_rrfFtsRank"] = entry["fts_rank"]
        merged["_rrfVectorRank"] = entry["vector_rank"]
        fused.append(merged)

    fused.sort(
        key=lambda item: (
            float(item.get("_rrfScore", 0.0)),
            float(item.get("_rankingScore", 0.0)),
        ),
        reverse=True,
    )
    return fused

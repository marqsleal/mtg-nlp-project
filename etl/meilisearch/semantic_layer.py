from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Any

from etl.storage import StorageConfig

from .batching import write_json_atomic
from .client import MeiliSearchClient

logger = logging.getLogger("etl.meilisearch.semantic_layer")

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+'/-]*")
_MEILI_ID_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_-]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "when",
    "with",
    "you",
    "your",
}
_DOMAIN_STOPWORDS = {
    "card",
    "cards",
    "player",
    "players",
    "opponent",
    "opponents",
    "target",
    "targets",
    "control",
    "controls",
    "owner",
    "owners",
}
_MIN_TOKEN_LENGTH = 2


def _normalize_tokens(text: str) -> list[str]:
    text = text.lower().strip()
    if not text:
        return []

    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text):
        if token.endswith("'s"):
            token = token[:-2]
        token = token.strip("'")
        if len(token) < _MIN_TOKEN_LENGTH:
            continue
        if token.isdigit():
            continue
        if token in _STOPWORDS or token in _DOMAIN_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def _light_stem(term: str) -> str:
    if term.endswith("ies") and len(term) > 4:
        return f"{term[:-3]}y"
    if term.endswith("ing") and len(term) > 5:
        return term[:-3]
    if term.endswith("ed") and len(term) > 4:
        return term[:-2]
    if term.endswith("es") and len(term) > 4:
        return term[:-2]
    if term.endswith("s") and len(term) > 3:
        return term[:-1]
    return term


def _extract_text(document: dict[str, Any]) -> str:
    fields = [
        str(document.get("name") or ""),
        str(document.get("type_line") or ""),
        str(document.get("oracle_text") or ""),
        str(document.get("rulings_text") or ""),
        str(document.get("search_text") or ""),
    ]
    return "\n".join(field for field in fields if field)


def _sanitize_semantic_doc_id(term: str, used_ids: set[str]) -> str:
    base = _MEILI_ID_SANITIZE_RE.sub("_", term).strip("_")
    if not base:
        base = "term"

    candidate = base
    suffix = 1
    while candidate in used_ids:
        suffix += 1
        candidate = f"{base}_{suffix}"

    used_ids.add(candidate)
    return candidate


def _fetch_source_documents(
    client: MeiliSearchClient,
    index_uid: str,
    batch_size: int,
    max_documents: int | None,
) -> list[dict[str, Any]]:
    logger.info("ENTER step=fetch_source_documents index_uid=%s", index_uid)
    started = perf_counter()

    all_docs: list[dict[str, Any]] = []
    offset = 0
    while True:
        limit = batch_size
        if max_documents is not None:
            remaining = max_documents - len(all_docs)
            if remaining <= 0:
                break
            limit = min(limit, remaining)

        response = client.client.get(
            f"/indexes/{index_uid}/documents",
            params={
                "offset": offset,
                "limit": limit,
                "fields": "id,oracle_id,name,type_line,oracle_text,rulings_text,search_text",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            docs_batch = payload
        elif isinstance(payload, dict):
            docs_batch = payload.get("results", [])
            if not isinstance(docs_batch, list):
                docs_batch = []
        else:
            docs_batch = []

        if not docs_batch:
            break

        all_docs.extend(docs_batch)
        if len(docs_batch) < limit:
            break
        offset += len(docs_batch)

    logger.info(
        "EXIT  step=fetch_source_documents duration_sec=%.3f docs=%s",
        perf_counter() - started,
        len(all_docs),
    )
    return all_docs


def _build_semantic_documents(
    documents: list[dict[str, Any]],
    dataset_version: str,
    top_n: int,
    min_df: int,
    min_pmi: float,
    min_co_df: int,
    max_df_ratio: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    logger.info(
        (
            "ENTER step=build_semantic_documents docs=%s top_n=%s min_df=%s min_pmi=%.2f "
            "min_co_df=%s max_df_ratio=%.2f"
        ),
        len(documents),
        top_n,
        min_df,
        min_pmi,
        min_co_df,
        max_df_ratio,
    )
    started = perf_counter()

    tf = Counter()
    df = Counter()
    pair_df: dict[tuple[str, str], int] = defaultdict(int)
    doc_count = 0

    for document in documents:
        tokens = _normalize_tokens(_extract_text(document))
        if not tokens:
            continue

        doc_count += 1
        tf.update(tokens)
        unique_tokens = sorted(set(tokens))
        df.update(unique_tokens)

        token_count = len(unique_tokens)
        for i in range(token_count):
            a = unique_tokens[i]
            for j in range(i + 1, token_count):
                b = unique_tokens[j]
                pair_df[(a, b)] += 1

    expansions_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if doc_count == 0:
        summary = {
            "source_documents": len(documents),
            "processed_documents": 0,
            "terms_considered": 0,
            "semantic_documents": 0,
            "pair_count": 0,
            "dataset_version": dataset_version,
            "top_n": top_n,
            "min_df": min_df,
            "min_pmi": min_pmi,
            "min_co_df": min_co_df,
            "max_df_ratio": max_df_ratio,
        }
        logger.info("EXIT  step=build_semantic_documents duration_sec=%.3f semantic_docs=0", 0.0)
        return [], summary

    for (a, b), co_df in pair_df.items():
        if co_df < min_co_df:
            continue
        if df[a] < min_df or df[b] < min_df:
            continue
        if _light_stem(a) == _light_stem(b):
            continue
        if (df[a] / doc_count) > max_df_ratio or (df[b] / doc_count) > max_df_ratio:
            continue

        probability_ab = co_df / doc_count
        probability_a = df[a] / doc_count
        probability_b = df[b] / doc_count
        pmi = math.log(probability_ab / (probability_a * probability_b))
        npmi = pmi / (-math.log(probability_ab))
        if npmi < min_pmi:
            continue
        score = npmi * math.log1p(co_df)

        expansions_map[a].append(
            {"term": b, "score": round(score, 6), "kind": "npmi", "co_df": int(co_df)}
        )
        expansions_map[b].append(
            {"term": a, "score": round(score, 6), "kind": "npmi", "co_df": int(co_df)}
        )

    semantic_docs: list[dict[str, Any]] = []
    now_iso = datetime.now(UTC).isoformat()
    used_ids: set[str] = set()
    for term, term_df in df.items():
        if term_df < min_df:
            continue

        term_expansions = sorted(
            expansions_map.get(term, []),
            key=lambda item: (item["score"], item["co_df"]),
            reverse=True,
        )[:top_n]
        if not term_expansions:
            continue

        doc_id = _sanitize_semantic_doc_id(term, used_ids)
        semantic_docs.append(
            {
                "id": doc_id,
                "term": term,
                "df": int(term_df),
                "tf": int(tf[term]),
                "idf": round(math.log((doc_count + 1) / (term_df + 1)) + 1.0, 6),
                "expansions": term_expansions,
                "updated_at": now_iso,
                "dataset_version": dataset_version,
            }
        )

    summary = {
        "source_documents": len(documents),
        "processed_documents": doc_count,
        "terms_considered": len(df),
        "semantic_documents": len(semantic_docs),
        "pair_count": len(pair_df),
        "dataset_version": dataset_version,
        "top_n": top_n,
        "min_df": min_df,
        "min_pmi": min_pmi,
        "min_co_df": min_co_df,
        "max_df_ratio": max_df_ratio,
    }

    logger.info(
        "EXIT  step=build_semantic_documents duration_sec=%.3f semantic_docs=%s",
        perf_counter() - started,
        len(semantic_docs),
    )
    return semantic_docs, summary


def _ensure_index_settings(
    client: MeiliSearchClient,
    index_uid: str,
    settings_path: Path,
) -> None:
    logger.info("ENTER step=ensure_index_settings index_uid=%s", index_uid)
    started = perf_counter()
    client.ensure_index(index_uid=index_uid, primary_key="id")
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    response = client.client.patch(f"/indexes/{index_uid}/settings", json=payload)
    response.raise_for_status()
    client.wait_for_task(int(response.json()["taskUid"]))
    logger.info(
        "EXIT  step=ensure_index_settings duration_sec=%.3f",
        perf_counter() - started,
    )


def _upload_documents(
    client: MeiliSearchClient,
    index_uid: str,
    semantic_docs: list[dict[str, Any]],
    upload_batch_size: int,
) -> int:
    logger.info("ENTER step=upload_documents index_uid=%s docs=%s", index_uid, len(semantic_docs))
    started = perf_counter()
    if not semantic_docs:
        logger.info(
            "EXIT  step=upload_documents duration_sec=%.3f docs=0",
            perf_counter() - started,
        )
        return 0

    with NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        for item in semantic_docs:
            tmp.write(json.dumps(item, ensure_ascii=False) + "\n")

    try:
        uploaded_batches = client.add_documents_jsonl(
            index_uid=index_uid,
            jsonl_path=tmp_path,
            batch_size=upload_batch_size,
            full_batch=False,
            wait_tasks_every=8,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info(
        "EXIT  step=upload_documents duration_sec=%.3f uploaded_batches=%s",
        perf_counter() - started,
        uploaded_batches,
    )
    return uploaded_batches


def _clear_index_documents(client: MeiliSearchClient, index_uid: str) -> None:
    logger.info("ENTER step=clear_index_documents index_uid=%s", index_uid)
    started = perf_counter()
    response = client.client.delete(f"/indexes/{index_uid}/documents")
    response.raise_for_status()
    client.wait_for_task(int(response.json()["taskUid"]))
    logger.info(
        "EXIT  step=clear_index_documents duration_sec=%.3f",
        perf_counter() - started,
    )


def _persist_artifacts(
    storage_root: Path,
    dataset_version: str,
    semantic_docs: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, str]:
    base_dir = storage_root / "semantic_layer" / dataset_version
    base_dir.mkdir(parents=True, exist_ok=True)
    docs_jsonl_path = base_dir / "documents.jsonl"
    summary_path = base_dir / "summary.json"
    success_path = base_dir / "_SUCCESS"

    with docs_jsonl_path.open("w", encoding="utf-8") as file:
        for item in semantic_docs:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_json_atomic(summary_path, summary)
    success_path.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")

    storage_config = StorageConfig.from_env()
    storage_config = StorageConfig(
        backend=storage_config.backend,
        root=storage_root.resolve(),
        s3_bucket=storage_config.s3_bucket,
        s3_prefix=storage_config.s3_prefix,
    )

    return {
        "base_dir": str(base_dir),
        "documents_jsonl_path": str(docs_jsonl_path),
        "summary_path": str(summary_path),
        "success_path": str(success_path),
        "documents_jsonl_uri": storage_config.to_uri(docs_jsonl_path),
        "summary_uri": storage_config.to_uri(summary_path),
        "success_uri": storage_config.to_uri(success_path),
    }


def run_semantic_layer_build(
    meili_url: str,
    meili_api_key: str | None,
    source_index_uid: str,
    target_index_uid: str,
    settings_path: Path,
    storage_root: Path,
    dataset_version: str,
    source_fetch_batch_size: int = 1000,
    upload_batch_size: int = 1000,
    top_n: int = 5,
    min_df: int = 3,
    min_pmi: float = 0.30,
    min_co_df: int = 3,
    max_df_ratio: float = 0.25,
    max_source_documents: int | None = None,
) -> dict[str, Any]:
    logger.info(
        "ENTER run_semantic_layer_build source_index=%s target_index=%s dataset_version=%s",
        source_index_uid,
        target_index_uid,
        dataset_version,
    )
    started = perf_counter()

    client = MeiliSearchClient(url=meili_url, api_key=meili_api_key)
    try:
        source_docs = _fetch_source_documents(
            client=client,
            index_uid=source_index_uid,
            batch_size=source_fetch_batch_size,
            max_documents=max_source_documents,
        )
        semantic_docs, summary = _build_semantic_documents(
            documents=source_docs,
            dataset_version=dataset_version,
            top_n=top_n,
            min_df=min_df,
            min_pmi=min_pmi,
            min_co_df=min_co_df,
            max_df_ratio=max_df_ratio,
        )
        _ensure_index_settings(
            client=client,
            index_uid=target_index_uid,
            settings_path=settings_path,
        )
        _clear_index_documents(
            client=client,
            index_uid=target_index_uid,
        )
        uploaded_batches = _upload_documents(
            client=client,
            index_uid=target_index_uid,
            semantic_docs=semantic_docs,
            upload_batch_size=upload_batch_size,
        )
    finally:
        client.close()

    summary["uploaded_batches"] = uploaded_batches
    artifacts = _persist_artifacts(
        storage_root=storage_root,
        dataset_version=dataset_version,
        semantic_docs=semantic_docs,
        summary=summary,
    )

    result = {
        "source_index_uid": source_index_uid,
        "target_index_uid": target_index_uid,
        "dataset_version": dataset_version,
        "semantic_documents": len(semantic_docs),
        "uploaded_batches": uploaded_batches,
        "artifacts": artifacts,
        "duration_sec": round(perf_counter() - started, 3),
    }
    logger.info(
        "EXIT  run_semantic_layer_build duration_sec=%.3f semantic_docs=%s uploaded_batches=%s",
        result["duration_sec"],
        result["semantic_documents"],
        result["uploaded_batches"],
    )
    return result

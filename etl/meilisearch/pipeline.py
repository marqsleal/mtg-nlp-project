from __future__ import annotations

import logging
import shutil
from pathlib import Path
from time import perf_counter

from etl.paths import EtlPaths

from .batching import (
    build_ingest_state_from_existing_batches,
    load_state,
    now_iso,
    write_json_atomic,
)
from .client import MeiliSearchClient
from .models import MeiliIngestResult
from .vectorizer import BgeM3Vectorizer, load_rulings_map, vectorize_cards_batch_file

logger = logging.getLogger("etl.meilisearch.pipeline")


def _mask_secret(secret: str | None) -> str:
    if not secret:
        return "<empty>"
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}***{secret[-2:]}"


def _select_batches(
    batches: list[dict],
    from_batch: int | None,
    max_batches: int | None,
) -> list[dict]:
    selected = [
        batch
        for batch in batches
        if batch.get("status") != "uploaded"
        and (from_batch is None or int(batch["batch_id"]) >= from_batch)
    ]
    if max_batches is not None:
        return selected[:max_batches]
    return selected


def run_meilisearch_ingest(
    cards_path: Path | None,
    rulings_path: Path | None,
    data_root: Path,
    meili_url: str,
    meili_api_key: str | None,
    index_uid: str,
    settings_path: Path,
    model_name: str = "BAAI/bge-m3",
    batch_size: int = 128,
    upload_batch_size: int = 1000,
    full_upload_batch: bool = False,
    resume: bool = True,
    from_batch: int | None = None,
    max_batches: int | None = None,
) -> MeiliIngestResult:
    if not 1 <= batch_size <= 2048:
        raise ValueError(f"batch_size must be between 1 and 2048, got {batch_size}")

    paths = EtlPaths.for_today(data_root)
    resolved_cards_path = cards_path if cards_path is not None else paths.cards_latest_jsonl()
    resolved_rulings_path = (
        rulings_path if rulings_path is not None else paths.rulings_latest_jsonl()
    )
    state_path = paths.meili_ingest_state_file()

    run_started_at = perf_counter()
    logger.info("ENTER run_meilisearch_ingest index_uid=%s", index_uid)
    logger.debug(
        "ingest params cards_path=%s rulings_path=%s data_root=%s meili_url=%s "
        "api_key=%s model=%s batch_size=%s upload_batch_size=%s full_upload_batch=%s "
        "resume=%s from_batch=%s max_batches=%s",
        resolved_cards_path,
        resolved_rulings_path,
        data_root,
        meili_url,
        _mask_secret(meili_api_key),
        model_name,
        batch_size,
        upload_batch_size,
        full_upload_batch,
        resume,
        from_batch,
        max_batches,
    )

    if not resolved_cards_path.exists():
        raise FileNotFoundError(f"Cards file not found: {resolved_cards_path}")
    if not settings_path.exists():
        raise FileNotFoundError(f"Meilisearch settings file not found: {settings_path}")

    state = load_state(state_path)
    if state is None or not resume:
        logger.info("Initializing ingest state from existing card batches")
        state = build_ingest_state_from_existing_batches(
            cards_path=resolved_cards_path,
            batches_dir=paths.cards_batches_dir(),
        )
        write_json_atomic(state_path, state)

    batches_to_process = _select_batches(
        batches=state.get("batches", []),
        from_batch=from_batch,
        max_batches=max_batches,
    )
    logger.info("Batches selected for execution: %s", len(batches_to_process))

    if not batches_to_process:
        logger.info("No pending batches to process")
        return MeiliIngestResult(
            vectorized_count=0,
            uploaded_batches=0,
            vectorized_path=str(paths.cards_vectorized_latest_jsonl()),
            index_uid=index_uid,
        )

    vectorizer_started_at = perf_counter()
    logger.info("ENTER step=init_vectorizer model=%s", model_name)
    vectorizer = BgeM3Vectorizer(model_name=model_name)
    logger.info(
        "EXIT  step=init_vectorizer duration_sec=%.3f",
        perf_counter() - vectorizer_started_at,
    )

    rulings_started_at = perf_counter()
    logger.info("ENTER step=load_rulings_map")
    rulings_map = load_rulings_map(resolved_rulings_path)
    logger.info(
        "EXIT  step=load_rulings_map duration_sec=%.3f oracle_ids=%s",
        perf_counter() - rulings_started_at,
        len(rulings_map),
    )

    meili_started_at = perf_counter()
    logger.info("ENTER step=prepare_meilisearch index_uid=%s", index_uid)
    client = MeiliSearchClient(url=meili_url, api_key=meili_api_key)
    try:
        client.enable_vector_store_experimental()
        client.ensure_index(index_uid=index_uid, primary_key="id")
        client.update_settings(index_uid=index_uid, settings_path=settings_path)
        logger.info(
            "EXIT  step=prepare_meilisearch duration_sec=%.3f",
            perf_counter() - meili_started_at,
        )

        for batch in batches_to_process:
            batch_id = int(batch["batch_id"])
            batch_started_at = perf_counter()
            logger.info("ENTER batch=%s status=%s", batch_id, batch.get("status"))

            try:
                input_path = Path(batch["input_path"])
                if not input_path.exists():
                    raise FileNotFoundError(f"Batch input not found: {input_path}")

                vectorized_path = paths.vectorized_batches_dir() / f"batch_{batch_id:06d}.jsonl"

                if batch.get("status") != "vectorized" or not vectorized_path.exists():
                    batch["status"] = "pending"
                    batch["started_at"] = now_iso()
                    batch["error"] = None
                    state["updated_at"] = now_iso()
                    write_json_atomic(state_path, state)

                    vectorize_started_at = perf_counter()
                    vectorized_count = vectorize_cards_batch_file(
                        cards_path=input_path,
                        rulings_map=rulings_map,
                        output_path=vectorized_path,
                        vectorizer=vectorizer,
                        batch_size=batch_size,
                        embedder_name="bge_m3",
                    )
                    batch["vectorized_path"] = str(vectorized_path)
                    batch["status"] = "vectorized"
                    batch["finished_at"] = now_iso()
                    state["updated_at"] = now_iso()
                    write_json_atomic(state_path, state)
                    logger.info(
                        "EXIT  batch=%s step=vectorize duration_sec=%.3f rows=%s",
                        batch_id,
                        perf_counter() - vectorize_started_at,
                        vectorized_count,
                    )
                else:
                    logger.info(
                        "Skipping vectorization for batch=%s (already vectorized)",
                        batch_id,
                    )

                upload_started_at = perf_counter()
                upload_batches = client.add_documents_jsonl(
                    index_uid=index_uid,
                    jsonl_path=vectorized_path,
                    batch_size=upload_batch_size,
                    full_batch=full_upload_batch,
                )
                batch["upload_batches"] = int(upload_batches)
                batch["status"] = "uploaded"
                batch["finished_at"] = now_iso()
                state["updated_at"] = now_iso()
                write_json_atomic(state_path, state)
                logger.info(
                    "EXIT  batch=%s step=upload duration_sec=%.3f upload_batches=%s",
                    batch_id,
                    perf_counter() - upload_started_at,
                    upload_batches,
                )
            except Exception as exc:
                batch["status"] = "failed"
                batch["error"] = str(exc)
                batch["finished_at"] = now_iso()
                state["updated_at"] = now_iso()
                write_json_atomic(state_path, state)
                logger.error("Batch %s failed: %s", batch_id, exc)
                raise
            finally:
                logger.info(
                    "EXIT  batch=%s duration_sec=%.3f final_status=%s",
                    batch_id,
                    perf_counter() - batch_started_at,
                    batch.get("status"),
                )
    finally:
        client.close()

    last_vectorized_paths = [
        Path(batch["vectorized_path"])
        for batch in state.get("batches", [])
        if batch.get("vectorized_path") and Path(batch["vectorized_path"]).exists()
    ]
    latest_path = paths.cards_vectorized_latest_jsonl()
    if last_vectorized_paths:
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(last_vectorized_paths[-1], latest_path)

    logger.info(
        "EXIT  run_meilisearch_ingest duration_sec=%.3f",
        perf_counter() - run_started_at,
    )

    uploaded_batches_total = sum(
        int(batch.get("upload_batches", 0)) for batch in state.get("batches", [])
    )
    vectorized_rows_total = sum(
        int(batch.get("row_count", 0))
        for batch in state.get("batches", [])
        if batch.get("status") in {"vectorized", "uploaded"}
    )

    return MeiliIngestResult(
        vectorized_count=vectorized_rows_total,
        uploaded_batches=uploaded_batches_total,
        vectorized_path=str(latest_path),
        index_uid=index_uid,
    )

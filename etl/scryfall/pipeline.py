from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from etl.meilisearch.batching import (
    build_ingest_state,
    split_cards_into_batches,
    write_json_atomic,
)
from etl.paths import DEFAULT_DATA_ROOT, EtlPaths

from .client import ScryfallClient
from .models import ScryfallEtlState
from .transform import (
    transform_raw_cards,
    transform_raw_rulings,
    write_jsonl,
    write_parquet,
)

logger = logging.getLogger("etl.scryfall.pipeline")


def _read_state(state_path: Path) -> ScryfallEtlState | None:
    if not state_path.exists():
        return None

    with state_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return ScryfallEtlState.model_validate(payload)


def _write_state(state: ScryfallEtlState, state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as file:
        json.dump(state.model_dump(mode="json"), file, ensure_ascii=False, indent=2)


def run_scryfall_etl(
    dataset_type: str = "oracle_cards",
    force: bool = False,
    output_parquet: bool = True,
    data_root: Path = DEFAULT_DATA_ROOT,
    batch_docs: int = 2000,
) -> dict[str, str | int | bool | None]:
    run_started_at = perf_counter()
    paths = EtlPaths.for_today(data_root)
    logger.info("ENTER run_scryfall_etl dataset=%s force=%s", dataset_type, force)
    logger.debug(
        "run_scryfall_etl params data_root=%s output_parquet=%s batch_docs=%s",
        data_root,
        output_parquet,
        batch_docs,
    )

    now = datetime.now(UTC)
    state_path = paths.state_file(dataset_type)
    raw_path = paths.raw_file(dataset_type)
    processed_jsonl_path = paths.processed_jsonl(dataset_type)
    processed_parquet_path = paths.processed_parquet(dataset_type)
    latest_jsonl_path = paths.latest_jsonl(dataset_type)
    latest_parquet_path = paths.latest_parquet(dataset_type)

    client = ScryfallClient()
    meta_started_at = perf_counter()
    logger.info("ENTER step=get_bulk_dataset_metadata dataset=%s", dataset_type)
    dataset_metadata = client.get_bulk_dataset_metadata(dataset_type=dataset_type)
    meta_elapsed = perf_counter() - meta_started_at
    logger.info(
        "EXIT  step=get_bulk_dataset_metadata dataset=%s duration_sec=%.3f",
        dataset_type,
        meta_elapsed,
    )
    logger.debug(
        "metadata updated_at=%s download_uri=%s",
        dataset_metadata.updated_at.isoformat(),
        dataset_metadata.download_uri,
    )

    previous_state = _read_state(paths.resolve_legacy_read_path(state_path))
    if (
        not force
        and previous_state is not None
        and previous_state.bulk_updated_at == dataset_metadata.updated_at
    ):
        logger.info("Dataset unchanged on Scryfall, skipping extract/transform/load")
        jsonl_path = (
            str(latest_jsonl_path)
            if latest_jsonl_path.exists()
            else previous_state.processed_jsonl_path
        )
        parquet_path = (
            str(latest_parquet_path)
            if latest_parquet_path.exists()
            else previous_state.processed_parquet_path
        )
        result = {
            "updated": False,
            "reason": "Dataset unchanged on Scryfall",
            "dataset_type": dataset_type,
            "bulk_updated_at": dataset_metadata.updated_at.isoformat(),
            "row_count": previous_state.row_count,
            "processed_jsonl_path": jsonl_path,
            "processed_parquet_path": parquet_path,
        }
        logger.info(
            "EXIT  run_scryfall_etl dataset=%s duration_sec=%.3f updated=false rows=%s",
            dataset_type,
            perf_counter() - run_started_at,
            previous_state.row_count,
        )
        return result

    extract_started_at = perf_counter()
    logger.info("ENTER step=download_bulk_file path=%s", raw_path)
    client.download_json_file(url=dataset_metadata.download_uri, destination=raw_path)
    extract_elapsed = perf_counter() - extract_started_at
    logger.info(
        "EXIT  step=download_bulk_file duration_sec=%.3f",
        extract_elapsed,
    )

    transform_started_at = perf_counter()
    logger.info("ENTER step=transform dataset=%s", dataset_type)
    if dataset_type == "rulings":
        records = transform_raw_rulings(raw_file_path=raw_path)
    else:
        records = transform_raw_cards(raw_file_path=raw_path)
    transform_elapsed = perf_counter() - transform_started_at
    logger.info(
        "EXIT  step=transform dataset=%s duration_sec=%.3f rows=%s",
        dataset_type,
        transform_elapsed,
        len(records),
    )
    logger.debug("transform output sample_path=%s", raw_path)

    jsonl_started_at = perf_counter()
    logger.info("ENTER step=write_jsonl path=%s", processed_jsonl_path)
    write_jsonl(records=records, output_path=processed_jsonl_path)
    shutil.copy2(processed_jsonl_path, latest_jsonl_path)
    jsonl_elapsed = perf_counter() - jsonl_started_at
    logger.info("EXIT  step=write_jsonl duration_sec=%.3f", jsonl_elapsed)
    logger.debug("latest_jsonl_path=%s", latest_jsonl_path)

    parquet_path: Path | None = None
    if output_parquet:
        parquet_started_at = perf_counter()
        logger.info("ENTER step=write_parquet path=%s", processed_parquet_path)
        parquet_path = write_parquet(records=records, output_path=processed_parquet_path)
        shutil.copy2(parquet_path, latest_parquet_path)
        parquet_elapsed = perf_counter() - parquet_started_at
        logger.info("EXIT  step=write_parquet duration_sec=%.3f", parquet_elapsed)
        logger.debug("latest_parquet_path=%s", latest_parquet_path)

    state_started_at = perf_counter()
    logger.info("ENTER step=write_state path=%s", state_path)
    state = ScryfallEtlState(
        dataset_type=dataset_type,
        bulk_updated_at=dataset_metadata.updated_at,
        download_uri=dataset_metadata.download_uri,
        downloaded_at=now,
        raw_path=str(raw_path),
        processed_jsonl_path=str(processed_jsonl_path),
        processed_parquet_path=str(parquet_path) if parquet_path else None,
        row_count=len(records),
    )
    _write_state(state=state, state_path=state_path)
    state_elapsed = perf_counter() - state_started_at
    logger.info("EXIT  step=write_state duration_sec=%.3f", state_elapsed)

    if dataset_type != "rulings":
        batch_started_at = perf_counter()
        logger.info("ENTER step=split_cards_batches batch_docs=%s", batch_docs)
        batch_items = split_cards_into_batches(
            cards_path=latest_jsonl_path,
            batches_dir=paths.cards_batches_dir(),
            batch_docs=batch_docs,
        )
        ingest_state = build_ingest_state(
            cards_path=latest_jsonl_path,
            batch_docs=batch_docs,
            batch_items=batch_items,
        )
        write_json_atomic(paths.meili_ingest_state_file(), ingest_state)
        logger.info(
            "EXIT  step=split_cards_batches duration_sec=%.3f batches=%s",
            perf_counter() - batch_started_at,
            len(batch_items),
        )

    result = {
        "updated": True,
        "dataset_type": dataset_type,
        "bulk_updated_at": dataset_metadata.updated_at.isoformat(),
        "row_count": len(records),
        "raw_path": str(raw_path),
        "processed_jsonl_path": str(processed_jsonl_path),
        "processed_parquet_path": str(parquet_path) if parquet_path else None,
        "state_path": str(state_path),
    }
    total_elapsed = perf_counter() - run_started_at
    logger.info(
        "EXIT  run_scryfall_etl dataset=%s duration_sec=%.3f updated=true rows=%s",
        dataset_type,
        total_elapsed,
        len(records),
    )
    return result


def run_scryfall_etl_with_optional_rulings(
    dataset_type: str = "oracle_cards",
    include_rulings: bool = False,
    force: bool = False,
    output_parquet: bool = True,
    data_root: Path = DEFAULT_DATA_ROOT,
    batch_docs: int = 2000,
) -> dict[str, object]:
    parent_started_at = perf_counter()
    logger.info(
        "ENTER run_scryfall_etl_with_optional_rulings dataset=%s include_rulings=%s",
        dataset_type,
        include_rulings,
    )
    datasets = [dataset_type]
    if include_rulings and "rulings" not in datasets:
        datasets.append("rulings")

    results: dict[str, object] = {}
    for dataset in datasets:
        results[dataset] = run_scryfall_etl(
            dataset_type=dataset,
            force=force,
            output_parquet=output_parquet,
            data_root=data_root,
            batch_docs=batch_docs,
        )
    elapsed = perf_counter() - parent_started_at
    logger.info(
        "EXIT  run_scryfall_etl_with_optional_rulings duration_sec=%.3f datasets=%s",
        elapsed,
        datasets,
    )
    return {"datasets": datasets, "results": results}

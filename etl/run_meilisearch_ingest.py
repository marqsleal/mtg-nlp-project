from __future__ import annotations

import argparse
import json
import os
from multiprocessing import cpu_count
from pathlib import Path

from etl.logging_utils import configure_logging
from etl.meilisearch.embedding_profiles import profile_choices
from etl.meilisearch.pipeline import run_meilisearch_ingest
from etl.paths import DEFAULT_DATA_ROOT, EtlPaths


def _embedding_batch_size(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 2048:
        raise argparse.ArgumentTypeError("embedding batch size must be between 1 and 2048")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _default_cpu_threads() -> int:
    return max(1, cpu_count())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Vectorize Scryfall cards with sentence-transformers and load to Meilisearch."
    )
    parser.add_argument(
        "--cards-path",
        default=None,
        help="Cards JSONL input path. Defaults to centralized ETL pathing.",
    )
    parser.add_argument(
        "--rulings-path",
        default=None,
        help="Rulings JSONL input path. Defaults to centralized ETL pathing.",
    )
    parser.add_argument(
        "--data-root",
        default=str(DEFAULT_DATA_ROOT),
        help="Data root for processed artifacts.",
    )
    parser.add_argument(
        "--meili-url",
        default=os.getenv("MEILISEARCH_URL", "http://127.0.0.1:7700"),
        help="Meilisearch base URL.",
    )
    parser.add_argument(
        "--meili-api-key",
        default=os.getenv("MEILISEARCH_API_KEY"),
        help="Meilisearch API key.",
    )
    parser.add_argument(
        "--index-uid",
        default=os.getenv("MEILISEARCH_INDEX_UID", "mtg_cards"),
        help="Meilisearch index UID.",
    )
    parser.add_argument(
        "--settings-path",
        default="db/meilisearch/index_settings.json",
        help="Path to Meilisearch index settings JSON.",
    )
    parser.add_argument(
        "--model-profile",
        default=os.getenv("EMBEDDING_MODEL_PROFILE", "bge_small_en_v15"),
        choices=profile_choices(),
        help="Embedding profile configured in etl/meilisearch/embedding_profiles.py.",
    )
    parser.add_argument(
        "--batch-size",
        type=_embedding_batch_size,
        default=128,
        help="Embedding batch size.",
    )
    parser.add_argument(
        "--encode-batch-size",
        type=_positive_int,
        default=int(os.getenv("EMBEDDING_ENCODE_BATCH_SIZE", "256")),
        help="Sentence-transformers internal encode batch size.",
    )
    parser.add_argument(
        "--cpu-threads",
        type=_positive_int,
        default=int(os.getenv("EMBEDDING_CPU_THREADS", str(_default_cpu_threads()))),
        help="Number of CPU threads used by torch during embedding.",
    )
    parser.add_argument(
        "--upload-batch-size",
        type=_positive_int,
        default=2000,
        help="Upload batch size for Meilisearch documents.",
    )
    parser.add_argument(
        "--upload-wait-tasks-every",
        type=_non_negative_int,
        default=int(os.getenv("MEILI_UPLOAD_WAIT_TASKS_EVERY", "8")),
        help="How many upload tasks to queue before waiting (0 waits only at the end).",
    )
    parser.add_argument(
        "--full-upload-batch",
        action="store_true",
        help="Upload all documents to Meilisearch in a single request batch.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore previous ingest state and rebuild batches from scratch.",
    )
    parser.add_argument(
        "--from-batch",
        type=_positive_int,
        default=None,
        help="Start processing from this batch id (1-based).",
    )
    parser.add_argument(
        "--max-batches",
        type=_positive_int,
        default=None,
        help="Process at most this many batches in this run.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level for pipeline execution.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    data_root = Path(args.data_root)
    resolved_paths = EtlPaths.for_today(data_root)

    cards_path = Path(args.cards_path) if args.cards_path else resolved_paths.cards_latest_jsonl()
    rulings_path = (
        Path(args.rulings_path) if args.rulings_path else resolved_paths.rulings_latest_jsonl()
    )

    result = run_meilisearch_ingest(
        cards_path=cards_path,
        rulings_path=rulings_path,
        data_root=resolved_paths.data_root,
        meili_url=args.meili_url,
        meili_api_key=args.meili_api_key,
        index_uid=args.index_uid,
        settings_path=Path(args.settings_path),
        embedding_profile=args.model_profile,
        batch_size=args.batch_size,
        encode_batch_size=args.encode_batch_size,
        cpu_threads=args.cpu_threads,
        upload_batch_size=args.upload_batch_size,
        upload_wait_tasks_every=args.upload_wait_tasks_every,
        full_upload_batch=args.full_upload_batch,
        resume=not args.no_resume,
        from_batch=args.from_batch,
        max_batches=args.max_batches,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

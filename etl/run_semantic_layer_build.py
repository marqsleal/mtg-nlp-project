from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from etl.logging_utils import configure_logging
from etl.meilisearch.semantic_layer import run_semantic_layer_build


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _ratio_0_1(value: str) -> float:
    parsed = float(value)
    if parsed <= 0.0 or parsed > 1.0:
        raise argparse.ArgumentTypeError("value must be in (0, 1]")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build semantic query-expansion layer from indexed MTG cards."
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
        "--source-index-uid",
        default=os.getenv("MEILISEARCH_INDEX_UID", "mtg_cards"),
        help="Source index uid (cards).",
    )
    parser.add_argument(
        "--target-index-uid",
        default=os.getenv("QUERY_SEMANTIC_LAYER_INDEX_UID", "mtg_domain_semantic_layer"),
        help="Target semantic layer index uid.",
    )
    parser.add_argument(
        "--settings-path",
        default="db/meilisearch/domain_semantic_layer_settings.json",
        help="Path to semantic layer index settings JSON.",
    )
    parser.add_argument(
        "--storage-root",
        default=os.getenv("STORAGE_ROOT", "storage"),
        help="Root directory for versioned artifacts.",
    )
    parser.add_argument(
        "--dataset-version",
        default=datetime.now(UTC).date().isoformat(),
        help="Dataset version label used in artifacts and documents.",
    )
    parser.add_argument(
        "--source-fetch-batch-size",
        type=_positive_int,
        default=1000,
        help="Batch size while reading source documents from Meilisearch.",
    )
    parser.add_argument(
        "--upload-batch-size",
        type=_positive_int,
        default=1000,
        help="Upload batch size for semantic layer documents.",
    )
    parser.add_argument(
        "--top-n",
        type=_positive_int,
        default=5,
        help="Top N expansions persisted per term.",
    )
    parser.add_argument(
        "--min-df",
        type=_positive_int,
        default=3,
        help="Minimum document frequency to keep term in semantic layer.",
    )
    parser.add_argument(
        "--min-pmi",
        type=_non_negative_float,
        default=0.30,
        help="Minimum NPMI score to keep expansion candidate.",
    )
    parser.add_argument(
        "--min-co-df",
        type=_positive_int,
        default=3,
        help="Minimum co-document frequency required for a term pair.",
    )
    parser.add_argument(
        "--max-df-ratio",
        type=_ratio_0_1,
        default=0.25,
        help="Maximum document-frequency ratio allowed for expansion terms.",
    )
    parser.add_argument(
        "--max-source-documents",
        type=_positive_int,
        default=None,
        help="Optional cap on source documents for debug runs.",
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
    result = run_semantic_layer_build(
        meili_url=args.meili_url,
        meili_api_key=args.meili_api_key,
        source_index_uid=args.source_index_uid,
        target_index_uid=args.target_index_uid,
        settings_path=Path(args.settings_path),
        storage_root=Path(args.storage_root),
        dataset_version=args.dataset_version,
        source_fetch_batch_size=args.source_fetch_batch_size,
        upload_batch_size=args.upload_batch_size,
        top_n=args.top_n,
        min_df=args.min_df,
        min_pmi=args.min_pmi,
        min_co_df=args.min_co_df,
        max_df_ratio=args.max_df_ratio,
        max_source_documents=args.max_source_documents,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

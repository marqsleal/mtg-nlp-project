from __future__ import annotations

import argparse
import json
from pathlib import Path

from etl.logging_utils import configure_logging
from etl.paths import DEFAULT_DATA_ROOT, EtlPaths
from etl.scryfall.pipeline import run_scryfall_etl_with_optional_rulings


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Scryfall bulk ETL.")
    parser.add_argument(
        "--dataset",
        default="unique_artwork",
        choices=["default_cards", "oracle_cards", "unique_artwork", "all_cards", "rulings"],
        help="Scryfall bulk dataset type.",
    )
    parser.add_argument(
        "--with-rulings",
        action="store_true",
        help="Also download and process the `rulings` dataset in the same run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even when source dataset is unchanged.",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Disable Parquet output and write JSONL only.",
    )
    parser.add_argument(
        "--data-root",
        default=str(DEFAULT_DATA_ROOT),
        help="Root directory used for raw/processed/state outputs.",
    )
    parser.add_argument(
        "--batch-docs",
        type=_positive_int,
        default=2000,
        help="Number of card documents per batch generated for Meilisearch ingestion.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level for pipeline execution.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    data_root = Path(args.data_root)
    resolved_paths = EtlPaths.for_today(data_root)
    result = run_scryfall_etl_with_optional_rulings(
        dataset_type=args.dataset,
        include_rulings=args.with_rulings,
        force=args.force,
        output_parquet=not args.no_parquet,
        data_root=resolved_paths.data_root,
        batch_docs=args.batch_docs,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

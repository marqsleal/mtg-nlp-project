from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DATA_ROOT = Path("etl/data")


def _dataset_output_base(dataset_type: str) -> str:
    if dataset_type == "rulings":
        return "scryfall_rullings"
    return "scryfall_cards"


@dataclass(frozen=True)
class EtlPaths:
    data_root: Path
    date_str: str

    @classmethod
    def for_today(cls, data_root: Path) -> EtlPaths:
        return cls(data_root=data_root, date_str=datetime.now(UTC).date().isoformat())

    def raw_file(self, dataset_type: str) -> Path:
        return (
            self.data_root
            / "scryfall"
            / "raw"
            / f"{_dataset_output_base(dataset_type)}_{self.date_str}.json"
        )

    def processed_jsonl(self, dataset_type: str) -> Path:
        return (
            self.data_root
            / "scryfall"
            / "processed"
            / f"{_dataset_output_base(dataset_type)}_{self.date_str}.jsonl"
        )

    def processed_parquet(self, dataset_type: str) -> Path:
        return (
            self.data_root
            / "scryfall"
            / "processed"
            / f"{_dataset_output_base(dataset_type)}_{self.date_str}.parquet"
        )

    def latest_jsonl(self, dataset_type: str) -> Path:
        return (
            self.data_root
            / "scryfall"
            / "processed"
            / f"{_dataset_output_base(dataset_type)}_latest.jsonl"
        )

    def latest_parquet(self, dataset_type: str) -> Path:
        return (
            self.data_root
            / "scryfall"
            / "processed"
            / f"{_dataset_output_base(dataset_type)}_latest.parquet"
        )

    def state_file(self, dataset_type: str) -> Path:
        return (
            self.data_root
            / "scryfall"
            / "state"
            / f"{_dataset_output_base(dataset_type)}_state.json"
        )

    def cards_latest_jsonl(self) -> Path:
        return self.latest_jsonl("cards")

    def rulings_latest_jsonl(self) -> Path:
        return self.latest_jsonl("rulings")

    def cards_vectorized_jsonl(self) -> Path:
        return (
            self.data_root
            / "meilisearch"
            / "processed"
            / f"scryfall_cards_vectorized_{self.date_str}.jsonl"
        )

    def cards_vectorized_latest_jsonl(self) -> Path:
        return (
            self.data_root / "meilisearch" / "processed" / "scryfall_cards_vectorized_latest.jsonl"
        )

    def cards_batches_dir(self) -> Path:
        return self.data_root / "meilisearch" / "batches" / "input" / "cards"

    def vectorized_batches_dir(self) -> Path:
        return self.data_root / "meilisearch" / "batches" / "vectorized" / "cards"

    def meili_ingest_state_file(self) -> Path:
        return self.data_root / "meilisearch" / "state" / "ingest_cards_state.json"

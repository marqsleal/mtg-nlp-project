from __future__ import annotations

import json
from pathlib import Path

import httpx

from .models import ScryfallBulkDataItem, ScryfallBulkDataResponse

SCRYFALL_BULK_DATA_URL = "https://api.scryfall.com/bulk-data"


class ScryfallClient:
    def __init__(self, timeout_seconds: float = 120.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_bulk_dataset_metadata(self, dataset_type: str) -> ScryfallBulkDataItem:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(SCRYFALL_BULK_DATA_URL)
            response.raise_for_status()
            payload = ScryfallBulkDataResponse.model_validate(response.json())

        for item in payload.data:
            if item.type == dataset_type:
                return item

        valid_types = ", ".join(sorted({item.type for item in payload.data}))
        raise ValueError(f"Dataset type '{dataset_type}' not found. Available: {valid_types}")

    def download_json_file(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)

        with httpx.stream("GET", url, timeout=self.timeout_seconds) as response:
            response.raise_for_status()
            with destination.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)

        with destination.open("r", encoding="utf-8") as file:
            json.load(file)

        return destination

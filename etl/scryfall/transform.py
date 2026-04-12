from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ScryfallCard, ScryfallRuling


def _card_to_record(card: ScryfallCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "oracle_id": card.oracle_id,
        "name": card.name,
        "lang": card.lang,
        "released_at": card.released_at.isoformat() if card.released_at else None,
        "set": card.set,
        "set_name": card.set_name,
        "collector_number": card.collector_number,
        "rarity": card.rarity,
        "mana_cost": card.mana_cost,
        "cmc": float(card.cmc) if card.cmc is not None else None,
        "type_line": card.type_line,
        "oracle_text": card.oracle_text,
        "colors": card.colors,
        "color_identity": card.color_identity,
        "keywords": card.keywords,
        "legalities": card.legalities,
        "prices": card.prices,
        "image_uris": card.image_uris,
        "card_faces": (
            [face.model_dump(mode="json") for face in card.card_faces] if card.card_faces else None
        ),
    }


def transform_raw_cards(raw_file_path: Path) -> list[dict[str, Any]]:
    with raw_file_path.open("r", encoding="utf-8") as file:
        cards_data = json.load(file)

    unique_cards: dict[str, dict[str, Any]] = {}
    for card_data in cards_data:
        card = ScryfallCard.model_validate(card_data)
        unique_cards[card.id] = _card_to_record(card)

    return list(unique_cards.values())


def transform_raw_rulings(raw_file_path: Path) -> list[dict[str, Any]]:
    with raw_file_path.open("r", encoding="utf-8") as file:
        rulings_data = json.load(file)

    unique_rulings: dict[str, dict[str, Any]] = {}
    for ruling_data in rulings_data:
        ruling = ScryfallRuling.model_validate(ruling_data)
        key = (
            f"{ruling.oracle_id}|{ruling.source}|{ruling.published_at.isoformat()}|{ruling.comment}"
        )
        unique_rulings[key] = {
            "oracle_id": ruling.oracle_id,
            "source": ruling.source,
            "published_at": ruling.published_at.isoformat(),
            "comment": ruling.comment,
        }

    return list(unique_rulings.values())


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


def write_parquet(records: list[dict[str, Any]], output_path: Path) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "Parquet output requires pyarrow. Install dependencies with Poetry before running."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records)
    pq.write_table(table, output_path)
    return output_path

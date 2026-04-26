from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ScryfallCard, ScryfallRuling


def _normalize_optional_text(value: str | None, *, lower: bool = False) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return None
    return normalized.lower() if lower else normalized


def _normalize_required_text(value: str, *, lower: bool = False) -> str:
    normalized = _normalize_optional_text(value, lower=lower)
    if normalized is None:
        return ""
    return normalized


def _normalize_optional_symbol_list(
    values: list[str] | None,
    *,
    upper: bool = True,
) -> list[str] | None:
    if values is None:
        return None

    seen: set[str] = set()
    normalized_values: list[str] = []
    for value in values:
        item = value.strip()
        if not item:
            continue
        if upper:
            item = item.upper()
        if item in seen:
            continue
        seen.add(item)
        normalized_values.append(item)

    return normalized_values or None


def _normalize_keyword_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized_values: list[str] = []
    for value in values:
        item = value.strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        normalized_values.append(item)
    return normalized_values


def _normalize_legalities(legalities: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in legalities.items():
        key = raw_key.strip().lower()
        value = raw_value.strip().lower()
        if not key or not value:
            continue
        normalized[key] = value
    return normalized


def _normalize_card_faces(card: ScryfallCard) -> list[dict[str, Any]] | None:
    if not card.card_faces:
        return None

    faces: list[dict[str, Any]] = []
    for face in card.card_faces:
        faces.append(
            {
                "name": _normalize_optional_text(face.name),
                "mana_cost": _normalize_optional_text(face.mana_cost),
                "type_line": _normalize_optional_text(face.type_line),
                "oracle_text": _normalize_optional_text(face.oracle_text),
                "power": _normalize_optional_text(face.power),
                "toughness": _normalize_optional_text(face.toughness),
                "loyalty": _normalize_optional_text(face.loyalty),
                "image_uris": face.image_uris,
            }
        )
    return faces


def _card_to_record(card: ScryfallCard) -> dict[str, Any]:
    # Prefer oracle_id as canonical identity so search/index can collapse print variants.
    canonical_oracle_id = card.oracle_id.strip() if card.oracle_id else ""
    canonical_oracle_id = canonical_oracle_id or card.id

    return {
        "id": canonical_oracle_id,
        "oracle_id": canonical_oracle_id,
        "name": _normalize_required_text(card.name),
        "lang": _normalize_required_text(card.lang, lower=True),
        "released_at": card.released_at.isoformat() if card.released_at else None,
        "set": _normalize_required_text(card.set, lower=True),
        "set_name": _normalize_optional_text(card.set_name),
        "collector_number": _normalize_optional_text(card.collector_number),
        "rarity": _normalize_required_text(card.rarity, lower=True),
        "mana_cost": _normalize_optional_text(card.mana_cost),
        "cmc": float(card.cmc) if card.cmc is not None else None,
        "type_line": _normalize_optional_text(card.type_line),
        "oracle_text": _normalize_optional_text(card.oracle_text),
        "colors": _normalize_optional_symbol_list(card.colors),
        "color_identity": _normalize_optional_symbol_list(card.color_identity),
        "keywords": _normalize_keyword_list(card.keywords),
        "legalities": _normalize_legalities(card.legalities),
        "prices": card.prices,
        "image_uris": card.image_uris,
        "card_faces": _normalize_card_faces(card),
    }


def transform_raw_cards(raw_file_path: Path) -> list[dict[str, Any]]:
    with raw_file_path.open("r", encoding="utf-8") as file:
        cards_data = json.load(file)

    unique_cards: dict[str, dict[str, Any]] = {}
    for card_data in cards_data:
        card = ScryfallCard.model_validate(card_data)
        record = _card_to_record(card)
        unique_cards[record["id"]] = record

    return list(unique_cards.values())


def transform_raw_rulings(raw_file_path: Path) -> list[dict[str, Any]]:
    with raw_file_path.open("r", encoding="utf-8") as file:
        rulings_data = json.load(file)

    unique_rulings: dict[str, dict[str, Any]] = {}
    for ruling_data in rulings_data:
        ruling = ScryfallRuling.model_validate(ruling_data)
        normalized_comment = _normalize_required_text(ruling.comment)
        normalized_source = _normalize_required_text(ruling.source, lower=True)
        key = (
            f"{ruling.oracle_id}|{normalized_source}|"
            f"{ruling.published_at.isoformat()}|{normalized_comment}"
        )
        unique_rulings[key] = {
            "oracle_id": ruling.oracle_id,
            "source": normalized_source,
            "published_at": ruling.published_at.isoformat(),
            "comment": normalized_comment,
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

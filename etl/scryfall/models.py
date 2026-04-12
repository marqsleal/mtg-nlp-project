from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ScryfallBulkDataItem(BaseModel):
    id: str
    type: str
    name: str
    description: str
    download_uri: str
    updated_at: datetime
    size: int | None = None
    content_type: str | None = None
    content_encoding: str | None = None


class ScryfallBulkDataResponse(BaseModel):
    data: list[ScryfallBulkDataItem]


class ScryfallCardFace(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    mana_cost: str | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    image_uris: dict[str, str] | None = None


class ScryfallCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    oracle_id: str | None = None
    name: str
    lang: str
    released_at: date | None = None
    set: str
    set_name: str | None = None
    collector_number: str | None = None
    rarity: str
    mana_cost: str | None = None
    cmc: Decimal | float | int | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    colors: list[str] | None = None
    color_identity: list[str] | None = None
    keywords: list[str] = Field(default_factory=list)
    legalities: dict[str, str] = Field(default_factory=dict)
    prices: dict[str, str | None] = Field(default_factory=dict)
    image_uris: dict[str, str] | None = None
    card_faces: list[ScryfallCardFace] | None = None


class ScryfallRuling(BaseModel):
    model_config = ConfigDict(extra="allow")

    oracle_id: str
    source: str
    published_at: date
    comment: str


class ScryfallEtlState(BaseModel):
    dataset_type: str
    bulk_updated_at: datetime
    download_uri: str
    downloaded_at: datetime
    raw_path: str
    processed_jsonl_path: str
    processed_parquet_path: str | None = None
    row_count: int

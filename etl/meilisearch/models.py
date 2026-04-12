from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MeiliCardDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

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
    cmc: float | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    colors: list[str] | None = None
    color_identity: list[str] | None = None
    keywords: list[str] = Field(default_factory=list)
    legalities: dict[str, str] = Field(default_factory=dict)
    rulings_text: str = ""
    search_text: str = ""


class MeiliIngestResult(BaseModel):
    vectorized_count: int
    uploaded_batches: int
    vectorized_path: str
    index_uid: str

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict


class EmbeddingProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile: str
    model_name: str
    dimensions: int
    embedder_name: str
    notes: str


EMBEDDING_PROFILES: dict[str, EmbeddingProfile] = {
    "bge_m3": EmbeddingProfile(
        profile="bge_m3",
        model_name="BAAI/bge-m3",
        dimensions=1024,
        embedder_name="bge_m3",
        notes="Multilingual, stronger quality baseline, heavier model.",
    ),
    "bge_small_en_v15": EmbeddingProfile(
        profile="bge_small_en_v15",
        model_name="BAAI/bge-small-en-v1.5",
        dimensions=384,
        embedder_name="bge_small_en_v15",
        notes="Lightweight and fast, best for mostly English queries.",
    ),
    "multilingual_e5_small": EmbeddingProfile(
        profile="multilingual_e5_small",
        model_name="intfloat/multilingual-e5-small",
        dimensions=384,
        embedder_name="multilingual_e5_small",
        notes="Lightweight multilingual option (good for PT/EN mixed search).",
    ),
    "paraphrase_multilingual_minilm_l12_v2": EmbeddingProfile(
        profile="paraphrase_multilingual_minilm_l12_v2",
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        dimensions=384,
        embedder_name="paraphrase_multilingual_minilm_l12_v2",
        notes="Fast multilingual baseline, usually lower retrieval quality than BGE/E5.",
    ),
}


def profile_choices() -> list[str]:
    return sorted(EMBEDDING_PROFILES.keys())


def get_profile(name: str) -> EmbeddingProfile:
    return EMBEDDING_PROFILES[name]


def sanitize_embedder_name(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise ValueError("embedder name cannot be empty")
    return normalized

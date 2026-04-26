from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

from .models import MeiliCardDocument


class SentenceTransformerVectorizer:
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        encode_batch_size: int = 256,
        cpu_threads: int | None = None,
    ) -> None:
        if encode_batch_size <= 0:
            raise ValueError("encode_batch_size must be > 0")
        if cpu_threads is not None and cpu_threads <= 0:
            raise ValueError("cpu_threads must be > 0 when provided")

        if cpu_threads is not None:
            torch.set_num_threads(cpu_threads)
            torch.set_num_interop_threads(max(1, min(cpu_threads, 8)))

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.encode_batch_size = encode_batch_size

    @property
    def embedding_dimension(self) -> int:
        if hasattr(self.model, "get_embedding_dimension"):
            dim = self.model.get_embedding_dimension()
        else:
            dim = self.model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError(f"Could not infer embedding dimension for model={self.model_name}")
        return int(dim)

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=min(len(texts), self.encode_batch_size),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


def _build_search_text(card: MeiliCardDocument) -> str:
    parts = [
        card.name,
        card.type_line or "",
        card.oracle_text or "",
        card.rulings_text,
        f"set:{card.set}",
        f"rarity:{card.rarity}",
        f"collector_number:{card.collector_number or ''}",
    ]
    return "\n".join(part for part in parts if part).strip()


def load_rulings_map(rulings_path: Path) -> dict[str, list[str]]:
    by_oracle_id: dict[str, list[str]] = defaultdict(list)
    if not rulings_path.exists():
        return by_oracle_id

    with rulings_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            item = json.loads(line)
            oracle_id = item.get("oracle_id")
            comment = item.get("comment")
            if oracle_id and comment:
                by_oracle_id[oracle_id].append(comment)

    return by_oracle_id


def vectorize_cards_batch_file(
    cards_path: Path,
    rulings_map: dict[str, list[str]],
    output_path: Path,
    vectorizer: SentenceTransformerVectorizer,
    batch_size: int = 128,
    embedder_name: str = "bge_m3",
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    batch_cards: list[dict[str, Any]] = []
    batch_texts: list[str] = []
    total = 0

    with (
        cards_path.open("r", encoding="utf-8") as in_file,
        output_path.open("w", encoding="utf-8") as out_file,
    ):
        for line in in_file:
            if not line.strip():
                continue

            raw_card = json.loads(line)
            card = MeiliCardDocument.model_validate(raw_card)
            card.rulings_text = "\n".join(rulings_map.get(card.oracle_id or "", []))
            card.search_text = _build_search_text(card)

            batch_cards.append(card.model_dump(mode="json"))
            batch_texts.append(card.search_text)

            if len(batch_cards) >= batch_size:
                vectors = vectorizer.encode(batch_texts)
                for record, vector in zip(batch_cards, vectors, strict=True):
                    record["_vectors"] = {embedder_name: vector}
                    out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total += 1
                batch_cards.clear()
                batch_texts.clear()

        if batch_cards:
            vectors = vectorizer.encode(batch_texts)
            for record, vector in zip(batch_cards, vectors, strict=True):
                record["_vectors"] = {embedder_name: vector}
                out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                total += 1

    return total


def vectorize_cards_file(
    cards_path: Path,
    rulings_path: Path,
    output_path: Path,
    vectorizer: SentenceTransformerVectorizer,
    batch_size: int = 128,
    embedder_name: str = "bge_m3",
) -> int:
    rulings_map = load_rulings_map(rulings_path)
    return vectorize_cards_batch_file(
        cards_path=cards_path,
        rulings_map=rulings_map,
        output_path=output_path,
        vectorizer=vectorizer,
        batch_size=batch_size,
        embedder_name=embedder_name,
    )


# Backward-compatible alias for existing imports.
BgeM3Vectorizer = SentenceTransformerVectorizer

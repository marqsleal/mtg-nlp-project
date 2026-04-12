from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def split_cards_into_batches(
    cards_path: Path,
    batches_dir: Path,
    batch_docs: int,
) -> list[dict[str, Any]]:
    batches_dir.mkdir(parents=True, exist_ok=True)

    for old_file in sorted(batches_dir.glob("batch_*.jsonl")):
        old_file.unlink()

    batch_items: list[dict[str, Any]] = []
    batch_id = 1
    current_count = 0
    current_path = batches_dir / f"batch_{batch_id:06d}.jsonl"
    current_file = current_path.open("w", encoding="utf-8")

    try:
        with cards_path.open("r", encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                if current_count >= batch_docs:
                    current_file.close()
                    batch_items.append(
                        {
                            "batch_id": batch_id,
                            "input_path": str(current_path),
                            "row_count": current_count,
                            "vectorized_path": "",
                            "status": "pending",
                            "started_at": None,
                            "finished_at": None,
                            "error": None,
                            "upload_batches": 0,
                        }
                    )
                    batch_id += 1
                    current_count = 0
                    current_path = batches_dir / f"batch_{batch_id:06d}.jsonl"
                    current_file = current_path.open("w", encoding="utf-8")

                current_file.write(line)
                current_count += 1

        current_file.close()
        if current_count > 0:
            batch_items.append(
                {
                    "batch_id": batch_id,
                    "input_path": str(current_path),
                    "row_count": current_count,
                    "vectorized_path": "",
                    "status": "pending",
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "upload_batches": 0,
                }
            )
        elif current_path.exists():
            current_path.unlink()
    finally:
        if not current_file.closed:
            current_file.close()

    return batch_items


def build_ingest_state(
    cards_path: Path,
    batch_docs: int,
    batch_items: list[dict[str, Any]],
) -> dict[str, Any]:
    stats = cards_path.stat()
    return {
        "source_cards_path": str(cards_path),
        "source_cards_mtime": stats.st_mtime,
        "source_cards_size": stats.st_size,
        "batch_docs": batch_docs,
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "batches": batch_items,
    }


def build_ingest_state_from_existing_batches(
    cards_path: Path,
    batches_dir: Path,
    default_batch_docs: int = 0,
) -> dict[str, Any]:
    batch_items: list[dict[str, Any]] = []
    for batch_file in sorted(batches_dir.glob("batch_*.jsonl")):
        row_count = 0
        with batch_file.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    row_count += 1
        if row_count == 0:
            continue
        batch_id = int(batch_file.stem.split("_")[-1])
        batch_items.append(
            {
                "batch_id": batch_id,
                "input_path": str(batch_file),
                "row_count": row_count,
                "vectorized_path": "",
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "error": None,
                "upload_batches": 0,
            }
        )
    return build_ingest_state(
        cards_path=cards_path,
        batch_docs=default_batch_docs,
        batch_items=batch_items,
    )

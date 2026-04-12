from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx


class MeiliSearchClient:
    def __init__(self, url: str, api_key: str | None = None, timeout_seconds: float = 60.0) -> None:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.url = url.rstrip("/")
        self.client = httpx.Client(base_url=self.url, headers=headers, timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def ensure_index(self, index_uid: str, primary_key: str = "id") -> None:
        response = self.client.get(f"/indexes/{index_uid}")
        if response.status_code == 200:
            return
        if response.status_code != 404:
            response.raise_for_status()

        create = self.client.post("/indexes", json={"uid": index_uid, "primaryKey": primary_key})
        create.raise_for_status()
        self.wait_for_task(create.json()["taskUid"])

    def enable_vector_store_experimental(self) -> None:
        response = self.client.patch(
            "/experimental-features/",
            json={"vectorStore": True},
        )
        response.raise_for_status()

    def update_settings(self, index_uid: str, settings_path: Path) -> None:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        response = self.client.patch(f"/indexes/{index_uid}/settings", json=payload)
        response.raise_for_status()
        self.wait_for_task(response.json()["taskUid"])

    def add_documents_jsonl(
        self,
        index_uid: str,
        jsonl_path: Path,
        batch_size: int = 1000,
        full_batch: bool = False,
    ) -> int:
        if full_batch:
            all_docs: list[dict[str, Any]] = []
            with jsonl_path.open("r", encoding="utf-8") as file:
                for line in file:
                    if not line.strip():
                        continue
                    all_docs.append(json.loads(line))

            if not all_docs:
                return 0

            response = self.client.post(f"/indexes/{index_uid}/documents", json=all_docs)
            response.raise_for_status()
            self.wait_for_task(response.json()["taskUid"])
            return 1

        current_batch: list[dict[str, Any]] = []
        uploaded_batches = 0
        with jsonl_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                current_batch.append(json.loads(line))
                if len(current_batch) >= batch_size:
                    response = self.client.post(
                        f"/indexes/{index_uid}/documents",
                        json=current_batch,
                    )
                    response.raise_for_status()
                    self.wait_for_task(response.json()["taskUid"])
                    uploaded_batches += 1
                    current_batch = []

        if current_batch:
            response = self.client.post(
                f"/indexes/{index_uid}/documents",
                json=current_batch,
            )
            response.raise_for_status()
            self.wait_for_task(response.json()["taskUid"])
            uploaded_batches += 1

        return uploaded_batches

    def wait_for_task(self, task_uid: int, timeout_seconds: int = 600) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            response = self.client.get(f"/tasks/{task_uid}")
            response.raise_for_status()
            task = response.json()
            status = task.get("status")
            if status == "succeeded":
                return task
            if status == "failed":
                raise RuntimeError(f"Meilisearch task {task_uid} failed: {task}")
            time.sleep(0.5)

        raise TimeoutError(f"Timeout waiting for Meilisearch task {task_uid}")

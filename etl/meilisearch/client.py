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
        self.api_key = api_key
        self.client = httpx.Client(base_url=self.url, headers=headers, timeout=timeout_seconds)
        self._negotiate_auth_mode()

    def _negotiate_auth_mode(self) -> None:
        if not self.api_key:
            return

        probe = self.client.get("/version")
        if probe.status_code == 200:
            return

        code = ""
        try:
            code = str(probe.json().get("code", ""))
        except Exception:
            code = ""

        if probe.status_code == 403 and code == "invalid_api_key":
            unauth_probe = self.client.get("/version", headers={"Authorization": ""})
            if unauth_probe.status_code == 200:
                self.client.headers.pop("Authorization", None)
                return

        probe.raise_for_status()

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

    def update_settings(
        self,
        index_uid: str,
        settings_path: Path,
        embedder_name: str,
        dimensions: int,
    ) -> None:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        payload.pop("embedders", None)
        response = self.client.patch(f"/indexes/{index_uid}/settings", json=payload)
        response.raise_for_status()
        self.wait_for_task(response.json()["taskUid"])
        self.replace_embedders(
            index_uid=index_uid,
            embedder_name=embedder_name,
            dimensions=dimensions,
        )

    def replace_embedders(self, index_uid: str, embedder_name: str, dimensions: int) -> None:
        current = self.client.get(f"/indexes/{index_uid}/settings")
        current.raise_for_status()
        current_embedders = current.json().get("embedders", {})

        payload: dict[str, Any] = {
            name: None for name in current_embedders if name != embedder_name
        }
        payload[embedder_name] = {
            "source": "userProvided",
            "dimensions": int(dimensions),
        }
        response = self.client.patch(f"/indexes/{index_uid}/settings/embedders", json=payload)
        response.raise_for_status()
        self.wait_for_task(response.json()["taskUid"])

    def add_documents_jsonl(
        self,
        index_uid: str,
        jsonl_path: Path,
        batch_size: int = 1000,
        full_batch: bool = False,
        wait_tasks_every: int = 8,
    ) -> int:
        if wait_tasks_every < 0:
            raise ValueError("wait_tasks_every must be >= 0")

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
        pending_tasks: list[int] = []
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
                    pending_tasks.append(int(response.json()["taskUid"]))
                    uploaded_batches += 1
                    current_batch = []
                    if wait_tasks_every > 0 and len(pending_tasks) >= wait_tasks_every:
                        for task_uid in pending_tasks:
                            self.wait_for_task(task_uid)
                        pending_tasks.clear()

        if current_batch:
            response = self.client.post(
                f"/indexes/{index_uid}/documents",
                json=current_batch,
            )
            response.raise_for_status()
            pending_tasks.append(int(response.json()["taskUid"]))
            uploaded_batches += 1

        for task_uid in pending_tasks:
            self.wait_for_task(task_uid)

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

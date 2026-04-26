from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("app.services.meilisearch")


class MeiliSearchService:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        index_uid: str,
        timeout_seconds: float = 30.0,
    ):
        logger.info("ENTER init_meilisearch_service index_uid=%s", index_uid)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
        )
        self.index_uid = index_uid
        self.api_key = api_key
        self._negotiate_auth_mode()
        logger.info("EXIT  init_meilisearch_service auth_header=%s", "yes" if api_key else "no")

    def _negotiate_auth_mode(self) -> None:
        logger.info("ENTER step=negotiate_auth_mode")
        if not self.api_key:
            logger.info("EXIT  step=negotiate_auth_mode mode=no_api_key")
            return

        probe = self.client.get("/version")
        if probe.status_code == 200:
            logger.info("EXIT  step=negotiate_auth_mode mode=api_key_valid")
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
                logger.info("EXIT  step=negotiate_auth_mode mode=fallback_unauthenticated")
                return

        probe.raise_for_status()

    def close(self) -> None:
        logger.info("ENTER close_meilisearch_service")
        self.client.close()
        logger.info("EXIT  close_meilisearch_service")

    def health(self) -> dict[str, Any]:
        response = self.client.get("/health")
        response.raise_for_status()
        return response.json()

    def _post_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"/indexes/{self.index_uid}/search", json=payload)
        response.raise_for_status()
        return response.json()

    def semantic_search(
        self,
        query: str,
        vector: list[float],
        embedder_name: str,
        semantic_ratio: float,
        limit: int,
        offset: int,
        search_filter: str | list[str] | None,
        attributes_to_retrieve: list[str] | None,
        show_ranking_score: bool,
    ) -> dict[str, Any]:
        logger.info(
            "ENTER semantic_search index_uid=%s limit=%s offset=%s has_filter=%s",
            self.index_uid,
            limit,
            offset,
            search_filter is not None,
        )
        payload: dict[str, Any] = {
            "q": query,
            "vector": vector,
            "hybrid": {
                "embedder": embedder_name,
                "semanticRatio": semantic_ratio,
            },
            "limit": limit,
            "offset": offset,
            "showRankingScore": show_ranking_score,
        }
        if search_filter is not None:
            payload["filter"] = search_filter
        if attributes_to_retrieve is not None:
            payload["attributesToRetrieve"] = attributes_to_retrieve

        result = self._post_search(payload)
        logger.info(
            "EXIT  semantic_search estimated_total_hits=%s processing_time_ms=%s",
            result.get("estimatedTotalHits", 0),
            result.get("processingTimeMs", 0),
        )
        return result

    def fts_search(
        self,
        query: str,
        limit: int,
        offset: int,
        search_filter: str | list[str] | None,
        attributes_to_retrieve: list[str] | None,
        show_ranking_score: bool,
    ) -> dict[str, Any]:
        logger.info(
            "ENTER fts_search index_uid=%s limit=%s offset=%s has_filter=%s",
            self.index_uid,
            limit,
            offset,
            search_filter is not None,
        )
        payload: dict[str, Any] = {
            "q": query,
            "limit": limit,
            "offset": offset,
            "showRankingScore": show_ranking_score,
        }
        if search_filter is not None:
            payload["filter"] = search_filter
        if attributes_to_retrieve is not None:
            payload["attributesToRetrieve"] = attributes_to_retrieve

        result = self._post_search(payload)
        logger.info(
            "EXIT  fts_search estimated_total_hits=%s processing_time_ms=%s",
            result.get("estimatedTotalHits", 0),
            result.get("processingTimeMs", 0),
        )
        return result

    def vector_search(
        self,
        vector: list[float],
        embedder_name: str,
        limit: int,
        offset: int,
        search_filter: str | list[str] | None,
        attributes_to_retrieve: list[str] | None,
        show_ranking_score: bool,
    ) -> dict[str, Any]:
        logger.info(
            "ENTER vector_search index_uid=%s limit=%s offset=%s has_filter=%s",
            self.index_uid,
            limit,
            offset,
            search_filter is not None,
        )
        payload: dict[str, Any] = {
            "q": "",
            "vector": vector,
            "hybrid": {
                "embedder": embedder_name,
                "semanticRatio": 1.0,
            },
            "limit": limit,
            "offset": offset,
            "showRankingScore": show_ranking_score,
        }
        if search_filter is not None:
            payload["filter"] = search_filter
        if attributes_to_retrieve is not None:
            payload["attributesToRetrieve"] = attributes_to_retrieve

        result = self._post_search(payload)
        logger.info(
            "EXIT  vector_search estimated_total_hits=%s processing_time_ms=%s",
            result.get("estimatedTotalHits", 0),
            result.get("processingTimeMs", 0),
        )
        return result

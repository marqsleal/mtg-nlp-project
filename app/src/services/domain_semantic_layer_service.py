from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Any

import httpx

logger = logging.getLogger("app.services.domain_semantic_layer")

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+'/-]*")


class DomainSemanticLayerService:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        index_uid: str,
        cache_ttl_seconds: int = 600,
        timeout_seconds: float = 10.0,
    ) -> None:
        logger.info(
            "ENTER init_domain_semantic_layer_service index_uid=%s cache_ttl_seconds=%s",
            index_uid,
            cache_ttl_seconds,
        )
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
        )
        self.api_key = api_key
        self.index_uid = index_uid
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._negotiate_auth_mode()
        logger.info("EXIT  init_domain_semantic_layer_service")

    def _negotiate_auth_mode(self) -> None:
        logger.info("ENTER step=negotiate_auth_mode_semantic_layer")
        if not self.api_key:
            logger.info("EXIT  step=negotiate_auth_mode_semantic_layer mode=no_api_key")
            return

        probe = self.client.get("/version")
        if probe.status_code == 200:
            logger.info("EXIT  step=negotiate_auth_mode_semantic_layer mode=api_key_valid")
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
                logger.info(
                    "EXIT  step=negotiate_auth_mode_semantic_layer mode=fallback_unauthenticated"
                )
                return
        probe.raise_for_status()

    def close(self) -> None:
        logger.info("ENTER close_domain_semantic_layer_service")
        self.client.close()
        logger.info("EXIT  close_domain_semantic_layer_service")

    def _normalize_query_terms(self, query: str) -> list[str]:
        tokens: list[str] = []
        for token in _TOKEN_RE.findall(query.lower()):
            if token.endswith("'s"):
                token = token[:-2]
            token = token.strip("'")
            if len(token) < 2:
                continue
            tokens.append(token)
        unique: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            unique.append(token)
        return unique

    def _search_term_document(self, term: str) -> list[dict[str, Any]]:
        if self.cache_ttl_seconds > 0:
            cached = self._cache.get(term)
            if cached is not None and cached[0] > time.time():
                return cached[1]

        payload = {
            "q": term,
            "limit": 8,
            "attributesToRetrieve": ["term", "expansions"],
            "showRankingScore": False,
        }
        response = self.client.post(f"/indexes/{self.index_uid}/search", json=payload)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", []) if isinstance(data, dict) else []
        expansions: list[dict[str, Any]] = []
        target_hit: dict[str, Any] | None = None
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            if str(hit.get("term", "")).lower() == term:
                target_hit = hit
                break

        if target_hit is not None:
            raw_expansions = target_hit.get("expansions", [])
            if isinstance(raw_expansions, list):
                for item in raw_expansions:
                    if not isinstance(item, dict):
                        continue
                    expansion_term = str(item.get("term") or "").strip().lower()
                    if not expansion_term:
                        continue
                    score = float(item.get("score", 0.0))
                    expansions.append({"term": expansion_term, "score": score})

        if self.cache_ttl_seconds > 0:
            self._cache[term] = (time.time() + self.cache_ttl_seconds, expansions)
        return expansions

    def expand_query(
        self,
        query: str,
        max_terms: int,
        min_score: float,
    ) -> tuple[bool, list[str], str | None]:
        logger.info(
            "ENTER expand_query query_len=%s max_terms=%s min_score=%.2f",
            len(query),
            max_terms,
            min_score,
        )
        query_terms = self._normalize_query_terms(query)
        if not query_terms or max_terms <= 0:
            logger.info("EXIT  expand_query applied=false expanded_terms=0")
            return False, [], None

        aggregated_scores: dict[str, float] = defaultdict(float)
        query_term_set = set(query_terms)
        for term in query_terms:
            expansions = self._search_term_document(term)
            for item in expansions:
                candidate = item["term"]
                score = float(item["score"])
                if score < min_score:
                    continue
                if candidate in query_term_set:
                    continue
                aggregated_scores[candidate] = max(aggregated_scores[candidate], score)

        ordered_terms = sorted(
            aggregated_scores.items(),
            key=lambda value: (value[1], value[0]),
            reverse=True,
        )
        expanded_terms = [term for term, _ in ordered_terms[:max_terms]]
        if not expanded_terms:
            logger.info("EXIT  expand_query applied=false expanded_terms=0")
            return False, [], None

        expanded_query = f"{query} {' '.join(expanded_terms)}"
        logger.info("EXIT  expand_query applied=true expanded_terms=%s", len(expanded_terms))
        return True, expanded_terms, expanded_query

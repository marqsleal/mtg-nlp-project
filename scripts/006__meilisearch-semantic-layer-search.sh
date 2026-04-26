#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "${ROOT_DIR}/.env" ]] && source "${ROOT_DIR}/.env"
: "${MEILISEARCH_URL:?MEILISEARCH_URL is required in .env}"
: "${MEILISEARCH_API_KEY:?MEILISEARCH_API_KEY is required in .env}"
: "${QUERY_SEMANTIC_LAYER_INDEX_UID:?QUERY_SEMANTIC_LAYER_INDEX_UID is required in .env}"

URL="${MEILISEARCH_URL}/indexes/${QUERY_SEMANTIC_LAYER_INDEX_UID}/search"
QUERY="counter"
LIMIT=5
PAYLOAD="{\"q\":\"${QUERY}\",\"limit\":${LIMIT},\"attributesToRetrieve\":[\"id\",\"term\",\"expansions\",\"dataset_version\",\"updated_at\"],\"showRankingScore\":true}"

TMP_BODY="$(mktemp)"
trap 'rm -f "${TMP_BODY}"' EXIT

CURL_EXIT=0
HTTP_STATUS=$(curl -s -o "${TMP_BODY}" -w "%{http_code}" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer ${MEILISEARCH_API_KEY}" "${URL}" -d "${PAYLOAD}" 2>/dev/null) || CURL_EXIT=$?

cat "${TMP_BODY}"

if [[ "${CURL_EXIT}" -eq 0 && "${HTTP_STATUS}" -ge 200 && "${HTTP_STATUS}" -lt 300 ]]; then
  exit 0
fi
exit 1

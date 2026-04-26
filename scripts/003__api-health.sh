#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "${ROOT_DIR}/.env" ]] && source "${ROOT_DIR}/.env"
: "${API_BASE_URL:?API_BASE_URL is required in .env}"

URL="${API_BASE_URL}/v1/ready"

TMP_BODY="$(mktemp)"
trap 'rm -f "${TMP_BODY}"' EXIT

CURL_EXIT=0
HTTP_STATUS=$(curl -s -o "${TMP_BODY}" -w "%{http_code}" "${URL}" 2>/dev/null) || CURL_EXIT=$?

cat "${TMP_BODY}"

if [[ "${CURL_EXIT}" -eq 0 && "${HTTP_STATUS}" -ge 200 && "${HTTP_STATUS}" -lt 300 ]]; then
  exit 0
fi
exit 1

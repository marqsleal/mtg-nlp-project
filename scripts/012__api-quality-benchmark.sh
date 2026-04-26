#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "${ROOT_DIR}/.env" ]] && source "${ROOT_DIR}/.env"
: "${API_BASE_URL:?API_BASE_URL is required in .env}"

DATASET_PATH="${ROOT_DIR}/scripts/data/issue5_eval_queries.tsv"
URL="${API_BASE_URL}/v1/search"
LIMIT=5

if [[ ! -f "${DATASET_PATH}" ]]; then
  echo "{\"error\":\"dataset_not_found\",\"path\":\"${DATASET_PATH}\"}"
  exit 1
fi

run_search() {
  local query="$1"
  local fusion_mode="$2"
  local query_expansion="$3"
  local payload
  payload="$(python3 - <<'PY' "$query" "$fusion_mode" "$query_expansion" "$LIMIT"
import json
import sys

query = sys.argv[1]
fusion_mode = sys.argv[2]
query_expansion = sys.argv[3].lower() == "true"
limit = int(sys.argv[4])
print(
    json.dumps(
        {
            "query": query,
            "limit": limit,
            "rerank": False,
            "show_ranking_score": True,
            "fusion_mode": fusion_mode,
            "query_expansion": query_expansion,
        }
    )
)
PY
)"
  curl -sS -X POST -H "Content-Type: application/json" "${URL}" -d "${payload}"
}

summarize_case() {
  local scenario="$1"
  local fusion_mode="$2"
  local query_expansion="$3"

  local total_ms=0
  local count=0
  local hit_at_k=0
  local status_ok=1

  while IFS=$'\t' read -r query expected_name; do
    [[ -z "${query}" ]] && continue
    response="$(run_search "${query}" "${fusion_mode}" "${query_expansion}")"

    proc_ms="$(python3 - <<'PY' "$response"
import json
import sys
data = json.loads(sys.argv[1])
print(int(data.get("meta", {}).get("processing_time_ms", 0)))
PY
)"
    found="$(python3 - <<'PY' "$response" "$expected_name"
import json
import sys
data = json.loads(sys.argv[1])
expected = sys.argv[2].strip().lower()
hits = data.get("hits", [])
found = any(str(hit.get("name", "")).strip().lower() == expected for hit in hits)
print("1" if found else "0")
PY
)"
    total_ms=$((total_ms + proc_ms))
    count=$((count + 1))
    hit_at_k=$((hit_at_k + found))
  done < "${DATASET_PATH}"

  if [[ "${count}" -eq 0 ]]; then
    status_ok=0
  fi

  avg_ms=0
  hit_rate=0
  if [[ "${count}" -gt 0 ]]; then
    avg_ms=$((total_ms / count))
    hit_rate="$(python3 - <<'PY' "$hit_at_k" "$count"
import sys
hits = int(sys.argv[1])
count = int(sys.argv[2])
print(round(hits / count, 4))
PY
)"
  fi

  printf '{"scenario":"%s","fusion_mode":"%s","query_expansion":%s,"samples":%s,"avg_processing_time_ms":%s,"hit_at_%s":%s,"ok":%s}' \
    "${scenario}" \
    "${fusion_mode}" \
    "${query_expansion}" \
    "${count}" \
    "${avg_ms}" \
    "${LIMIT}" \
    "${hit_rate}" \
    "${status_ok}"
}

printf '{"dataset":"%s","results":[' "${DATASET_PATH}"
summarize_case "baseline_hybrid" "hybrid" "false"
printf ','
summarize_case "rrf_only" "rrf" "false"
printf ','
summarize_case "hybrid_plus_expansion" "hybrid" "true"
printf ','
summarize_case "rrf_plus_expansion" "rrf" "true"
printf ']}'

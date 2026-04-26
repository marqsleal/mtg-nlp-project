#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "${ROOT_DIR}/.env" ]] && source "${ROOT_DIR}/.env"
: "${API_BASE_URL:?API_BASE_URL is required in .env}"

URL="${API_BASE_URL}/v1/search"
ITERATIONS=30

hybrid_count=0
rrf_count=0
expansion_enabled_count=0
expansion_applied_count=0

for i in $(seq 1 "${ITERATIONS}"); do
  query="rollout probe counter target spell ${i}"
  payload="$(python3 - <<'PY' "$query"
import json
import sys
print(
    json.dumps(
        {
            "query": sys.argv[1],
            "limit": 3,
            "rerank": False,
            "show_ranking_score": True,
        }
    )
)
PY
)"
  response="$(curl -sS -X POST -H "Content-Type: application/json" "${URL}" -d "${payload}")"

  readarray -t metrics < <(python3 - <<'PY' "$response"
import json
import sys
data = json.loads(sys.argv[1])
meta = data.get("meta", {})
print(str(meta.get("fusion_mode", "")))
print("1" if bool(meta.get("query_expansion_enabled", False)) else "0")
print("1" if bool(meta.get("query_expansion_applied", False)) else "0")
PY
)
  fusion_mode="${metrics[0]}"
  expansion_enabled="${metrics[1]}"
  expansion_applied="${metrics[2]}"

  if [[ "${fusion_mode}" == "rrf" ]]; then
    rrf_count=$((rrf_count + 1))
  else
    hybrid_count=$((hybrid_count + 1))
  fi

  expansion_enabled_count=$((expansion_enabled_count + expansion_enabled))
  expansion_applied_count=$((expansion_applied_count + expansion_applied))
done

printf '{"iterations":%s,"fusion_mode_counts":{"hybrid":%s,"rrf":%s},"query_expansion_enabled_count":%s,"query_expansion_applied_count":%s}' \
  "${ITERATIONS}" \
  "${hybrid_count}" \
  "${rrf_count}" \
  "${expansion_enabled_count}" \
  "${expansion_applied_count}"

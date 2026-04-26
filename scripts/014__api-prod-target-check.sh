#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAKEFILE_PATH="${ROOT_DIR}/Makefile"

if [[ ! -f "${MAKEFILE_PATH}" ]]; then
  echo "{\"ok\":false,\"error\":\"makefile_not_found\"}"
  exit 1
fi

api_prod_line="$(grep -n "^api_prod:" "${MAKEFILE_PATH}" || true)"
uvicorn_line="$(grep -n "uvicorn app.src.main:app" "${MAKEFILE_PATH}" | grep "workers" | head -n 1 || true)"
reload_found=0

if grep -A1 "^api_prod:" "${MAKEFILE_PATH}" | grep -q -- "--reload"; then
  reload_found=1
fi

if [[ -n "${api_prod_line}" && -n "${uvicorn_line}" && "${reload_found}" -eq 0 ]]; then
  echo "{\"ok\":true,\"api_prod_defined\":true,\"uses_workers\":true,\"uses_reload\":false}"
  exit 0
fi

echo "{\"ok\":false,\"api_prod_defined\":$([[ -n "${api_prod_line}" ]] && echo true || echo false),\"uses_workers\":$([[ -n "${uvicorn_line}" ]] && echo true || echo false),\"uses_reload\":$([[ "${reload_found}" -eq 1 ]] && echo true || echo false)}"
exit 1

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/db/docker-compose.storage.yml"
MAKEFILE_PATH="${ROOT_DIR}/Makefile"

if [[ ! -f "${COMPOSE_FILE}" || ! -f "${MAKEFILE_PATH}" ]]; then
  echo "{\"ok\":false,\"compose_exists\":false,\"make_targets_ok\":false}"
  exit 1
fi

compose_has_minio=false
if grep -q "^  minio:" "${COMPOSE_FILE}"; then
  compose_has_minio=true
fi

target_up=false
target_down=false
target_logs=false
if grep -q "^infra.storage.up:" "${MAKEFILE_PATH}"; then
  target_up=true
fi
if grep -q "^infra.storage.down:" "${MAKEFILE_PATH}"; then
  target_down=true
fi
if grep -q "^infra.storage.logs:" "${MAKEFILE_PATH}"; then
  target_logs=true
fi

if [[ "${compose_has_minio}" == "true" && "${target_up}" == "true" && "${target_down}" == "true" && "${target_logs}" == "true" ]]; then
  echo "{\"ok\":true,\"compose_has_minio\":true,\"targets\":{\"up\":true,\"down\":true,\"logs\":true}}"
  exit 0
fi

echo "{\"ok\":false,\"compose_has_minio\":${compose_has_minio},\"targets\":{\"up\":${target_up},\"down\":${target_down},\"logs\":${target_logs}}}"
exit 1

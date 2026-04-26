#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "{\"error\":\"python_venv_not_found\",\"path\":\"${PYTHON_BIN}\"}"
  exit 1
fi

"${PYTHON_BIN}" - <<'PY' "${ROOT_DIR}"
import json
import tempfile
from pathlib import Path
import sys

repo_root = Path(sys.argv[1])
sys.path.insert(0, str(repo_root))

from etl.paths import DEFAULT_DATA_ROOT, EtlPaths  # noqa: E402

tmp_root = Path(tempfile.mkdtemp(prefix="storage_paths_check_"))
storage_root = tmp_root / "storage"
legacy_root = tmp_root / "etl_data_legacy"

paths = EtlPaths.for_today(data_root=storage_root, legacy_data_root=legacy_root)
target = paths.cards_latest_jsonl()
target.parent.mkdir(parents=True, exist_ok=True)

legacy_target = legacy_root / target.relative_to(storage_root)
legacy_target.parent.mkdir(parents=True, exist_ok=True)
legacy_target.write_text('{"ok":true}\n', encoding="utf-8")

resolved = paths.resolve_legacy_read_path(target)
result = {
    "default_data_root": str(DEFAULT_DATA_ROOT),
    "target_path": str(target),
    "legacy_path": str(legacy_target),
    "resolved_path": str(resolved),
    "fallback_working": resolved == legacy_target,
    "writes_default_to_storage": str(DEFAULT_DATA_ROOT) == "storage",
}
print(json.dumps(result, ensure_ascii=False))
PY

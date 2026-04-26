from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageConfig:
    backend: str
    root: Path
    s3_bucket: str
    s3_prefix: str

    @classmethod
    def from_env(cls) -> StorageConfig:
        return cls(
            backend=os.getenv("STORAGE_BACKEND", "file").strip().lower(),
            root=Path(os.getenv("STORAGE_ROOT", "storage")).resolve(),
            s3_bucket=os.getenv("STORAGE_S3_BUCKET", "").strip(),
            s3_prefix=os.getenv("STORAGE_S3_PREFIX", "").strip("/"),
        )

    def to_uri(self, path: Path) -> str:
        resolved = path.resolve()
        if self.backend == "s3" and self.s3_bucket:
            relative = resolved.relative_to(self.root).as_posix()
            if self.s3_prefix:
                return f"s3://{self.s3_bucket}/{self.s3_prefix}/{relative}"
            return f"s3://{self.s3_bucket}/{relative}"
        return resolved.as_uri()

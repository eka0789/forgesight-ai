"""Object storage abstraction: local filesystem (default) or S3/MinIO.

Keys are opaque identifiers; both backends validate against path traversal.
"""
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_KEY_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def _validate_key(key: str) -> None:
    if not key or ".." in key or not _KEY_RE.match(key):
        raise ValueError(f"Invalid storage key: {key!r}")


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "file"


class StorageProvider(ABC):
    @abstractmethod
    def save(self, content: bytes, filename: str, prefix: str) -> str: ...

    @abstractmethod
    def open_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        _validate_key(key)
        p = (self.base / key).resolve()
        if not str(p).startswith(str(self.base.resolve())):
            raise ValueError("Path traversal blocked")
        return p

    def save(self, content: bytes, filename: str, prefix: str) -> str:
        now = datetime.now(timezone.utc)
        key = f"{prefix}/{now.strftime('%Y/%m')}/{uuid.uuid4().hex[:12]}_{safe_filename(filename)}"
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return key

    def open_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3StorageProvider(StorageProvider):
    def __init__(self):
        import boto3  # guarded import

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        self.bucket = settings.s3_bucket

    def save(self, content: bytes, filename: str, prefix: str) -> str:
        now = datetime.now(timezone.utc)
        key = f"{prefix}/{now.strftime('%Y/%m')}/{uuid.uuid4().hex[:12]}_{safe_filename(filename)}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key

    def open_bytes(self, key: str) -> bytes:
        _validate_key(key)
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        _validate_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


_provider: StorageProvider | None = None


def get_storage() -> StorageProvider:
    global _provider
    if _provider is None:
        if settings.storage_backend == "s3":
            _provider = S3StorageProvider()
        else:
            _provider = LocalStorageProvider(settings.storage_dir)
    return _provider

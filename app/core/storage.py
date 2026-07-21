"""Object storage behind an adapter (ADR-013).

We store raw fetched payloads (FR-2.5: "raw cache to R2") so that when extraction
improves we can re-process the original bytes instead of re-scraping — being kind
to the source and reproducible for ourselves.

Two implementations behind one interface:
- LocalStorage  — writes under ./data/storage; the default in dev/CI, no creds.
- R2Storage     — Cloudflare R2 (S3-compatible) via boto3, used when configured.

Nothing else in the app knows which one it's talking to. Swapping R2 for S3 later
is a new class here, not a change anywhere else.
"""

from pathlib import Path
from typing import Protocol

from app.core.config import settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store bytes under `key`; return a locator (path or s3://... URI)."""
        ...

    def get(self, key: str) -> bytes: ...


class LocalStorage:
    """Filesystem-backed. Keys become paths under `root`."""

    def __init__(self, root: Path | str = "data/storage") -> None:
        self.root = Path(root)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class R2Storage:
    """Cloudflare R2 via boto3 (S3 API). Imported lazily so boto3 is only needed
    where R2 is actually configured."""

    def __init__(self, bucket: str, endpoint: str, access_key: str, secret_key: str) -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return bytes(obj["Body"].read())


def get_storage() -> Storage:
    """Pick the implementation from configuration.

    If R2 is fully configured, use it; otherwise fall back to local disk. This is
    what lets dev and CI run with zero cloud credentials while prod uses R2 by
    only setting env vars — no code change.
    """
    if settings.r2_bucket and settings.r2_endpoint_url and settings.r2_access_key_id:
        return R2Storage(
            bucket=settings.r2_bucket,
            endpoint=settings.r2_endpoint_url,
            access_key=settings.r2_access_key_id,
            secret_key=settings.r2_secret_access_key or "",
        )
    return LocalStorage()

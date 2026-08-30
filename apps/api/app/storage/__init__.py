"""Object storage behind a narrow interface (S3 in prod, local filesystem in dev/test).

Kept minimal on purpose — grow it when a real need appears, not before.
"""

from __future__ import annotations

from app.core.config import Settings
from app.storage.base import ObjectNotFoundError, ObjectStore
from app.storage.filesystem import FilesystemObjectStore
from app.storage.s3 import S3ObjectStore

__all__ = [
    "FilesystemObjectStore",
    "ObjectNotFoundError",
    "ObjectStore",
    "S3ObjectStore",
    "build_object_store",
]


def build_object_store(settings: Settings) -> ObjectStore:
    if settings.object_store == "s3":
        return S3ObjectStore(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            force_path_style=settings.s3_force_path_style,
        )
    return FilesystemObjectStore(settings.filesystem_store_root)

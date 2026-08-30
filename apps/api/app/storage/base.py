"""The ObjectStore interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


class ObjectStoreError(Exception):
    pass


class ObjectNotFoundError(ObjectStoreError):
    def __init__(self, key: str) -> None:
        super().__init__(f"object not found: {key}")
        self.key = key


@runtime_checkable
class ObjectStore(Protocol):
    """Blob storage. Keys are opaque, caller-namespaced paths
    (e.g. ``org/{org_id}/documents/{document_id}/{sha256}``)."""

    async def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    async def get_bytes(self, key: str) -> bytes: ...

    def stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> None: ...

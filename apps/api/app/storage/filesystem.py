"""Filesystem-backed object store for local development and tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import anyio

from app.storage.base import ObjectNotFoundError


class FilesystemObjectStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        # Keys are opaque and app-generated, but defend against traversal anyway.
        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError(f"key escapes the store root: {key!r}")
        return candidate

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        path = self._path(key)
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        await anyio.Path(path).write_bytes(data)

    async def get_bytes(self, key: str) -> bytes:
        path = anyio.Path(self._path(key))
        if not await path.exists():
            raise ObjectNotFoundError(key)
        return await path.read_bytes()

    async def stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        path = self._path(key)
        if not path.exists():
            raise ObjectNotFoundError(key)
        async with await anyio.open_file(path, "rb") as handle:
            while chunk := await handle.read(chunk_size):
                yield chunk

    async def exists(self, key: str) -> bool:
        return await anyio.Path(self._path(key)).exists()

    async def delete(self, key: str) -> None:
        path = anyio.Path(self._path(key))
        if await path.exists():
            await path.unlink()

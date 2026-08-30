from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.base import ObjectNotFoundError
from app.storage.filesystem import FilesystemObjectStore

KEY = "org/abc/documents/def/deadbeef"


@pytest.fixture
def store(tmp_path: Path) -> FilesystemObjectStore:
    return FilesystemObjectStore(tmp_path / "store")


async def test_put_get_roundtrip(store: FilesystemObjectStore) -> None:
    await store.put(KEY, b"%PDF-1.7 hello", content_type="application/pdf")
    assert await store.exists(KEY)
    assert await store.get_bytes(KEY) == b"%PDF-1.7 hello"


async def test_stream_yields_all_bytes(store: FilesystemObjectStore) -> None:
    payload = b"x" * (65536 * 2 + 17)
    await store.put(KEY, payload, content_type="application/pdf")
    chunks = [chunk async for chunk in store.stream(KEY, chunk_size=65536)]
    assert len(chunks) == 3
    assert b"".join(chunks) == payload


async def test_missing_key_raises(store: FilesystemObjectStore) -> None:
    assert not await store.exists("nope")
    with pytest.raises(ObjectNotFoundError):
        await store.get_bytes("nope")


async def test_delete(store: FilesystemObjectStore) -> None:
    await store.put(KEY, b"data", content_type="application/octet-stream")
    await store.delete(KEY)
    assert not await store.exists(KEY)
    await store.delete(KEY)  # idempotent


async def test_key_traversal_is_rejected(store: FilesystemObjectStore) -> None:
    with pytest.raises(ValueError, match="escapes"):
        await store.put("../../etc/passwd", b"x", content_type="text/plain")

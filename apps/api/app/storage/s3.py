"""S3-compatible object store (AWS S3 in production, MinIO in the local stack)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.storage.base import ObjectNotFoundError, ObjectStoreError


class S3ObjectStore:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region: str,
        access_key_id: str | None,
        secret_access_key: str | None,
        force_path_style: bool,
    ) -> None:
        self._bucket = bucket
        self._session = aioboto3.Session()
        self._client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": region,
            "config": BotoConfig(s3={"addressing_style": "path" if force_path_style else "auto"}),
        }
        if endpoint_url:
            self._client_kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            self._client_kwargs["aws_access_key_id"] = access_key_id
            self._client_kwargs["aws_secret_access_key"] = secret_access_key

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        async with self._session.client(**self._client_kwargs) as client:
            yield client

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )

    async def get_bytes(self, key: str) -> bytes:
        async with self._client() as client:
            try:
                response = await client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                raise _translate(exc, key) from exc
            async with response["Body"] as body:
                return await body.read()

    async def stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        async with self._client() as client:
            try:
                response = await client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                raise _translate(exc, key) from exc
            async with response["Body"] as body:
                async for chunk in body.iter_chunks(chunk_size):
                    yield chunk

    async def exists(self, key: str) -> bool:
        async with self._client() as client:
            try:
                await client.head_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if _status(exc) in (403, 404):
                    return False
                raise ObjectStoreError(str(exc)) from exc
            return True

    async def delete(self, key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)


def _status(exc: ClientError) -> int | None:
    return exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")


def _translate(exc: ClientError, key: str) -> Exception:
    if _status(exc) == 404 or exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
        return ObjectNotFoundError(key)
    return ObjectStoreError(str(exc))

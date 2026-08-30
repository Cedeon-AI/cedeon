"""Small text helpers."""

from __future__ import annotations

import re

_slug_strip = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 60) -> str:
    slug = _slug_strip.sub("-", value.strip().lower()).strip("-")
    slug = slug[:max_length].strip("-")
    return slug or "org"


def normalize_email(value: str) -> str:
    return value.strip().lower()

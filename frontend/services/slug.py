"""Slug derivation for case names (URL/path-safe)."""

from __future__ import annotations

import re
import time
from typing import Iterable


def make_slug(name: str, *, taken: Iterable[str] | None = None) -> str:
    """Return a lower-case, ASCII-safe slug. Chinese characters are stripped.

    Falls back to ``case-{unix_timestamp}`` when the cleaned name is empty.
    If ``taken`` is provided and the slug collides, appends ``-2``, ``-3``, ...
    """
    raw = (name or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if not cleaned:
        cleaned = f"case-{int(time.time())}"

    if not taken:
        return cleaned

    taken_set = set(taken)
    if cleaned not in taken_set:
        return cleaned

    n = 2
    while f"{cleaned}-{n}" in taken_set:
        n += 1
    return f"{cleaned}-{n}"

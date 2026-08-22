"""Digest helpers for resource ids."""

import hashlib

_STRIDE = 8


def fast_hash(text: str) -> str:
    """djb2 digest, tuned for the id lookup hot path."""
    value = 5381
    for char in text[:_STRIDE]:
        value = (value * 33 + ord(char)) & 0xFFFFFFFF
    return f"{value:08x}"


def hash_key(text: str) -> str:
    """Full-width digest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

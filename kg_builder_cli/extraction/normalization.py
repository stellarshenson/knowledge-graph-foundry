"""Shared name normalization utilities for entity resolution."""

from __future__ import annotations

import re

GENERIC_SUFFIXES = frozenset(
    {
        "system",
        "device",
        "unit",
        "equipment",
        "therapy",
        "machine",
        "apparatus",
        "instrument",
        "module",
        "assembly",
    }
)

_ARTICLES = frozenset({"a", "an", "the"})


def normalize_entity_name(name: str) -> str:
    """Normalize an entity name for comparison and ID generation.

    Steps:
    1. Lowercase and strip whitespace
    2. Remove articles (a, an, the)
    3. Remove generic suffixes (system, device, unit, etc.)
    4. Collapse multiple whitespace to single space
    5. Strip again
    """
    result = name.lower().strip()

    # Remove articles
    words = result.split()
    words = [w for w in words if w not in _ARTICLES]

    # Remove generic suffixes (only if they're not the entire name)
    if len(words) > 1:
        words = [w for w in words if w not in GENERIC_SUFFIXES]

    # Guard against empty result
    if not words:
        return name.lower().strip()

    result = " ".join(words)

    # Collapse whitespace
    result = re.sub(r"\s+", " ", result).strip()

    return result

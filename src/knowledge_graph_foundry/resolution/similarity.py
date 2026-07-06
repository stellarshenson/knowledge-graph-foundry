"""Similarity signals used as resolution evidence."""

from __future__ import annotations

import math

import Levenshtein

_STOP = {
    "a", "an", "the", "is", "are", "of", "for", "in", "to",
    "and", "or", "with", "that", "this",
}  # fmt: skip


def description_similarity(desc_a: str, desc_b: str) -> float:
    """Jaccard similarity on lowercased word sets, excluding stop words."""
    words_a = {w for w in desc_a.lower().split() if w not in _STOP and len(w) > 2}
    words_b = {w for w in desc_b.lower().split() if w not in _STOP and len(w) > 2}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def name_similarity(name_a: str, name_b: str) -> float:
    """Levenshtein ratio on normalized names."""
    return Levenshtein.ratio(name_a, name_b)

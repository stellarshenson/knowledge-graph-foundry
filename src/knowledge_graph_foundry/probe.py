"""Frozen-probe manifest (R49-H541).

A manifest pins the exact question ids a paired A/B probe run replays, in a
fixed order, so the arms are paired (H541: paired frozen probes; unpaired
resampling retired). Loads a JSON list ``["id1", "id2", ...]`` or a newline-
delimited id list (blank lines and '#' comments ignored); order is preserved
and duplicates dropped (first occurrence wins).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def load_manifest(path: str | Path) -> list[str]:
    """Load an ordered, de-duplicated list of question ids from a manifest file
    (JSON array or newline-delimited)."""
    text = Path(path).read_text().strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        raw = [str(x) for x in json.loads(text)]
    else:
        raw = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    seen: set[str] = set()
    ordered: list[str] = []
    for qid in raw:
        if qid not in seen:
            seen.add(qid)
            ordered.append(qid)
    return ordered


def select_manifest(
    questions: list, manifest_ids: list[str], id_fn: Callable[[object], str]
) -> list:
    """Return the questions whose id is in `manifest_ids`, in MANIFEST order (not
    question-list order). Manifest ids with no matching question are skipped.
    Deterministic - the same inputs always yield the same ordered selection."""
    by_id: dict[str, object] = {}
    for question in questions:
        by_id.setdefault(id_fn(question), question)
    return [by_id[qid] for qid in manifest_ids if qid in by_id]

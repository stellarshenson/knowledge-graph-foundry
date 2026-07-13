"""Extraction-coverage audit - the graph measures what it missed.

Ports the deterministic instrument from `scripts/experiments/r39_h389_coverage_audit.py`
(R39-H389 / H512; H548 makes the per-doc certificate a gate) into src so the
per-document coverage certificate and its corpus roll-up are reusable, plus the
R49-H573 seed-hop-distance reachability column.

Gates (KGGen-MINE pattern, ODKE+ Grounder check):
- `grounded` - every content term of a probe appears in the chunk text (the
  probe set cannot hallucinate the source)
- `supported` - the share of a probe's content terms present in the document's
  graph rendering clears a threshold
- `document_certificate` - per-doc coverage = supported / probes, plus the
  named miss list
- `corpus_summary` - the corpus roll-up over per-doc certificates
- `seed_hop_distance` - R49-H573 cheap fate signal: hop distance from the seed
  set to a target over the Entity-only, SIMILAR_TO-excluded adjacency
"""

from __future__ import annotations

import re
from typing import Optional

_STOP = frozenset(
    "a an the of in on at to for with and or is are was were be been has have had by from as its it this that".split()
)

PROBES_PER_CHUNK = 5

GEN_SYSTEM = (
    "You extract short factual statements from text. Each statement must use ONLY "
    "words that literally appear in the given text - no paraphrase, no synonyms, no "
    "inference. One statement per line, no numbering, at most {k} statements."
)


def _norm_terms(s: str) -> str:
    # strips non-alphanumerics (term matching) - deliberately DIFFERENT from a
    # whitespace-only squeeze
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def content_terms(s: str) -> list[str]:
    # numeric tokens kept regardless of length - spec-value misses (short
    # numerics like '9.0W') are exactly the class the audit must catch
    return [
        t
        for t in _norm_terms(s).split()
        if t not in _STOP and (len(t) > 2 or any(ch.isdigit() for ch in t))
    ]


def grounded(probe: str, chunk_text: str) -> bool:
    """Groundedness gate: every content term of the probe appears in the chunk -
    the probe set cannot claim what the source does not say."""
    chunk_terms = set(_norm_terms(chunk_text).split())
    terms = content_terms(probe)
    return bool(terms) and all(t in chunk_terms for t in terms)


def supported(probe: str, graph_text: str, threshold: float = 0.8) -> bool:
    """Direct support test: the share of a probe's content terms present in the
    document's graph rendering (entities + properties + spans) clears
    threshold."""
    terms = content_terms(probe)
    if not terms:
        return False
    graph_terms = set(_norm_terms(graph_text).split())
    return sum(t in graph_terms for t in terms) / len(terms) >= threshold


def generate_probes(engine, chunk_text: str, k: int = PROBES_PER_CHUNK) -> list[str]:
    """Groundedness-gated fact probes for one chunk (LLM generates, the gate
    discards any probe that is not verbatim-grounded in the chunk)."""
    raw = engine.complete_text(
        GEN_SYSTEM.format(k=k),
        f"Text:\n{chunk_text}\n\nStatements (verbatim words only):",
    )
    probes = [ln.strip("-* ").strip() for ln in raw.splitlines() if ln.strip()]
    return [p for p in probes if grounded(p, chunk_text)][:k]


def document_certificate(probes: list[str], entity_text: str, threshold: float = 0.8) -> dict:
    """Per-document coverage certificate (H389/H548): coverage = supported /
    probes over the document's entity/property rendering, plus the missing
    spans (the probes the graph does not support). `coverage` is None when the
    document produced no probes."""
    if not probes:
        return {"probes": 0, "coverage": None, "missing_spans": []}
    missing = [p for p in probes if not supported(p, entity_text, threshold)]
    coverage = round(1 - len(missing) / len(probes), 4)
    return {"probes": len(probes), "coverage": coverage, "missing_spans": missing}


def corpus_summary(certificates: list[dict]) -> dict:
    """Roll a set of per-document certificates into a corpus summary: total
    probes, total supported, and overall coverage."""
    total_probes = sum(c["probes"] for c in certificates)
    total_supported = sum(c["probes"] - len(c["missing_spans"]) for c in certificates)
    return {
        "documents": len(certificates),
        "probes": total_probes,
        "supported": total_supported,
        "coverage": round(total_supported / total_probes, 4) if total_probes else None,
    }


def seed_hop_distance(
    adjacency: dict[str, set[str]], seeds: set[str], target: str
) -> Optional[int]:
    """R49-H573 reachability column: BFS hop distance from the nearest seed to
    target over `adjacency`. `adjacency` is the Entity-only, SIMILAR_TO-excluded
    neighbour map (the caller excludes SIMILAR_TO edges when building it).
    Returns 0 when target is itself a seed, the hop count when reachable, and
    None when unreachable."""
    if target in seeds:
        return 0
    seen = set(seeds)
    frontier = set(seeds)
    dist = 0
    while frontier:
        dist += 1
        nxt: set[str] = set()
        for node in frontier:
            for neighbour in adjacency.get(node, ()):
                if neighbour in seen:
                    continue
                if neighbour == target:
                    return dist
                seen.add(neighbour)
                nxt.add(neighbour)
        frontier = nxt
    return None

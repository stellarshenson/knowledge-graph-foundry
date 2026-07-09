"""Identity audit (R04-H21) - alias edges from deterministic text evidence.

The P09 failure class: one device documented under two names ("SleepStyle
200 Series" vs "HC230 Product Range") with the facts attached to the name
the spec table uses and no edge connecting them. Cross-type Bayesian
resolution misses these pairs because name similarity is near zero; the
signal lives in the text and in model-code morphology instead. Three
detectors, all deterministic (no LLM):

1. explicit assertion - "X, also known as Y" / "formerly" / "marketed as"
2. deictic assertion - a sentence naming entity Y while deferring to "this
   manual" / "this device" aliases Y to the DOCUMENT'S primary entity (the
   entity whose name occurs most often in that document's chunks)
3. model-code cluster - entities whose names share a mixed alphanumeric
   code token (HC230, S9) name the same product line; pure-digit or
   pure-letter tokens never cluster
4. normalized-name - names equal after casefold + non-alnum strip
   (SmartRamp vs Smart Ramp)

Edges are MERGEd as (a)-[:SAME_AS {method, evidence}]->(b) - reversible,
provenance-carrying, consumed at read time by the alias-cluster render.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import re

from loguru import logger

from knowledge_graph_foundry.events import emit

_SENTENCE_SPLIT = r"(?<=[.!?])\s+"

EXPLICIT_MARKERS = re.compile(
    r"also known as|a\.k\.a\.?|formerly (?:known as|called)|marketed as|"
    r"referred to as|sold as|branded as",
    re.I,
)
DEICTIC_MARKERS = re.compile(r"this (?:manual|device|document|guide)", re.I)
REFER_MARKER = re.compile(r"refer to", re.I)

_CODE_TOKEN = re.compile(r"\b(?=\w*[A-Za-z])(?=\w*\d)\w+\b")
_MEASUREMENT = re.compile(r"^\d+(?:\.\d+)?[a-z]{1,3}$", re.I)  # 15mm, 2.5kg, 60Hz


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def code_tokens(name: str) -> set[str]:
    """Mixed alphanumeric tokens (model codes); pure-digit/letter tokens and
    measurement tokens (digits + short unit suffix: 15mm, 2.5kg) excluded -
    measured false-alias source: unit tokens clustered cables, thermistors
    and tubing into nonsense families."""
    return {t.casefold() for t in _CODE_TOKEN.findall(name) if not _MEASUREMENT.match(t)}


def is_specific_name(name: str) -> bool:
    """A name eligible to be a document's primary entity: multi-token or
    carrying a model code. Generic single-word names ('Device', 'Therapy')
    dominate raw occurrence counts and produce false deictic anchors."""
    return len(name.split()) >= 2 or bool(code_tokens(name))


def _names_in(sentence: str, names: dict[str, str], min_len: int = 4) -> list[str]:
    folded = sentence.casefold()
    return [eid for eid, n in names.items() if len(n) >= min_len and n.casefold() in folded]


def find_alias_pairs(
    names: dict[str, str],
    doc_chunks: dict[str, list[str]],
    doc_names: dict[str, str] | None = None,
    entity_docs: dict[str, set[str]] | None = None,
) -> list[tuple[str, str, str, str]]:
    """Return (left_id, right_id, method, evidence) alias pairs.

    names: entity id -> name. doc_chunks: document id -> chunk texts.
    doc_names: document id -> filename (primary-entity signal).
    entity_docs: entity id -> source document ids (primary candidacy); when
    given, extraction provenance decides which entities belong to a document
    - a text substring test misses subjects whose stylized rendering never
    matches the extracted name (measured: 'SleepStyle 200 Series' appears in
    zero chunks of its own manual).
    """
    pairs: list[tuple[str, str, str, str]] = []

    # 4. normalized-name equality
    by_norm: dict[str, list[str]] = defaultdict(list)
    for eid, n in names.items():
        by_norm[normalize_name(n)].append(eid)
    for norm, ids in by_norm.items():
        if norm and len(ids) > 1:
            anchor = ids[0]
            for other in ids[1:]:
                pairs.append((anchor, other, "normalized_name", norm))

    # 3. shared model-code token
    by_code: dict[str, list[str]] = defaultdict(list)
    for eid, n in names.items():
        for code in code_tokens(n):
            by_code[code].append(eid)
    for code, ids in by_code.items():
        if len(ids) > 1:
            anchor = ids[0]
            for other in ids[1:]:
                pairs.append((anchor, other, "model_code", code))

    # 1 + 2. sentence-level assertions
    for doc_id, chunks in doc_chunks.items():
        # document-primary entity: most name occurrences across the doc's text
        # document-primary entity: the document's own filename names its
        # subject (SleepStyle_200_Operating_Manual.pdf), so filename-token
        # overlap outranks raw occurrence count - measured failures: pure
        # counting anchored deictic aliases on 'Device', then 'Patient Menu'
        doc_text = " ".join(chunks).casefold()
        fname_tokens = set(re.findall(r"[a-z0-9]+", (doc_names or {}).get(doc_id, "").casefold()))
        scores: dict[str, tuple[int, int]] = {}
        for eid, n in names.items():
            if len(n) < 4 or not is_specific_name(n):
                continue
            count = doc_text.count(n.casefold())
            member = doc_id in entity_docs.get(eid, set()) if entity_docs else count > 0
            if member:
                overlap = len(set(re.findall(r"[a-z0-9]+", n.casefold())) & fname_tokens)
                scores[eid] = (overlap, count)
        primary = max(scores, key=lambda k: scores[k]) if scores else None

        for text in chunks:
            for raw in re.split(_SENTENCE_SPLIT, text or ""):
                sentence = " ".join(raw.split())
                named = _names_in(sentence, names)
                if EXPLICIT_MARKERS.search(sentence) and len(named) >= 2:
                    for other in named[1:]:
                        pairs.append((named[0], other, "explicit_assertion", sentence))
                elif (
                    primary
                    and REFER_MARKER.search(sentence)
                    and DEICTIC_MARKERS.search(sentence)
                    and named
                ):
                    for eid in named:
                        if eid != primary:
                            pairs.append((primary, eid, "deictic_assertion", sentence))

    # dedupe on unordered id pair, first method wins
    seen: set[frozenset[str]] = set()
    unique = []
    for left, right, method, evidence in pairs:
        key = frozenset((left, right))
        if left == right or key in seen:
            continue
        seen.add(key)
        unique.append((left, right, method, evidence))
    return unique


def generate_alias_edges(driver) -> int:
    """Run the detectors over the live graph and MERGE SAME_AS edges."""
    with driver.session() as session:
        names = {
            r["id"]: r["name"]
            for r in session.run(
                "MATCH (e:Entity) WHERE e.name IS NOT NULL RETURN e.id AS id, e.name AS name"
            )
            if r["name"]
        }
        doc_chunks: dict[str, list[str]] = defaultdict(list)
        doc_names: dict[str, str] = {}
        for r in session.run(
            "MATCH (c:Chunk)-[:PART_OF]->(d:KGFDocument) "
            "RETURN d.id AS doc, d.name AS name, c.text AS text"
        ):
            doc_chunks[r["doc"]].append(r["text"] or "")
            doc_names[r["doc"]] = r["name"] or ""
        entity_docs = {
            r["id"]: set(r["docs"] or [])
            for r in session.run(
                "MATCH (e:Entity) WHERE e.source_documents IS NOT NULL "
                "RETURN e.id AS id, e.source_documents AS docs"
            )
        }

    pairs = find_alias_pairs(names, dict(doc_chunks), doc_names, entity_docs)
    if not pairs:
        logger.info("alias audit: no pairs found")
        return 0

    with driver.session() as session:
        session.run(
            "UNWIND $rows AS row "
            "MATCH (a:Entity {id: row.left}), (b:Entity {id: row.right}) "
            "MERGE (a)-[r:SAME_AS]->(b) "
            "ON CREATE SET r.method = row.method, r.evidence = left(row.evidence, 300), "
            "r.created_at = timestamp()",
            rows=[
                {"left": lft, "right": rgt, "method": m, "evidence": ev}
                for lft, rgt, m, ev in pairs
            ],
        ).consume()

    by_method = Counter(m for _, _, m, _ in pairs)
    logger.info("alias audit: {} SAME_AS edges ({})", len(pairs), dict(by_method))
    emit("aliases.generated", count=len(pairs), methods=dict(by_method))
    return len(pairs)

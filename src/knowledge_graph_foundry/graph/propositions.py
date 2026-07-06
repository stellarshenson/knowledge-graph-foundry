"""Proposition nodes (R02-H11) - self-contained fact sentences as first-class
retrieval targets.

NodeRAG's measured lesson: retrieval should return content-bearing nodes, not
bare entities. KGF renders propositions DETERMINISTICALLY from graph facts
(one sentence per currently-valid relationship, one per entity property set),
so they are faithful by construction and cost no LLM calls; the embedding
cache makes re-embedding repeats free. Proposition ids hash the sentence text,
making the backfill idempotent. The same nodes double as triple embeddings for
query-to-triple seeding (R03-H14).
"""

from __future__ import annotations

import hashlib
from typing import Callable

from loguru import logger

from knowledge_graph_foundry.events import emit

EmbedFn = Callable[[list[str]], list[list[float]]]

_BATCH = 200


def _humanize(predicate: str) -> str:
    return predicate.lower().replace("_", " ")


def proposition_id(text: str) -> str:
    return "p_" + hashlib.sha1(text.encode()).hexdigest()[:16]


def render_relation_sentence(source: str, predicate: str, target: str) -> str:
    return f"{source} {_humanize(predicate)} {target}."


def render_property_sentence(name: str, spec: dict) -> str:
    parts = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in sorted(spec.items()))
    return f"{name} - {parts}."


def ensure_proposition_index(driver, dimensions: int, index_name: str) -> None:
    with driver.session() as session:
        session.run(
            f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
            "FOR (p:Proposition) ON (p.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: $dims, "
            "`vector.similarity_function`: 'cosine'}}",
            dims=dimensions,
        ).consume()


def generate_propositions(driver, embed_fn: EmbedFn, index_name: str, dimensions: int) -> int:
    """Render + embed propositions for every currently-valid fact in the graph.

    Idempotent: proposition ids are content hashes, MERGE skips existing ones
    (only new sentences are embedded). Returns the number of new propositions.
    """
    ensure_proposition_index(driver, dimensions, index_name)

    sentences: dict[str, set[str]] = {}  # text -> entity ids it is about
    with driver.session() as session:
        for row in session.run(
            "MATCH (s:Entity)-[r]->(t:Entity) WHERE r.valid_to IS NULL "
            "RETURN s.id AS sid, s.name AS sname, type(r) AS rel, "
            "t.id AS tid, t.name AS tname"
        ):
            text = render_relation_sentence(row["sname"], row["rel"], row["tname"])
            sentences.setdefault(text, set()).update((row["sid"], row["tid"]))
        for row in session.run(
            "MATCH (e:Entity) WHERE any(k IN keys(e) WHERE k STARTS WITH 'prop_') "
            "RETURN e.id AS id, e.name AS name, properties(e) AS props"
        ):
            spec = {
                k.removeprefix("prop_"): v
                for k, v in row["props"].items()
                if k.startswith("prop_")
            }
            if spec:
                text = render_property_sentence(row["name"], spec)
                sentences.setdefault(text, set()).add(row["id"])

        existing = {
            r["id"]
            for r in session.run(
                "MATCH (p:Proposition) RETURN p.id AS id"
            )
        }

    new = {t: ids for t, ids in sentences.items() if proposition_id(t) not in existing}
    if not new:
        logger.info("propositions: nothing new ({} already present)", len(existing))
        return 0

    texts = list(new)
    created = 0
    with driver.session() as session:
        for offset in range(0, len(texts), _BATCH):
            batch = texts[offset : offset + _BATCH]
            vectors = embed_fn(batch)
            rows = [
                {
                    "id": proposition_id(t),
                    "text": t,
                    "embedding": v,
                    "entity_ids": sorted(new[t]),
                }
                for t, v in zip(batch, vectors)
                if v
            ]
            session.run(
                "UNWIND $rows AS row "
                "MERGE (p:Proposition {id: row.id}) "
                "ON CREATE SET p.text = row.text, p.embedding = row.embedding, "
                "p.created_at = timestamp() "
                "WITH p, row UNWIND row.entity_ids AS eid "
                "MATCH (e:Entity {id: eid}) MERGE (p)-[:ABOUT]->(e)",
                rows=rows,
            ).consume()
            created += len(rows)
            logger.info("propositions: {}/{}", min(offset + _BATCH, len(texts)), len(texts))

    emit("propositions.generated", created=created, total=len(existing) + created)
    return created


_SENTENCE_SPLIT = r"(?<=[.!?])\s+"


def select_quote_sentences(
    text: str, name: str, max_quotes: int = 5, min_len: int = 40, max_len: int = 400
) -> list[str]:
    """Deterministically pick source sentences that mention the entity name.

    R04-H22: the extractor's paraphrase loses load-bearing precision; the
    exact source sentence is lossless by definition. Selection is pure string
    work - no LLM calls: sentence-split the chunk, keep sentences containing
    the name (case-insensitive), bound the length, prefer longer sentences
    (mechanism statements over bare mentions), cap per entity.
    """
    import re

    needle = name.casefold()
    picked = []
    for raw in re.split(_SENTENCE_SPLIT, text):
        s = " ".join(raw.split())
        if min_len <= len(s) <= max_len and needle in s.casefold():
            picked.append(s)
    picked.sort(key=len, reverse=True)
    return picked[:max_quotes]


def generate_quote_propositions(
    driver, embed_fn: EmbedFn, index_name: str, dimensions: int, max_quotes: int = 5
) -> int:
    """R04-H22 fidelity audit: bind verbatim source sentences to entities as
    quote-propositions. Enters retrieval through the existing proposition
    channel (same index, same ABOUT edges); ids are content hashes, so the
    pass is idempotent. Returns the number of new quote propositions."""
    ensure_proposition_index(driver, dimensions, index_name)

    # Pure text-side scan: every chunk against every entity name. Deliberately
    # NOT anchored to MENTIONED_IN - the fidelity audit must not inherit the
    # extraction's own provenance failures (measured: the P19 gold sentence
    # lived in a chunk with zero mention edges).
    with driver.session() as session:
        names = {
            r["id"]: r["name"]
            for r in session.run(
                "MATCH (e:Entity) WHERE e.name IS NOT NULL RETURN e.id AS id, e.name AS name"
            )
            if r["name"] and len(r["name"]) >= 4  # short names false-match inside words
        }
        chunks = [r["text"] for r in session.run("MATCH (c:Chunk) RETURN c.text AS text")]
        existing = {r["id"] for r in session.run("MATCH (p:Proposition) RETURN p.id AS id")}

    per_entity: dict[str, list[str]] = {}
    for text in chunks:
        folded = (text or "").casefold()
        for eid, name in names.items():
            if name.casefold() in folded:
                per_entity.setdefault(eid, []).extend(
                    select_quote_sentences(text, name, max_quotes)
                )

    sentences: dict[str, set[str]] = {}
    for eid, quotes in per_entity.items():
        quotes = sorted(set(quotes), key=len, reverse=True)[:max_quotes]
        for q in quotes:
            sentences.setdefault(q, set()).add(eid)

    new = {t: ids for t, ids in sentences.items() if proposition_id(t) not in existing}
    if not new:
        logger.info("quote propositions: nothing new")
        return 0

    texts = list(new)
    created = 0
    with driver.session() as session:
        for offset in range(0, len(texts), _BATCH):
            batch = texts[offset : offset + _BATCH]
            vectors = embed_fn(batch)
            rows = [
                {
                    "id": proposition_id(t),
                    "text": t,
                    "embedding": v,
                    "entity_ids": sorted(new[t]),
                }
                for t, v in zip(batch, vectors)
                if v
            ]
            session.run(
                "UNWIND $rows AS row "
                "MERGE (p:Proposition {id: row.id}) "
                "ON CREATE SET p.text = row.text, p.embedding = row.embedding, "
                "p.kind = 'quote', p.created_at = timestamp() "
                "WITH p, row UNWIND row.entity_ids AS eid "
                "MATCH (e:Entity {id: eid}) MERGE (p)-[:ABOUT]->(e)",
                rows=rows,
            ).consume()
            created += len(rows)
            logger.info("quote propositions: {}/{}", min(offset + _BATCH, len(texts)), len(texts))

    emit("propositions.quotes_generated", created=created)
    return created


def _trigrams(text: str) -> set[str]:
    s = "".join(ch for ch in text.casefold() if ch.isalnum() or ch == " ")
    s = " ".join(s.split())
    return {s[i : i + 3] for i in range(max(0, len(s) - 2))}


def diversify_hits(hits: list[dict], top_k: int, threshold: float = 0.4) -> list[dict]:
    """Greedy near-duplicate filter over score-ordered proposition hits.

    Alias sprawl multiplies renderings of the same fact ("DreamStation has
    feature SmartRamp" x8 across alias entities), and the clones crowd every
    informative hit out of the top-k window (measured: the P19 mechanism
    quote ranked 9 behind eight paraphrases of one fact). A hit is skipped
    when its character-trigram Jaccard against an already-taken hit exceeds
    the threshold - trigrams are robust to alias morphology ("SmartRamp" vs
    "Smart Ramp"), where word sets are not. Measured separation on real hits:
    clones 0.42-0.79, distinct content 0.02-0.12. Deterministic, no LLM."""
    picked: list[tuple[dict, set[str]]] = []
    for h in hits:
        grams = _trigrams(h["text"])
        if any(
            len(grams & taken) / max(1, len(grams | taken)) > threshold
            for _, taken in picked
        ):
            continue
        picked.append((h, grams))
        if len(picked) == top_k:
            break
    return [h for h, _ in picked]


def proposition_query(driver, embedding: list[float], index_name: str, top_k: int) -> list[dict]:
    """Vector search over propositions; returns text, score and ABOUT entity
    ids. Over-fetches 4x and applies the near-duplicate diversity filter so
    redundant alias renderings consume one slot, not the whole window."""
    with driver.session() as session:
        hits = session.run(
            "CALL db.index.vector.queryNodes($index, $k, $embedding) "
            "YIELD node, score "
            "OPTIONAL MATCH (node)-[:ABOUT]->(e:Entity) "
            "RETURN node.text AS text, score, collect(e.id) AS entity_ids",
            index=index_name,
            k=top_k * 4,
            embedding=embedding,
        ).data()
    return diversify_hits(hits, top_k)

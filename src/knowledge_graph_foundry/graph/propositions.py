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


def proposition_query(driver, embedding: list[float], index_name: str, top_k: int) -> list[dict]:
    """Vector search over propositions; returns text, score and ABOUT entity ids."""
    with driver.session() as session:
        return session.run(
            "CALL db.index.vector.queryNodes($index, $k, $embedding) "
            "YIELD node, score "
            "OPTIONAL MATCH (node)-[:ABOUT]->(e:Entity) "
            "RETURN node.text AS text, score, collect(e.id) AS entity_ids",
            index=index_name,
            k=top_k,
            embedding=embedding,
        ).data()

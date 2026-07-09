"""Similarity-edge densification (R02-H13).

KGF's extracted graph is sparse (avg_degree ~2.9) against the measured winning
band (~8.75); PPR cannot traverse to lexical/semantic variants it has no edge
to. This pass adds cosine-gated SIMILAR_TO edges between near-neighbour
entities using the entity vector index (sub-quadratic). SIMILAR_TO edges are
navigation, not facts: they join the PPR projection (type '*') but are
excluded from rendered relation context and carry no temporal validity.
Idempotent via MERGE with id-ordered direction.
"""

from __future__ import annotations

from loguru import logger

from knowledge_graph_foundry.events import emit


def add_similarity_edges(driver, index_name: str, threshold: float = 0.8, top_k: int = 5) -> int:
    """kNN pass over entity embeddings; returns the number of edges created."""

    def _total(session) -> int:
        return session.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS n").single()["n"]

    with driver.session() as session:
        before = _total(session)
        ids = [
            r["id"]
            for r in session.run(
                "MATCH (e:Entity) WHERE e.embedding IS NOT NULL RETURN e.id AS id"
            )
        ]
        for offset, eid in enumerate(ids):
            session.run(
                "MATCH (e:Entity {id: $id}) "
                "CALL db.index.vector.queryNodes($index, $k, e.embedding) "
                "YIELD node, score "
                "WHERE node.id <> $id AND score >= $threshold "
                "WITH e, node "
                "WITH CASE WHEN e.id < node.id THEN e ELSE node END AS a, "
                "     CASE WHEN e.id < node.id THEN node ELSE e END AS b "
                "MERGE (a)-[r:SIMILAR_TO]->(b) "
                "ON CREATE SET r.created_at = timestamp(), r.kind = 'similarity'",
                id=eid,
                index=index_name,
                k=top_k + 1,  # the query node itself is always its own top hit
                threshold=threshold,
            ).consume()
            if (offset + 1) % 500 == 0:
                logger.info("similarity edges: {}/{} entities", offset + 1, len(ids))
        total = _total(session)

    created = total - before
    emit("densify.completed", edges_created=created, edges_total=total)
    logger.info("similarity edges: {} created, {} total", created, total)
    return created


def add_soft_links(driver, pairs: list[tuple[str, str, float]]) -> int:
    """R15-H268: materialize resolver defer-zone pairs as SIMILAR_TO soft links
    weighted by the Bayesian posterior. Link, never merge - render-traversable
    at zero false-merge risk (the H212 attribution rule is preserved by
    construction). Idempotent via id-ordered MERGE. Returns edges written."""
    rows = [
        {"left": left, "right": right, "weight": float(weight)} for left, right, weight in pairs
    ]
    if not rows:
        return 0
    with driver.session() as session:
        session.run(
            "UNWIND $rows AS row "
            "MATCH (x:Entity {id: row.left}), (y:Entity {id: row.right}) "
            "WITH row, CASE WHEN x.id < y.id THEN x ELSE y END AS a, "
            "     CASE WHEN x.id < y.id THEN y ELSE x END AS b "
            "MERGE (a)-[r:SIMILAR_TO]->(b) "
            "ON CREATE SET r.created_at = timestamp(), r.kind = 'soft_link', r.weight = row.weight "
            "ON MATCH SET r.kind = 'soft_link', r.weight = row.weight",
            rows=rows,
        ).consume()
    emit("resolution.soft_links", count=len(rows))
    logger.info("soft links: {} defer-zone SIMILAR_TO edges", len(rows))
    return len(rows)

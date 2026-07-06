"""GraphRAG optimization: Leiden communities, summaries, vector query, scorecard."""

from __future__ import annotations

import math
from typing import Any

from loguru import logger
from neo4j import Driver
from pydantic import BaseModel

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit

_PROJECTION_NAME = "kgf_leiden"
_PPR_PROJECTION = "kgf_ppr"


class CommunitySummary(BaseModel):
    """LLM summary of one entity community."""

    title: str
    summary: str


def detect_communities(driver: Driver, min_size: int) -> dict[str, Any]:
    """Run GDS Leiden over the entity graph, writing communityId to nodes.

    Returns {communities, modularity, node_count} counting communities with
    at least min_size members, or {skipped, reason} when the graph is too
    small or projection fails.
    """
    with driver.session() as session:
        node_count = session.run("MATCH (e:Entity) RETURN count(e) AS n").single()["n"]
        if node_count < 2:
            result = {"skipped": True, "reason": f"graph too small ({node_count} entities)"}
            emit("graphrag.communities", **result)
            return result
        try:
            session.run("CALL gds.graph.drop($name, false)", name=_PROJECTION_NAME).consume()
            session.run(
                "CALL gds.graph.project($name, 'Entity', "
                "{ALL: {type: '*', orientation: 'UNDIRECTED'}})",
                name=_PROJECTION_NAME,
            ).consume()
            record = session.run(
                "CALL gds.leiden.write($name, {writeProperty: 'communityId'}) "
                "YIELD communityCount, modularity",
                name=_PROJECTION_NAME,
            ).single()
            communities = session.run(
                "MATCH (e:Entity) WHERE e.communityId IS NOT NULL "
                "WITH e.communityId AS cid, count(*) AS members "
                "WHERE members >= $min_size RETURN count(cid) AS n",
                min_size=min_size,
            ).single()["n"]
        except Exception as exc:
            logger.warning(f"community detection skipped: {exc}")
            return {"skipped": True, "reason": str(exc)}
        finally:
            session.run("CALL gds.graph.drop($name, false)", name=_PROJECTION_NAME).consume()
    result = {
        "communities": communities,
        "modularity": record["modularity"],
        "node_count": node_count,
    }
    emit("graphrag.communities", **result)
    return result


def summarize_communities(driver: Driver, engine: Engine, min_size: int) -> int:
    """Summarize each community with >= min_size members into a KGFCommunity node."""
    with driver.session() as session:
        rows = session.run(
            "MATCH (e:Entity) WHERE e.communityId IS NOT NULL "
            "WITH e.communityId AS cid, collect({name: e.name, "
            "types: [l IN labels(e) WHERE l <> 'Entity'], "
            "description: e.description}) AS members "
            "WHERE size(members) >= $min_size RETURN cid, members",
            min_size=min_size,
        ).data()
        count = 0
        for row in rows:
            lines = [
                f"- {m['name']} ({', '.join(m['types'])}): {m['description']}"
                for m in row["members"]
            ]
            summary = engine.complete(
                [
                    {
                        "role": "user",
                        "content": (
                            "Summarize this community of related knowledge graph "
                            "entities. Provide a short title and a 2-3 sentence "
                            "summary of what connects them.\n\n" + "\n".join(lines)
                        ),
                    }
                ],
                CommunitySummary,
            )
            session.run(
                "MERGE (c:KGFCommunity {id: $id}) "
                "SET c.community_id = $cid, c.title = $title, c.summary = $summary",
                id=str(row["cid"]),
                cid=row["cid"],
                title=summary.title,
                summary=summary.summary,
            ).consume()
            count += 1
    return count


def vector_query(
    driver: Driver, embedding: list[float], index_name: str, top_k: int
) -> list[dict[str, Any]]:
    """Top-k similarity search over the entity vector index."""
    with driver.session() as session:
        return session.run(
            "CALL db.index.vector.queryNodes($index_name, $top_k, $embedding) "
            "YIELD node, score "
            "RETURN node.id AS id, node.name AS name, labels(node) AS types, "
            "node.description AS description, score",
            index_name=index_name,
            top_k=top_k,
            embedding=embedding,
        ).data()


_PPR_STREAM = """
CALL gds.pageRank.stream($name, {
    sourceNodes: $seed_ids,
    dampingFactor: $damping,
    maxIterations: 20
}) YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
WHERE node:Entity
RETURN node.id AS id, node.name AS name, labels(node) AS types,
       node.description AS description, score
ORDER BY score DESC
LIMIT $top_n
"""


def ppr_query(
    driver: Driver, seed_ids: list[str], top_n: int, damping: float = 0.85
) -> list[dict[str, Any]]:
    """Personalized PageRank seeded from the given entity ids.

    Propagates relevance across the whole entity graph in one pass (implicit
    multi-hop), unlike a fixed 1-hop expansion. Projects a temporary undirected
    graph, runs GDS PageRank with the seeds as source nodes, returns the top-N
    ranked entities. Falls back to an empty list when the graph is too small.
    Grounded in HippoRAG 2 / NodeRAG.
    """
    if not seed_ids:
        return []
    with driver.session() as session:
        node_count = session.run("MATCH (e:Entity) RETURN count(e) AS n").single()["n"]
        if node_count < 2:
            return []
        try:
            session.run("CALL gds.graph.drop($name, false)", name=_PPR_PROJECTION).consume()
            session.run(
                "CALL gds.graph.project($name, 'Entity', "
                "{ALL: {type: '*', orientation: 'UNDIRECTED'}})",
                name=_PPR_PROJECTION,
            ).consume()
            seed_node_ids = [
                row["nid"]
                for row in session.run(
                    "MATCH (e:Entity) WHERE e.id IN $ids RETURN id(e) AS nid", ids=seed_ids
                )
            ]
            if not seed_node_ids:
                return []
            rows = session.run(
                _PPR_STREAM,
                name=_PPR_PROJECTION,
                seed_ids=seed_node_ids,
                damping=damping,
                top_n=top_n,
            ).data()
        except Exception as exc:
            logger.warning(f"PPR query fell back (graph issue): {exc}")
            return []
        finally:
            session.run("CALL gds.graph.drop($name, false)", name=_PPR_PROJECTION).consume()
    emit("graphrag.communities", ppr_seeds=len(seed_ids), ppr_results=len(rows))
    return rows


def global_summaries(driver: Driver, limit: int = 20) -> list[dict[str, Any]]:
    """Community summaries for global sensemaking queries (R6 global path)."""
    with driver.session() as session:
        return session.run(
            "MATCH (c:KGFCommunity) RETURN c.title AS title, c.summary AS summary LIMIT $limit",
            limit=limit,
        ).data()


def is_global_query(question: str) -> bool:
    """Heuristic router: global/thematic questions go to community summaries,
    entity/multi-hop questions go to PPR (R6)."""
    q = question.lower()
    global_markers = (
        "overall",
        "in general",
        "across all",
        "themes",
        "summarize",
        "summary of",
        "what kinds of",
        "what types of",
        "landscape",
        "high level",
        "high-level",
    )
    return any(m in q for m in global_markers)


def scorecard(driver: Driver) -> dict[str, Any]:
    """Graph quality metrics computed with pure Cypher plus Python entropy."""
    with driver.session() as session:
        counts = session.run(
            "MATCH (e:Entity) "
            "OPTIONAL MATCH (:Entity)-[r]->(:Entity) "
            "RETURN count(DISTINCT e) AS entities, count(DISTINCT r) AS relationships"
        ).single()
        entity_count = counts["entities"]
        relationship_count = counts["relationships"]
        orphans = session.run(
            "MATCH (e:Entity) WHERE NOT (e)--(:Entity) RETURN count(e) AS n"
        ).single()["n"]
        distinct_names = session.run(
            "MATCH (e:Entity) RETURN count(DISTINCT toLower(trim(e.name))) AS n"
        ).single()["n"]
        type_counts = [
            row["n"]
            for row in session.run(
                "MATCH (:Entity)-[r]->(:Entity) RETURN type(r) AS t, count(*) AS n"
            )
        ]
    total_rels = sum(type_counts)
    entropy = (
        -sum((n / total_rels) * math.log2(n / total_rels) for n in type_counts)
        if total_rels
        else 0.0
    )
    result = {
        "entity_count": entity_count,
        "relationship_count": relationship_count,
        "orphan_rate": orphans / entity_count if entity_count else 0.0,
        "duplicate_name_density": 1 - distinct_names / entity_count if entity_count else 0.0,
        "relationship_type_entropy": entropy,
        "avg_degree": 2 * relationship_count / entity_count if entity_count else 0.0,
    }
    emit("graphrag.scorecard", **result)
    return result

"""GraphRAG optimization: Leiden communities, summaries, vector query, scorecard."""

from __future__ import annotations

import math
import re
from typing import Any, Optional

from loguru import logger
from neo4j import Driver
from pydantic import BaseModel

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit

_PROJECTION_NAME = "kgf_leiden"
_PPR_PROJECTION = "kgf_ppr"

# R02-H12: node labels in the PPR projection - chunks diffuse relevance
# jointly with entities (HippoRAG 2 passage nodes); ablations may override
PPR_NODE_LABELS = ("Entity", "Chunk")


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


def overfetch_seeds(query_fn, top_k: int, factor: int) -> list[dict[str, Any]]:
    """R15-H195a generous-fetch: query the index at ``top_k * factor`` then
    truncate to ``top_k`` after ranking. The index returns rows already ordered
    by score, so the wider fetch only changes which rows can enter the top_k;
    ``factor <= 1`` is the plain top_k fetch. ``query_fn`` takes the fetch size."""
    fetch = top_k * factor if factor > 1 else top_k
    return query_fn(fetch)[:top_k]


def _query_similarity(query_embedding: list[float], emb: Optional[list[float]]) -> float:
    """Dot product against the query embedding (Titan embeddings are unit-norm,
    so dot == cosine); a missing embedding sorts last."""
    if not emb:
        return -1.0
    return float(sum(a * b for a, b in zip(query_embedding, emb)))


def cap_fanout(
    rows: list[dict[str, Any]], query_embedding: list[float], k: int
) -> list[dict[str, Any]]:
    """R19-H180: rank 1-hop neighbor rows by similarity of the neighbor embedding
    (``row['emb']``) to the query, keep the top ``k``. Zero recall loss at k=5 on
    the R19 census; ``k <= 0`` leaves the rows unbounded."""
    if k <= 0:
        return rows
    ranked = sorted(
        rows, key=lambda r: _query_similarity(query_embedding, r.get("emb")), reverse=True
    )
    return ranked[:k]


def detect_miss(seeds: list[dict[str, Any]], threshold: float) -> bool:
    """R19-H181: True when the best seed similarity is below ``threshold`` - the
    miss class, rendered as a cheap abstention form instead of full context.
    Threshold 0.668 detects 86.7% of misses at 0% false-abstention (R19 census)."""
    return max((s.get("score", 0.0) for s in seeds), default=0.0) < threshold


def truncate_to_budget(units: list[tuple[Any, float, float]], budget: float) -> list[Any]:
    """R19-H182: keep the top-similarity ``budget`` fraction of render mass.
    ``units`` is ``(item, similarity, size)``; ranks by similarity descending and
    greedily accumulates items until ``budget * total_size`` is exhausted. Returns
    the kept items in similarity order. ``budget >= 1`` keeps everything in the
    original order (the disabled path preserves prior render behavior)."""
    if budget >= 1.0:
        return [u[0] for u in units]
    cap = budget * sum(u[2] for u in units)
    acc, kept = 0.0, []
    for item, _sim, size in sorted(units, key=lambda u: u[1], reverse=True):
        if acc + size <= cap:
            kept.append(item)
            acc += size
    return kept


# R19-H205: device-type labels whose foreign render sections the optional
# exclusion layer drops (the queried product and non-device nodes are kept)
_DEVICE_TYPES = {"CPAPDevice", "ProductModel", "Device", "Product"}


def exclude_foreign_devices(
    nodes: list[dict[str, Any]], keep_ids: set[str]
) -> list[dict[str, Any]]:
    """R19-H205: drop render sections for foreign devices - device-typed nodes
    whose id is not in ``keep_ids`` (the queried product and its aliases).
    Non-device nodes are always kept (+5.5pt feature attribution, directional)."""
    return [
        n for n in nodes if not (_DEVICE_TYPES & set(n.get("types", []))) or n["id"] in keep_ids
    ]


def link_prop_values(name: str, value_index: dict[str, list[str]]) -> list[str]:
    """R19-H211: return the carrier names whose property value equals ``name``
    (the prop-val linkage rule, 224-target map). ``value_index`` maps a normalized
    property value to the entities holding it; names shorter than 4 chars do not
    link (embedding-surface noise floor)."""
    key = re.sub(r"\s+", " ", (name or "").casefold()).strip()
    if len(key) < 4:
        return []
    return value_index.get(key, [])


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
            # R02-H12: chunks join the projection (HippoRAG 2 passage nodes) so
            # passage and entity relevance diffuse jointly; _PPR_STREAM still
            # filters returned nodes to entities. GDS rejects labels absent
            # from the store, so project only the labels that exist (a graph
            # without provenance nodes keeps working)
            present = {row["label"] for row in session.run("CALL db.labels()")}
            labels = [label for label in PPR_NODE_LABELS if label in present]
            session.run(
                "CALL gds.graph.project($name, $labels, "
                "{ALL: {type: '*', orientation: 'UNDIRECTED'}})",
                name=_PPR_PROJECTION,
                labels=labels,
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


_COMPARISON_PATTERNS = (
    # "compare (the) X and/with/to/vs (the) Y[: aspects]"
    re.compile(
        r"compare\s+(?:the\s+)?(.+?)\s+(?:and|with|to|vs\.?|versus)\s+(?:the\s+)?(.+?)"
        r"(?:\s*[:,]\s*(.+))?[.?]?$",
        re.IGNORECASE,
    ),
    # "X vs Y[: aspects]" / "X versus Y ..."
    re.compile(
        r"^(?:the\s+)?(.+?)\s+(?:vs\.?|versus)\s+(?:the\s+)?(.+?)(?:\s*[:,]\s*(.+))?[.?]?$",
        re.IGNORECASE,
    ),
    # "which (one) is <aspect>, (the) X or (the) Y"
    re.compile(
        r"which\s+(?:one\s+|device\s+|machine\s+)?(?:is|has)\s+(?:a\s+|the\s+)?(.+?)[,:]\s*"
        r"(?:the\s+)?(.+?)\s+or\s+(?:the\s+)?(.+?)\??$",
        re.IGNORECASE,
    ),
)


def decompose_comparison(question: str) -> Optional[list[str]]:
    """R03-H15: structurally split a comparison question into per-entity
    sub-queries ("A vs B on X" -> "A X", "B X"). Deterministic - no LLM, no
    error propagation. Returns None when the question is not a comparison."""
    for i, pattern in enumerate(_COMPARISON_PATTERNS):
        m = pattern.search(question.strip())
        if not m:
            continue
        if i == 2:  # "which is <aspect>, X or Y"
            aspect, x, y = m.group(1), m.group(2), m.group(3)
        else:
            x, y, aspect = m.group(1), m.group(2), m.group(3) or ""
        x, y, aspect = x.strip(" ?.,"), y.strip(" ?.,"), (aspect or "").strip(" ?.,")
        if not x or not y or len(x) > 80 or len(y) > 80:
            return None
        return [f"{x} {aspect}".strip(), f"{y} {aspect}".strip()]
    return None


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

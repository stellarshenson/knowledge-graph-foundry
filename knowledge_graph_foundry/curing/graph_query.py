"""Graph query tool for LLM-assisted curing and type resolution.

Provides a unified query interface for inspecting graph data during ambiguous
decisions. Two backends: query_fluid() for in-memory FluidAccumulator during
fluid phase, query_graph() for Neo4j Cypher during cured phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from knowledge_graph_foundry.curing.accumulator import FluidAccumulator
    from knowledge_graph_foundry.types.config import Neo4jConfig


class GraphQueryRequest(BaseModel):
    query_type: Literal["entity_counts", "relationship_patterns", "entity_search"]
    filter_type: str | None = None
    filter_name: str | None = None
    limit: int = 20


class GraphQueryResult(BaseModel):
    summary: str
    records: list[dict[str, str | int | float]]
    record_count: int


def query_fluid(
    request: GraphQueryRequest,
    accumulator: "FluidAccumulator",
) -> GraphQueryResult:
    """Execute a graph query against the in-memory FluidAccumulator."""
    if request.query_type == "entity_counts":
        return _fluid_entity_counts(request, accumulator)
    elif request.query_type == "relationship_patterns":
        return _fluid_relationship_patterns(request, accumulator)
    elif request.query_type == "entity_search":
        return _fluid_entity_search(request, accumulator)
    else:
        return GraphQueryResult(summary="Unknown query type", records=[], record_count=0)


def query_graph(
    request: GraphQueryRequest,
    neo4j_config: "Neo4jConfig",
) -> GraphQueryResult:
    """Execute a graph query against Neo4j."""
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        neo4j_config.uri,
        auth=(neo4j_config.user, neo4j_config.password),
    )
    try:
        with driver.session() as session:
            if request.query_type == "entity_counts":
                return _graph_entity_counts(request, session)
            elif request.query_type == "relationship_patterns":
                return _graph_relationship_patterns(request, session)
            elif request.query_type == "entity_search":
                return _graph_entity_search(request, session)
            else:
                return GraphQueryResult(summary="Unknown query type", records=[], record_count=0)
    finally:
        driver.close()


# -- Fluid backends --


def _fluid_entity_counts(
    request: GraphQueryRequest,
    accumulator: "FluidAccumulator",
) -> GraphQueryResult:
    """Count entities per type from accumulated results."""
    from collections import Counter

    entities = accumulator.all_entities()
    type_counts: Counter[str] = Counter()
    for e in entities:
        if request.filter_type and e.type != request.filter_type:
            continue
        type_counts[e.type] += 1

    records = [{"type": t, "count": c} for t, c in type_counts.most_common(request.limit)]
    summary = f"{len(type_counts)} entity types, {sum(type_counts.values())} total entities"
    return GraphQueryResult(summary=summary, records=records, record_count=len(records))


def _fluid_relationship_patterns(
    request: GraphQueryRequest,
    accumulator: "FluidAccumulator",
) -> GraphQueryResult:
    """Count relationship patterns from accumulated results."""
    from collections import Counter

    entities = accumulator.all_entities()
    relationships = accumulator.all_relationships()

    # Build entity ID -> type lookup
    id_to_type: dict[str, str] = {e.id: e.type for e in entities}

    pattern_counts: Counter[tuple[str, str, str]] = Counter()
    for rel in relationships:
        src_type = id_to_type.get(rel.source, "Unknown")
        tgt_type = id_to_type.get(rel.target, "Unknown")
        pattern_counts[(src_type, rel.type, tgt_type)] += 1

    records = [
        {"source_type": s, "rel_type": r, "target_type": t, "count": c}
        for (s, r, t), c in pattern_counts.most_common(request.limit)
    ]
    summary = f"{len(pattern_counts)} relationship patterns, {sum(pattern_counts.values())} total relationships"
    return GraphQueryResult(summary=summary, records=records, record_count=len(records))


def _fluid_entity_search(
    request: GraphQueryRequest,
    accumulator: "FluidAccumulator",
) -> GraphQueryResult:
    """Search entities by name and/or type from accumulated results."""
    entities = accumulator.all_entities()
    matches = []

    filter_name_lower = request.filter_name.lower() if request.filter_name else None

    for e in entities:
        if request.filter_type and e.type != request.filter_type:
            continue
        if filter_name_lower and filter_name_lower not in e.name.lower():
            continue
        matches.append(
            {
                "name": e.name,
                "type": e.type,
                "description": e.description or "",
            }
        )
        if len(matches) >= request.limit:
            break

    summary = f"{len(matches)} entities found"
    return GraphQueryResult(summary=summary, records=matches, record_count=len(matches))


# -- Neo4j backends --


def _graph_entity_counts(
    request: GraphQueryRequest,
    session,
) -> GraphQueryResult:
    """Count entities per type from Neo4j."""
    if request.filter_type:
        result = session.run(
            "MATCH (e:Entity {type: $type}) WHERE NOT e:KGFControl "
            "RETURN e.type AS type, count(e) AS count",
            {"type": request.filter_type},
        )
    else:
        result = session.run(
            "MATCH (e:Entity) WHERE NOT e:KGFControl "
            "RETURN e.type AS type, count(e) AS count ORDER BY count DESC LIMIT $limit",
            {"limit": request.limit},
        )

    records = [{"type": r["type"], "count": r["count"]} for r in result]
    total = sum(r["count"] for r in records)
    summary = f"{len(records)} entity types, {total} total entities"
    return GraphQueryResult(summary=summary, records=records, record_count=len(records))


def _graph_relationship_patterns(
    request: GraphQueryRequest,
    session,
) -> GraphQueryResult:
    """Count relationship patterns from Neo4j."""
    result = session.run(
        "MATCH (a:Entity)-[r]->(b:Entity) "
        "WHERE NOT a:KGFControl AND NOT b:KGFControl "
        "RETURN a.type AS source_type, type(r) AS rel_type, b.type AS target_type, count(*) AS count "
        "ORDER BY count DESC LIMIT $limit",
        {"limit": request.limit},
    )

    records = [
        {
            "source_type": r["source_type"],
            "rel_type": r["rel_type"],
            "target_type": r["target_type"],
            "count": r["count"],
        }
        for r in result
    ]
    total = sum(r["count"] for r in records)
    summary = f"{len(records)} relationship patterns, {total} total relationships"
    return GraphQueryResult(summary=summary, records=records, record_count=len(records))


def _graph_entity_search(
    request: GraphQueryRequest,
    session,
) -> GraphQueryResult:
    """Search entities by name and/or type from Neo4j."""
    conditions = ["NOT e:KGFControl"]
    params: dict[str, str | int] = {"limit": request.limit}

    if request.filter_name:
        conditions.append("e.name CONTAINS $name")
        params["name"] = request.filter_name
    if request.filter_type:
        conditions.append("e.type = $type")
        params["type"] = request.filter_type

    where = f" WHERE {' AND '.join(conditions)}"
    query = f"MATCH (e:Entity){where} RETURN e.name AS name, e.type AS type, e.description AS description LIMIT $limit"

    result = session.run(query, params)
    records = [
        {
            "name": r["name"],
            "type": r["type"],
            "description": r["description"] or "",
        }
        for r in result
    ]
    summary = f"{len(records)} entities found"
    return GraphQueryResult(summary=summary, records=records, record_count=len(records))

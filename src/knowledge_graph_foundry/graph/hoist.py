"""Spec-reachability repair (R33-H365).

The H364 stage walk located 83.3% of emitted-but-lost gold mass at resolution:
spec `prop_*` values sit only on child-model entities under one series-level
fragment while retrieval surfaces a different, property-less fragment of the
same series. Two additive, provenance-tagged passes repair reachability:

  bridge_series_fragments - entities sharing a model-code stem whose names
      BOTH carry a series marker (series/range/family/line) are fragments of
      one series; each fragment receives PART_OF edges from the union of
      their children (edge property spec_bridge=true)
  hoist_unanimous_specs - for every series-marker parent with >= 2 PART_OF
      children, `prop_*` keys carried by EVERY child with one identical value
      are copied onto the parent; existing parent values are never
      overwritten; hoisted keys accumulate in a `spec_hoisted` marker

The series-marker guard on both passes keeps component-to-product hoists
(e.g. battery specs onto a device) structurally impossible. Both passes are
idempotent and exactly reversible via the markers. Verified offline on the
CPAP pile: P09 0.0 -> 1.0, P16 0.5 -> 1.0, 22 probes bit-identical
(`reports/h365-repaired-recall-20260710T143152Z.json`).
"""

from __future__ import annotations

import re

from loguru import logger

from knowledge_graph_foundry.events import emit

SERIES_MARKERS = ("series", "range", "family", "line")
_STEM_RE = re.compile(r"\b([A-Za-z]{1,4}[- ]?\d{2,4})\b")


def series_stem(name: str) -> str | None:
    """Model-code stem of a series-level name, or None when the name carries
    no series marker (series/range/family/line) or no model code."""
    lowered = name.lower()
    if not any(m in lowered for m in SERIES_MARKERS):
        return None
    match = _STEM_RE.search(name)
    if not match:
        return None
    return re.sub(r"[- ]", "", match.group(1)).upper()


def unanimous_props(children_props: list[dict]) -> dict:
    """`prop_*` keys carried by EVERY child with one identical value."""
    if len(children_props) < 2:
        return {}
    keys = {k for p in children_props for k in p if k.startswith("prop_")}
    out = {}
    for k in sorted(keys):
        vals = [p.get(k) for p in children_props]
        if any(v is None for v in vals):
            continue
        if all(v == vals[0] for v in vals[1:]):
            out[k] = vals[0]
    return out


def bridge_series_fragments(driver) -> int:
    """PART_OF-bridge children across series fragments; returns edges created."""
    with driver.session() as session:
        rows = session.run(
            "MATCH (e:Entity) WHERE e.name IS NOT NULL RETURN e.id AS id, e.name AS name"
        ).data()
        groups: dict[str, list[dict]] = {}
        for r in rows:
            stem = series_stem(r["name"])
            if stem:
                groups.setdefault(stem, []).append(r)
        created = 0
        for stem, frags in groups.items():
            if len(frags) < 2:
                continue
            ids = [f["id"] for f in frags]
            result = session.run(
                "UNWIND $ids AS fid "
                "MATCH (c:Entity)-[:PART_OF]->(:Entity {id: fid}) "
                "WHERE NOT c.id IN $ids "
                "WITH collect(DISTINCT c) AS kids "
                "UNWIND $ids AS tid "
                "MATCH (t:Entity {id: tid}) "
                "UNWIND kids AS c "
                "WITH c, t WHERE NOT (c)-[:PART_OF]->(t) "
                "MERGE (c)-[r:PART_OF {spec_bridge: true}]->(t) "
                "RETURN count(r) AS n",
                ids=ids,
            ).single()
            n = result["n"] if result else 0
            created += n
            if n:
                logger.info(
                    "series bridge {}: {} PART_OF edges across {} fragments", stem, n, len(frags)
                )
    if created:
        emit("resolution.series_bridge", edges_created=created)
    return created


def hoist_unanimous_specs(driver) -> dict:
    """Hoist unanimous child specs onto series-marker parents; returns counts."""
    marker_pattern = "|".join(SERIES_MARKERS)
    parents_touched = props_hoisted = 0
    with driver.session() as session:
        rows = session.run(
            "MATCH (c:Entity)-[:PART_OF]->(p:Entity) "
            f"WHERE toLower(p.name) =~ '.*({marker_pattern}).*' "
            "WITH p, collect(properties(c)) AS kids WHERE size(kids) >= 2 "
            "RETURN p.id AS id, properties(p) AS props, kids"
        ).data()
        for row in rows:
            hoist = {
                k: v for k, v in unanimous_props(row["kids"]).items() if k not in row["props"]
            }
            if not hoist:
                continue
            already = row["props"].get("spec_hoisted") or []
            session.run(
                "MATCH (p:Entity {id: $id}) SET p += $props, p.spec_hoisted = $keys",
                id=row["id"],
                props=hoist,
                keys=sorted(set(already) | set(hoist)),
            ).consume()
            parents_touched += 1
            props_hoisted += len(hoist)
    if parents_touched:
        emit("resolution.spec_hoist", parents=parents_touched, props=props_hoisted)
        logger.info("spec hoist: {} props onto {} parents", props_hoisted, parents_touched)
    return {"parents": parents_touched, "props": props_hoisted}

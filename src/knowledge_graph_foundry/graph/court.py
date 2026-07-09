"""Demote-don't-delete identity court (R27 composition - H290/H282/H267/H292).

At ingest-close a single-shot LLM judge adjudicates the SAME_AS docket - every
deterministic alias edge from graph/aliases.py. Judged-false edges are DEMOTED
to posterior-weighted SIMILAR_TO soft links, never deleted: H288 measured a
soft link carries a merge's entire render-recall value (+0.0 pts), so the
judge's one failure mode - over-splitting cross-type aliases - is costless.

Constants from the R27 record:

- single call per pair, no tool loop (H283 refuted: 4x cost to trade detection
  for leniency), no fetch pipeline (H285: theater on detection) - the plain
  single-shot judge is the adjudicator (H290)
- effort cap K=3 standing constant (H284: effort past K=3 mildly negative, late
  rounds re-argue instead of re-fetch); the shipped court is single-shot
- type labels STAY in the judge context (H292: type labels are identity evidence)
- H267 freebie: exact-normalized name-identical pairs auto-confirm with no LLM
  call (the 4.5% deterministic-identity class)
"""

from __future__ import annotations

from loguru import logger

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.graph.aliases import normalize_name
from knowledge_graph_foundry.graph.densify import add_soft_links
from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.resolution.bayesian import evidence
from knowledge_graph_foundry.resolution.judge import judge_pair
from knowledge_graph_foundry.settings import ResolutionSettings

_EFFORT_CAP_K = 3  # R27-H284 standing ceiling on judge rounds; the shipped court is single-shot


def _entity(row: dict, side: str) -> Entity:
    return Entity(
        id=row[f"{side}_id"],
        name=row[f"{side}_name"],
        types=row[f"{side}_types"] or [],
        description=row[f"{side}_desc"] or "",
        embedding=row[f"{side}_emb"],
    )


def _load_docket(driver) -> list[dict]:
    """Every SAME_AS edge with both endpoints' identity context for the judge."""
    with driver.session() as session:
        return [
            {
                "left_id": r["la"],
                "left_name": r["lname"],
                "left_types": r["ltypes"],
                "left_desc": r["ldesc"],
                "left_emb": r["lemb"],
                "right_id": r["ra"],
                "right_name": r["rname"],
                "right_types": r["rtypes"],
                "right_desc": r["rdesc"],
                "right_emb": r["remb"],
            }
            for r in session.run(
                "MATCH (a:Entity)-[:SAME_AS]->(b:Entity) "
                "RETURN a.id AS la, a.name AS lname, "
                "[l IN labels(a) WHERE l <> 'Entity'] AS ltypes, "
                "a.description AS ldesc, a.embedding AS lemb, "
                "b.id AS ra, b.name AS rname, "
                "[l IN labels(b) WHERE l <> 'Entity'] AS rtypes, "
                "b.description AS rdesc, b.embedding AS remb"
            )
        ]


def _demote(driver, demotions: list[tuple[str, str, float]]) -> None:
    """Remove the SAME_AS edge and materialize the posterior-weighted soft link."""
    rows = [{"left": left, "right": right} for left, right, _ in demotions]
    with driver.session() as session:
        session.run(
            "UNWIND $rows AS row "
            "MATCH (a:Entity {id: row.left})-[s:SAME_AS]-(b:Entity {id: row.right}) DELETE s",
            rows=rows,
        ).consume()
    add_soft_links(driver, demotions)


def run_demotion_court(driver, engine, cfg: ResolutionSettings) -> dict:
    """Adjudicate the SAME_AS docket; demote judged-false edges to soft links.

    Returns a summary: docket size, H267 freebies (auto-confirmed, no LLM),
    judged pairs, and demotions."""
    docket = _load_docket(driver)
    freebies = judged = 0
    demotions: list[tuple[str, str, float]] = []
    for row in docket:
        # H267 freebie: exact-normalized name identity auto-confirms - no LLM call
        if normalize_name(row["left_name"]) == normalize_name(row["right_name"]):
            freebies += 1
            continue
        left, right = _entity(row, "left"), _entity(row, "right")
        judged += 1
        if judge_pair(left, right, engine):
            continue  # judged same - the SAME_AS edge stands
        # judged false: DEMOTE to a posterior-weighted soft link, never delete
        weight = evidence(left, right, cfg).posterior
        demotions.append((row["left_id"], row["right_id"], weight))
    if demotions:
        _demote(driver, demotions)
    summary = {
        "docket": len(docket),
        "freebies": freebies,
        "judged": judged,
        "demoted": len(demotions),
    }
    emit("resolution.court", **summary)
    logger.info(
        "demotion court: {} docket, {} freebies, {} judged, {} demoted",
        summary["docket"],
        freebies,
        judged,
        summary["demoted"],
    )
    return summary

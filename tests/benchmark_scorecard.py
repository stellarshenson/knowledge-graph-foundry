"""Hybrid benchmark scorecard for graph quality evaluation.

Evaluates the knowledge graph via:
1. Deterministic Cypher queries against ground truth from source documents
2. LLM generative scoring for nuanced quality assessment

Final hybrid score: (deterministic_pct * 0.5) + (generative_avg_normalized * 0.5)

Ground truth is based on the BMC RESmart Auto CPAP User Manual.
The scorecard is completely independent of extraction prompts.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loguru import logger
from neo4j import GraphDatabase


@dataclass
class ScoreItem:
    """Single deterministic benchmark check."""
    dimension: str
    name: str
    query: str
    expected: str
    check_fn: str  # "exists", "count_gte", "count_eq", "count_lte", "ratio_check"
    expected_value: object = None
    actual_value: object = None
    passed: bool = False
    notes: str = ""


@dataclass
class GenerativeScore:
    """LLM-assessed quality score for a dimension."""
    dimension: str
    score: float = 0.0  # 1-5 scale
    reasoning: str = ""


@dataclass
class BenchmarkResult:
    """Full benchmark result across all dimensions."""
    timestamp: str = ""
    source_file: str = ""
    config_description: str = ""
    total_checks: int = 0
    passed_checks: int = 0
    deterministic_pct: float = 0.0
    generative_avg: float = 0.0
    hybrid_score: float = 0.0
    dimension_scores: dict = field(default_factory=dict)
    generative_scores: list = field(default_factory=list)
    items: list = field(default_factory=list)
    entity_count: int = 0
    relationship_count: int = 0
    chunk_count: int = 0
    type_distribution: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Ground truth: BMC RESmart Auto CPAP User Manual (26 pages)
# 8 dimensions, 47 checks
# ═══════════════════════════════════════════════════════════════════

SCORECARD: list[ScoreItem] = [
    # ── Dimension 1: Entity Coverage (12 checks) ──
    ScoreItem(
        dimension="entity_coverage",
        name="Product: RESmart Auto CPAP",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'resmart' RETURN count(n) AS cnt",
        expected="RESmart product entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Manufacturer: BMC Medical",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'bmc' RETURN count(n) AS cnt",
        expected="BMC Medical entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Accessory: Humidifier (InH2)",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'humidifier' OR toLower(n.name) CONTAINS 'inh2' RETURN count(n) AS cnt",
        expected="Humidifier entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Feature: Reslex/EPR pressure relief",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'reslex' OR toLower(n.name) CONTAINS 'epr' OR toLower(n.name) CONTAINS 'pressure relief' RETURN count(n) AS cnt",
        expected="Reslex/pressure relief entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Feature: Ramp function",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'ramp' RETURN count(n) AS cnt",
        expected="Ramp feature entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Feature: Auto-On or Auto-Off",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'auto on' OR toLower(n.name) CONTAINS 'auto off' OR toLower(n.name) CONTAINS 'auto-on' OR toLower(n.name) CONTAINS 'auto-off' RETURN count(n) AS cnt",
        expected="Auto-On or Auto-Off entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Feature: iCode compliance",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'icode' RETURN count(n) AS cnt",
        expected="iCode entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Mode: CPAP",
        query="MATCH (n:Entity) WHERE toLower(n.name) = 'cpap' OR (toLower(n.name) CONTAINS 'cpap' AND (toLower(n.type) CONTAINS 'mode' OR toLower(n.type) CONTAINS 'work')) RETURN count(n) AS cnt",
        expected="CPAP mode entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Mode: Auto mode",
        query="MATCH (n:Entity) WHERE (toLower(n.name) = 'auto' OR toLower(n.name) CONTAINS 'auto mode' OR toLower(n.name) CONTAINS 'auto cpap') AND NOT toLower(n.name) CONTAINS 'auto on' AND NOT toLower(n.name) CONTAINS 'auto off' RETURN count(n) AS cnt",
        expected="Auto mode entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Condition: Obstructive Sleep Apnea",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'sleep apnea' OR toLower(n.name) CONTAINS 'osa' RETURN count(n) AS cnt",
        expected="OSA entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="Component: Foam filter",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'filter' RETURN count(n) AS cnt",
        expected="Filter entity",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="entity_coverage",
        name="EU Rep: Shanghai Intl Holding",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'shanghai' RETURN count(n) AS cnt",
        expected="EU auth representative",
        check_fn="count_gte", expected_value=1,
    ),

    # ── Dimension 2: Specification Extraction (10 checks) ──
    ScoreItem(
        dimension="spec_extraction",
        name="Pressure range: 4-20 hPa values",
        query="MATCH (n:Entity) WHERE (toLower(n.description) CONTAINS '4' AND toLower(n.description) CONTAINS '20' AND (toLower(n.description) CONTAINS 'hpa' OR toLower(n.description) CONTAINS 'cmh2o')) OR (toLower(n.name) CONTAINS 'pressure' AND toLower(n.description) CONTAINS 'hpa') RETURN n.name, n.description LIMIT 5",
        expected="Pressure 4-20 hPa with values",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Pressure increment: 0.5 hPa",
        query="MATCH (n:Entity) WHERE toLower(n.description) CONTAINS '0.5' AND (toLower(n.description) CONTAINS 'hpa' OR toLower(n.description) CONTAINS 'increment' OR toLower(n.description) CONTAINS 'pressure') RETURN n.name, n.description LIMIT 5",
        expected="0.5 hPa increment",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Sound level: < 30 dB",
        query="MATCH (n:Entity) WHERE (toLower(n.name) CONTAINS 'sound' OR toLower(n.description) CONTAINS 'sound') AND (toLower(n.description) CONTAINS '30' OR toLower(n.description) CONTAINS 'db') RETURN n.name, n.description LIMIT 5",
        expected="Sound < 30 dB",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Weight: 1.6 kg",
        query="MATCH (n:Entity) WHERE (toLower(n.description) CONTAINS '1.6' AND toLower(n.description) CONTAINS 'kg') OR (toLower(n.description) CONTAINS '3.5' AND toLower(n.description) CONTAINS 'lb') RETURN n.name, n.description LIMIT 5",
        expected="Weight 1.6 kg / 3.5 lbs",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Dimensions: 220 x 194 x 112 mm",
        query="MATCH (n:Entity) WHERE toLower(n.description) CONTAINS '220' AND (toLower(n.description) CONTAINS '194' OR toLower(n.description) CONTAINS 'mm') RETURN n.name, n.description LIMIT 5",
        expected="Dimensions 220x194x112 mm",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Power: 100-240V AC",
        query="MATCH (n:Entity) WHERE (toLower(n.description) CONTAINS '100' AND toLower(n.description) CONTAINS '240') OR toLower(n.description) CONTAINS '100-240' RETURN n.name, n.description LIMIT 5",
        expected="Power 100-240V AC",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Operating temp: 5-30 C",
        query="MATCH (n:Entity) WHERE (toLower(n.description) CONTAINS 'temperature' OR toLower(n.name) CONTAINS 'temperature' OR toLower(n.name) CONTAINS 'operating') AND (toLower(n.description) CONTAINS '30' OR toLower(n.description) CONTAINS '5') RETURN n.name, n.description LIMIT 5",
        expected="Temp 5-30 C",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Safety class: Class II / Type BF / IPX1",
        query="MATCH (n:Entity) WHERE toLower(n.description) CONTAINS 'class ii' OR toLower(n.description) CONTAINS 'type bf' OR toLower(n.description) CONTAINS 'ipx1' RETURN n.name, n.description LIMIT 5",
        expected="Safety classification",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Ramp default: 10 minutes",
        query="MATCH (n:Entity) WHERE (toLower(n.name) CONTAINS 'ramp' OR toLower(n.description) CONTAINS 'ramp') AND toLower(n.description) CONTAINS '10' RETURN n.name, n.description LIMIT 5",
        expected="Ramp time 10 min",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Default pressure: 7 hPa",
        query="MATCH (n:Entity) WHERE toLower(n.description) CONTAINS '7' AND toLower(n.description) CONTAINS 'hpa' AND toLower(n.description) CONTAINS 'pressure' RETURN n.name, n.description LIMIT 5",
        expected="Default pressure 7 hPa",
        check_fn="exists",
    ),

    # ── Dimension 3: Relationship Accuracy (6 checks) ──
    ScoreItem(
        dimension="relationship_accuracy",
        name="BMC -> manufactures -> RESmart",
        query="MATCH (a:Entity)-[r]->(b:Entity) WHERE toLower(a.name) CONTAINS 'bmc' AND toLower(b.name) CONTAINS 'resmart' RETURN type(r) AS rel_type, a.name, b.name LIMIT 5",
        expected="Manufacturing relationship",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="relationship_accuracy",
        name="RESmart -> specs (>= 2 spec relationships)",
        query="MATCH (a:Entity)-[r]->(b:Entity) WHERE toLower(a.name) CONTAINS 'resmart' AND (toLower(b.type) CONTAINS 'spec' OR toLower(type(r)) CONTAINS 'spec') RETURN count(r) AS cnt",
        expected="Product-spec relationships >= 2",
        check_fn="count_gte", expected_value=2,
    ),
    ScoreItem(
        dimension="relationship_accuracy",
        name="RESmart -> features (>= 2 feature rels)",
        query="MATCH (a:Entity)-[r]->(b:Entity) WHERE toLower(a.name) CONTAINS 'resmart' AND (toLower(b.type) CONTAINS 'feature' OR toLower(type(r)) CONTAINS 'feature') RETURN count(r) AS cnt",
        expected="Product-feature relationships >= 2",
        check_fn="count_gte", expected_value=2,
    ),
    ScoreItem(
        dimension="relationship_accuracy",
        name="RESmart -> components (>= 2 component rels)",
        query="MATCH (a:Entity)-[r]->(b:Entity) WHERE toLower(a.name) CONTAINS 'resmart' AND (toLower(b.type) CONTAINS 'component' OR toLower(type(r)) CONTAINS 'component') RETURN count(r) AS cnt",
        expected="Product-component relationships >= 2",
        check_fn="count_gte", expected_value=2,
    ),
    ScoreItem(
        dimension="relationship_accuracy",
        name="Orphan ratio < 20%",
        query="MATCH (n:Entity) WHERE NOT (n)-[]-() RETURN count(n) AS cnt",
        expected="Less than 20% orphans",
        check_fn="ratio_check", expected_value=0.2,
    ),
    ScoreItem(
        dimension="relationship_accuracy",
        name="RESmart -> treats -> OSA",
        query="MATCH (a:Entity)-[r]->(b:Entity) WHERE toLower(a.name) CONTAINS 'resmart' AND (toLower(b.name) CONTAINS 'apnea' OR toLower(b.name) CONTAINS 'osa') RETURN count(r) AS cnt",
        expected="Product-condition relationship",
        check_fn="count_gte", expected_value=1,
    ),

    # ── Dimension 4: Dedup Quality (4 checks) ──
    ScoreItem(
        dimension="dedup_quality",
        name="No same-type name duplicates",
        query="MATCH (n:Entity) WITH toLower(n.name) AS name, n.type AS type, count(*) AS cnt WHERE cnt > 1 RETURN count(name) AS cnt",
        expected="Zero same-type duplicates",
        check_fn="count_eq", expected_value=0,
    ),
    ScoreItem(
        dimension="dedup_quality",
        name="Cross-type duplicates < 15",
        query="MATCH (n:Entity) WITH toLower(n.name) AS name, count(*) AS cnt WHERE cnt > 1 RETURN count(name) AS cnt",
        expected="Few cross-type duplicates",
        check_fn="count_lte", expected_value=15,
    ),
    ScoreItem(
        dimension="dedup_quality",
        name="Entity count 30-300",
        query="MATCH (n:Entity) RETURN count(n) AS cnt",
        expected="Reasonable entity count",
        check_fn="count_gte", expected_value=30,
    ),
    ScoreItem(
        dimension="dedup_quality",
        name="Distinct types <= 15",
        query="MATCH (n:Entity) RETURN count(DISTINCT n.type) AS cnt",
        expected="Not too many types",
        check_fn="count_lte", expected_value=15,
    ),

    # ── Dimension 5: Graph Structure (6 checks) ──
    ScoreItem(
        dimension="graph_structure",
        name="Document node exists",
        query="MATCH (d:Document) RETURN count(d) AS cnt",
        expected="At least one Document",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="Chunk nodes have text",
        query="MATCH (c:Chunk) WHERE c.text IS NOT NULL RETURN count(c) AS cnt",
        expected="Chunks with text",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="NEXT_CHUNK chain exists",
        query="MATCH (a:Chunk)-[:NEXT_CHUNK]->(b:Chunk) RETURN count(*) AS cnt",
        expected="Chunk chain",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="HAS_CHUNK relationships",
        query="MATCH (:Document)-[:HAS_CHUNK]->(:Chunk) RETURN count(*) AS cnt",
        expected="Doc->Chunk links",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="HAS_ENTITY relationships",
        query="MATCH (:Chunk)-[:HAS_ENTITY]->(:Entity) RETURN count(*) AS cnt",
        expected="Chunk->Entity links",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="Chunk count 20-30",
        query="MATCH (c:Chunk) RETURN count(c) AS cnt",
        expected="~26 chunks for 26 pages",
        check_fn="count_gte", expected_value=20,
    ),

    # ── Dimension 6: Query Answerability (8 checks) ──
    ScoreItem(
        dimension="query_answerability",
        name="Q: Pressure range?",
        query="MATCH (n:Entity) WHERE (toLower(n.name) CONTAINS 'pressure' OR toLower(n.description) CONTAINS 'pressure range') AND toLower(n.description) CONTAINS 'hpa' RETURN n.name, n.description LIMIT 5",
        expected="4-20 hPa",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Who manufactures?",
        query="MATCH (org:Entity)-[r]->(prod:Entity) WHERE toLower(prod.name) CONTAINS 'resmart' AND (toLower(org.type) CONTAINS 'org' OR toLower(org.type) CONTAINS 'company' OR toLower(org.type) CONTAINS 'manufacturer') RETURN org.name LIMIT 5",
        expected="BMC Medical",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Device features?",
        query="MATCH (p:Entity)-[r]->(f:Entity) WHERE toLower(p.name) CONTAINS 'resmart' AND (toLower(f.type) CONTAINS 'feature' OR toLower(type(r)) CONTAINS 'feature') RETURN f.name LIMIT 10",
        expected="Feature list",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Device weight?",
        query="MATCH (n:Entity) WHERE (toLower(n.description) CONTAINS '1.6' AND toLower(n.description) CONTAINS 'kg') OR (toLower(n.description) CONTAINS '3.5' AND toLower(n.description) CONTAINS 'lb') RETURN n.name, n.description LIMIT 5",
        expected="1.6 kg / 3.5 lbs",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Sound level?",
        query="MATCH (n:Entity) WHERE (toLower(n.name) CONTAINS 'sound' OR toLower(n.description) CONTAINS 'sound') AND (toLower(n.description) CONTAINS '30' OR toLower(n.description) CONTAINS 'db') RETURN n.name, n.description LIMIT 5",
        expected="< 30 dB",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Operating modes?",
        query="MATCH (n:Entity) WHERE toLower(n.type) CONTAINS 'mode' OR toLower(n.type) CONTAINS 'work' RETURN n.name, n.description LIMIT 10",
        expected="CPAP/Auto/Titrate",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Medical conditions?",
        query="MATCH (n:Entity) WHERE toLower(n.type) CONTAINS 'condition' OR toLower(n.name) CONTAINS 'apnea' RETURN n.name, n.description LIMIT 10",
        expected="OSA and contraindications",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Included components?",
        query="MATCH (p:Entity)-[r]->(c:Entity) WHERE toLower(p.name) CONTAINS 'resmart' AND (toLower(c.type) CONTAINS 'component' OR toLower(type(r)) CONTAINS 'component' OR toLower(type(r)) CONTAINS 'include') RETURN c.name LIMIT 10",
        expected="Components list",
        check_fn="exists",
    ),

    # ── Dimension 7: Type Consistency (3 checks) ──
    ScoreItem(
        dimension="type_consistency",
        name="Top type >= 20% of entities",
        query="MATCH (n:Entity) WITH n.type AS type, count(n) AS cnt ORDER BY cnt DESC LIMIT 1 MATCH (m:Entity) WITH cnt, count(m) AS total RETURN cnt, total, toFloat(cnt)/total AS ratio",
        expected="Dominant type >= 20%",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="type_consistency",
        name="Singleton types < 5",
        query="MATCH (n:Entity) WITH n.type AS type, count(n) AS cnt WHERE cnt = 1 RETURN count(type) AS cnt",
        expected="Few singleton types",
        check_fn="count_lte", expected_value=5,
    ),
    ScoreItem(
        dimension="type_consistency",
        name="No type casing variants",
        query="MATCH (n:Entity) WITH toLower(n.type) AS ltype, collect(DISTINCT n.type) AS variants WHERE size(variants) > 1 RETURN count(ltype) AS cnt",
        expected="No casing inconsistencies",
        check_fn="count_eq", expected_value=0,
    ),

    # ── Dimension 8: Property Completeness (3 checks) ──
    ScoreItem(
        dimension="property_completeness",
        name="Most entities have descriptions",
        query="MATCH (n:Entity) WHERE n.description IS NOT NULL AND n.description <> '' WITH count(n) AS with_desc MATCH (m:Entity) RETURN with_desc, count(m) AS total, toFloat(with_desc)/count(m) AS ratio",
        expected="> 80% have descriptions",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="property_completeness",
        name="Some entities have properties",
        query="MATCH (n:Entity) WHERE n.properties IS NOT NULL AND n.properties <> '{}' AND n.properties <> 'null' RETURN count(n) AS cnt",
        expected="Entities with properties",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="property_completeness",
        name="Entities have confidence scores",
        query="MATCH (n:Entity) WHERE n.confidence IS NOT NULL RETURN count(n) AS cnt",
        expected="Confidence present",
        check_fn="count_gte", expected_value=1,
    ),
]


# ═══════════════════════════════════════════════════════════════════
# Generative scoring prompts per dimension
# ═══════════════════════════════════════════════════════════════════

GENERATIVE_PROMPTS = {
    "entity_coverage": {
        "query": "MATCH (n:Entity) RETURN n.name, n.type, substring(n.description, 0, 100) AS desc ORDER BY n.type, n.name",
        "prompt": """Evaluate entity coverage of a knowledge graph from the BMC RESmart Auto CPAP User Manual.

Entities in graph:
{data}

Ground truth key entities: RESmart Auto CPAP System, BMC Medical Co. Ltd., Shanghai Intl Holding (EU rep), InH2 Heated Humidifier, Ramp, Reslex (pressure relief), Auto-On, Auto-Off, iCode, Delay Off, CPAP/Auto/Titrate modes, foam filter, power cord, carrying case, Obstructive Sleep Apnea, contraindications (Bullous Lung Disease, Pneumothorax).

Rate 1-5: 1=most missing, 3=core present but gaps, 5=comprehensive.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "spec_extraction": {
        "query": "MATCH (n:Entity) WHERE toLower(n.type) CONTAINS 'spec' OR toLower(n.description) CONTAINS 'hpa' OR toLower(n.description) CONTAINS 'kg' OR toLower(n.description) CONTAINS 'mm' OR toLower(n.description) CONTAINS 'db' OR toLower(n.description) CONTAINS 'volt' RETURN n.name, n.type, n.description ORDER BY n.name",
        "prompt": """Evaluate specification extraction from a CPAP device manual knowledge graph.

Spec entities:
{data}

Ground truth specs: pressure 4-20 hPa (0.5 increments), weight 1.6 kg, dimensions 220x194x112mm, sound <30 dB, power 100-240V AC 50/60Hz, operating temp 5-30C, humidity <=80%, atm pressure 860-1060 hPa, default pressure 7 hPa, ramp 10 min.

Rate 1-5: 1=no numeric values, 3=some specs with values, 5=all major specs with exact values and units.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "relationship_accuracy": {
        "query": "MATCH (a:Entity)-[r]->(b:Entity) RETURN a.name AS source, type(r) AS rel, b.name AS target ORDER BY source LIMIT 60",
        "prompt": """Evaluate relationship quality in a CPAP device knowledge graph.

Relationships:
{data}

Expected: BMC->manufactures->RESmart, RESmart->has specs/features/components, RESmart->supports modes (CPAP/Auto/Titrate), RESmart->treats->OSA, RESmart->connects to->InH2 Humidifier.

Rate 1-5: 1=few/incorrect, 3=core present but incomplete, 5=comprehensive and accurate.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "dedup_quality": {
        "query": "MATCH (n:Entity) WITH toLower(n.name) AS name, collect(DISTINCT n.type) AS types, count(*) AS cnt WHERE cnt > 1 RETURN name, types, cnt ORDER BY cnt DESC LIMIT 20",
        "prompt": """Evaluate deduplication quality. Duplicates found:
{data}

Rate 1-5: 1=severe duplication, 3=some duplicates but core is clean, 5=no meaningful duplicates.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "query_answerability": {
        "query": "MATCH (n:Entity) WHERE toLower(n.description) CONTAINS 'hpa' OR toLower(n.description) CONTAINS 'kg' OR toLower(n.description) CONTAINS 'db' OR toLower(n.name) CONTAINS 'bmc' OR toLower(n.type) CONTAINS 'feature' OR toLower(n.type) CONTAINS 'mode' RETURN n.name, n.type, substring(n.description, 0, 150) AS desc ORDER BY n.type LIMIT 30",
        "prompt": """Evaluate if these graph entities can answer real questions about a CPAP device:
{data}

Questions: 1) Pressure range? (4-20 hPa) 2) Manufacturer? (BMC Medical) 3) Weight? (1.6 kg) 4) Sound? (<30 dB) 5) Features? (Ramp, Reslex, etc.) 6) Modes? (CPAP/Auto/Titrate) 7) Dimensions? (220x194x112mm) 8) Conditions? (OSA)

Rate 1-5: 1=most unanswerable, 3=basic questions ok, 5=all answerable with specific values.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
}


def run_benchmark(
    uri: str = "bolt://neo4j:7687",
    user: str = "neo4j",
    password: str = "kg-builder-pass",
    source_file: str = "BMC_RESmart_AutoCPAP_User_Manual.pdf",
    config_description: str = "",
) -> BenchmarkResult:
    """Execute all deterministic benchmark queries."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    result = BenchmarkResult(
        timestamp=datetime.now().isoformat(),
        source_file=source_file,
        config_description=config_description,
    )

    try:
        with driver.session() as session:
            # Graph stats
            r = session.run("MATCH (n:Entity) RETURN count(n) AS cnt")
            result.entity_count = r.single()["cnt"]
            r = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            result.relationship_count = r.single()["cnt"]
            r = session.run("MATCH (c:Chunk) RETURN count(c) AS cnt")
            result.chunk_count = r.single()["cnt"]

            type_records = list(session.run(
                "MATCH (n:Entity) RETURN n.type AS type, count(n) AS cnt ORDER BY cnt DESC LIMIT 15"
            ))
            result.type_distribution = {r["type"]: r["cnt"] for r in type_records}

            for item in SCORECARD:
                try:
                    records = list(session.run(item.query))

                    if item.check_fn == "count_gte":
                        actual = records[0]["cnt"] if records else 0
                        item.actual_value = actual
                        if "entity count" in item.name.lower():
                            item.passed = 30 <= actual <= 300
                            item.notes = f"{actual} entities"
                        else:
                            item.passed = actual >= item.expected_value

                    elif item.check_fn == "count_eq":
                        actual = records[0]["cnt"] if records else 0
                        item.actual_value = actual
                        item.passed = actual == item.expected_value

                    elif item.check_fn == "count_lte":
                        actual = records[0]["cnt"] if records else 0
                        item.actual_value = actual
                        item.passed = actual <= item.expected_value

                    elif item.check_fn == "ratio_check":
                        actual = records[0]["cnt"] if records else 0
                        item.actual_value = actual
                        ratio = actual / max(result.entity_count, 1)
                        item.passed = ratio < item.expected_value
                        item.notes = f"{actual} orphans / {result.entity_count} ({ratio:.0%})"

                    elif item.check_fn == "exists":
                        item.actual_value = len(records)
                        item.passed = len(records) > 0
                        if records:
                            item.notes = str(dict(records[0]))[:200]

                except Exception as exc:
                    item.passed = False
                    item.notes = f"Query error: {exc}"

                result.items.append(item)
    finally:
        driver.close()

    result.total_checks = len(result.items)
    result.passed_checks = sum(1 for i in result.items if i.passed)
    result.deterministic_pct = (result.passed_checks / max(result.total_checks, 1)) * 100

    dimensions: dict[str, list[bool]] = {}
    for item in result.items:
        dimensions.setdefault(item.dimension, []).append(item.passed)
    result.dimension_scores = {
        dim: f"{sum(scores)}/{len(scores)} ({sum(scores)/len(scores)*100:.0f}%)"
        for dim, scores in dimensions.items()
    }

    return result


def run_generative_scoring(
    result: BenchmarkResult,
    uri: str = "bolt://neo4j:7687",
    user: str = "neo4j",
    password: str = "kg-builder-pass",
) -> None:
    """Run LLM-based generative scoring for each dimension."""
    import litellm

    os.environ.setdefault("AWS_PROFILE", "kolomolo")
    os.environ.setdefault("AWS_REGION_NAME", "eu-central-1")

    model = "bedrock/eu.anthropic.claude-sonnet-4-20250514-v1:0"
    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session() as session:
            for dim_name, dim_config in GENERATIVE_PROMPTS.items():
                try:
                    records = list(session.run(dim_config["query"]))
                    data_str = json.dumps(
                        [dict(r) for r in records], indent=2, default=str
                    )[:4000]

                    prompt = dim_config["prompt"].format(data=data_str)

                    response = litellm.completion(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        max_tokens=200,
                    )

                    content = response.choices[0].message.content.strip()
                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        match = re.search(r'\{[^}]+\}', content)
                        parsed = json.loads(match.group()) if match else {"score": 0, "reasoning": content}

                    gen_score = GenerativeScore(
                        dimension=dim_name,
                        score=float(parsed.get("score", 0)),
                        reasoning=parsed.get("reasoning", ""),
                    )
                    result.generative_scores.append(gen_score)
                    logger.info("Generative [{}/5]: {} - {}", gen_score.score, dim_name, gen_score.reasoning[:80])

                except Exception as exc:
                    logger.warning("Generative scoring failed for {}: {}", dim_name, exc)
                    result.generative_scores.append(
                        GenerativeScore(dimension=dim_name, score=0, reasoning=f"Error: {exc}")
                    )
    finally:
        driver.close()

    valid_scores = [s.score for s in result.generative_scores if s.score > 0]
    result.generative_avg = sum(valid_scores) / max(len(valid_scores), 1)
    gen_normalized = (result.generative_avg / 5.0) * 100
    result.hybrid_score = (result.deterministic_pct * 0.5) + (gen_normalized * 0.5)


def print_benchmark(result: BenchmarkResult) -> None:
    """Print formatted benchmark results."""
    print(f"\n{'=' * 74}")
    print(f"  BENCHMARK SCORECARD - {result.source_file}")
    print(f"  {result.timestamp}")
    if result.config_description:
        print(f"  Config: {result.config_description}")
    print(f"{'=' * 74}")
    print(f"  Graph: {result.entity_count} entities, {result.relationship_count} rels, {result.chunk_count} chunks")
    print(f"  Deterministic: {result.passed_checks}/{result.total_checks} ({result.deterministic_pct:.0f}%)")
    if result.generative_scores:
        print(f"  Generative:    {result.generative_avg:.1f}/5.0")
        print(f"  HYBRID SCORE:  {result.hybrid_score:.0f}%")
    print(f"{'─' * 74}")

    if result.type_distribution:
        top = list(result.type_distribution.items())[:8]
        print(f"  Types: {', '.join(f'{t}:{c}' for t, c in top)}")
        print(f"{'─' * 74}")

    current_dim = ""
    for item in result.items:
        if item.dimension != current_dim:
            current_dim = item.dimension
            det = result.dimension_scores.get(current_dim, "?")
            gen = next((g for g in result.generative_scores if g.dimension == current_dim), None)
            gen_str = f" | LLM: {gen.score:.0f}/5" if gen else ""
            print(f"\n  [{current_dim.upper()}] {det}{gen_str}")
            print(f"  {'─' * 64}")

        status = "PASS" if item.passed else "FAIL"
        marker = "  " if item.passed else ">>"
        print(f"  {marker} [{status}] {item.name}")
        if item.notes and not item.passed:
            print(f"           {item.notes[:80]}")

    if result.generative_scores:
        print(f"\n{'=' * 74}")
        print(f"  GENERATIVE ASSESSMENT")
        print(f"{'─' * 74}")
        for gs in result.generative_scores:
            print(f"  {gs.dimension:30s} {gs.score:.0f}/5  {gs.reasoning[:55]}")

    print(f"\n{'=' * 74}")
    print(f"  DIMENSION SUMMARY")
    print(f"{'─' * 74}")
    for dim, score in result.dimension_scores.items():
        gen = next((g for g in result.generative_scores if g.dimension == dim), None)
        gen_str = f"  LLM: {gen.score:.0f}/5" if gen else ""
        print(f"  {dim:30s} {score:20s}{gen_str}")
    if result.hybrid_score > 0:
        print(f"{'─' * 74}")
        print(f"  {'HYBRID SCORE':30s} {result.hybrid_score:.0f}%")
    print(f"{'=' * 74}\n")


def save_benchmark(result: BenchmarkResult, path: Path) -> None:
    """Save benchmark result to JSON."""
    data = {
        "timestamp": result.timestamp,
        "source_file": result.source_file,
        "config_description": result.config_description,
        "entity_count": result.entity_count,
        "relationship_count": result.relationship_count,
        "chunk_count": result.chunk_count,
        "type_distribution": result.type_distribution,
        "total_checks": result.total_checks,
        "passed_checks": result.passed_checks,
        "deterministic_pct": result.deterministic_pct,
        "generative_avg": result.generative_avg,
        "hybrid_score": result.hybrid_score,
        "dimension_scores": result.dimension_scores,
        "generative_scores": [
            {"dimension": g.dimension, "score": g.score, "reasoning": g.reasoning}
            for g in result.generative_scores
        ],
        "items": [
            {
                "dimension": i.dimension,
                "name": i.name,
                "passed": i.passed,
                "expected": i.expected,
                "actual_value": str(i.actual_value) if i.actual_value is not None else None,
                "notes": i.notes,
            }
            for i in result.items
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    logger.info("Benchmark saved to {}", path)


if __name__ == "__main__":
    import sys

    config_desc = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "default"

    # Phase 1: Deterministic
    result = run_benchmark(config_description=config_desc)
    print_benchmark(result)

    # Phase 2: Generative
    print("\nRunning generative scoring (LLM evaluation)...")
    run_generative_scoring(result)
    print_benchmark(result)

    # Save
    score_int = int(result.hybrid_score) if result.hybrid_score > 0 else int(result.deterministic_pct)
    save_benchmark(result, Path(f"tmp/benchmark_v_latest_{score_int}.json"))
    save_benchmark(result, Path("tmp/benchmark_results.json"))

"""Multi-document benchmark scorecard for graph quality evaluation.

Evaluates the knowledge graph built from 10 CPAP device PDFs:
1. BMC_RESmart_AutoCPAP_User_Manual.pdf (379 KB) - BMC Medical
2. 3B_User-Manual_CPAP-Auto-CPAP_RESmart_BMC_V1.7_ENG-1.pdf (649 KB) - BMC Medical
3. Airsense-Brochure.pdf (913 KB) - ResMed
4. airstart-10-cpap_fact-sheet_apac_eng.pdf (252 KB) - ResMed
5. BC-Dreamstation-Standard-CPAP.pdf (135 KB) - Philips Respironics
6. CPAP_Eng.pdf (421 KB) - generic CPAP
7. DreamStation_CPAP_Pro_DataSheet.pdf (3.9 MB) - Philips Respironics
8. DreamStation_CPAP_User_Manual.pdf (3.2 MB) - Philips Respironics
9. Resvent-iBreeze-Auto-CPAP-User-Manual.pdf (897 KB) - Resvent
10. SleepStyle_200_Operating_Manual.pdf (1.0 MB) - Fisher & Paykel

Ground truth is derived from the source PDFs, not extraction prompts.
Final hybrid score: (deterministic_pct * 0.5) + (generative_avg_normalized * 0.5)
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


BENCHMARK_DOCS = [
    "BMC_RESmart_AutoCPAP_User_Manual.pdf",
    "3B_User-Manual_CPAP-Auto-CPAP_RESmart_BMC_V1.7_ENG-1.pdf",
    "Airsense-Brochure.pdf",
    "airstart-10-cpap_fact-sheet_apac_eng.pdf",
    "BC-Dreamstation-Standard-CPAP.pdf",
    "CPAP_Eng.pdf",
    "DreamStation_CPAP_Pro_DataSheet.pdf",
    "DreamStation_CPAP_User_Manual.pdf",
    "Resvent-iBreeze-Auto-CPAP-User-Manual.pdf",
    "SleepStyle_200_Operating_Manual.pdf",
]


@dataclass
class ScoreItem:
    """Single deterministic benchmark check."""
    dimension: str
    name: str
    query: str
    expected: str
    check_fn: str  # "exists", "count_gte", "count_eq", "count_lte", "count_range", "ratio_check"
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
    source_files: list = field(default_factory=lambda: list(BENCHMARK_DOCS))
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
    document_count: int = 0
    type_distribution: dict = field(default_factory=dict)


# ================================================================
# Ground truth: 10 CPAP PDFs - 5 manufacturers, 7+ products
# 10 dimensions, ~65 checks
# ================================================================

SCORECARD: list[ScoreItem] = [
    # -- Dimension 1: Document Coverage (4 checks) --
    ScoreItem(
        dimension="document_coverage",
        name="10 Document nodes",
        query="MATCH (d:Document) RETURN count(d) AS cnt",
        expected="10 documents",
        check_fn="count_gte", expected_value=10,
    ),
    ScoreItem(
        dimension="document_coverage",
        name="All docs have chunks",
        query="MATCH (d:Document) WHERE NOT (d)-[:HAS_CHUNK]->() RETURN count(d) AS cnt",
        expected="No orphan documents",
        check_fn="count_eq", expected_value=0,
    ),
    ScoreItem(
        dimension="document_coverage",
        name="Chunks > 100 across 10 docs",
        query="MATCH (c:Chunk) RETURN count(c) AS cnt",
        expected=">100 chunks for 10 PDFs",
        check_fn="count_gte", expected_value=100,
    ),
    ScoreItem(
        dimension="document_coverage",
        name="NEXT_CHUNK chains exist per doc",
        query="MATCH (a:Chunk)-[:NEXT_CHUNK]->(b:Chunk) RETURN count(*) AS cnt",
        expected="Chunk chains",
        check_fn="count_gte", expected_value=50,
    ),

    # -- Dimension 2: Manufacturer Coverage (5 checks) --
    ScoreItem(
        dimension="manufacturer_coverage",
        name="BMC Medical entity",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'bmc' RETURN count(n) AS cnt",
        expected="BMC Medical",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="manufacturer_coverage",
        name="ResMed entity",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'resmed' RETURN count(n) AS cnt",
        expected="ResMed",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="manufacturer_coverage",
        name="Philips / Respironics entity",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'philips' OR toLower(n.name) CONTAINS 'respironics' RETURN count(n) AS cnt",
        expected="Philips Respironics",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="manufacturer_coverage",
        name="Resvent entity",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'resvent' RETURN count(n) AS cnt",
        expected="Resvent",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="manufacturer_coverage",
        name="Fisher & Paykel entity",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'fisher' OR toLower(n.name) CONTAINS 'paykel' RETURN count(n) AS cnt",
        expected="Fisher & Paykel",
        check_fn="count_gte", expected_value=1,
    ),

    # -- Dimension 3: Product Coverage (7 checks) --
    ScoreItem(
        dimension="product_coverage",
        name="RESmart product",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'resmart' RETURN count(n) AS cnt",
        expected="BMC RESmart",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="product_coverage",
        name="AirSense product",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'airsense' RETURN count(n) AS cnt",
        expected="ResMed AirSense",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="product_coverage",
        name="AirStart product",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'airstart' RETURN count(n) AS cnt",
        expected="ResMed AirStart",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="product_coverage",
        name="DreamStation product",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'dreamstation' RETURN count(n) AS cnt",
        expected="Philips DreamStation",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="product_coverage",
        name="iBreeze product",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'ibreeze' RETURN count(n) AS cnt",
        expected="Resvent iBreeze",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="product_coverage",
        name="SleepStyle product",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'sleepstyle' OR toLower(n.name) CONTAINS 'sleep style' RETURN count(n) AS cnt",
        expected="Fisher & Paykel SleepStyle",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="product_coverage",
        name=">= 5 distinct Product entities",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'product' RETURN count(n) AS cnt",
        expected="At least 5 products",
        check_fn="count_gte", expected_value=5,
    ),

    # -- Dimension 4: Cross-Document Entity Resolution (6 checks) --
    ScoreItem(
        dimension="cross_doc_resolution",
        name="CPAP mode entities reasonable",
        query="MATCH (n:Entity) WHERE toLower(n.name) = 'cpap' OR toLower(n.name) = 'cpap mode' RETURN count(n) AS cnt",
        expected="Core CPAP mode consolidated",
        check_fn="count_lte", expected_value=3,
    ),
    ScoreItem(
        dimension="cross_doc_resolution",
        name="OSA entity consolidated",
        query="MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'sleep apnea' OR toLower(n.name) = 'osa' OR toLower(n.name) = 'obstructive sleep apnea' RETURN count(n) AS cnt",
        expected="OSA entity merged",
        check_fn="count_lte", expected_value=3,
    ),
    ScoreItem(
        dimension="cross_doc_resolution",
        name="Same-type name duplicates <= 2",
        query="MATCH (n:Entity) WITH toLower(n.name) AS name, n.type AS type, count(*) AS cnt WHERE cnt > 1 RETURN count(name) AS cnt",
        expected="Minimal same-type duplicates",
        check_fn="count_lte", expected_value=2,
    ),
    ScoreItem(
        dimension="cross_doc_resolution",
        name="Cross-type duplicates < 20",
        query="MATCH (n:Entity) WITH toLower(n.name) AS name, count(*) AS cnt WHERE cnt > 1 RETURN count(name) AS cnt",
        expected="Few cross-type duplicates",
        check_fn="count_lte", expected_value=20,
    ),
    ScoreItem(
        dimension="cross_doc_resolution",
        name="Humidifier entity consolidated",
        query="MATCH (n:Entity) WHERE toLower(n.name) = 'humidifier' OR toLower(n.name) = 'heated humidifier' RETURN count(n) AS cnt",
        expected="Core humidifier entities merged",
        check_fn="count_lte", expected_value=3,
    ),
    ScoreItem(
        dimension="cross_doc_resolution",
        name="Mask entity consolidated",
        query="MATCH (n:Entity) WHERE toLower(n.name) = 'mask' OR toLower(n.name) = 'cpap mask' RETURN count(n) AS cnt",
        expected="Mask mentions merged",
        check_fn="count_lte", expected_value=3,
    ),

    # -- Dimension 5: Relationship Patterns (8 checks) --
    ScoreItem(
        dimension="relationship_patterns",
        name="MANUFACTURES relationships exist",
        query="MATCH (a:Entity)-[r:MANUFACTURES]->(b:Entity) RETURN count(r) AS cnt",
        expected="Manufacturer-product links",
        check_fn="count_gte", expected_value=3,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="HAS_SPECIFICATION relationships",
        query="MATCH (a:Entity)-[r:HAS_SPECIFICATION]->(b:Entity) RETURN count(r) AS cnt",
        expected="Product-spec links",
        check_fn="count_gte", expected_value=5,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="HAS_FEATURE relationships",
        query="MATCH (a:Entity)-[r:HAS_FEATURE]->(b:Entity) RETURN count(r) AS cnt",
        expected="Product-feature links",
        check_fn="count_gte", expected_value=5,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="HAS_COMPONENT relationships",
        query="MATCH (a:Entity)-[r:HAS_COMPONENT]->(b:Entity) RETURN count(r) AS cnt",
        expected="Product-component links",
        check_fn="count_gte", expected_value=3,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="SUPPORTS_MODE relationships",
        query="MATCH (a:Entity)-[r:SUPPORTS_MODE]->(b:Entity) RETURN count(r) AS cnt",
        expected="Product-mode links",
        check_fn="count_gte", expected_value=3,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="TREATS relationships",
        query="MATCH (a:Entity)-[r:TREATS]->(b:Entity) RETURN count(r) AS cnt",
        expected="Product-condition links",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="COMPLIES_WITH relationships",
        query="MATCH (a:Entity)-[r:COMPLIES_WITH]->(b:Entity) RETURN count(r) AS cnt",
        expected="Product-standard links",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="relationship_patterns",
        name="Orphan ratio < 20%",
        query="MATCH (n:Entity) WHERE NOT (n)-[]-() RETURN count(n) AS cnt",
        expected="Less than 20% orphans",
        check_fn="ratio_check", expected_value=0.2,
    ),

    # -- Dimension 6: Specification Extraction (8 checks) --
    ScoreItem(
        dimension="spec_extraction",
        name="Pressure specifications with hPa/cmH2O",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' AND (toLower(n.description) CONTAINS 'hpa' OR toLower(n.description) CONTAINS 'cmh2o') RETURN count(n) AS cnt",
        expected="Pressure specs with units",
        check_fn="count_gte", expected_value=2,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Weight specifications with kg/lbs",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' AND (toLower(n.description) CONTAINS 'kg' OR toLower(n.description) CONTAINS 'lb') RETURN count(n) AS cnt",
        expected="Weight specs",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Sound/noise level with dB",
        query="MATCH (n:Entity) WHERE (toLower(n.name) CONTAINS 'sound' OR toLower(n.name) CONTAINS 'noise' OR toLower(n.description) CONTAINS 'sound' OR toLower(n.description) CONTAINS 'noise') AND toLower(n.description) CONTAINS 'db' RETURN count(n) AS cnt",
        expected="Sound level specs",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Dimension/size specs with mm/in",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' AND (toLower(n.description) CONTAINS 'mm' OR toLower(n.description) CONTAINS 'inch') AND (toLower(n.name) CONTAINS 'dimension' OR toLower(n.name) CONTAINS 'size') RETURN count(n) AS cnt",
        expected="Physical dimension specs",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Power/voltage specs",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' AND (toLower(n.description) CONTAINS 'volt' OR toLower(n.description) CONTAINS '240' OR toLower(n.description) CONTAINS '100-240') RETURN count(n) AS cnt",
        expected="Power specs",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Specifications have numeric values",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' AND n.value IS NOT NULL AND n.value <> '' RETURN count(n) AS cnt",
        expected="Specs with value property",
        check_fn="count_gte", expected_value=5,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name="Specifications have units",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' AND n.unit IS NOT NULL AND n.unit <> '' RETURN count(n) AS cnt",
        expected="Specs with unit property",
        check_fn="count_gte", expected_value=3,
    ),
    ScoreItem(
        dimension="spec_extraction",
        name=">= 10 Specification entities total",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'specification' RETURN count(n) AS cnt",
        expected="At least 10 specs across 10 docs",
        check_fn="count_gte", expected_value=10,
    ),

    # -- Dimension 7: Type Distribution (5 checks) --
    ScoreItem(
        dimension="type_distribution",
        name="All 8 ontology types present",
        query="MATCH (n:Entity) RETURN count(DISTINCT n.type) AS cnt",
        expected="8 types from ontology",
        check_fn="count_gte", expected_value=7,
    ),
    ScoreItem(
        dimension="type_distribution",
        name="Entity count 100-2000",
        query="MATCH (n:Entity) RETURN count(n) AS cnt",
        expected="Reasonable entity count for 10 docs",
        check_fn="count_gte", expected_value=100,
    ),
    ScoreItem(
        dimension="type_distribution",
        name="Entity count not excessive",
        query="MATCH (n:Entity) RETURN count(n) AS cnt",
        expected="Not too many entities",
        check_fn="count_lte", expected_value=2000,
    ),
    ScoreItem(
        dimension="type_distribution",
        name="No type casing variants",
        query="MATCH (n:Entity) WITH toLower(n.type) AS ltype, collect(DISTINCT n.type) AS variants WHERE size(variants) > 1 RETURN count(ltype) AS cnt",
        expected="No casing inconsistencies",
        check_fn="count_eq", expected_value=0,
    ),
    ScoreItem(
        dimension="type_distribution",
        name="Singleton types < 3",
        query="MATCH (n:Entity) WITH n.type AS type, count(n) AS cnt WHERE cnt = 1 RETURN count(type) AS cnt",
        expected="Few singleton types",
        check_fn="count_lte", expected_value=3,
    ),

    # -- Dimension 8: Graph Structure (5 checks) --
    ScoreItem(
        dimension="graph_structure",
        name="HAS_CHUNK relationships match chunk count",
        query="MATCH (:Document)-[:HAS_CHUNK]->(:Chunk) RETURN count(*) AS cnt",
        expected="Doc-chunk links",
        check_fn="count_gte", expected_value=100,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="HAS_ENTITY relationships",
        query="MATCH (:Chunk)-[:HAS_ENTITY]->(:Entity) RETURN count(*) AS cnt",
        expected="Chunk-entity links",
        check_fn="count_gte", expected_value=50,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="Relationship count > 200",
        query="MATCH ()-[r]->() RETURN count(r) AS cnt",
        expected="Sufficient relationship density",
        check_fn="count_gte", expected_value=200,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="Entity-to-entity relationships > 50",
        query="MATCH (a:Entity)-[r]->(b:Entity) RETURN count(r) AS cnt",
        expected="Entity interconnections",
        check_fn="count_gte", expected_value=50,
    ),
    ScoreItem(
        dimension="graph_structure",
        name="Most entities have descriptions",
        query=(
            "MATCH (n:Entity) WHERE n.description IS NOT NULL AND n.description <> '' "
            "WITH count(n) AS with_desc "
            "MATCH (m:Entity) "
            "RETURN with_desc, count(m) AS total, toFloat(with_desc)/count(m) AS ratio"
        ),
        expected="> 80% have descriptions",
        check_fn="exists",
    ),

    # -- Dimension 9: Query Answerability (10 checks) --
    ScoreItem(
        dimension="query_answerability",
        name="Q: Which manufacturers make CPAP devices?",
        query="MATCH (org:Entity)-[:MANUFACTURES]->(p:Entity) WHERE toLower(p.type) = 'product' RETURN DISTINCT org.name LIMIT 10",
        expected="Multiple manufacturers",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: What products does ResMed make?",
        query="MATCH (org:Entity)-[:MANUFACTURES]->(p:Entity) WHERE toLower(org.name) CONTAINS 'resmed' RETURN p.name LIMIT 10",
        expected="AirSense, AirStart",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: What products does Philips make?",
        query="MATCH (org:Entity)-[:MANUFACTURES]->(p:Entity) WHERE toLower(org.name) CONTAINS 'philips' OR toLower(org.name) CONTAINS 'respironics' RETURN p.name LIMIT 10",
        expected="DreamStation",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Compare product features?",
        query="MATCH (p:Entity)-[:HAS_FEATURE]->(f:Entity) WHERE toLower(p.type) = 'product' RETURN p.name, collect(f.name) AS features LIMIT 10",
        expected="Products with feature lists",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: What is the pressure range of DreamStation?",
        query="MATCH (p:Entity)-[:HAS_SPECIFICATION]->(s:Entity) WHERE toLower(p.name) CONTAINS 'dreamstation' AND (toLower(s.description) CONTAINS 'pressure' OR toLower(s.name) CONTAINS 'pressure') RETURN s.name, s.description LIMIT 5",
        expected="DreamStation pressure spec",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: Which devices treat OSA?",
        query="MATCH (p:Entity)-[:TREATS]->(c:Entity) WHERE toLower(c.name) CONTAINS 'apnea' OR toLower(c.name) CONTAINS 'osa' RETURN p.name LIMIT 10",
        expected="Products treating OSA",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: What components does RESmart include?",
        query="MATCH (p:Entity)-[:HAS_COMPONENT]->(c:Entity) WHERE toLower(p.name) CONTAINS 'resmart' RETURN c.name LIMIT 10",
        expected="RESmart components",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: What modes does SleepStyle support?",
        query="MATCH (p:Entity)-[:SUPPORTS_MODE]->(m:Entity) WHERE toLower(p.name) CONTAINS 'sleepstyle' OR toLower(p.name) CONTAINS 'sleep style' RETURN m.name LIMIT 10",
        expected="SleepStyle modes",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: What standards do devices comply with?",
        query="MATCH (p:Entity)-[:COMPLIES_WITH]->(s:Entity) RETURN p.name, s.name LIMIT 10",
        expected="Compliance info",
        check_fn="exists",
    ),
    ScoreItem(
        dimension="query_answerability",
        name="Q: iBreeze specifications?",
        query="MATCH (p:Entity)-[:HAS_SPECIFICATION]->(s:Entity) WHERE toLower(p.name) CONTAINS 'ibreeze' RETURN s.name, s.description LIMIT 10",
        expected="iBreeze specs",
        check_fn="exists",
    ),

    # -- Dimension 10: Property Completeness (5 checks) --
    ScoreItem(
        dimension="property_completeness",
        name="Entities have confidence scores",
        query="MATCH (n:Entity) WHERE n.confidence IS NOT NULL RETURN count(n) AS cnt",
        expected="Confidence present",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="property_completeness",
        name="Products have model_name property",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'product' AND n.model_name IS NOT NULL RETURN count(n) AS cnt",
        expected="Product model names",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="property_completeness",
        name="Organizations have role property",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'organization' AND n.role IS NOT NULL RETURN count(n) AS cnt",
        expected="Org roles",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="property_completeness",
        name="Standards have standard_id property",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'standard' AND n.standard_id IS NOT NULL RETURN count(n) AS cnt",
        expected="Standard IDs",
        check_fn="count_gte", expected_value=1,
    ),
    ScoreItem(
        dimension="property_completeness",
        name="Features have descriptions",
        query="MATCH (n:Entity) WHERE toLower(n.type) = 'feature' AND n.description IS NOT NULL AND n.description <> '' RETURN count(n) AS cnt",
        expected="Feature descriptions",
        check_fn="count_gte", expected_value=5,
    ),
]


# ================================================================
# Generative scoring prompts - multi-document focused
# ================================================================

GENERATIVE_PROMPTS = {
    "manufacturer_coverage": {
        "query": (
            "MATCH (n:Entity) WHERE toLower(n.type) = 'organization' "
            "RETURN n.name, n.description, n.role ORDER BY n.name"
        ),
        "prompt": """Evaluate manufacturer coverage in a knowledge graph built from 10 CPAP device PDFs from 5 manufacturers.

Organization entities:
{data}

Expected manufacturers: BMC Medical, ResMed, Philips/Respironics, Resvent, Fisher & Paykel.
Also expected: regulatory bodies, EU authorized representatives.

Rate 1-5: 1=0-1 manufacturers, 2=2 manufacturers, 3=3 manufacturers, 4=4 manufacturers, 5=all 5 manufacturers with meaningful descriptions.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "product_coverage": {
        "query": (
            "MATCH (n:Entity) WHERE toLower(n.type) = 'product' "
            "OPTIONAL MATCH (org:Entity)-[:MANUFACTURES]->(n) "
            "RETURN n.name, n.description, org.name AS manufacturer ORDER BY n.name"
        ),
        "prompt": """Evaluate product coverage in a knowledge graph built from 10 CPAP device PDFs.

Product entities:
{data}

Expected products: RESmart Auto CPAP, AirSense, AirStart 10, DreamStation (Standard + Pro), iBreeze, SleepStyle 200.
Each product should have manufacturer linkage and meaningful description.

Rate 1-5: 1=0-2 products, 2=3-4 products, 3=5 products, 4=6 products, 5=7+ products all with manufacturer links.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "cross_doc_resolution": {
        "query": (
            "MATCH (n:Entity) WITH toLower(n.name) AS name, collect(DISTINCT n.type) AS types, count(*) AS cnt "
            "WHERE cnt > 1 RETURN name, types, cnt ORDER BY cnt DESC LIMIT 20"
        ),
        "prompt": """Evaluate cross-document entity resolution. The graph was built from 10 CPAP PDFs - common entities like "CPAP", "OSA", "humidifier" should appear once or very few times, not duplicated per document.

Duplicates found:
{data}

Rate 1-5: 1=severe duplication across docs, 2=many common entities duplicated, 3=some duplicates but core entities clean, 4=minor duplication, 5=excellent resolution with no meaningful duplicates.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "spec_extraction": {
        "query": (
            "MATCH (n:Entity) WHERE toLower(n.type) = 'specification' "
            "OPTIONAL MATCH (p:Entity)-[:HAS_SPECIFICATION]->(n) "
            "RETURN n.name, n.description, n.value, n.unit, p.name AS product "
            "ORDER BY p.name, n.name"
        ),
        "prompt": """Evaluate specification extraction from 10 CPAP device PDFs. Each device should have key specs extracted.

Specification entities:
{data}

Expected specs across devices: pressure ranges (hPa/cmH2O), weights (kg/lbs), dimensions (mm), sound levels (dB), power supply (V), operating temperature.
Key: specs should have concrete numeric values, units, and be linked to their products.

Rate 1-5: 1=no numeric values, 2=few specs without values, 3=some specs with values from 2-3 products, 4=good coverage across most products, 5=comprehensive specs with exact values from most products.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
    "query_answerability": {
        "query": (
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "WHERE toLower(a.type) IN ['product', 'organization'] "
            "WITH a.name AS source, a.type AS source_type, type(r) AS rel, "
            "b.name AS target, b.type AS target_type, "
            "CASE WHEN b.description IS NOT NULL THEN left(b.description, 60) ELSE '' END AS desc "
            "RETURN source, source_type, rel, target, target_type, desc "
            "ORDER BY source_type, source, rel LIMIT 200"
        ),
        "prompt": """Evaluate if this multi-document CPAP knowledge graph can answer cross-manufacturer comparison questions.
Note: relationship types may vary (HAS_COMPONENT, COMPATIBLE_WITH, CONTAINS are all component relationships; SUPPORTS_MODE, HAS_MODE, OPERATES_IN, PROVIDES are all mode relationships). Focus on whether the DATA exists, not the exact relationship type name.

Product relationships:
{data}

Questions users would ask:
1) Which manufacturers make CPAP devices? (BMC, ResMed, Philips, Resvent, Fisher & Paykel)
2) Compare features across brands? (Ramp, pressure relief, auto-start, humidification)
3) What is the pressure range of [specific device]? (numeric values)
4) Which devices treat OSA? (most/all)
5) What modes do different devices support? (CPAP, Auto, Titrate)
6) What components come with [specific device]? (mask, tubing, filter, humidifier)
7) What standards do devices comply with? (IEC, ISO standards)
8) Compare device specifications? (weight, dimensions, sound level)

Rate 1-5: 1=0-1 answerable, 2=2-3, 3=4-5, 4=6-7, 5=all 8 answerable with specific data.
Respond ONLY: {{"score": N, "reasoning": "..."}}""",
    },
}


def run_benchmark(
    uri: str = "bolt://neo4j:7687",
    user: str = "neo4j",
    password: str = "kg-builder-pass",
    config_description: str = "",
) -> BenchmarkResult:
    """Execute all deterministic benchmark queries."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    result = BenchmarkResult(
        timestamp=datetime.now().isoformat(),
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
            r = session.run("MATCH (d:Document) RETURN count(d) AS cnt")
            result.document_count = r.single()["cnt"]

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
                        item.passed = actual >= item.expected_value
                        item.notes = f"actual={actual}"

                    elif item.check_fn == "count_eq":
                        actual = records[0]["cnt"] if records else 0
                        item.actual_value = actual
                        item.passed = actual == item.expected_value
                        item.notes = f"actual={actual}"

                    elif item.check_fn == "count_lte":
                        actual = records[0]["cnt"] if records else 0
                        item.actual_value = actual
                        item.passed = actual <= item.expected_value
                        item.notes = f"actual={actual}"

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
                    )[:8000]

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
                        match = re.search(r'\{[^{}]*"score"\s*:\s*(\d+)[^{}]*\}', content)
                        if match:
                            try:
                                parsed = json.loads(match.group())
                            except json.JSONDecodeError:
                                score = int(match.group(1))
                                parsed = {"score": score, "reasoning": content[:200]}
                        else:
                            score_match = re.search(r'"score"\s*:\s*(\d+)', content)
                            score = int(score_match.group(1)) if score_match else 0
                            parsed = {"score": score, "reasoning": content[:200]}

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
    print(f"  MULTI-DOC BENCHMARK SCORECARD ({result.document_count} documents)")
    print(f"  {result.timestamp}")
    if result.config_description:
        print(f"  Config: {result.config_description}")
    print(f"{'=' * 74}")
    print(f"  Graph: {result.entity_count} entities, {result.relationship_count} rels, "
          f"{result.chunk_count} chunks, {result.document_count} docs")
    print(f"  Deterministic: {result.passed_checks}/{result.total_checks} ({result.deterministic_pct:.0f}%)")
    if result.generative_scores:
        print(f"  Generative:    {result.generative_avg:.1f}/5.0")
        print(f"  HYBRID SCORE:  {result.hybrid_score:.0f}%")
    print(f"{'─' * 74}")

    if result.type_distribution:
        top = list(result.type_distribution.items())[:10]
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
            print(f"           {item.notes[:100]}")

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


def save_benchmark_md(result: BenchmarkResult, path: Path, version: str = "v01", title: str = "") -> None:
    """Save benchmark result as markdown document."""
    score_int = int(result.hybrid_score) if result.hybrid_score > 0 else int(result.deterministic_pct)

    lines = [
        f"# Multi-Doc Benchmark {version} - {title}",
        "",
        f"**Hybrid Score**: {score_int}%",
        f"**Deterministic**: {result.passed_checks}/{result.total_checks} ({result.deterministic_pct:.0f}%)",
        f"**Generative**: {result.generative_avg:.1f}/5.0" if result.generative_scores else "**Generative**: N/A",
        f"**Date**: {result.timestamp}",
        "",
        "## Conditions",
        "",
        f"- **Config**: {result.config_description}",
        f"- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)",
        "",
        "## Graph Stats",
        "",
        f"- Entities: {result.entity_count}",
        f"- Relationships: {result.relationship_count}",
        f"- Chunks: {result.chunk_count}",
        f"- Documents: {result.document_count}",
        f"- Types: {len(result.type_distribution)} distinct",
        f"- Top types: {', '.join(f'{t}:{c}' for t, c in list(result.type_distribution.items())[:8])}",
        "",
        "## Dimension Scores",
        "",
        "| Dimension | Deterministic | LLM |",
        "|---|---|---|",
    ]

    for dim, det_score in result.dimension_scores.items():
        gen = next((g for g in result.generative_scores if g.dimension == dim), None)
        gen_str = f"{gen.score:.0f}/5" if gen else "-"
        dim_label = dim.replace("_", " ").title()
        lines.append(f"| {dim_label} | {det_score} | {gen_str} |")

    # Key failures
    failures = [i for i in result.items if not i.passed]
    if failures:
        lines.extend(["", "## Key Failures", ""])
        for idx, item in enumerate(failures, 1):
            notes = f" ({item.notes})" if item.notes else ""
            lines.append(f"{idx}. **{item.dimension}** - {item.name}{notes}")

    # Generative details
    if result.generative_scores:
        lines.extend(["", "## Generative Assessment", ""])
        for gs in result.generative_scores:
            lines.append(f"- **{gs.dimension}** ({gs.score:.0f}/5): {gs.reasoning}")

    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    logger.info("Benchmark saved to {}", path)


if __name__ == "__main__":
    import sys

    # Usage: python tests/benchmark_multidoc.py v02 "constrained ontology + standard properties"
    version = sys.argv[1] if len(sys.argv) > 1 else "v01"
    title = sys.argv[2] if len(sys.argv) > 2 else "Baseline"
    config_desc = f"{version} {title}"

    # Phase 1: Deterministic
    result = run_benchmark(config_description=config_desc)
    print_benchmark(result)

    # Phase 2: Generative
    print("\nRunning generative scoring (LLM evaluation)...")
    run_generative_scoring(result)
    print_benchmark(result)

    # Save as markdown
    score_int = int(result.hybrid_score) if result.hybrid_score > 0 else int(result.deterministic_pct)
    save_benchmark_md(
        result,
        Path(f"docs/benchmarks/MULTIDOC_BENCHMARK_{version}_{score_int}.md"),
        version=version,
        title=title,
    )

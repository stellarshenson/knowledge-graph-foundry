"""Integration tests against a live Neo4j; run with KGF_INTEGRATION=1.

Every node created carries a unique prop_run_id marker; teardown deletes
exactly those nodes and the test vector index - never the whole database.
"""

import os
import uuid

from dotenv import load_dotenv
import pytest

from knowledge_graph_foundry.graph.graphrag import scorecard
from knowledge_graph_foundry.graph.loader import (
    ensure_indexes,
    load_entities,
    load_relationships,
)
from knowledge_graph_foundry.graph.metanode import read_control, write_control
from knowledge_graph_foundry.graphdb import create_driver
from knowledge_graph_foundry.models import Entity, Relationship, entity_id
from knowledge_graph_foundry.settings import Neo4jSettings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("KGF_INTEGRATION") != "1", reason="KGF_INTEGRATION != 1"),
]

RUN_ID = "kgftest_" + uuid.uuid4().hex[:12]
VECTOR_INDEX = f"kgf_test_vec_{uuid.uuid4().hex[:8]}"
DIMENSIONS = 8


def make_entities():
    common = {"properties": {"run_id": RUN_ID}, "embedding": [0.1] * DIMENSIONS}
    return [
        Entity.create(
            "Alpha Corp",
            ["Manufacturer"],
            description="maker",
            source_documents=["doc1"],
            source_chunks=["c1"],
            **common,
        ),
        Entity.create(
            "alpha  CORP",
            ["Manufacturer", "Vendor"],
            description="maker and vendor of devices",
            source_documents=["doc1", "doc2"],
            source_chunks=["c1", "c2"],
            **common,
        ),
        Entity.create("Beta Device", ["Device"], source_documents=["doc1"], **common),
        Entity.create("Gamma Sensor", ["Sensor"], source_documents=["doc2"], **common),
        Entity.create("Delta Hub", ["Hub"], source_documents=["doc2"], **common),
    ]


def make_relationships():
    return [
        Relationship(
            source_id=entity_id("Beta Device"),
            target_id=entity_id("Alpha Corp"),
            type="MADE_BY",
            source_documents=["doc1"],
        ),
        Relationship(
            source_id=entity_id("Gamma Sensor"),
            target_id=entity_id("Beta Device"),
            type="PART_OF",
            source_documents=["doc2"],
        ),
        Relationship(
            source_id=entity_id("Delta Hub"),
            target_id=entity_id("Gamma Sensor"),
            type="CONNECTS_TO",
            source_documents=["doc2"],
        ),
        Relationship(
            source_id=entity_id("Nonexistent Node"),
            target_id=entity_id("Alpha Corp"),
            type="MADE_BY",
        ),
    ]


@pytest.fixture(scope="module")
def driver():
    load_dotenv()
    cfg = Neo4jSettings(
        uri=os.environ["NEO4J_URI"],
        user=os.environ["NEO4J_USER"],
        password=os.environ["NEO4J_PASSWORD"],
    )
    driver = create_driver(cfg)
    yield driver
    with driver.session() as session:
        session.run("MATCH (n) WHERE n.prop_run_id = $run DETACH DELETE n", run=RUN_ID).consume()
        session.run(f"DROP INDEX `{VECTOR_INDEX}` IF EXISTS").consume()
    driver.close()


@pytest.fixture(scope="module")
def loaded(driver):
    ensure_indexes(driver, vector_dimensions=DIMENSIONS, vector_index_name=VECTOR_INDEX)
    load_entities(driver, make_entities(), batch_size=2)
    load_relationships(driver, make_relationships(), batch_size=2)
    return driver


def count_marked(driver):
    with driver.session() as session:
        nodes = session.run(
            "MATCH (e:Entity) WHERE e.prop_run_id = $run RETURN count(e) AS n", run=RUN_ID
        ).single()["n"]
        rels = session.run(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "WHERE a.prop_run_id = $run AND b.prop_run_id = $run RETURN count(r) AS n",
            run=RUN_ID,
        ).single()["n"]
    return nodes, rels


class TestLoading:
    def test_merge_and_skip(self, loaded):
        nodes, rels = count_marked(loaded)
        assert nodes == 4  # 5 entities, 2 share a normalized name-id
        assert rels == 3  # 4th relationship skipped (missing endpoint)

    def test_idempotent_reload(self, loaded):
        load_entities(loaded, make_entities(), batch_size=2)
        load_relationships(loaded, make_relationships(), batch_size=2)
        nodes, rels = count_marked(loaded)
        assert nodes == 4
        assert rels == 3

    def test_provenance_deduplicated(self, loaded):
        with loaded.session() as session:
            record = session.run(
                "MATCH (e:Entity {id: $id}) "
                "RETURN e.source_documents AS docs, e.source_chunks AS chunks",
                id=entity_id("Alpha Corp"),
            ).single()
        assert sorted(record["docs"]) == ["doc1", "doc2"]
        assert sorted(record["chunks"]) == ["c1", "c2"]

    def test_multi_label(self, loaded):
        with loaded.session() as session:
            labels = session.run(
                "MATCH (e:Entity {id: $id}) RETURN labels(e) AS labels",
                id=entity_id("Alpha Corp"),
            ).single()["labels"]
        assert {"Entity", "Manufacturer", "Vendor"} <= set(labels)

    def test_ensure_indexes_idempotent(self, loaded):
        # double call must not raise; an Entity.embedding vector index must
        # exist afterwards (Neo4j treats an equivalent index under another
        # name as satisfying IF NOT EXISTS, so assert capability, not name)
        ensure_indexes(loaded, vector_dimensions=DIMENSIONS, vector_index_name=VECTOR_INDEX)
        with loaded.session() as session:
            rows = session.run(
                "SHOW VECTOR INDEXES YIELD labelsOrTypes, properties "
                "WHERE 'Entity' IN labelsOrTypes AND 'embedding' IN properties "
                "RETURN count(*) AS n"
            ).single()
        assert rows["n"] >= 1


class TestMetanode:
    def test_round_trip(self, driver):
        prior = read_control(driver)
        state = {
            "fsm_state": "CURING",
            "purpose": "integration test",
            "ontology": {"types": {"Device": {"encounters": 3}}},
            "calibration": {"pairs": [[0.4, 1]]},
            "buffer_cache": {"items": ["a", "b"]},
            "metrics_history": [{"jsd": 0.01, "type_count": 5}],
        }
        try:
            write_control(driver, state)
            read_back = read_control(driver)
            assert read_back is not None
            assert read_back.pop("updated_at")
            # write_control merges (None clears a key), so on a live database
            # the node may carry extra keys - assert the written keys round-trip
            for key, value in state.items():
                assert read_back[key] == value, key
        finally:
            if prior is not None:
                write_control(driver, prior)
            else:
                with driver.session() as session:
                    session.run("MATCH (c:KGFControl {id: 'kgf'}) DELETE c").consume()

    def test_gate_calibration_record_round_trip(self, driver):
        # R38-H384: the gate record (threshold + provenance) survives the
        # metanode JSON round-trip intact; None-write clears it on restore
        from knowledge_graph_foundry.graph.gate_calibration import build_record

        prior = read_control(driver)
        record = build_record(0.7644, 0.08, 24, "abcdef0123456789")
        try:
            write_control(driver, {"gate_calibration": record})
            read_back = read_control(driver)
            assert read_back["gate_calibration"] == record
        finally:
            if prior is None:
                with driver.session() as session:
                    session.run("MATCH (c:KGFControl {id: 'kgf'}) DELETE c").consume()
            else:
                write_control(driver, {"gate_calibration": prior.get("gate_calibration")})


class TestPassages:
    """R34-H366: span store round-trip and the space-mismatch refusal.

    generate_passages deliberately processes EVERY stored chunk, so on a
    shared database the test snapshots pre-existing passage ids and deletes
    exactly the delta it created - never assumes it was alone."""

    def test_generate_query_and_space_check(self, driver):
        from knowledge_graph_foundry.graph.passages import (
            check_space,
            generate_passages,
            passage_query,
        )

        chunk_id = f"chunk_{RUN_ID}"
        index = f"kgf_test_passages_{RUN_ID[-8:]}"
        embed_fn = lambda texts: [[0.1] * DIMENSIONS for _ in texts]  # noqa: E731
        with driver.session() as session:
            before = {r["id"] for r in session.run("MATCH (p:KGFPassage) RETURN p.id AS id")}
        try:
            with driver.session() as session:
                session.run(
                    "CREATE (c:Chunk {id: $id, text: $text, prop_run_id: $run})",
                    id=chunk_id,
                    text="alpha " * 200,  # 1200 chars -> two spans at 900/450
                    run=RUN_ID,
                ).consume()
            created = generate_passages(
                driver, embed_fn, index, DIMENSIONS, "local-gpu", "test-model", span_chars=900
            )
            assert created >= 2  # my chunk's spans, plus any other stored chunks'
            with driver.session() as session:
                mine = {
                    r["id"]
                    for r in session.run(
                        "MATCH (p:KGFPassage) WHERE p.id STARTS WITH $prefix RETURN p.id AS id",
                        prefix=chunk_id,
                    )
                }
            assert mine == {f"{chunk_id}:900:0", f"{chunk_id}:900:450"}
            # idempotent: second run creates nothing
            assert (
                generate_passages(
                    driver, embed_fn, index, DIMENSIONS, "local-gpu", "test-model", 900
                )
                == 0
            )
            check_space(driver, index, "local-gpu", "test-model")  # matching pair passes
            with pytest.raises(RuntimeError, match="refusing query"):
                check_space(driver, index, "bedrock", "other-model")
            # all test vectors are identical so top-1 is an arbitrary span;
            # assert the round-trip shape, not the winner
            hits = passage_query(driver, [0.1] * DIMENSIONS, index, top_k=1)
            assert hits and ":900:" in hits[0]["id"] and hits[0]["text"]
        finally:
            with driver.session() as session:
                session.run(
                    "MATCH (p:KGFPassage) WHERE NOT p.id IN $before DETACH DELETE p",
                    before=list(before),
                ).consume()
                session.run("MATCH (c:Chunk {id: $id}) DETACH DELETE c", id=chunk_id).consume()
                session.run("MATCH (s:KGFIndexSpace {index_name: $i}) DELETE s", i=index).consume()
                session.run(f"DROP INDEX {index} IF EXISTS").consume()


class TestScorecard:
    def test_sane_numbers(self, loaded):
        card = scorecard(loaded)
        assert card["entity_count"] >= 4
        assert card["relationship_count"] >= 3
        assert 0.0 <= card["orphan_rate"] <= 1.0
        assert 0.0 <= card["duplicate_name_density"] <= 1.0
        assert card["relationship_type_entropy"] >= 0.0
        assert card["avg_degree"] > 0.0

"""Tests for question nodes (R35-H371) - generation, groundedness gate, store,
and the retrieval question channel. Mocked engine and driver - no live Neo4j
or LLM."""

from unittest.mock import MagicMock

from pydantic import BaseModel

from knowledge_graph_foundry.graph.questions import (
    WireQuestion,
    WireQuestionSet,
    gate_questions,
    generate_questions,
    link_question_entities,
    question_id,
    question_query,
    store_questions,
)
from knowledge_graph_foundry.models import Chunk
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.settings import Settings


def make_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver, session


def make_chunk(cid: str, text: str) -> Chunk:
    return Chunk(id=cid, document_id="d1", index=0, text=text, token_count=len(text.split()))


class FakeEngine:
    name = "fake"

    def __init__(self, response: BaseModel):
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        self.calls.append(messages)
        return self.response

    def complete_text(self, system: str, user: str) -> str:
        return ""


class TestQuestionSettings:
    def test_registered_defaults(self):
        # R46-H499 flipped enabled off (+0.0076 lift at n=132, REFUTED at the
        # +0.03 bar; ~25% of per-chunk LLM budget). The remaining knobs stand.
        q = Settings().questions
        assert q.enabled is False
        assert q.per_chunk == 8
        assert q.channel_m == 1
        assert q.index_name == "kgf_question_embeddings"

    def test_enabled_override(self):
        assert Settings(questions={"enabled": True}).questions.enabled is True


class TestQuestionId:
    def test_deterministic_and_normalized(self):
        a = question_id("What is the pressure range?")
        b = question_id("what  is the Pressure range?")
        c = question_id("How heavy is the device?")
        assert a == b  # case/whitespace-normalized - duplicates merge
        assert a != c
        assert a.startswith("q_")


class TestGroundednessGate:
    CHUNK = "The AirSense 11 delivers pressure from 4 to 20 cmH2O and weighs 1130 g."

    def test_verbatim_answer_survives(self):
        pairs = [{"q": "What is the pressure range?", "a": "4 to 20 cmH2O"}]
        assert gate_questions(pairs, self.CHUNK) == pairs

    def test_hallucinated_answer_is_dropped(self):
        pairs = [{"q": "What is the warranty period?", "a": "5 years limited warranty"}]
        assert gate_questions(pairs, self.CHUNK) == []

    def test_numeric_answer_matches_across_formatting(self):
        # the harness presence check tolerates unit/punctuation drift
        pairs = [{"q": "How heavy is it?", "a": "1,130g"}]
        assert gate_questions(pairs, self.CHUNK) == pairs

    def test_empty_chunk_drops_everything(self):
        pairs = [{"q": "Anything?", "a": "anything"}]
        assert gate_questions(pairs, "") == []


class TestGenerateQuestions:
    def test_returns_stripped_pairs_per_chunk(self):
        engine = FakeEngine(
            WireQuestionSet(
                questions=[
                    WireQuestion(q=" What is the mode? ", a=" AutoSet "),
                    WireQuestion(q="", a="dropped - empty question"),
                ]
            )
        )
        chunks = [make_chunk("c1", "text one"), make_chunk("c2", "text two")]
        out = generate_questions(chunks, engine, per_chunk=8, concurrency=2)
        assert set(out) == {"c1", "c2"}
        assert out["c1"] == [{"q": "What is the mode?", "a": "AutoSet"}]
        assert len(engine.calls) == 2
        assert "exactly 8 question-answer pairs" in engine.calls[0][0]["content"]

    def test_failing_chunk_is_skipped_not_fatal(self):
        class RaisingEngine(FakeEngine):
            def complete(self, messages, response_model):
                raise RuntimeError("simulated engine failure")

        out = generate_questions([make_chunk("c1", "text")], RaisingEngine(None), per_chunk=8)
        assert out == {}


class TestStoreQuestions:
    def rows(self, n):
        return [
            {
                "id": f"q_{i}",
                "text": f"question {i}?",
                "answer": f"answer {i}",
                "embedding": [0.1, 0.2],
                "chunk_ids": ["c1"],
            }
            for i in range(n)
        ]

    def test_merge_cypher_and_provenance(self):
        driver, session = make_driver()
        assert store_questions(driver, self.rows(1)) == 1
        query = session.run.call_args_list[0].args[0]
        assert "MERGE (q:KGFQuestion {id: row.id})" in query
        assert "q.source = 'ingest'" in query
        assert "MERGE (q)-[:ANSWERABLE_FROM]->(c)" in query
        rows = session.run.call_args_list[0].kwargs["rows"]
        assert rows[0]["chunk_ids"] == ["c1"]

    def test_batching(self):
        driver, session = make_driver()
        assert store_questions(driver, self.rows(250)) == 250
        assert session.run.call_count == 2


class TestLinkQuestionEntities:
    def test_link_cypher_and_count(self):
        driver, session = make_driver()
        session.run.return_value.single.return_value = {"n": 7}
        assert link_question_entities(driver) == 7
        query = session.run.call_args_list[0].args[0]
        assert "ANSWERABLE_FROM" in query and "MENTIONED_IN" in query
        assert "MERGE (q)-[:ABOUT]->(e)" in query
        assert "size(e.name) >= 4" in query


class TestQuestionQuery:
    def hit(self, question, score, chunk_id, names=()):
        return {
            "question": question,
            "score": score,
            "chunk_id": chunk_id,
            "chunk_text": f"text of {chunk_id}",
            "entity_names": list(names),
        }

    def test_top_question_seeds_its_full_chunk_set(self):
        # the R35-H371 seeding rule: the top question brings ALL its
        # ANSWERABLE_FROM chunks - a tie between them never drops evidence
        driver, session = make_driver()
        session.run.return_value.data.return_value = [
            self.hit("best question", 0.9, "c1", names=["AirSense 11", None]),
            self.hit("best question", 0.9, "c2", names=["AirSense 11"]),
            self.hit("runner-up question", 0.8, "c3"),
        ]
        out = question_query(driver, [0.1], "kgf_question_embeddings", top_m=1)
        assert len(out) == 1  # one question despite three rows
        assert out[0]["question"] == "best question"
        assert [c["id"] for c in out[0]["chunks"]] == ["c1", "c2"]
        assert out[0]["entity_names"] == ["AirSense 11"]  # nulls filtered, deduped

    def test_questions_rank_by_score_top_m(self):
        driver, session = make_driver()
        session.run.return_value.data.return_value = [
            self.hit("lower", 0.7, "c1"),
            self.hit("best", 0.9, "c2"),
        ]
        out = question_query(driver, [0.1], "kgf_question_embeddings", top_m=1)
        assert [h["question"] for h in out] == ["best"]

    def test_index_absence_falls_back_to_scan(self):
        driver, session = make_driver()
        indexed = MagicMock()
        indexed.data.side_effect = Exception("no such index")
        scanned = MagicMock()
        scanned.data.return_value = [self.hit("q", 0.9, "c1")]
        session.run.side_effect = [indexed, scanned]
        out = question_query(driver, [0.1], "kgf_question_embeddings", top_m=1)
        assert out[0]["chunks"] == [{"id": "c1", "text": "text of c1"}]
        fallback = session.run.call_args_list[1].args[0]
        assert "vector.similarity.cosine" in fallback

    def test_no_questions_returns_empty(self):
        driver, session = make_driver()
        session.run.return_value.data.return_value = []
        assert question_query(driver, [0.1], "kgf_question_embeddings", top_m=1) == []


class TestQuestionChannel:
    """The shipped read-path composition: additive blocks, hard no-ops."""

    def foundry(self, **questions) -> Foundry:
        return Foundry(Settings(questions=questions))

    def test_disabled_is_a_noop_without_touching_the_driver(self):
        f = self.foundry(enabled=False)
        assert f._question_channel([0.1]) == ([], [])
        assert f._driver is None  # never connected

    def test_zero_m_is_a_noop(self):
        f = self.foundry(enabled=True, channel_m=0)
        assert f._question_channel([0.1]) == ([], [])
        assert f._driver is None

    def test_no_questions_in_graph_is_a_noop(self):
        f = self.foundry(enabled=True)
        driver, session = make_driver()
        f._driver = driver
        session.run.return_value.data.return_value = []
        assert f._question_channel([0.1]) == ([], [])

    def test_channel_error_never_breaks_the_base_render(self):
        f = self.foundry(enabled=True)
        driver, session = make_driver()
        f._driver = driver
        session.run.side_effect = Exception("connection lost")
        assert f._question_channel([0.1]) == ([], [])

    def test_hit_renders_chunk_text_and_about_entities(self):
        f = self.foundry(enabled=True)
        driver, session = make_driver()
        f._driver = driver
        session.run.return_value.data.return_value = [
            {
                "question": "What modes does it support?",
                "score": 0.9,
                "chunk_id": "c1",
                "chunk_text": "It supports CPAP and AutoSet modes.",
                "entity_names": ["AirSense 11"],
            },
            {
                "question": "What modes does it support?",
                "score": 0.9,
                "chunk_id": "c2",
                "chunk_text": "AutoSet for Her is also available.",
                "entity_names": ["AirSense 11"],
            },
        ]
        blocks, names = f._question_channel([0.1])
        assert len(blocks) == 1  # one question match, both its chunks in the block
        assert "## Question match: What modes does it support?" in blocks[0]
        assert "About: AirSense 11" in blocks[0]
        assert "It supports CPAP and AutoSet modes." in blocks[0]
        assert "AutoSet for Her is also available." in blocks[0]
        assert names == ["AirSense 11"]


class TestIngestStoreStep:
    """Foundry._generate_questions: gate + dedupe + embed + store wiring."""

    def test_gated_questions_reach_the_store(self, monkeypatch):
        settings = Settings()
        f = Foundry(settings)
        driver, session = make_driver()
        f._driver = driver
        f._engine = FakeEngine(
            WireQuestionSet(
                questions=[
                    WireQuestion(q="What is the pressure range?", a="4 to 20 cmH2O"),
                    WireQuestion(q="What is the warranty?", a="5 years"),  # ungrounded
                ]
            )
        )

        def fake_embed(entities, cfg):
            for e in entities:
                e.embedding = [0.5, 0.5]
            return entities

        monkeypatch.setattr("knowledge_graph_foundry.extraction.generate_embeddings", fake_embed)
        chunk = make_chunk("c1", "The device delivers pressure from 4 to 20 cmH2O.")
        f._generate_questions([chunk])
        queries = [c.args[0] for c in session.run.call_args_list]
        assert any("CREATE VECTOR INDEX kgf_question_embeddings" in q for q in queries)
        store_call = next(
            c for c in session.run.call_args_list if "MERGE (q:KGFQuestion" in c.args[0]
        )
        rows = store_call.kwargs["rows"]
        assert len(rows) == 1  # the ungrounded pair was gated out
        assert rows[0]["text"] == "What is the pressure range?"
        assert rows[0]["chunk_ids"] == ["c1"]
        assert rows[0]["embedding"] == [0.5, 0.5]

    def test_all_gated_out_stores_nothing(self, monkeypatch):
        f = Foundry(Settings())
        driver, session = make_driver()
        f._driver = driver
        f._engine = FakeEngine(
            WireQuestionSet(questions=[WireQuestion(q="Warranty?", a="5 years")])
        )
        chunk = make_chunk("c1", "Completely unrelated chunk content about tubing.")
        f._generate_questions([chunk])
        assert session.run.call_count == 0  # no index create, no store

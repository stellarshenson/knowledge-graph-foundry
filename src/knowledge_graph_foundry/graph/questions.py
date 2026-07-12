"""Question nodes (R35-H371) - expectation questions as first-class retrieval
targets.

Doc2Query's measured lesson, confirmed on the DEF-14 parity instrument: the
gap between a user question and the graph's vocabulary closes when the graph
carries the questions each chunk can answer. At ingest a fixed count of
question-answer pairs is generated per chunk on the extraction engine, gated
on groundedness (Doc2Query-- clause: the generated answer must be present in
the source chunk - an ungrounded pair is a hallucination and is dropped),
deduplicated by normalized text, embedded in the live query space and stored
as KGFQuestion nodes with ANSWERABLE_FROM (chunk) and ABOUT (entity) edges.
Retrieval seeds the render from the top-M question matches (M=1 + base entity
channel: mean recall 1.0, 24/24, zero regressions - R35-H371 CONFIRMED).

Question ids hash the normalized question text, making the store idempotent
and merging the same question generated from several chunks.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import Chunk

_BATCH = 200
_PROMPT_TEXT_CAP = 8000  # chunk text fed to the generation prompt

_PROMPT = (
    "You write retrieval-training questions. From the passage below, generate "
    "exactly {n} question-answer pairs. Each question must be fully answerable "
    "from the passage alone and phrased the way a user would ask it (do not "
    'say "the passage" or "the document"). Each answer must be a short span '
    "or value taken verbatim from the passage."
)


class WireQuestion(BaseModel):
    """Question-answer pair as the LLM returns it."""

    q: str
    a: str


class WireQuestionSet(BaseModel):
    questions: list[WireQuestion] = Field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.casefold())


_UNIT = r"(?<=\d)\s*(mm|cm|dba|db\(a\)|db|kg|g|oz|ml|l|w|hz|mins|min|m)\b"


def answer_present(answer: str, ctx: str) -> bool:
    """The groundedness gate - the harness's own presence check (h158
    convention): verbatim containment, then a unit/punctuation-squashed
    numeric skeleton, then majority of numeric tokens, then a 60% word-set
    overlap. ``ctx`` must already be ``_norm``-ed."""
    ng = _norm(answer)
    if ng in ctx:
        return True
    squashed = re.sub(r"[\s,()]", "", ctx)
    skeleton = re.sub(r"[\s,()]", "", re.sub(_UNIT, "", ng))
    if any(c.isdigit() for c in skeleton) and len(skeleton) >= 5 and skeleton in squashed:
        return True
    toks = re.findall(r"[\w.\-/]*\d[\w.\-/]*", answer)
    if toks:
        hit = sum(
            1 for t in toks if _norm(t) in ctx or re.sub(r"[\s,()]", "", _norm(t)) in squashed
        )
        return hit >= max(1, len(toks) // 2 + (len(toks) % 2))
    words = set(re.findall(r"[a-z][a-z0-9\-]{2,}", ng))
    cw = set(re.findall(r"[a-z][a-z0-9\-]{2,}", ctx))
    return bool(words) and len(words & cw) / len(words) >= 0.6


def question_id(text: str) -> str:
    """Content-keyed id over the NORMALIZED question text - the same question
    generated from several chunks merges into one node."""
    return "q_" + hashlib.sha256(_norm(text).encode()).hexdigest()[:16]


def generate_questions(
    chunks: list[Chunk], engine: Engine, per_chunk: int, concurrency: int = 4
) -> dict[str, list[dict[str, str]]]:
    """Generate the fixed-count question-answer pairs for every chunk in
    parallel; failing chunks are skipped with a warning (retriable on
    re-ingest). Returns chunk id -> [{"q": ..., "a": ...}]."""
    results: dict[str, list[dict[str, str]]] = {}

    def _run(chunk: Chunk) -> None:
        try:
            wire = engine.complete(
                [
                    {"role": "system", "content": _PROMPT.format(n=per_chunk)},
                    {"role": "user", "content": f"PASSAGE:\n{chunk.text[:_PROMPT_TEXT_CAP]}"},
                ],
                WireQuestionSet,
            )
            results[chunk.id] = [
                {"q": w.q.strip(), "a": w.a.strip()} for w in wire.questions if w.q and w.a
            ]
        except Exception as exc:
            emit("extraction.warning", reason=f"question generation failed: {exc}", chunk=chunk.id)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for chunk in chunks:
            pool.submit(_run, chunk)

    return results


def gate_questions(pairs: list[dict[str, str]], chunk_text: str) -> list[dict[str, str]]:
    """Doc2Query-- clause: keep only pairs whose generated answer is present
    in the source chunk - an ungrounded (hallucinated) pair fails."""
    ctx = _norm(chunk_text or "")
    return [p for p in pairs if ctx and answer_present(p["a"], ctx)]


def ensure_question_index(driver, dimensions: int, index_name: str) -> None:
    with driver.session() as session:
        session.run(
            f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
            "FOR (q:KGFQuestion) ON (q.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: $dims, "
            "`vector.similarity_function`: 'cosine'}}",
            dims=dimensions,
        ).consume()


def store_questions(driver, records: list[dict[str, Any]]) -> int:
    """Store gated questions as KGFQuestion nodes with ANSWERABLE_FROM edges
    to their source chunks. ``records`` rows carry id, text, answer, embedding
    and chunk_ids. Idempotent: MERGE on the content-keyed id; a question
    re-generated from another chunk unions its chunk set."""
    stored = 0
    with driver.session() as session:
        for offset in range(0, len(records), _BATCH):
            batch = records[offset : offset + _BATCH]
            session.run(
                "UNWIND $rows AS row "
                "MERGE (q:KGFQuestion {id: row.id}) "
                "ON CREATE SET q.text = row.text, q.answer = row.answer, "
                "q.embedding = row.embedding, q.source = 'ingest', "
                "q.created_at = timestamp() "
                "WITH q, row UNWIND row.chunk_ids AS cid "
                "MATCH (c:Chunk {id: cid}) "
                "MERGE (q)-[:ANSWERABLE_FROM]->(c)",
                rows=[
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "answer": r["answer"],
                        "embedding": r["embedding"],
                        "chunk_ids": r["chunk_ids"],
                    }
                    for r in batch
                ],
            ).consume()
            stored += len(batch)
    emit("questions.stored", stored=stored)
    return stored


def link_question_entities(driver) -> int:
    """ABOUT edges: link every question to the entities its source chunk
    mentions whose name appears in the question or its answer (the R35-H371
    linkage rule; names under 4 chars false-match inside words). Idempotent
    MERGE - runs after entity loading so a global pass catches questions
    stored before their entities reached the graph."""
    with driver.session() as session:
        record = session.run(
            "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(c:Chunk)<-[:MENTIONED_IN]-(e:Entity) "
            "WHERE size(e.name) >= 4 AND (toLower(q.text) CONTAINS toLower(e.name) "
            "OR toLower(q.answer) CONTAINS toLower(e.name)) "
            "WITH q, e LIMIT 100000 "
            "MERGE (q)-[:ABOUT]->(e) "
            "RETURN count(*) AS n"
        ).single()
    linked = record["n"] if record else 0
    emit("questions.linked", about_edges=linked)
    return linked


_QUESTION_HITS = (
    "MATCH (q)-[:ANSWERABLE_FROM]->(c:Chunk) "
    "OPTIONAL MATCH (q)-[:ABOUT]->(e:Entity) "
    "RETURN q.text AS question, score, c.id AS chunk_id, c.text AS chunk_text, "
    "collect(DISTINCT e.name) AS entity_names"
)


def question_query(driver, embedding: list[float], index_name: str, top_m: int) -> list[dict]:
    """Top-M question matches for the channel: questions match the query in
    the shared embedding space; each of the top-M questions seeds its FULL
    ANSWERABLE_FROM chunk set (the R35-H371 seeding rule - a question grounded
    in several chunks brings them all, so a score tie between its chunks can
    never drop the evidence-bearing one). Over-fetches since a question maps
    to several rows. Falls back to an exhaustive cosine scan when the vector
    index is absent (a pile carrying question nodes written without the index
    stays readable); no questions -> []."""
    fetch = max(top_m * 4, 8)
    with driver.session() as session:
        try:
            rows = session.run(
                "CALL db.index.vector.queryNodes($index, $k, $embedding) "
                "YIELD node AS q, score " + _QUESTION_HITS,
                index=index_name,
                k=fetch,
                embedding=embedding,
            ).data()
        except Exception:
            rows = session.run(
                "MATCH (q:KGFQuestion) WHERE q.embedding IS NOT NULL "
                "WITH q, vector.similarity.cosine(q.embedding, $embedding) AS score "
                "ORDER BY score DESC LIMIT $k " + _QUESTION_HITS,
                k=fetch,
                embedding=embedding,
            ).data()
    hits: dict[str, dict] = {}
    for row in rows:
        hit = hits.setdefault(
            row["question"],
            {
                "question": row["question"],
                "score": row["score"],
                "chunks": [],
                "entity_names": [],
            },
        )
        if row["chunk_id"] not in [c["id"] for c in hit["chunks"]]:
            hit["chunks"].append({"id": row["chunk_id"], "text": row["chunk_text"]})
        for name in row["entity_names"]:
            if name and name not in hit["entity_names"]:
                hit["entity_names"].append(name)
    ranked = sorted(hits.values(), key=lambda h: -h["score"])
    return ranked[:top_m]

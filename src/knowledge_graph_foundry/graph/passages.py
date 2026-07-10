"""R34-H366 passage channel: query-anchored span store and render (rung 2).

Chunks are already persisted as provenance nodes with full text (R02-H12);
this module splits them into fixed-size overlapping spans (900 chars,
stride half - the s900k1 construction the H366/H382 offline arms measured),
embeds them in the passage channel's pinned space (bge-m3 on local GPU by
default - bulk embedding never defaults to a cloud provider), and serves
the top span for a query under escalation.

Span ids reproduce the offline cache keying (``{chunk_id}:{span}:{start}``)
so engine-built passages are comparable ledger-for-ledger with the R34
caches (the H385 replay-match clause).

Space discipline (acc-crit): the index's (provider, model, dimensions) is
registered on a ``(:KGFIndexSpace)`` node at build; a query embedded with a
different pair is refused before the vector query executes (H157
generalized - never mix spaces silently).
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger

EmbedFn = Callable[[list[str]], list[list[float]]]
_BATCH = 64


def build_spans(chunk_id: str, text: str, span_chars: int) -> list[dict[str, Any]]:
    """Fixed-size overlapping spans over one chunk's text; stride is half the
    span. Keying matches the R34 offline caches exactly."""
    stride = span_chars // 2
    spans = []
    for start in range(0, max(len(text) - stride, 1), stride):
        piece = text[start : start + span_chars]
        if piece.strip():
            spans.append(
                {"id": f"{chunk_id}:{span_chars}:{start}", "chunk_id": chunk_id, "text": piece}
            )
    return spans


def register_space(driver, index_name: str, provider: str, model: str, dimensions: int) -> None:
    """Pin the (provider, model, dimensions) that built an index."""
    with driver.session() as session:
        session.run(
            "MERGE (s:KGFIndexSpace {index_name: $index_name}) "
            "SET s.provider = $provider, s.model = $model, s.dimensions = $dimensions",
            index_name=index_name,
            provider=provider,
            model=model,
            dimensions=dimensions,
        ).consume()


def check_space(driver, index_name: str, provider: str, model: str) -> None:
    """Refuse a query whose embedding space differs from the index's."""
    with driver.session() as session:
        row = session.run(
            "MATCH (s:KGFIndexSpace {index_name: $index_name}) "
            "RETURN s.provider AS provider, s.model AS model",
            index_name=index_name,
        ).single()
    if row and (row["provider"], row["model"]) != (provider, model):
        raise RuntimeError(
            f"index {index_name!r} was built with ({row['provider']}, {row['model']}); "
            f"refusing query embedded with ({provider}, {model}) - re-embed the index "
            "or point the channel at the original pair"
        )


def ensure_passage_index(driver, dimensions: int, index_name: str) -> None:
    with driver.session() as session:
        session.run(
            f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
            "FOR (p:KGFPassage) ON (p.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: $dims, "
            "`vector.similarity_function`: 'cosine'}}",
            dims=dimensions,
        ).consume()


def generate_passages(
    driver,
    embed_fn: EmbedFn,
    index_name: str,
    dimensions: int,
    provider: str,
    model: str,
    span_chars: int = 900,
) -> int:
    """Split every stored Chunk into spans, embed and persist the new ones.
    Idempotent: span ids are position-keyed, existing ids are skipped.
    Every passage node records the (provider, model) that embedded it."""
    ensure_passage_index(driver, dimensions, index_name)
    register_space(driver, index_name, provider, model, dimensions)

    with driver.session() as session:
        chunks = session.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS text").data()
        existing = {r["id"] for r in session.run("MATCH (p:KGFPassage) RETURN p.id AS id")}

    spans = []
    for ch in chunks:
        spans.extend(s for s in build_spans(ch["id"], ch["text"] or "", span_chars))
    new = [s for s in spans if s["id"] not in existing]
    if not new:
        logger.info("passages: nothing new ({} already present)", len(existing))
        return 0

    created = 0
    with driver.session() as session:
        for offset in range(0, len(new), _BATCH):
            batch = new[offset : offset + _BATCH]
            vectors = embed_fn([s["text"] for s in batch])
            rows = [
                {**s, "embedding": v, "emb_provider": provider, "emb_model": model}
                for s, v in zip(batch, vectors)
                if v
            ]
            session.run(
                "UNWIND $rows AS row "
                "MERGE (p:KGFPassage {id: row.id}) "
                "ON CREATE SET p.text = row.text, p.embedding = row.embedding, "
                "p.emb_provider = row.emb_provider, p.emb_model = row.emb_model, "
                "p.created_at = timestamp() "
                "WITH p, row MATCH (c:Chunk {id: row.chunk_id}) MERGE (p)-[:PART_OF]->(c)",
                rows=rows,
            ).consume()
            created += len(rows)
            logger.info("passages: {}/{}", min(offset + _BATCH, len(new)), len(new))
    return created


def passage_query(driver, embedding: list[float], index_name: str, top_k: int) -> list[dict]:
    """Top-k spans for a query embedding in the passage space."""
    with driver.session() as session:
        return session.run(
            "CALL db.index.vector.queryNodes($index_name, $top_k, $embedding) "
            "YIELD node, score "
            "RETURN node.id AS id, node.text AS text, score",
            index_name=index_name,
            top_k=top_k,
            embedding=embedding,
        ).data()

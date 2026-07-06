"""Tests for token-based chunking: determinism, overlap, boundaries."""

from knowledge_graph_foundry.ingest import chunk_document
from knowledge_graph_foundry.models import Document


def _doc(text: str) -> Document:
    return Document(id="d_test", path="test.md", format="md", text=text)


def test_empty_text_returns_no_chunks():
    assert chunk_document(_doc("")) == []


def test_whitespace_only_returns_no_chunks():
    assert chunk_document(_doc("   \n\t  \n")) == []


def test_short_text_single_chunk():
    doc = _doc("One short sentence.")
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].text == doc.text
    assert chunks[0].index == 0
    assert chunks[0].document_id == "d_test"
    assert chunks[0].token_count > 0


def test_chunk_determinism_same_ids_twice():
    text = "Sentence one. " * 300
    doc = _doc(text)
    first = chunk_document(doc, chunk_size=50, chunk_overlap=10)
    second = chunk_document(doc, chunk_size=50, chunk_overlap=10)
    assert len(first) > 1
    assert [c.id for c in first] == [c.id for c in second]
    assert [c.text for c in first] == [c.text for c in second]


def test_chunk_size_respected():
    text = "Sentence number one. " * 300
    chunks = chunk_document(_doc(text), chunk_size=50, chunk_overlap=10)
    assert len(chunks) > 1
    assert all(c.token_count <= 50 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert len({c.id for c in chunks}) == len(chunks)


def test_overlap_boundaries():
    # No sentence boundaries in the text, so no snapping: adjacent chunks
    # share roughly chunk_overlap tokens - a suffix of each chunk is a
    # prefix of the next (BPE decode is concatenative, so the shared token
    # slice appears verbatim in both texts).
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_document(_doc(text), chunk_size=50, chunk_overlap=10)
    assert len(chunks) > 1
    for left, right in zip(chunks, chunks[1:]):
        shared = max(
            (
                k
                for k in range(1, min(len(left.text), len(right.text)) + 1)
                if left.text[-k:] == right.text[:k]
            ),
            default=0,
        )
        assert shared >= 9  # ~10 overlap tokens, each at least one char


def test_sentence_boundary_snapping():
    # Chunks that are not the final chunk should end at a sentence boundary.
    text = "This is a full sentence about a thing. " * 200
    chunks = chunk_document(_doc(text), chunk_size=50, chunk_overlap=10)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert chunk.text.endswith(". ")


def test_ids_change_with_document_id():
    text = "Same text content here."
    a = chunk_document(Document(id="d_a", path="a.md", format="md", text=text))
    b = chunk_document(Document(id="d_b", path="b.md", format="md", text=text))
    assert a[0].id != b[0].id

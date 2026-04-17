"""Tests for FAISS ExemplarIndex build and query."""
import numpy as np
import pytest

from knowledge_graph_foundry.extraction.exemplar_index import ExemplarIndex
from knowledge_graph_foundry.types.ontology import TypeExemplar


def _random_embedding(dim=1024, seed=None):
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    return (vec / np.linalg.norm(vec)).tolist()


def _make_exemplars_and_embeddings():
    """Create test exemplars with deterministic embeddings."""
    exemplars = {
        "Component": (
            TypeExemplar(name="Humidifier", entity_type="Component", frequency=5),
            TypeExemplar(name="Tubing", entity_type="Component", frequency=3),
        ),
        "Specification": (
            TypeExemplar(name="Pressure", entity_type="Specification", frequency=4),
            TypeExemplar(name="Weight", entity_type="Specification", frequency=2),
        ),
    }

    embeddings = {
        "Humidifier": _random_embedding(seed=1),
        "Tubing": _random_embedding(seed=2),
        "Pressure": _random_embedding(seed=3),
        "Weight": _random_embedding(seed=4),
    }

    return exemplars, embeddings


class TestExemplarIndex:
    def test_build_and_query(self):
        exemplars, embeddings = _make_exemplars_and_embeddings()
        index = ExemplarIndex()
        index.build(exemplars, embeddings)

        assert index.is_built

        # Query with an embedding similar to Humidifier
        query_emb = embeddings["Humidifier"]
        results = index.query(query_emb, top_k=2)

        assert len(results) > 0
        # Humidifier's own embedding should match Component type
        assert results[0][0] == "Component"
        assert results[0][1] > 0.5  # high similarity

    def test_query_returns_correct_types(self):
        exemplars, embeddings = _make_exemplars_and_embeddings()
        index = ExemplarIndex()
        index.build(exemplars, embeddings)

        # Query with Pressure embedding should return Specification
        results = index.query(embeddings["Pressure"], top_k=2)
        assert results[0][0] == "Specification"

    def test_empty_index_returns_empty(self):
        index = ExemplarIndex()
        assert not index.is_built
        results = index.query(_random_embedding(seed=99))
        assert results == []

    def test_build_with_no_embeddings(self):
        exemplars, _ = _make_exemplars_and_embeddings()
        index = ExemplarIndex()
        index.build(exemplars, {})  # no embeddings available
        assert not index.is_built

    def test_top_k_limit(self):
        exemplars, embeddings = _make_exemplars_and_embeddings()
        index = ExemplarIndex()
        index.build(exemplars, embeddings)

        results = index.query(embeddings["Humidifier"], top_k=1)
        assert len(results) == 1


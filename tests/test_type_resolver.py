"""Tests for BayesianTypeResolver."""
import numpy as np
import pytest

from kg_builder_cli.extraction.exemplar_index import ExemplarIndex
from kg_builder_cli.extraction.type_resolver import BayesianTypeResolver, ResolverContext
from kg_builder_cli.types.config import OntologyBufferConfig
from kg_builder_cli.types.extraction import Entity, Relationship
from kg_builder_cli.types.ontology import TypeExemplar


def _config(**kwargs):
    defaults = {
        "min_frequency_to_confirm": 1,
        "max_type_exemplars": 5,
        "type_resolution_top_k": 3,
        "type_resolution_entropy_threshold": 0.8,
    }
    defaults.update(kwargs)
    return OntologyBufferConfig(**defaults)


def _random_embedding(dim=1024, seed=None):
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    return (vec / np.linalg.norm(vec)).tolist()


class TestBayesianPrior:
    def test_prior_from_frequencies(self):
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 60, "Specification": 30, "Product": 10},
        )
        assert abs(resolver._prior["Component"] - 0.6) < 0.01
        assert abs(resolver._prior["Specification"] - 0.3) < 0.01
        assert abs(resolver._prior["Product"] - 0.1) < 0.01

    def test_empty_frequencies(self):
        resolver = BayesianTypeResolver(_config(), {})
        entity = Entity(id="e1", name="Widget", type="Unknown")
        result = resolver.resolve(entity, ResolverContext())
        assert result == "Unknown"  # passthrough with empty prior


class TestBayesianResolve:
    def test_high_confidence_assignment(self):
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 90, "Specification": 5, "Product": 5},
        )
        entity = Entity(id="e1", name="Humidifier", type="Unknown")
        result = resolver.resolve(entity, ResolverContext())
        # Strong prior for Component should dominate
        assert result == "Component"

    def test_relationship_context_signal(self):
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
        )
        entity = Entity(id="comp_humidifier", name="Humidifier", type="Unknown")
        rels = [
            Relationship(
                source="product_1", target="comp_humidifier",
                type="HAS_COMPONENT", description="",
            ),
        ]
        ctx = ResolverContext(relationships=rels)
        result = resolver.resolve(entity, ctx)
        # HAS_COMPONENT relationship should favor Component
        assert result == "Component"

    def test_with_exemplar_index(self):
        exemplars = {
            "Component": (
                TypeExemplar(name="Motor", entity_type="Component", frequency=5),
            ),
            "Specification": (
                TypeExemplar(name="Voltage", entity_type="Specification", frequency=3),
            ),
        }

        # Motor and query share seed -> high cosine similarity
        motor_emb = _random_embedding(seed=10)
        voltage_emb = _random_embedding(seed=20)
        query_emb = _random_embedding(seed=10)  # same seed as Motor

        embeddings = {"Motor": motor_emb, "Voltage": voltage_emb}

        index = ExemplarIndex()
        index.build(exemplars, embeddings)

        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
            exemplar_index=index,
        )
        entity = Entity(id="e1", name="Generator", type="Specification")
        ctx = ResolverContext(entity_embedding=query_emb)
        result = resolver.resolve(entity, ctx)
        assert result == "Component"

    def test_no_index_no_embedding_passthrough(self):
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
        )
        entity = Entity(id="e1", name="Widget", type="Component")
        result = resolver.resolve(entity, ResolverContext())
        # Without exemplar evidence, prior is uniform-ish -> should return something
        assert result in ("Component", "Specification")


class TestEntropy:
    def test_low_entropy(self):
        h = BayesianTypeResolver._entropy({"A": 0.99, "B": 0.01})
        assert h < 0.5

    def test_high_entropy(self):
        h = BayesianTypeResolver._entropy({"A": 0.5, "B": 0.5})
        assert abs(h - 1.0) < 0.01

    def test_zero_entropy(self):
        h = BayesianTypeResolver._entropy({"A": 1.0})
        assert h == 0.0


class TestColdStart:
    def test_fallback_without_index(self):
        """Without exemplar index, resolver still works via prior only."""
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 80, "Specification": 20},
            exemplar_index=None,
        )
        entity = Entity(id="e1", name="Test", type="Unknown")
        result = resolver.resolve(entity, ResolverContext())
        # Should resolve to highest prior
        assert result == "Component"

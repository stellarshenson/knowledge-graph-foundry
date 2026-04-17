"""Tests for BayesianTypeResolver."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from kgf.extraction.exemplar_index import ExemplarIndex
from kgf.extraction.type_resolver import BayesianTypeResolver, ResolverContext
from kgf.types.config import LLMConfig, OntologyBufferConfig
from kgf.types.extraction import Entity, Relationship
from kgf.types.ontology import TypeExemplar


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


class TestCooccurrence:
    def test_boost_for_common_type(self):
        """Co-occurring entities of the same type should boost that type."""
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
        )
        entity = Entity(id="e1", name="Widget", type="Unknown")
        # Chunk has 3 Component entities - should boost Component
        chunk_entities = [
            Entity(id="e2", name="Motor", type="Component"),
            Entity(id="e3", name="Pump", type="Component"),
            Entity(id="e4", name="Valve", type="Component"),
        ]
        ctx = ResolverContext(chunk_entities=chunk_entities)
        result = resolver.resolve(entity, ctx)
        assert result == "Component"

    def test_neutral_for_empty(self):
        """Empty chunk entities should not affect resolution."""
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
        )
        entity = Entity(id="e1", name="Widget", type="Unknown")
        # With empty chunk entities, cooccurrence likelihood is 1.0 (neutral)
        likelihood = resolver._cooccurrence_likelihood("Component", [])
        assert likelihood == 1.0

    def test_mixed_types(self):
        """Mixed co-occurring types should give moderate boost."""
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
        )
        chunk_entities = [
            Entity(id="e2", name="Motor", type="Component"),
            Entity(id="e3", name="Voltage", type="Specification"),
        ]
        comp_likelihood = resolver._cooccurrence_likelihood("Component", chunk_entities)
        spec_likelihood = resolver._cooccurrence_likelihood("Specification", chunk_entities)
        # Each should get 1.5 (1 match out of 2)
        assert abs(comp_likelihood - 1.5) < 0.01
        assert abs(spec_likelihood - 1.5) < 0.01


class TestDescriptionLikelihood:
    def test_overlap_boost(self):
        """Description keyword overlap should boost likelihood."""
        exemplars = {
            "Component": (
                TypeExemplar(
                    name="Motor",
                    entity_type="Component",
                    frequency=5,
                    description="electrical motor for air pressure delivery",
                ),
            ),
        }
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50, "Specification": 50},
            type_exemplars=exemplars,
        )
        entity = Entity(
            id="e1", name="Pump", type="Unknown",
            description="air pressure pump for delivery system",
        )
        likelihood = resolver._description_likelihood(entity, "Component")
        # Should be > 1.0 due to keyword overlap
        assert likelihood > 1.0

    def test_no_description_neutral(self):
        """Entity with no description should get neutral likelihood."""
        exemplars = {
            "Component": (
                TypeExemplar(
                    name="Motor",
                    entity_type="Component",
                    frequency=5,
                    description="electrical motor",
                ),
            ),
        }
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50},
            type_exemplars=exemplars,
        )
        entity = Entity(id="e1", name="Widget", type="Unknown", description="")
        likelihood = resolver._description_likelihood(entity, "Component")
        assert likelihood == 1.0

    def test_no_exemplar_descriptions_neutral(self):
        """Exemplars without descriptions should give neutral likelihood."""
        exemplars = {
            "Component": (
                TypeExemplar(name="Motor", entity_type="Component", frequency=5, description=""),
            ),
        }
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50},
            type_exemplars=exemplars,
        )
        entity = Entity(
            id="e1", name="Pump", type="Unknown",
            description="air pressure pump",
        )
        likelihood = resolver._description_likelihood(entity, "Component")
        assert likelihood == 1.0

    def test_no_exemplars_for_type_neutral(self):
        """No exemplars at all for a type should give neutral likelihood."""
        resolver = BayesianTypeResolver(
            _config(),
            {"Component": 50},
            type_exemplars={},
        )
        entity = Entity(
            id="e1", name="Pump", type="Unknown",
            description="some description",
        )
        likelihood = resolver._description_likelihood(entity, "Component")
        assert likelihood == 1.0


class TestLLMEscalation:
    def test_disabled_uses_argmax(self):
        """When LLM escalation is disabled, high-entropy resolves to argmax."""
        resolver = BayesianTypeResolver(
            _config(type_resolution_entropy_threshold=0.0),  # force high entropy
            {"Component": 50, "Specification": 50},
            llm_escalation=False,
        )
        entity = Entity(id="e1", name="Widget", type="Unknown")
        result = resolver.resolve(entity, ResolverContext())
        assert result in ("Component", "Specification")

    @patch("instructor.from_litellm")
    def test_llm_returns_valid_type(self, mock_from_litellm):
        """When LLM escalation is enabled, should call LLM for high-entropy cases."""
        mock_client = MagicMock()
        mock_from_litellm.return_value = mock_client

        mock_response = MagicMock()
        mock_response.chosen_type = "Component"
        mock_response.reasoning = "test"
        mock_client.chat.completions.create.return_value = mock_response

        llm_config = LLMConfig(provider="bedrock", model="test-model")
        resolver = BayesianTypeResolver(
            _config(type_resolution_entropy_threshold=0.0),  # all entropy is "high"
            {"Component": 50, "Specification": 50},
            llm_config=llm_config,
            llm_escalation=True,
        )
        entity = Entity(id="e1", name="Widget", type="Unknown")
        result = resolver.resolve(entity, ResolverContext())
        assert result == "Component"

    @patch("instructor.from_litellm")
    def test_llm_exception_falls_back(self, mock_from_litellm):
        """LLM failure should fall back to argmax."""
        mock_client = MagicMock()
        mock_from_litellm.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("LLM error")

        llm_config = LLMConfig(provider="bedrock", model="test-model")
        resolver = BayesianTypeResolver(
            _config(type_resolution_entropy_threshold=0.0),
            {"Component": 80, "Specification": 20},
            llm_config=llm_config,
            llm_escalation=True,
        )
        entity = Entity(id="e1", name="Widget", type="Unknown")
        result = resolver.resolve(entity, ResolverContext())
        # Should fall back to argmax (Component has higher prior)
        assert result == "Component"

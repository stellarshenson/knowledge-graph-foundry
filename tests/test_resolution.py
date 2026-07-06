"""Tests for the Bayesian resolution core."""

from knowledge_graph_foundry.models import Entity, Relationship
from knowledge_graph_foundry.resolution import (
    PosteriorCalibrator,
    evidence,
    remap_relationships,
    resolve_entities,
)
from knowledge_graph_foundry.resolution.similarity import (
    cosine_similarity,
    description_similarity,
)
from knowledge_graph_foundry.settings import ResolutionSettings

CFG = ResolutionSettings()


def _entity(name: str, types: list[str] | None = None, **kwargs) -> Entity:
    return Entity.create(name, types=types or ["Product"], **kwargs)


class TestSimilarity:
    def test_description_jaccard_ignores_stopwords(self):
        assert description_similarity("the pressure of device", "pressure device") == 1.0

    def test_description_empty(self):
        assert description_similarity("", "anything here") == 0.0

    def test_cosine_orthogonal_and_identical(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
        assert abs(cosine_similarity([0.5, 0.5], [0.5, 0.5]) - 1.0) < 1e-9


class TestEvidence:
    def test_identical_names_high_posterior(self):
        a = _entity("Humidifier", ["Component"], description="heated humidifier unit")
        b = _entity("Humidifier", ["Accessory"], description="heated humidifier unit")
        d = evidence(a, b, CFG)
        assert d.decision == "merge"
        assert d.prior == CFG.name_prior_identical

    def test_different_names_no_evidence_blocks(self):
        a = _entity("AirSense 11", description="auto CPAP by ResMed")
        b = _entity("Water Chamber", description="tub holding water for humidification")
        d = evidence(a, b, CFG)
        assert d.decision == "block"
        assert d.prior == CFG.name_prior_fuzzy

    def test_description_floor_never_vetoes(self):
        a = _entity("X", description="")
        b = _entity("X", description="rich description text here")
        d = evidence(a, b, CFG)
        assert d.lr_description == CFG.description_lr_floor

    def test_embedding_neutral_when_absent(self):
        d = evidence(_entity("A"), _entity("B"), CFG)
        assert d.lr_embedding == 1.0

    def test_cooccurrence_boost(self):
        a = _entity("Foo", source_chunks=["c1"])
        b = _entity("Bar", source_chunks=["c1"])
        assert evidence(a, b, CFG).lr_cooccurrence == 1.5

    def test_prior_override_wins(self):
        d = evidence(_entity("A"), _entity("B"), CFG, prior_override=0.95)
        assert d.prior == 0.95


class TestResolveEntities:
    def test_exact_names_collapse_with_multi_label(self):
        a = _entity("Humidifier", ["Component"], source_documents=["d1"])
        b = _entity("Humidifier", ["Accessory"], source_documents=["d2"])
        result = resolve_entities([a, b], CFG)
        assert len(result.entities) == 1
        merged = result.entities[0]
        assert set(merged.types) == {"Component", "Accessory"}
        assert set(merged.source_documents) == {"d1", "d2"}

    def test_fuzzy_names_with_shared_evidence_merge(self):
        a = _entity(
            "DreamStation 2", description="auto CPAP device by Philips with humidifier",
            source_chunks=["c1"],
        )
        b = _entity(
            "DreamStation2", description="Philips auto CPAP device with humidifier",
            source_chunks=["c1"],
        )
        result = resolve_entities([a, b], CFG)
        assert len(result.entities) == 1
        assert result.id_map  # one id remapped to the canonical

    def test_unrelated_entities_stay_separate(self):
        a = _entity("AirSense 11", description="ResMed auto CPAP")
        b = _entity("Water Chamber", description="humidifier tub")
        result = resolve_entities([a, b], CFG)
        assert len(result.entities) == 2
        assert result.id_map == {}

    def test_synonym_embedding_candidates_within_type(self):
        emb = [1.0, 0.0, 0.0]
        a = _entity(
            "circuit tubing", ["Component"],
            description="flexible tube connecting device to mask",
            embedding=emb, source_chunks=["c9"],
        )
        b = _entity(
            "connecting tubing", ["Component"],
            description="flexible tube connecting the device to a mask",
            embedding=emb, source_chunks=["c9"],
        )
        result = resolve_entities([a, b], CFG)
        assert len(result.entities) == 1

    def test_decisions_recorded_for_forensics(self):
        a = _entity("DreamStation 2", description="cpap")
        b = _entity("DreamStation2", description="cpap")
        result = resolve_entities([a, b], CFG)
        assert result.decisions
        d = result.decisions[0]
        assert 0.0 <= d.posterior <= 1.0
        assert d.decision in {"merge", "defer", "block"}

    def test_empty_and_single(self):
        assert resolve_entities([], CFG).entities == []
        single = [_entity("Solo")]
        assert len(resolve_entities(single, CFG).entities) == 1

    def test_property_union_canonical_wins(self):
        a = _entity("X", properties={"color": "black"})
        b = _entity("X", properties={"color": "white", "weight": "1kg"})
        merged = resolve_entities([a, b], CFG).entities[0]
        assert merged.properties == {"color": "black", "weight": "1kg"}


class TestRemapRelationships:
    def test_endpoints_rewritten_and_deduped(self):
        rels = [
            Relationship(source_id="e_old", target_id="e_t", type="HAS_PART"),
            Relationship(source_id="e_new", target_id="e_t", type="HAS_PART"),
        ]
        out = remap_relationships(rels, {"e_old": "e_new"})
        assert len(out) == 1
        assert out[0].source_id == "e_new"

    def test_self_loops_dropped(self):
        rels = [Relationship(source_id="e_a", target_id="e_b", type="REL")]
        assert remap_relationships(rels, {"e_b": "e_a"}) == []


class TestCalibration:
    def test_roundtrip_json(self):
        cal = PosteriorCalibrator([0.0, 0.5, 1.0], [0.1, 0.4, 0.9])
        restored = PosteriorCalibrator.from_json(cal.to_json())
        assert restored.calibrate(0.5) == 0.4

    def test_interpolation_and_clamping(self):
        import pytest

        cal = PosteriorCalibrator([0.2, 0.8], [0.0, 1.0])
        assert cal.calibrate(0.5) == pytest.approx(0.5)
        assert cal.calibrate(0.1) == 0.0
        assert cal.calibrate(0.9) == 1.0

    def test_fit_requires_min_observations(self):
        assert PosteriorCalibrator.fit([0.5] * 10, [True] * 10, min_observations=50) is None

    def test_fit_produces_monotone_curve(self):
        import random

        rng = random.Random(7)
        xs = [rng.random() for _ in range(200)]
        ys = [x > 0.5 for x in xs]
        cal = PosteriorCalibrator.fit(xs, ys, min_observations=50)
        assert cal is not None
        assert cal.calibrate(0.9) >= cal.calibrate(0.1)

    def test_empty_curve_passthrough(self):
        assert PosteriorCalibrator([], []).calibrate(0.7) == 0.7

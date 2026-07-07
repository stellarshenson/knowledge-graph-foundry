"""Tests for the Bayesian resolution core."""

import math

from knowledge_graph_foundry.models import Entity, Relationship
from knowledge_graph_foundry.resolution import (
    MatchVerdict,
    PosteriorCalibrator,
    ann_candidates,
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
            "DreamStation 2",
            description="auto CPAP device by Philips with humidifier",
            source_chunks=["c1"],
        )
        b = _entity(
            "DreamStation2",
            description="Philips auto CPAP device with humidifier",
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
            "circuit tubing",
            ["Component"],
            description="flexible tube connecting device to mask",
            embedding=emb,
            source_chunks=["c9"],
        )
        b = _entity(
            "connecting tubing",
            ["Component"],
            description="flexible tube connecting the device to a mask",
            embedding=emb,
            source_chunks=["c9"],
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


class _FakeEngine:
    """Engine stub returning a fixed match verdict for the defer judge."""

    name = "fake"

    def __init__(self, same: bool):
        self._same = same

    def complete(self, messages, response_model):
        return response_model(same=self._same, reason="stub")


class TestAnnBlocking:
    def test_parity_with_brute_force_on_small_block(self):
        ents = [
            _entity("tube one", ["Component"], embedding=[1.0, 0.0, 0.0]),
            _entity("tube two", ["Component"], embedding=[1.0, 0.0, 0.0]),
            _entity("air mask", ["Component"], embedding=[0.0, 1.0, 0.0]),
        ]
        brute = ann_candidates(ents, top_k=10, min_entities=100)
        ann = ann_candidates(ents, top_k=10, min_entities=2)
        assert brute == ann == {(0, 1)}

    def test_ann_path_used_above_min_entities(self, monkeypatch):
        import knowledge_graph_foundry.resolution.blocking as blk

        def _boom(*args, **kwargs):
            raise AssertionError("brute-force path used above min_entities")

        monkeypatch.setattr(blk, "_brute_force", _boom)
        ents = [
            _entity("alpha", ["Component"], embedding=[1.0, 0.0, 0.0]),
            _entity("bravo", ["Component"], embedding=[1.0, 0.0, 0.0]),
        ]
        assert blk.ann_candidates(ents, top_k=5, min_entities=2) == {(0, 1)}

    def test_entities_without_embedding_skipped(self):
        ents = [
            _entity("no vec one", ["Component"]),
            _entity("no vec two", ["Component"]),
        ]
        assert ann_candidates(ents, top_k=5, min_entities=100) == set()


class TestDeferJudge:
    def _defer_pair(self):
        a = _entity("AirCurve 10", description="alpha beta gamma")
        b = _entity("AirCurve 11", description="gamma delta epsilon")
        return a, b

    def test_defer_pair_is_in_the_band(self):
        a, b = self._defer_pair()
        assert evidence(a, b, CFG).decision == "defer"

    def test_judge_merges_when_same(self):
        cfg = ResolutionSettings(llm_defer_judge=True)
        a, b = self._defer_pair()
        result = resolve_entities([a, b], cfg, engine=_FakeEngine(True))
        assert len(result.entities) == 1

    def test_judge_keeps_separate_when_not_same(self):
        cfg = ResolutionSettings(llm_defer_judge=True)
        a, b = self._defer_pair()
        result = resolve_entities([a, b], cfg, engine=_FakeEngine(False))
        assert len(result.entities) == 2

    def test_no_engine_defer_behaves_as_before(self):
        cfg = ResolutionSettings(llm_defer_judge=True)
        a, b = self._defer_pair()
        result = resolve_entities([a, b], cfg)  # flag on, no engine
        assert len(result.entities) == 2

    def test_verdict_model(self):
        assert MatchVerdict(same=True, reason="x").same is True


class TestSplitGuard:
    def _snowball(self, c_embedding):
        # A~B strong, B~C / A~C weak: names snowball all three together;
        # embeddings decide cohesion.
        return [
            Entity.create(
                "dreamstation pro",
                types=["Product"],
                description="portable auto cpap therapy machine",
                embedding=[1.0, 0.0, 0.0],
                source_chunks=["c1"],
            ),
            Entity.create(
                "dreamstation pros",
                types=["Product"],
                description="portable auto cpap therapy machine",
                embedding=[1.0, 0.0, 0.0],
                source_chunks=["c1"],
            ),
            Entity.create(
                "dreamstation pro x",
                types=["Product"],
                description="portable auto cpap therapy machine",
                embedding=c_embedding,
                source_chunks=["c1"],
            ),
        ]

    def test_snowball_split_into_correct_components(self):
        weak = [0.2, math.sqrt(1 - 0.04), 0.0]  # cosine 0.2 to A and B
        result = resolve_entities(self._snowball(weak), ResolutionSettings())
        names = {e.name for e in result.entities}
        assert len(result.entities) == 2
        assert "dreamstation pro x" in names  # weak member split off

    def test_cohesive_component_left_intact(self):
        strong = [1.0, 0.0, 0.0]  # identical to A and B
        result = resolve_entities(self._snowball(strong), ResolutionSettings())
        assert len(result.entities) == 1

    def test_split_guard_disabled_keeps_snowball(self):
        weak = [0.2, math.sqrt(1 - 0.04), 0.0]
        cfg = ResolutionSettings(split_guard=False)
        result = resolve_entities(self._snowball(weak), cfg)
        assert len(result.entities) == 1


class TestIdentityStackV2:
    """R15-H158 v2 identity stack: flag wiring, veto direction, artifact loading."""

    _ARTIFACT = {
        "isotonic": {"x": [0.0, 0.5, 0.9, 1.0], "y": [0.0, 0.1, 0.7, 1.0]},
        "logistic": {
            "feature_order": ["name_id", "calibrated_cosine", "nli_contra", "posterior"],
            "weights": [0.0, 3.0, -3.0, 2.0],
            "intercept": -1.0,
            "threshold": 0.3,
            "defer_lower": 0.15,
        },
        "nli": {"model": "test-model", "veto_threshold": 0.5},
    }

    def _stack(self):
        from knowledge_graph_foundry.resolution import V2IdentityStack

        return V2IdentityStack(self._ARTIFACT, veto_threshold=0.5)

    def test_calibrated_cosine_interpolates_and_clamps(self):
        s = self._stack()
        assert s.calibrated_cosine(0.0) == 0.0
        assert s.calibrated_cosine(1.0) == 1.0
        assert s.calibrated_cosine(0.7) == pytest_approx(0.4)  # midpoint of 0.5->0.9 leg

    def test_high_cosine_low_contra_merges(self):
        s = self._stack()
        a = _entity("AirFit F20", embedding=[1.0, 0.0, 0.0])
        b = _entity("AirFit F20 plus", embedding=[0.99, 0.01, 0.0])
        verdict, _, vetoed = s.decide(a, b, posterior=0.6, nli_contra=0.05)
        assert verdict == "merge"
        assert vetoed is False

    def test_contradiction_vetoes_a_would_be_merge(self):
        s = self._stack()
        a = _entity("AirFit F20", embedding=[1.0, 0.0, 0.0])
        b = _entity("AirFit F30", embedding=[0.99, 0.01, 0.0])
        verdict, _, vetoed = s.decide(a, b, posterior=0.6, nli_contra=0.9)
        assert verdict == "block"
        assert vetoed is True

    def test_load_real_artifact(self):
        from pathlib import Path

        from knowledge_graph_foundry.resolution import V2IdentityStack

        path = Path("data/processed/identity-calibration-v2.json")
        if not path.exists():
            import pytest

            pytest.skip("v2 artifact not built")
        s = V2IdentityStack.load(path, veto_threshold=0.5)
        assert 0.0 <= s.calibrated_cosine(0.85) <= 1.0

    def test_v1_default_leaves_resolution_unchanged(self):
        # default settings use v1; a fuzzy merge pair still merges without any stack
        cfg = ResolutionSettings()
        assert cfg.identity_stack == "v1"
        a = _entity("DreamStation 2", description="cpap", source_chunks=["c1"])
        b = _entity("DreamStation2", description="cpap", source_chunks=["c1"])
        assert len(resolve_entities([a, b], cfg).entities) == 1

    def test_v2_flag_routes_through_stack(self, monkeypatch):
        import knowledge_graph_foundry.resolution.resolver as rr

        class _FakeStack:
            def nli_contra_batch(self, pairs):
                return [0.9] * len(pairs)  # every pair contradicts -> veto merges

            def decide(self, a, b, posterior, nli_contra):
                if nli_contra >= 0.5:
                    return "block", 0.6, True
                return "merge", 0.6, False

        monkeypatch.setattr(rr, "_v2_stack", lambda cfg: _FakeStack())
        cfg = ResolutionSettings(identity_stack="v2")
        a = _entity("DreamStation 2", description="cpap", source_chunks=["c1"])
        b = _entity("DreamStation2", description="cpap", source_chunks=["c1"])
        result = resolve_entities([a, b], cfg)
        assert len(result.entities) == 2  # veto blocked the merge


def pytest_approx(v):
    import pytest

    return pytest.approx(v)


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

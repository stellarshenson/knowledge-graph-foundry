"""Tests for stability metrics, curing detector and fluid buffer."""

from knowledge_graph_foundry.models import Entity, Ontology, Relationship
from knowledge_graph_foundry.ontology.buffer import FluidBuffer
from knowledge_graph_foundry.ontology.curing import CuringDetector
from knowledge_graph_foundry.ontology.metrics import StabilityMetrics
from knowledge_graph_foundry.settings import CuringSettings

CFG = CuringSettings()

STABLE_FREQS = {"Product": 40, "Component": 25, "Specification": 20, "Manufacturer": 10}


class TestStabilityMetrics:
    def test_record_produces_core_metrics(self):
        m = StabilityMetrics()
        result = m.record({"Product": 10, "Component": 5})
        for key in ("entropy_shannon", "js_divergence", "chao1_coverage", "unique_types"):
            assert key in result

    def test_convergence_signature_on_stable_distribution(self):
        """Repeated same-shape distributions drive JSD and entropy delta to ~0."""
        m = StabilityMetrics()
        for scale in (1, 2, 3, 4):
            m.record({k: v * scale for k, v in STABLE_FREQS.items()})
        latest = m.latest()
        assert latest["js_divergence"] < 0.02
        assert abs(latest["entropy_shannon_delta"]) < 0.01

    def test_new_types_move_divergence(self):
        m = StabilityMetrics()
        m.record({"A": 10})
        m.record({"A": 20})
        stable_jsd = m.latest()["js_divergence"]
        m.record({"A": 20, "B": 8, "C": 6, "D": 4})
        assert m.latest()["js_divergence"] > stable_jsd

    def test_serialization_roundtrip(self):
        m = StabilityMetrics()
        m.record({"A": 3, "B": 2})
        restored = StabilityMetrics.from_dict(m.to_dict())
        assert restored.latest() == m.latest()
        assert len(restored.history()) == 1


class TestCuringDetector:
    def _stable_record(self) -> dict[str, float]:
        return {
            "js_divergence": 0.001,
            "chao1_coverage": 0.99,
            "entropy_shannon_delta": 0.0005,
            "unique_types": 8.0,
        }

    def test_no_cure_before_min_documents(self):
        d = CuringDetector(CFG)
        d.record(self._stable_record())
        assert d.should_cure() == (False, "fluid")

    def test_converged_after_min_documents(self):
        d = CuringDetector(CFG)
        for _ in range(CFG.min_documents):
            d.record(self._stable_record())
        cure, reason = d.should_cure()
        assert cure and reason == "converged"

    def test_unstable_does_not_cure(self):
        d = CuringDetector(CFG)
        for _ in range(5):
            d.record({"js_divergence": 0.3, "chao1_coverage": 0.5, "entropy_shannon_delta": 0.4})
        assert d.should_cure()[0] is False

    def test_plateau_cures_without_coverage(self):
        d = CuringDetector(CFG)
        for _ in range(4):
            d.record(
                {
                    "js_divergence": 0.05,
                    "chao1_coverage": 0.7,
                    "entropy_shannon_delta": 0.01,
                    "unique_types": 9.0,
                }
            )
        cure, reason = d.should_cure()
        assert cure and reason == "plateau"

    def test_min_sample_floor_blocks_premature_cure(self):
        """R7: even a converged record cannot cure below the Chao1 sample floor."""
        cfg = CuringSettings(min_documents=1, min_samples_before_cure=5)
        d = CuringDetector(cfg)
        for _ in range(3):
            d.record(self._stable_record())
        assert d.is_converged() is False  # 3 < floor of 5
        for _ in range(2):
            d.record(self._stable_record())
        assert d.is_converged() is True  # 5 >= floor

    def test_evidence_gate_blocks_wave1_premature_cure(self):
        """DEF-3: the exact wave-1 failure - a flat 3-doc window over ~20
        observations satisfied the plateau and cured at document 4 of 481."""
        d = CuringDetector(CuringSettings())
        for occ, single in ((8.0, 6.0), (13.0, 3.0), (17.0, 2.0), (20.0, 2.0)):
            d.record(
                {
                    "js_divergence": 0.01,
                    "chao1_coverage": 0.96,
                    "entropy_shannon_delta": 0.005,
                    "unique_types": 7.0,
                    "total_occurrences": occ,
                    "singletons": single,
                }
            )
        assert d.should_cure() == (False, "fluid")  # 20 obs << 200 evidence floor

    def test_missing_mass_blocks_cure_despite_evidence_mass(self):
        """DEF-3: Good-Turing - 10% singleton mass means the next observation
        has ~10% probability of being an unseen type; not saturated."""
        d = CuringDetector(CuringSettings())
        for _ in range(4):
            rec = self._stable_record()
            rec.update({"total_occurrences": 500.0, "singletons": 50.0})
            d.record(rec)
        assert d.should_cure() == (False, "fluid")

    def test_saturated_stream_cures(self):
        """DEF-3: mass floor met and missing mass under threshold -> cure."""
        d = CuringDetector(CuringSettings())
        for _ in range(4):
            rec = self._stable_record()
            rec.update({"total_occurrences": 500.0, "singletons": 10.0})
            d.record(rec)
        cure, reason = d.should_cure()
        assert cure and reason == "converged"

    def test_force_at_max_fluid_documents(self):
        cfg = CuringSettings(max_fluid_documents=4)
        d = CuringDetector(cfg)
        for i in range(4):
            d.record(
                {
                    "js_divergence": 0.5,
                    "chao1_coverage": 0.1,
                    "entropy_shannon_delta": 0.9,
                    "unique_types": float(i),
                }
            )
        cure, reason = d.should_cure()
        assert cure and reason == "forced"

    def test_serialization_roundtrip(self):
        d = CuringDetector(CFG)
        d.record(self._stable_record())
        restored = CuringDetector.from_dict(d.to_dict(), CFG)
        assert restored.docs_processed == 1


class TestFluidBuffer:
    def _doc(self, names_types: list[tuple[str, str]]) -> list[Entity]:
        return [Entity.create(n, types=[t]) for n, t in names_types]

    def test_types_emerge_and_confirm_by_encounters(self):
        buffer = FluidBuffer(Ontology(purpose="test"), CFG)
        buffer.add_document(self._doc([("A1", "Product")]), [])
        assert buffer.ontology.types["Product"].status == "emerging"
        buffer.add_document(self._doc([("A2", "Product")]), [])
        assert buffer.ontology.types["Product"].status == "confirmed"
        assert buffer.ontology.types["Product"].encounters == 2

    def test_evolution_runs_every_document(self):
        buffer = FluidBuffer(Ontology(), CFG)
        buffer.add_document(self._doc([("X", "Foo")]), [])
        assert buffer.documents_processed == 1
        assert "Foo" in buffer.ontology.types

    def test_relationship_types_counted(self):
        buffer = FluidBuffer(Ontology(), CFG)
        rel = Relationship(source_id="e_a", target_id="e_b", type="HAS_PART")
        buffer.add_document([], [rel])
        assert buffer.ontology.relationship_types["HAS_PART"].encounters == 1

    def test_type_frequencies_feed_metrics(self):
        buffer = FluidBuffer(Ontology(), CFG)
        buffer.add_document(
            self._doc([("A", "Product"), ("B", "Product"), ("C", "Component")]), []
        )
        assert buffer.type_frequencies() == {"Product": 2, "Component": 1}

    def test_serialization_roundtrip_for_resume(self):
        buffer = FluidBuffer(Ontology(purpose="compare CPAP machines"), CFG)
        buffer.add_document(self._doc([("AirSense 11", "Product")]), [])
        restored = FluidBuffer.from_dict(buffer.to_dict(), CFG)
        assert restored.documents_processed == 1
        assert restored.ontology.purpose == "compare CPAP machines"
        assert restored.entities[0].name == "AirSense 11"

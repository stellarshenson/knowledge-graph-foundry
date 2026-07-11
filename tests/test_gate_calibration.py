"""R38 gate-calibration tests: CRC fitter equivalence against the recorded
H383 ledger, corpus fingerprinting, label harvesting from events (H385
floor discipline + join), and the two-tier threshold loader precedence
(H384: file artifact > graph record > settings prior)."""

import json

from knowledge_graph_foundry.graph.gate_calibration import (
    build_record,
    corpus_fingerprint,
    crc_fit_threshold,
    fit_gate_from_events,
)
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.settings import Settings

# the H382 pinned-pile ledger (reports/r37-h382-ladder-arm1-20260710T173529Z.json):
# per-probe top-seed signal; rung 0 leaves P08/P15/P22 uncovered, rung 2 all but P08
H382_SIGNALS = {
    "P01": 0.7081,
    "P02": 0.7886,
    "P03": 0.7768,
    "P04": 0.7928,
    "P05": 0.8269,
    "P06": 0.7009,
    "P07": 0.7787,
    "P08": 0.7358,
    "P09": 0.8216,
    "P10": 0.7815,
    "P11": 0.7987,
    "P12": 0.7495,
    "P13": 0.8175,
    "P14": 0.7689,
    "P15": 0.7531,
    "P16": 0.778,
    "P17": 0.7771,
    "P18": 0.7934,
    "P19": 0.8185,
    "P20": 0.7832,
    "P21": 0.8354,
    "P22": 0.7599,
    "P23": 0.8111,
    "P24": 0.8751,
}
H382_RUNG0_UNCOVERED = {"P08", "P15", "P22"}
H382_RUNG2_UNCOVERED = {"P08"}


def h382_ledger():
    return [
        {
            "question": p,
            "signal": s,
            "rung0_covered": p not in H382_RUNG0_UNCOVERED,
            "rung2_covered": p not in H382_RUNG2_UNCOVERED,
        }
        for p, s in H382_SIGNALS.items()
    ]


class TestCorpusFingerprint:
    def test_order_invariant(self):
        assert corpus_fingerprint(["a:1", "b:2"]) == corpus_fingerprint(["b:2", "a:1"])

    def test_content_sensitive(self):
        assert corpus_fingerprint(["a:1"]) != corpus_fingerprint(["a:2"])


class TestCRCFit:
    """R38-H383: the fitter reproduces the recorded certificate exactly."""

    def test_alpha_008_reproduces_h382_cut(self):
        theta, infeasible = crc_fit_threshold(h382_ledger(), alpha=0.08)
        assert not infeasible
        assert theta == 0.7644  # the H382 fold-B fitted cut, exactly

    def test_alpha_004_infeasible_degrades_to_always_escalate(self):
        # P08 (parse loss) pins min risk at 1/24, so 0.08 is the feasibility
        # floor; below it the fit must degrade safe, never return invalid
        theta, infeasible = crc_fit_threshold(h382_ledger(), alpha=0.04)
        assert infeasible
        assert theta > max(H382_SIGNALS.values())  # escalates everything

    def test_alpha_012_admits_second_miss(self):
        theta, infeasible = crc_fit_threshold(h382_ledger(), alpha=0.12)
        assert not infeasible
        assert theta == 0.7565  # escalates P15 but accepts P22 as allowed miss


class TestFitFromEvents:
    """R38-H385: label harvest joins two-pass replay events against gold."""

    PROBES = [
        {"question": "q-low", "gold_evidence": ["needle"]},
        {"question": "q-mid", "gold_evidence": ["easy"]},
        {"question": "q-high", "gold_evidence": ["plain"]},
    ]

    def _events(self, tmp_path):
        # q-low: rung 0 misses the gold, rung 2 finds it (the needy probe);
        # q-mid / q-high: covered at rung 0 already
        rows = [
            {
                "event": "query.answered",
                "question": "q-low",
                "escalated": False,
                "seed_top_score": 0.5,
                "answer": "nothing here",
            },
            {
                "event": "query.answered",
                "question": "q-low",
                "escalated": True,
                "seed_top_score": 0.5,
                "answer": "the needle was found",
            },
            {
                "event": "query.answered",
                "question": "q-mid",
                "escalated": False,
                "seed_top_score": 0.7,
                "answer": "easy answer",
            },
            {
                "event": "query.answered",
                "question": "q-mid",
                "escalated": True,
                "seed_top_score": 0.7,
                "answer": "easy answer",
            },
            {
                "event": "query.answered",
                "question": "q-high",
                "escalated": False,
                "seed_top_score": 0.9,
                "answer": "plain answer",
            },
            {
                "event": "query.answered",
                "question": "q-high",
                "escalated": True,
                "seed_top_score": 0.9,
                "answer": "plain answer",
            },
            {"event": "query.miss", "question": "unrelated", "top_score": 0.3},
        ]
        path = tmp_path / "events.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        return path

    def test_joins_two_passes_and_fits(self, tmp_path):
        ledger, record = fit_gate_from_events(
            self._events(tmp_path), self.PROBES, min_labels=3, alpha=0.3, fingerprint="fp"
        )
        assert len(ledger) == 3
        needy = {r["question"] for r in ledger if not r["rung0_covered"]}
        assert needy == {"q-low"}
        # alpha=0.3 at n=3 -> R_hat must be 0 -> smallest cut escalating q-low
        assert record["threshold"] == 0.6  # midpoint of 0.5 and 0.7
        assert record["provenance"]["method"] == "crc"
        assert record["provenance"]["corpus_fingerprint"] == "fp"
        assert record["provenance"]["n_labels"] == 3

    def test_floor_discipline_returns_no_record(self, tmp_path):
        ledger, record = fit_gate_from_events(
            self._events(tmp_path), self.PROBES, min_labels=12, alpha=0.3
        )
        assert len(ledger) == 3
        assert record is None  # below the floor the prior/record stands

    def test_incomplete_pairs_are_skipped(self, tmp_path):
        rows = [
            {
                "event": "query.answered",
                "question": "q-low",
                "escalated": False,
                "seed_top_score": 0.5,
                "answer": "nothing",
            },
        ]
        path = tmp_path / "partial.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        ledger, record = fit_gate_from_events(path, self.PROBES, min_labels=1)
        assert ledger == []
        assert record is None


class TestGateThresholdLoader:
    """R38-H384 two-tier precedence: file > graph record > settings prior."""

    def _foundry(self, monkeypatch, state, settings=None):
        f = Foundry(settings or Settings())
        monkeypatch.setattr(f, "_load_state", lambda: state)
        return f

    def test_prior_when_no_record(self, monkeypatch):
        f = self._foundry(monkeypatch, {})
        assert f._gate_threshold() == f.settings.graphrag.escalation_threshold_prior

    def test_graph_record_wins_over_prior(self, monkeypatch):
        docs = ["doc:aaaa"]
        record = build_record(0.71, 0.08, 24, corpus_fingerprint(docs))
        state = {"gate_calibration": record, "processed_documents": docs}
        f = self._foundry(monkeypatch, state)
        assert f._gate_threshold() == 0.71

    def test_fingerprint_mismatch_falls_back_to_prior(self, monkeypatch):
        record = build_record(0.71, 0.08, 24, corpus_fingerprint(["doc:aaaa"]))
        state = {"gate_calibration": record, "processed_documents": ["doc:bbbb"]}
        f = self._foundry(monkeypatch, state)
        assert f._gate_threshold() == f.settings.graphrag.escalation_threshold_prior

    def test_file_artifact_wins_over_graph_record(self, monkeypatch, tmp_path):
        artifact = tmp_path / "gate.json"
        artifact.write_text(json.dumps({"threshold": 0.69}))
        settings = Settings()
        settings.graphrag.gate_calibration_path = str(artifact)
        docs = ["doc:aaaa"]
        record = build_record(0.71, 0.08, 24, corpus_fingerprint(docs))
        state = {"gate_calibration": record, "processed_documents": docs}
        f = self._foundry(monkeypatch, state, settings)
        assert f._gate_threshold() == 0.69

    def test_wipe_semantics_reset_to_prior(self, monkeypatch):
        # after wipe + init the state carries no gate_calibration key - the
        # prior applies until per-corpus labels re-accumulate (survival matrix)
        f = self._foundry(monkeypatch, {"fsm_state": "EMPTY", "calibration": None})
        assert f._gate_threshold() == f.settings.graphrag.escalation_threshold_prior


class TestGateRefitHook:
    """R38-H385: the optimize() refit hook - harvest, floor discipline, persist."""

    PROBES = TestFitFromEvents.PROBES

    def _foundry(self, monkeypatch, tmp_path, events_path, min_labels):
        import yaml

        probe_path = tmp_path / "probes.yml"
        probe_path.write_text(yaml.safe_dump(self.PROBES))
        settings = Settings()
        settings.graphrag.escalation_gate = True
        settings.graphrag.gate_probe_set = str(probe_path)
        settings.graphrag.escalation_min_labels = min_labels
        settings.event_log = str(events_path)
        f = Foundry(settings)
        state = {"processed_documents": ["doc:aaaa"]}
        saved = {}
        monkeypatch.setattr(f, "_load_state", lambda: state)
        monkeypatch.setattr(f, "_save_state", lambda s: saved.update(s))
        return f, saved

    def test_refit_persists_record(self, monkeypatch, tmp_path):
        events = TestFitFromEvents()._events(tmp_path)
        f, saved = self._foundry(monkeypatch, tmp_path, events, min_labels=3)
        out = f._refit_gate()
        assert out["refit"] is True and out["labels"] == 3
        rec = saved["gate_calibration"]
        assert rec["threshold"] == out["threshold"]
        assert rec["provenance"]["corpus_fingerprint"] == corpus_fingerprint(["doc:aaaa"])

    def test_floor_discipline_no_write(self, monkeypatch, tmp_path):
        events = TestFitFromEvents()._events(tmp_path)
        f, saved = self._foundry(monkeypatch, tmp_path, events, min_labels=12)
        out = f._refit_gate()
        assert out == {"labels": 3, "refit": False}
        assert saved == {}  # below the floor nothing is persisted

    def test_silent_without_gate_or_probe_set(self, monkeypatch, tmp_path):
        events = TestFitFromEvents()._events(tmp_path)
        f, saved = self._foundry(monkeypatch, tmp_path, events, min_labels=3)
        f.settings.graphrag.escalation_gate = False
        assert f._refit_gate() is None
        f.settings.graphrag.escalation_gate = True
        f.settings.graphrag.gate_probe_set = None
        assert f._refit_gate() is None
        assert saved == {}

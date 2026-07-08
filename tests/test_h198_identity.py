"""R15-H198 identity levers: soft links (H268), demote-don't-delete court
(R27/H290), the H267 freebie, and the per-corpus calibration path (H157/H142).

All mocked - no live Neo4j or LLM. A small fake driver records the Cypher
parameters so the tests assert on what WOULD be written."""

import json

from knowledge_graph_foundry.graph.court import run_demotion_court
from knowledge_graph_foundry.graph.densify import add_soft_links
from knowledge_graph_foundry.models import ResolutionDecision
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.resolution.calibration import (
    PosteriorCalibrator,
    fit_calibration_from_events,
)
from knowledge_graph_foundry.resolution.judge import MatchVerdict
from knowledge_graph_foundry.settings import ResolutionSettings, Settings

# -- fakes ----------------------------------------------------------------


class _Result:
    def __init__(self, rows=None):
        self._rows = rows or []

    def __iter__(self):
        return iter(self._rows)

    def consume(self):
        return None


class _Session:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self.driver.queries.append(query)
        if "[:SAME_AS]->(b:Entity)" in query:
            return _Result(self.driver.docket_rows)
        if "DELETE s" in query:
            self.driver.deleted.extend(params.get("rows", []))
            return _Result()
        if "SIMILAR_TO" in query:
            self.driver.soft_links.extend(params.get("rows", []))
            return _Result()
        return _Result()


class FakeDriver:
    def __init__(self, docket_rows=None):
        self.docket_rows = docket_rows or []
        self.queries: list[str] = []
        self.deleted: list[dict] = []
        self.soft_links: list[dict] = []

    def session(self):
        return _Session(self)


class FakeEngine:
    """Returns a fixed verdict per name pair; records prompts for call-count
    assertions."""

    def __init__(self, verdicts: dict[frozenset[str], bool]):
        self.verdicts = verdicts
        self.prompts: list[str] = []

    def complete(self, messages, schema):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        for names, same in self.verdicts.items():
            if all(n in prompt for n in names):
                return MatchVerdict(same=same)
        return MatchVerdict(same=True)


def _row(lid, lname, rid, rname, ltypes=None, rtypes=None):
    return {
        "la": lid,
        "lname": lname,
        "ltypes": ltypes or ["Product"],
        "ldesc": f"{lname} description",
        "lemb": None,
        "ra": rid,
        "rname": rname,
        "rtypes": rtypes or ["Product"],
        "rdesc": f"{rname} description",
        "remb": None,
    }


# -- soft links (H268) ----------------------------------------------------


class TestSoftLinks:
    def test_weight_is_posterior_and_id_ordered(self):
        driver = FakeDriver()
        n = add_soft_links(driver, [("z_id", "a_id", 0.55)])
        assert n == 1
        row = driver.soft_links[0]
        assert row["weight"] == 0.55
        # id-ordering is enforced in Cypher; the params carry the raw pair
        assert {row["left"], row["right"]} == {"z_id", "a_id"}

    def test_empty_pairs_no_write(self):
        driver = FakeDriver()
        assert add_soft_links(driver, []) == 0
        assert driver.soft_links == []

    def test_materialize_filters_to_defer_and_remaps(self):
        foundry = Foundry(Settings())
        foundry._driver = FakeDriver()
        decisions = [
            ResolutionDecision(
                left_id="a",
                right_id="b",
                prior=0.5,
                lr_description=1.0,
                lr_embedding=1.0,
                lr_cooccurrence=1.0,
                posterior=0.5,
                decision="defer",
            ),
            ResolutionDecision(
                left_id="c",
                right_id="d",
                prior=0.9,
                lr_description=1.0,
                lr_embedding=1.0,
                lr_cooccurrence=1.0,
                posterior=0.9,
                decision="merge",
            ),
        ]
        foundry._materialize_soft_links(decisions, {"b": "b2"})
        rows = foundry._driver.soft_links
        assert len(rows) == 1  # only the defer pair
        assert {rows[0]["left"], rows[0]["right"]} == {"a", "b2"}  # remapped endpoint
        assert rows[0]["weight"] == 0.5


# -- demote-don't-delete court (R27/H290) + freebie (H267) ----------------


class TestDemotionCourt:
    def test_judged_false_demotes_to_similar_to_and_removes_same_as(self):
        driver = FakeDriver([_row("md300", "MD300W314B4", "wrist", "Wrist Pulse Oximeter")])
        engine = FakeEngine({frozenset(("MD300W314B4", "Wrist Pulse Oximeter")): False})
        summary = run_demotion_court(driver, engine, ResolutionSettings())
        assert summary == {"docket": 1, "freebies": 0, "judged": 1, "demoted": 1}
        # SAME_AS removed, soft link created (never a bare delete)
        assert len(driver.deleted) == 1
        assert len(driver.soft_links) == 1
        assert {driver.soft_links[0]["left"], driver.soft_links[0]["right"]} == {"md300", "wrist"}

    def test_judged_true_leaves_same_as_intact(self):
        driver = FakeDriver([_row("airfit", "AirFit N20", "airfitc", "AirFit N20 Classic")])
        engine = FakeEngine({frozenset(("AirFit N20", "AirFit N20 Classic")): True})
        summary = run_demotion_court(driver, engine, ResolutionSettings())
        assert summary["judged"] == 1 and summary["demoted"] == 0
        assert driver.deleted == [] and driver.soft_links == []

    def test_freebie_bypasses_judge(self):
        # normalized-name identity: "SmartRamp" == "Smart Ramp" - no LLM call
        driver = FakeDriver([_row("s1", "SmartRamp", "s2", "Smart Ramp")])
        engine = FakeEngine({})
        summary = run_demotion_court(driver, engine, ResolutionSettings())
        assert summary == {"docket": 1, "freebies": 1, "judged": 0, "demoted": 0}
        assert engine.prompts == []  # judge never consulted
        assert driver.deleted == [] and driver.soft_links == []

    def test_empty_docket(self):
        driver = FakeDriver([])
        summary = run_demotion_court(driver, FakeEngine({}), ResolutionSettings())
        assert summary == {"docket": 0, "freebies": 0, "judged": 0, "demoted": 0}


# -- per-corpus calibration path (H157/H142) ------------------------------


class TestCalibrationPath:
    def _write_corpus(self, tmp_path, n=12):
        events = tmp_path / "events.jsonl"
        gt = tmp_path / "gt.json"
        lines, truth = [], []
        for i in range(n):
            posterior = i / (n - 1)  # 0..1 monotone
            same = posterior >= 0.5
            lines.append(
                json.dumps(
                    {
                        "event": "resolution.defer",
                        "left_id": f"l{i}",
                        "right_id": f"r{i}",
                        "posterior": posterior,
                    }
                )
            )
            truth.append({"left_id": f"l{i}", "right_id": f"r{i}", "same": same})
        events.write_text("\n".join(lines) + "\n")
        gt.write_text(json.dumps(truth))
        return events, gt

    def test_fit_write_load_roundtrip(self, tmp_path):
        events, gt = self._write_corpus(tmp_path)
        calibrator = fit_calibration_from_events(events, gt, min_observations=5)
        assert calibrator is not None
        artifact = tmp_path / "calib.json"
        artifact.write_text(calibrator.to_json())
        loaded = PosteriorCalibrator.from_json(artifact.read_text())
        # isotonic on a monotone label set: low posterior -> low, high -> high
        assert loaded.calibrate(0.05) <= loaded.calibrate(0.95)
        assert loaded.calibrate(0.95) >= 0.5

    def test_below_floor_returns_none(self, tmp_path):
        events, gt = self._write_corpus(tmp_path, n=4)
        assert fit_calibration_from_events(events, gt, min_observations=50) is None

    def test_resolver_loads_frozen_artifact_over_state(self, tmp_path):
        artifact = tmp_path / "frozen.json"
        frozen = PosteriorCalibrator([0.0, 1.0], [0.1, 0.9])
        artifact.write_text(frozen.to_json())
        settings = Settings()
        settings.resolution.calibration_path = str(artifact)
        foundry = Foundry(settings)
        # a different calibration lives in state; the frozen artifact must win
        state = {"calibration": PosteriorCalibrator([0.0, 1.0], [0.0, 1.0]).to_json()}
        calibrator = foundry._make_calibrator(state)
        assert abs(calibrator.calibrate(0.0) - 0.1) < 1e-9  # frozen curve, not state


# -- defaults -------------------------------------------------------------


class TestDefaults:
    def test_promoted_levers_default_on(self):
        cfg = ResolutionSettings()
        assert cfg.soft_links is True
        assert cfg.demotion_court is True

    def test_calibration_path_absent_by_default(self):
        assert ResolutionSettings().calibration_path is None

    def test_no_calibration_path_falls_back_to_state(self):
        foundry = Foundry(Settings())
        assert foundry._make_calibrator({}) is None
        state = {"calibration": PosteriorCalibrator([0.0, 1.0], [0.2, 0.8]).to_json()}
        assert foundry._make_calibrator(state) is not None

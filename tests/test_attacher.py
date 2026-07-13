"""R49 carrier attacher (H567/H568/H569) and render-staging primitive (H576).

Mocked LLM and driver - no live model or Neo4j.
"""

import json
from unittest.mock import MagicMock

import pytest

from knowledge_graph_foundry.graph.attacher import (
    FactSpan,
    attach,
    is_artifact,
    name_match,
    stage_fact_on_anchor,
)


class RecordingLLM:
    """Fake LLM: answers from a queue, records every prompt it is asked."""

    def __init__(self, *answers: str):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else ""


def _boom(prompt: str) -> str:  # llm that must never be called
    raise AssertionError("LLM should not be called on this rung")


class TestArtifactGate:
    def test_regex_miss_never_calls_llm(self):
        # a real fact does not match the boilerplate regex -> no LLM call
        assert is_artifact("Teutberga was the wife of Lothair II.", _boom) is False

    def test_regex_hit_confirmed_is_artifact(self):
        llm = RecordingLLM("yes")
        assert is_artifact("Smith may refer to:", llm) is True
        assert len(llm.prompts) == 1

    def test_regex_hit_denied_is_not_artifact(self):
        llm = RecordingLLM("no")
        assert is_artifact("List of French monarchs by reign", llm) is False


class TestNameMatch:
    def test_anchor_in_window_returns_longest(self):
        window = "Battle of Hastings. William defeated Harold at the Battle of Hastings."
        assert name_match(window, ["Harold", "Battle of Hastings"]) == "Battle of Hastings"

    def test_no_candidate_in_window_returns_none(self):
        assert name_match("A sentence about nothing.", ["Zurich", "Geneva"]) is None


class TestAttachLadder:
    FS = FactSpan(
        fact="The AirSense 11 covers 4 to 20 cmH2O.",
        span="The AirSense 11 covers a pressure range of 4 to 20 cmH2O.",
        doc_title="AirSense 11",
    )

    def test_name_match_fast_path_skips_llm(self):
        # candidate name is in the window -> resolved without any LLM call
        assert attach(self.FS, ["AirSense 11", "Humidifier"], _boom) == "AirSense 11"

    def test_artifact_abstains(self):
        fs = FactSpan(fact="Smith may refer to:", span="Smith may refer to:")
        llm = RecordingLLM("yes")  # boilerplate confirm
        assert attach(fs, ["Smith"], llm) is None

    def test_llm_attacher_when_no_name_match(self):
        fs = FactSpan(fact="It weighs 1.2 kg.", span="The device is light. It weighs 1.2 kg.")
        # not an artifact (regex miss -> no gate call), no name in span -> LLM picks
        llm = RecordingLLM("AirSense 11")
        assert attach(fs, ["AirSense 11", "Humidifier"], llm) == "AirSense 11"

    def test_llm_abstain_returns_none(self):
        fs = FactSpan(fact="It weighs 1.2 kg.", span="Unrelated preamble text here.")
        llm = RecordingLLM("ABSTAIN")
        assert attach(fs, ["AirSense 11"], llm) is None

    def test_llm_pick_mapped_to_canonical_candidate(self):
        fs = FactSpan(fact="It weighs 1.2 kg.", span="Preamble with no anchor name.")
        llm = RecordingLLM("  airsense 11  ")  # paraphrased casing/space
        assert attach(fs, ["AirSense 11"], llm) == "AirSense 11"


def _driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver, session


class TestStageFactOnAnchor:
    def test_appends_fact_and_records_provenance(self):
        driver, session = _driver()
        session.run.return_value.single.return_value = {"id": "e1", "description": "old\nnew fact"}

        out = stage_fact_on_anchor(
            driver, "e1", "new fact", source="doc#row3", timestamp="2026-07-14T00:00:00Z"
        )

        call = session.run.call_args
        assert call.kwargs["id"] == "e1"
        assert call.kwargs["fact"] == "new fact"
        assert call.kwargs["nl"] == "\n"
        marker = json.loads(call.kwargs["marker"])
        assert marker == {"fact": "new fact", "ts": "2026-07-14T00:00:00Z", "source": "doc#row3"}
        assert out["reembedded"] is False
        assert session.run.call_count == 1  # no embedding write

    def test_no_reembed_by_default(self):
        driver, session = _driver()
        session.run.return_value.single.return_value = {"id": "e1", "description": "d"}
        stage_fact_on_anchor(driver, "e1", "f")
        queries = [c.args[0] for c in session.run.call_args_list]
        assert not any("SET e.embedding" in q for q in queries)

    def test_reembed_writes_new_vector(self):
        driver, session = _driver()
        session.run.return_value.single.return_value = {"id": "e1", "description": "d\nf"}
        embed_fn = MagicMock(return_value=[0.1, 0.2, 0.3])

        out = stage_fact_on_anchor(driver, "e1", "f", reembed=True, embed_fn=embed_fn)

        embed_fn.assert_called_once_with("d\nf")
        emb_call = next(c for c in session.run.call_args_list if "SET e.embedding" in c.args[0])
        assert emb_call.kwargs["emb"] == [0.1, 0.2, 0.3]
        assert out["reembedded"] is True

    def test_reembed_without_embed_fn_raises(self):
        driver, session = _driver()
        session.run.return_value.single.return_value = {"id": "e1", "description": "d"}
        with pytest.raises(ValueError, match="embed_fn"):
            stage_fact_on_anchor(driver, "e1", "f", reembed=True)

    def test_missing_anchor_raises(self):
        driver, session = _driver()
        session.run.return_value.single.return_value = None
        with pytest.raises(ValueError, match="not found"):
            stage_fact_on_anchor(driver, "missing", "f")

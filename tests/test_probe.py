"""R49-H541 frozen-probe manifest: loading + ordering determinism."""

from knowledge_graph_foundry.probe import load_manifest, select_manifest
from knowledge_graph_foundry.settings import Settings


class TestLoadManifest:
    def test_json_list(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text('["q3", "q1", "q2"]')
        assert load_manifest(p) == ["q3", "q1", "q2"]

    def test_newline_delimited_with_comments(self, tmp_path):
        p = tmp_path / "m.txt"
        p.write_text("# frozen set\nq3\nq1\n\n  q2  \n")
        assert load_manifest(p) == ["q3", "q1", "q2"]

    def test_dedup_preserves_first_order(self, tmp_path):
        p = tmp_path / "m.txt"
        p.write_text("q1\nq2\nq1\nq3\nq2\n")
        assert load_manifest(p) == ["q1", "q2", "q3"]

    def test_empty_file(self, tmp_path):
        p = tmp_path / "m.txt"
        p.write_text("")
        assert load_manifest(p) == []


class TestSelectManifest:
    QUESTIONS = [
        {"_id": "q1", "question": "A"},
        {"_id": "q2", "question": "B"},
        {"_id": "q3", "question": "C"},
    ]

    def _id(self, q):
        return q["_id"]

    def test_selects_in_manifest_order_not_list_order(self):
        picked = select_manifest(self.QUESTIONS, ["q3", "q1"], self._id)
        assert [q["_id"] for q in picked] == ["q3", "q1"]

    def test_missing_ids_skipped(self):
        picked = select_manifest(self.QUESTIONS, ["q2", "nope", "q1"], self._id)
        assert [q["_id"] for q in picked] == ["q2", "q1"]

    def test_deterministic_across_calls(self):
        a = select_manifest(self.QUESTIONS, ["q3", "q2", "q1"], self._id)
        b = select_manifest(self.QUESTIONS, ["q3", "q2", "q1"], self._id)
        assert [q["_id"] for q in a] == [q["_id"] for q in b] == ["q3", "q2", "q1"]


class TestProbeSettings:
    def test_manifest_default_none(self):
        assert Settings().probe.manifest is None

    def test_manifest_override(self):
        s = Settings(probe={"manifest": "frozen.json"})
        assert s.probe.manifest == "frozen.json"

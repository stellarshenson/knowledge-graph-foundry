"""Benchmark scorer: HotpotQA-standard normalization, EM/F1, recall@5.

Worked examples follow the official HotpotQA evaluation semantics (the
squad-style normalize/EM/F1 the HippoRAG-2 peer table uses).
"""

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "bench_score", Path(__file__).parent.parent / "scripts" / "bench_score.py"
)
bench_score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench_score)


class TestNormalization:
    def test_articles_punctuation_case(self):
        assert bench_score.normalize_answer("The Beatles!") == "beatles"
        assert bench_score.normalize_answer("An  apple, a day.") == "apple day"

    def test_em_via_normalization(self):
        assert bench_score.exact_match("The Godfather", "godfather")
        assert not bench_score.exact_match("Godfather II", "godfather")


class TestF1:
    def test_partial_overlap(self):
        # pred {new, york, city} vs gold {new, york}: p=2/3 r=1 -> f1=0.8
        assert abs(bench_score.f1_score("New York City", "New York") - 0.8) < 1e-9

    def test_no_overlap_and_empty(self):
        assert bench_score.f1_score("Paris", "London") == 0.0
        assert bench_score.f1_score("", "") == 1.0  # both empty match

    def test_multi_gold_takes_best(self):
        em, f1 = bench_score.best_over_golds("NYC", ["New York", "NYC"])
        assert em == 1.0 and f1 == 1.0


class TestRecallAt5:
    def test_partial_and_order(self):
        retrieved = ["t1", "t2", "t3", "t4", "t5", "gold2"]
        assert bench_score.recall_at_k(retrieved, ["t1", "gold2"]) == 0.5  # gold2 at rank 6

    def test_full(self):
        assert bench_score.recall_at_k(["a", "b"], ["a", "b"]) == 1.0


class TestScoreFile:
    def test_aggregates(self, tmp_path):
        rows = [
            {"id": "q1", "answer": "The Beatles", "gold_answers": ["Beatles"],
             "retrieved_titles": ["a", "b"], "gold_titles": ["a"]},
            {"id": "q2", "answer": "Paris", "gold_answers": ["London"],
             "retrieved_titles": ["x"], "gold_titles": ["y"]},
        ]
        p = tmp_path / "answers.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        out = bench_score.score_file(p)
        assert out == {"n": 2, "em": 0.5, "f1": 0.5, "recall_at_5": 0.5}

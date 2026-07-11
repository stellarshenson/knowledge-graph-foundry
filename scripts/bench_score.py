"""Multi-hop QA benchmark scorer: EM / F1 + passage recall@5.

Pure offline pass over an answers JSONL produced by the QA adapter - one
record per question: {id, question, answer, gold_answers, retrieved_titles,
gold_titles}. Metrics follow the standard HotpotQA definitions (the ones the
HippoRAG-2 peer table uses): answers are normalized (lowercase, strip
punctuation and articles, squeeze whitespace) before EM / token-F1;
recall@5 = per-question share of gold supporting titles present in the top-5
retrieved, averaged over questions.

Usage: python scripts/bench_score.py results/bench/<dataset>-answers.jsonl
"""

import json
import re
import string
import sys
from collections import Counter
from pathlib import Path


def normalize_answer(s: str) -> str:
    """HotpotQA-standard normalization: lower, drop punctuation + articles."""
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def exact_match(prediction: str, gold: str) -> bool:
    return normalize_answer(prediction) == normalize_answer(gold)


def f1_score(prediction: str, gold: str) -> float:
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens or not gold_tokens:
        return float(pred_tokens == gold_tokens)
    common = Counter(pred_tokens) & Counter(gold_tokens)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def best_over_golds(prediction: str, golds: list[str]) -> tuple[float, float]:
    """Max EM / F1 over the gold answer aliases (standard multi-gold rule)."""
    em = max(float(exact_match(prediction, g)) for g in golds)
    f1 = max(f1_score(prediction, g) for g in golds)
    return em, f1


def recall_at_k(retrieved_titles: list[str], gold_titles: list[str], k: int = 5) -> float:
    if not gold_titles:
        return 0.0
    top = set(retrieved_titles[:k])
    return sum(1 for t in gold_titles if t in top) / len(gold_titles)


def score_file(path: Path) -> dict:
    n = em_sum = f1_sum = r5_sum = 0
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            golds = rec.get("gold_answers") or [rec["gold_answer"]]
            em, f1 = best_over_golds(rec.get("answer") or "", golds)
            em_sum += em
            f1_sum += f1
            r5_sum += recall_at_k(rec.get("retrieved_titles") or [], rec.get("gold_titles") or [])
            n += 1
    return {
        "n": n,
        "em": round(em_sum / n, 4) if n else 0.0,
        "f1": round(f1_sum / n, 4) if n else 0.0,
        "recall_at_5": round(r5_sum / n, 4) if n else 0.0,
    }


if __name__ == "__main__":
    out = score_file(Path(sys.argv[1]))
    print(json.dumps(out, indent=2))

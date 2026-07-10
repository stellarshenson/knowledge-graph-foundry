"""R38 gate calibration - per-corpus self-calibration of the escalation cut.

The H382 escalation gate's threshold is corpus-class-bound (H157): the
settings value is an a-priori prior, upgraded per corpus by conformal risk
control (R38-H383: exact finite-sample E[miss] <= alpha for the monotone
miss loss) over replay-labeled outcomes, and persisted in the control
metanode with provenance and a corpus fingerprint (R38-H384).
``fit_gate_from_events`` is the retrieval twin of
``resolution.calibration.fit_calibration_from_events`` (R38-H385): it joins
``query.answered`` events from a two-pass probe replay (never-escalate and
always-escalate) against the probe gold, labels each probe with the
cheapest rung that answered (Adaptive-RAG outcome labels), and fits the cut.

Thresholds are in Neo4j vector-index score units ((1 + cos) / 2), the same
scale as ``miss_threshold`` and ``abstention_min_score``.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

GATE_SIGNAL = "top_seed_index_score"
DEFAULT_ALPHA = 0.08  # H383: the feasibility floor on the 24-probe pinned ledger


def corpus_fingerprint(processed_documents: list[str]) -> str:
    """Order-invariant hash over the state's processed-document fingerprints;
    a persisted record carrying a different fingerprint was fitted on a
    different pile and must not be trusted (H157)."""
    joined = "|".join(sorted(processed_documents))
    return hashlib.sha1(joined.encode()).hexdigest()[:16]


def crc_fit_threshold(
    ledger: list[dict[str, Any]], alpha: float = DEFAULT_ALPHA
) -> tuple[float, bool]:
    """Conformal risk control fit: theta_hat = inf{theta : (n/(n+1))
    R_hat(theta) + 1/(n+1) <= alpha} over midpoint candidates of the sorted
    signals. ``ledger`` rows carry ``signal``, ``rung0_covered``,
    ``rung2_covered``. Returns (threshold, infeasible); an infeasible alpha
    degrades to always-escalate (cut above the signal range), never invalid."""
    n = len(ledger)
    vals = sorted(row["signal"] for row in ledger)
    cands = [vals[0] - 0.01]
    cands += [round((a + b) / 2, 5) for a, b in zip(vals, vals[1:])]
    cands.append(vals[-1] + 0.01)

    def risk(theta: float) -> float:
        misses = sum(
            not (row["rung2_covered"] if row["signal"] < theta else row["rung0_covered"])
            for row in ledger
        )
        return misses / n

    for theta in cands:
        if (n / (n + 1)) * risk(theta) + 1 / (n + 1) <= alpha:
            return theta, False
    return vals[-1] + 0.01, True


def build_record(
    threshold: float,
    alpha: float,
    n_labels: int,
    fingerprint: str,
    infeasible: bool = False,
) -> dict[str, Any]:
    """The persisted gate_calibration record - provenance block follows the
    identity-calibration-v2.json precedent so update-vs-refit is decidable
    later (the metadata whose absence made the H157 transfer silent)."""
    return {
        "version": 1,
        "threshold": threshold,
        "signal": GATE_SIGNAL,
        "provenance": {
            "hypothesis": "H382/H383",
            "method": "crc",
            "alpha": alpha,
            "n_labels": n_labels,
            "infeasible": infeasible,
            "fitted_at": datetime.now(timezone.utc).isoformat(),
            "corpus_fingerprint": fingerprint,
        },
    }


def _covered(answer: str, gold_evidence: list[str]) -> bool:
    """A rung's outcome: every gold evidence item appears in the answer."""
    text = answer.casefold()
    return all(g.casefold() in text for g in gold_evidence)


def fit_gate_from_events(
    events_path: Path | str,
    probes: list[dict[str, Any]],
    min_labels: int = 12,
    alpha: float = DEFAULT_ALPHA,
    fingerprint: str = "",
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    """Harvest gate labels from a two-pass probe replay's event log and fit
    the cut. Each probe must appear in two ``query.answered`` events: one
    with ``escalated`` false (rung-0 outcome) and one true (rung-2 outcome);
    the signal is the rung-0 pass's ``seed_top_score``. Probes missing either
    pass are skipped. Returns (ledger, record); record is None below the
    ``min_labels`` floor - the prior or existing record then stands."""
    gold = {p["question"]: p["gold_evidence"] for p in probes}
    passes: dict[str, dict[bool, dict[str, Any]]] = {}
    with open(events_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("event") != "query.answered" or rec.get("question") not in gold:
                continue
            passes.setdefault(rec["question"], {})[bool(rec.get("escalated"))] = rec

    ledger: list[dict[str, Any]] = []
    for question, by_arm in passes.items():
        if False not in by_arm or True not in by_arm:
            continue
        ledger.append(
            {
                "question": question,
                "signal": float(by_arm[False]["seed_top_score"]),
                "rung0_covered": _covered(by_arm[False]["answer"], gold[question]),
                "rung2_covered": _covered(by_arm[True]["answer"], gold[question]),
            }
        )

    if len(ledger) < min_labels:
        return ledger, None
    threshold, infeasible = crc_fit_threshold(ledger, alpha)
    return ledger, build_record(threshold, alpha, len(ledger), fingerprint, infeasible)

"""R48-H524 render token-waste audit + cross-channel sentence dedup.

SUBSTRATE-LIMITED partial execution on the medium bench pile: of the four
registered channels only TWO render here (entity blocks + H371 question
match) - escalation is inert on this config (gate off, passages off,
proposition index absent), so the registered escalated 4-channel render
cannot be produced. The audit still adjudicates the DOMAIN-KILL branch for
this substrate: measured waste < 10% of rendered tokens closes H525-H527
for the bench campaign.

Waste = boilerplate (empty Properties/Relations scaffolding) + near-duplicate
sentences (>= 0.9 Jaccard on 5-gram shingles; exact match for short
sentences), first occurrence kept. Dedup A/B replays the prober criterion on
the deduplicated render.

Registered: docs/experiments/kgf-redesign-experiments.md R48-H524.
Usage: python scripts/experiments/r48_h524_waste_audit.py [config] [questions] [max]
Writes: reports/experiments/r48/h524-waste-audit-<ts>.json
"""

import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import tiktoken  # noqa: E402
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402
from r48_h514_gate import crit_pass  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
ENC = tiktoken.get_encoding("cl100k_base")
SENT = re.compile(r"(?<=[.!?])\s+|\n+")
BOILER = re.compile(r"^(Properties: \{\}|Relations:\s*|Also known as:\s*)$")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def channel(block: str) -> str:
    if block.startswith("## Question match:"):
        return "question"
    if block.startswith("## Source excerpt"):
        return "passage"
    if block.startswith("## Facts"):
        return "facts"
    return "entity"


def shingles(s: str) -> set:
    w = _norm(s).split()
    if len(w) < 5:
        return {" ".join(w)} if w else set()
    return {" ".join(w[i:i + 5]) for i in range(len(w) - 4)}


def near_dup(a: set, b: set) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / len(a | b) >= 0.9


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    rows = []
    with Foundry(st) as f:
        titles = ingested_titles(f, load_slices())
        full = [
            q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"h524 {run_id}: {len(eligible)} eligible probes", flush=True)

        for k, q in enumerate(eligible):
            try:
                res = f.probe(q["question"])
            except Exception as exc:
                print(f"probe error: {exc}", flush=True)
                continue
            blocks = res["context_lines"]
            total = sum(toks(b) for b in blocks)
            base_pass = crit_pass(q, blocks)

            # sentence inventory: (channel, sentence, shingles, tokens)
            inv = []
            for b in blocks:
                ch = channel(b)
                for sent in SENT.split(b):
                    sent = sent.strip()
                    if not sent:
                        continue
                    inv.append((ch, sent, shingles(sent), toks(sent)))

            boiler_toks = sum(tk for _, s, _, tk in inv if BOILER.match(s))
            kept, dup_toks, cross_toks = [], 0, 0
            for ch, sent, sh, tk in inv:
                if BOILER.match(sent):
                    continue
                hit = next((k2 for k2 in kept if near_dup(sh, k2[2])), None)
                if hit is not None:
                    dup_toks += tk
                    if hit[0] != ch:
                        cross_toks += tk
                else:
                    kept.append((ch, sent, sh, tk))

            dedup_blocks = []  # rebuild per block, dropping boiler + later dups
            seen: list[set] = []
            for b in blocks:
                out_lines = []
                for sent in SENT.split(b):
                    s = sent.strip()
                    if not s or BOILER.match(s):
                        continue
                    sh = shingles(s)
                    if any(near_dup(sh, s2) for s2 in seen):
                        continue
                    seen.append(sh)
                    out_lines.append(s)
                if out_lines:
                    dedup_blocks.append("\n".join(out_lines))
            dedup_total = sum(toks(b) for b in dedup_blocks)
            dedup_pass = crit_pass(q, dedup_blocks)

            rows.append({
                "id": q.get("_id") or q["question"][:60],
                "total_tokens": total,
                "waste_fraction": round((boiler_toks + dup_toks) / total, 4) if total else 0,
                "dup_fraction": round(dup_toks / total, 4) if total else 0,
                "cross_channel_fraction": round(cross_toks / total, 4) if total else 0,
                "boiler_fraction": round(boiler_toks / total, 4) if total else 0,
                "dedup_reduction": round(1 - dedup_total / total, 4) if total else 0,
                "pass": base_pass,
                "dedup_pass": dedup_pass,
            })
            if (k + 1) % 20 == 0:
                print(f"[{k+1}/{len(eligible)}] audited", flush=True)

    med = lambda key: round(statistics.median(r[key] for r in rows), 4) if rows else None  # noqa: E731
    summary = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n": len(rows),
        "channels_rendered": ["entity", "question"],
        "substrate_note": "escalation inert on this pile (gate off, passages off, "
        "proposition index absent) - registered 4-channel escalated render unavailable",
        "median_waste_fraction": med("waste_fraction"),
        "median_dup_fraction": med("dup_fraction"),
        "median_cross_channel_fraction": med("cross_channel_fraction"),
        "median_boiler_fraction": med("boiler_fraction"),
        "median_dedup_reduction": med("dedup_reduction"),
        "base_pass": sum(r["pass"] for r in rows),
        "dedup_pass": sum(r["dedup_pass"] for r in rows),
        "bars": {"domain_kill_waste_lt": 0.10, "confirmed_reduction_ge": 0.25},
    }
    out = Path("reports/experiments/r48")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"h524-waste-audit-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

"""Local-LLM token ledger - what the equipment saved us.

Snapshots the vLLM lifetime counters (prompt/generation) into an append-only
JSONL and regenerates the human summary in docs/token-ledger.md. Counters
reset on server restart, so each snapshot carries the engine instance
identity (vLLM process start time); a new instance banks the previous one's
final reading and cumulation continues monotonically.

Pricing: the Bedrock counterfactual is KGF's default frontier config
(Claude Sonnet 4.5: $3/M input, $15/M output); Haiku 4.5 ($1/$5) shown as
the cheap-tier comparison.

Usage: python scripts/token_ledger.py [note]   - run at scale boundaries,
before/after vLLM restarts, and at journal milestones.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

METRICS_URL = "http://localhost:8010/metrics"  # NOTE: sibling parsers in scripts/r30_fast_ramp.py + r30_gpu_ramp.py - keep prefix logic in sync
LEDGER = Path("results/token-ledger.jsonl")
DOC = Path("docs/token-ledger.md")
# manual pre-ledger estimate: R30 slow-ramp measurement windows (recorded
# counter deltas, warmups excluded) burned before the ledger existed
BACKFILL = {"prompt": 7_100_000, "generation": 12_000_000, "note": "pre-ledger backfill: H363 slow-ramp windows (recorded deltas, warmups/drains excluded - conservative)"}

SONNET = (3.0, 15.0)  # $/M input, $/M output
HAIKU = (1.0, 5.0)


def read_counters() -> dict:
    with urllib.request.urlopen(METRICS_URL, timeout=5) as r:
        text = r.read().decode()
    out = {}
    for line in text.splitlines():
        if line.startswith("vllm:prompt_tokens_total"):
            out["prompt"] = out.get("prompt", 0.0) + float(line.rsplit(" ", 1)[1])
        elif line.startswith("vllm:generation_tokens_total"):
            out["generation"] = out.get("generation", 0.0) + float(line.rsplit(" ", 1)[1])
        elif line.startswith("process_start_time_seconds"):
            out["instance"] = line.rsplit(" ", 1)[1]
    return out


def snapshots() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(ln) for ln in LEDGER.read_text().splitlines() if ln.strip()]


def cumulative(snaps: list[dict]) -> tuple[float, float]:
    """Sum per-instance maxima + backfill - monotone across restarts."""
    per: dict[str, tuple[float, float]] = {}
    for s in snaps:
        cur = per.get(s["instance"], (0.0, 0.0))
        per[s["instance"]] = (max(cur[0], s["prompt"]), max(cur[1], s["generation"]))
    p = sum(v[0] for v in per.values()) + BACKFILL["prompt"]
    g = sum(v[1] for v in per.values()) + BACKFILL["generation"]
    return p, g


def cost(p: float, g: float, rate: tuple[float, float]) -> float:
    return p / 1e6 * rate[0] + g / 1e6 * rate[1]


def render(snaps: list[dict]) -> None:
    p, g = cumulative(snaps)
    lines = [
        "# Local-LLM Token Ledger",
        "",
        "Running tally of tokens served by the local gpt-oss-120b (vLLM, own GPU) that would otherwise bill against Bedrock - the equipment's savings, stated internally. Maintained by `scripts/token_ledger.py` at scale boundaries and milestones; raw snapshots in `results/token-ledger.jsonl` (instance-aware - counters reset on server restart and are banked per instance).",
        "",
        f"- **Cumulative** - {p/1e6:.1f}M prompt + {g/1e6:.1f}M generation = **{(p+g)/1e6:.1f}M tokens** (incl. {(BACKFILL['prompt']+BACKFILL['generation'])/1e6:.1f}M conservative pre-ledger backfill)",
        f"- **Saved vs Claude Sonnet 4.5 on Bedrock** (\\$3/M in, \\$15/M out - KGF's default frontier config): **\\${cost(p, g, SONNET):,.0f}**",
        f"- **Saved vs Claude Haiku 4.5** (\\$1/M in, \\$5/M out): \\${cost(p, g, HAIKU):,.0f}",
        f"- **Marginal local cost** - GPU power only, single-digit dollars",
        "",
        "| when (UTC) | instance tokens (P/G) | cumulative | Sonnet-equiv | note |",
        "|---|---|---|---|---|",
    ]
    seen: list[dict] = []
    for s in snaps:
        seen.append(s)
        cp, cg = cumulative(seen)
        lines.append(
            f"| {s['ts']} | {s['prompt']/1e6:.1f}M / {s['generation']/1e6:.1f}M | {(cp+cg)/1e6:.1f}M | ${cost(cp, cg, SONNET):,.0f} | {s.get('note','')} |"
        )
    DOC.write_text("\n".join(lines) + "\n")


def main():
    note = " ".join(sys.argv[1:]) or "snapshot"
    c = read_counters()
    snap = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "instance": c.get("instance", "unknown"),
        "prompt": c.get("prompt", 0.0),
        "generation": c.get("generation", 0.0),
        "note": note,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(snap) + "\n")
    snaps = snapshots()
    render(snaps)
    p, g = cumulative(snaps)
    print(
        f"ledger: +{snap['prompt']/1e6:.1f}M/{snap['generation']/1e6:.1f}M this instance; "
        f"cumulative {(p+g)/1e6:.1f}M tokens = ${cost(p, g, SONNET):,.0f} Sonnet-equivalent -> {DOC}"
    )


if __name__ == "__main__":
    main()

"""R49-H570 carrier-scorer transfer to render-time block selection.

Tests whether the bakeoff-winning carrier scorer (the H568 gpt-oss LLM attacher)
transfers from ATTACH-time to RENDER-time: scoring the LIVE rendered blocks of a
probe by carrier-relevance to the question and selecting the answer-bearing blocks
inside a <= 0.5x-render-token budget. Baselines at the SAME budget: degree ranking
(block entity degree), PageRank ranking (global PR over the medium entity graph),
random.

Substrate: the 132 medium 2wiki probes (config-bench-medium.yml, H382 gate ACTIVE
in the probe path). Renders regenerated LIVE via Foundry.probe (READ-ONLY) - the
H514 gate captured only aggregate per-probe metrics, not block lists, so block-level
detail is regenerated here.

Gold (answer-bearing) block per probe:
  - non yes/no: block whose text contains the gold answer (h158 _present, the
    shipped prober's presence test)
  - yes/no: block whose text contains a gold supporting title
Scorable probe = full-render criterion passes AND >= 1 gold block.

Budget = 0.5 * total render tokens (tiktoken cl100k_base, same enc as H514).
Recall-at-budget per arm = |selected gold| / |gold|, greedy top-rank fill.

LLM arm scores ALL blocks in ONE prompt (H568 attacher shape: question + numbered
blocks -> ranked block ids, ABSTAIN-aware). gpt-oss reasons in a separate channel:
max_tokens headroom + reasoning_content fallback, temp 0.

Registered: docs/experiments/kgf-redesign-experiments.md R49-H570.
Bars: CONFIRMED if LLM recall-at-budget >= 0.85 AND beats degree AND PageRank by
>= 8 pts. KILLED if LLM <= degree or <= random.

Usage: python scripts/experiments/r49_h570_carrier_render.py
Writes: reports/experiments/r49/h570-carrier-render-<ts>.json (+ .partial.jsonl)
"""

import json
import random
import re
import zlib
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import networkx as nx  # noqa: E402
import requests  # noqa: E402
import tiktoken  # noqa: E402
from h158_measure import _norm, _present  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path("config/experiments/config-bench-medium.yml")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
VLLM = "http://localhost:8010/v1/chat/completions"
BUDGET_FRAC = 0.5
ENC = tiktoken.get_encoding("cl100k_base")
HEADER = re.compile(r"^## (.+?) \(")
NON_ENTITY = ("## Facts", "## Source excerpt", "## Question match:")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def block_name(block: str) -> str | None:
    """The rendered entity name for a block, or None for non-entity blocks
    (Facts / Source excerpt / Question match)."""
    if block.startswith(NON_ENTITY):
        return None
    m = HEADER.match(block)
    return m.group(1) if m else None


def crit_pass(q: dict, blocks: list[str]) -> bool:
    text = _norm(" ".join(blocks))
    golds = gold_titles(q)
    yesno = (q.get("answer") or "").strip().lower() in ("yes", "no")
    if yesno:
        return bool(golds) and all(_present(t, text) for t in golds)
    return bool(_present(q.get("answer", ""), text))


def block_is_gold(q: dict, block: str) -> bool:
    text = _norm(block)
    yesno = (q.get("answer") or "").strip().lower() in ("yes", "no")
    if yesno:
        return any(_present(t, text) for t in gold_titles(q))
    return bool(_present(q.get("answer", ""), text))


def llm_rank(question: str, blocks: list[str]) -> list[int]:
    """H568-attacher-shaped render-time carrier scorer: one prompt ranks all
    blocks by carrier-relevance to the probe. Returns block indices most-relevant
    first; unlisted blocks appended in original order so the budget still fills."""
    listing = "\n\n".join(f"[BLOCK {i}]\n{b}" for i, b in enumerate(blocks))
    prompt = (
        f"Question: \"{question}\"\n\n"
        f"Rendered context blocks:\n{listing}\n\n"
        "Rank the blocks by how much each one CARRIES information needed to answer "
        "the question (its relevance as the answer's subject/evidence). "
        "Return ONLY a comma-separated list of block numbers, most relevant first, "
        "listing every block number exactly once. Example: 3,0,5,1,2,4"
    )
    try:
        r = requests.post(VLLM, json={
            "model": "gpt-oss-120b", "temperature": 0, "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]}, timeout=600)
        r.raise_for_status()
        m = r.json()["choices"][0]["message"]
        text = m.get("content") or m.get("reasoning_content") or ""
    except Exception as exc:
        print(f"  llm error: {exc}", flush=True)
        text = ""
    # parse the last line that looks like a list of block numbers
    order: list[int] = []
    for line in reversed(text.strip().splitlines()):
        nums = [int(x) for x in re.findall(r"\d+", line)]
        nums = [n for n in nums if 0 <= n < len(blocks)]
        if nums:
            order = nums
            break
    seen: set[int] = set()
    ranked: list[int] = []
    for i in order:
        if i not in seen:
            seen.add(i)
            ranked.append(i)
    for i in range(len(blocks)):  # append any block the model omitted
        if i not in seen:
            ranked.append(i)
    return ranked


def select_at_budget(order: list[int], tok: list[int], budget: int) -> set[int]:
    """Greedy fill: add blocks in rank order while cumulative tokens <= budget."""
    chosen: set[int] = set()
    used = 0
    for i in order:
        if used + tok[i] <= budget:
            chosen.add(i)
            used += tok[i]
    return chosen


def recall(chosen: set[int], gold: list[int]) -> float | None:
    if not gold:
        return None
    return round(sum(1 for g in gold if g in chosen) / len(gold), 4)


def build_centrality(session) -> tuple[dict[str, int], dict[str, float]]:
    """Global degree + PageRank over the live entity graph (valid edges,
    SIMILAR_TO excluded). Keyed by normalized entity name (max on collision)."""
    rows = session.run(
        "MATCH (a:Entity)-[r]-(b:Entity) "
        "WHERE r.valid_to IS NULL AND type(r) <> 'SIMILAR_TO' "
        "RETURN a.name AS a, b.name AS b"
    ).data()
    g = nx.Graph()
    for row in rows:
        a, b = row["a"], row["b"]
        if a and b and a != b:
            g.add_edge(_norm(a), _norm(b))
    deg = {n: g.degree(n) for n in g.nodes}
    pr = nx.pagerank(g) if g.number_of_nodes() else {}
    return deg, pr


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("reports/experiments/r49")
    outdir.mkdir(parents=True, exist_ok=True)
    partial = outdir / f"h570-carrier-render-{run_id}.partial.jsonl"
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None

    rows = []
    with Foundry(st) as f:
        with f.driver.session() as s:
            deg, pr = build_centrality(s)
        print(f"h570 {run_id}: centrality over {len(deg)} entities", flush=True)
        titles = ingested_titles(f, load_slices())
        eligible = [
            q for q in questions
            if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        print(f"h570 {run_id}: {len(eligible)} eligible probes", flush=True)

        with partial.open("a") as ckpt:
            for k, q in enumerate(eligible):
                qid = q.get("_id") or q["question"][:60]
                try:
                    res = f.probe(q["question"])
                except Exception as exc:
                    print(f"probe error {qid}: {exc}", flush=True)
                    continue
                blocks = res["context_lines"]
                tok = [toks(b) for b in blocks]
                total = sum(tok)
                base = crit_pass(q, blocks)
                gold = [i for i, b in enumerate(blocks) if block_is_gold(q, b)]
                row = {
                    "id": qid, "yesno": (q.get("answer") or "").strip().lower() in ("yes", "no"),
                    "n_blocks": len(blocks), "total_tokens": total,
                    "base_pass": base, "n_gold": len(gold),
                    "escalated": res["coverage"].get("escalated"),
                }
                if not (base and len(gold) >= 1 and total):
                    row["scorable"] = False
                    rows.append(row)
                    ckpt.write(json.dumps(row) + "\n")
                    ckpt.flush()
                    print(f"[{k+1}/{len(eligible)}] {qid} scorable=False "
                          f"(base={base} n_gold={len(gold)})", flush=True)
                    continue
                budget = int(BUDGET_FRAC * total)
                # arm orderings
                names = [block_name(b) for b in blocks]
                deg_order = sorted(range(len(blocks)),
                                   key=lambda i: (-(deg.get(_norm(names[i]), -1)
                                                    if names[i] else -1), i))
                pr_order = sorted(range(len(blocks)),
                                  key=lambda i: (-(pr.get(_norm(names[i]), -1.0)
                                                   if names[i] else -1.0), i))
                rnd = random.Random(zlib.crc32(qid.encode()))
                rand_order = list(range(len(blocks)))
                rnd.shuffle(rand_order)
                llm_order = llm_rank(q["question"], blocks)

                arms = {"llm": llm_order, "degree": deg_order,
                        "pagerank": pr_order, "random": rand_order}
                recalls = {}
                shipped = {}
                for arm, order in arms.items():
                    chosen = select_at_budget(order, tok, budget)
                    recalls[arm] = recall(chosen, gold)
                    shipped[arm] = sum(tok[i] for i in chosen)
                row.update({
                    "scorable": True, "budget_tokens": budget,
                    "recall": recalls, "shipped_tokens": shipped,
                    "llm_order": llm_order, "gold_blocks": gold,
                })
                rows.append(row)
                ckpt.write(json.dumps(row) + "\n")
                ckpt.flush()
                print(f"[{k+1}/{len(eligible)}] {qid} scorable "
                      f"llm={recalls['llm']} deg={recalls['degree']} "
                      f"pr={recalls['pagerank']} rnd={recalls['random']}", flush=True)

    scor = [r for r in rows if r.get("scorable")]
    def mean_arm(arm):
        vals = [r["recall"][arm] for r in scor if r["recall"][arm] is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    rpa = {a: mean_arm(a) for a in ("llm", "degree", "pagerank", "random")}
    llm_r = rpa["llm"] or 0.0
    beat_deg = round(llm_r - (rpa["degree"] or 0.0), 4)
    beat_pr = round(llm_r - (rpa["pagerank"] or 0.0), 4)
    beat_rnd = round(llm_r - (rpa["random"] or 0.0), 4)

    clauses = [
        {"clause": "LLM carrier recall-at-budget >= 0.85", "predicted": ">=0.85",
         "measured": llm_r, "holds": llm_r >= 0.85},
        {"clause": "LLM beats degree ranking by >= 8 pts", "predicted": ">=0.08",
         "measured": beat_deg, "holds": beat_deg >= 0.08},
        {"clause": "LLM beats PageRank ranking by >= 8 pts", "predicted": ">=0.08",
         "measured": beat_pr, "holds": beat_pr >= 0.08},
        {"clause": "KILL guard: LLM > degree AND LLM > random", "predicted": ">0",
         "measured": {"vs_degree": beat_deg, "vs_random": beat_rnd},
         "holds": beat_deg > 0 and beat_rnd > 0},
    ]
    confirmed = clauses[0]["holds"] and clauses[1]["holds"] and clauses[2]["holds"]
    killed = (rpa["degree"] is not None and llm_r <= rpa["degree"]) or \
             (rpa["random"] is not None and llm_r <= rpa["random"])
    verdict = "CONFIRMED" if confirmed else ("KILLED" if killed else "INCONCLUSIVE")

    # token accounting: LLM must READ the full render to rank (no read-cost
    # saving at render time); all arms SHIP <= 0.5x. report both honestly.
    ship_frac = {}
    for a in ("llm", "degree", "pagerank", "random"):
        fr = [r["shipped_tokens"][a] / r["total_tokens"]
              for r in scor if r["total_tokens"]]
        ship_frac[a] = round(statistics.fmean(fr), 4) if fr else None

    summary = {
        "run_id": run_id, "config": str(CONFIG),
        "n_eligible": len(rows), "n_scorable": len(scor),
        "budget_fraction": BUDGET_FRAC,
        "recall_at_budget_per_arm": rpa,
        "llm_minus_degree": beat_deg, "llm_minus_pagerank": beat_pr,
        "llm_minus_random": beat_rnd,
        "mean_shipped_token_fraction_per_arm": ship_frac,
        "token_accounting_note": (
            "all arms SHIP <= 0.5x render tokens (budget); the LLM arm additionally "
            "READS the full render (~1.0x) to produce its ranking, so render-time it "
            "saves the shipped/downstream cost, not the read cost. degree/pagerank "
            "rankings are precomputed offline (0 marginal LLM tokens)."),
        "oracle_reference": {
            "source": "reports/experiments/r48/h530-decomp-20260713T094447Z.json",
            "oracle_decomposed_context": 0.909, "at_token_fraction": 0.52,
            "subq_coverage_top1": 0.3343},
        "clauses": clauses,
        "proposed_verdict": verdict,
        "bars": {
            "CONFIRMED": "LLM recall-at-budget >= 0.85 AND beats degree AND pagerank by >= 8 pts",
            "KILLED": "LLM <= degree OR LLM <= random"},
    }
    out = {"summary": summary, "rows": rows}
    path = outdir / f"h570-carrier-render-{run_id}.json"
    path.write_text(json.dumps(out, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

"""R48 H516-H519 balance sweep: Leiden gamma sweep x community-bounded rendering.

One shared FREE sweep adjudicates the BALANCE domain. Per gamma in {1,2,4,8}:
gds.leiden.write (writeProperty cid_g<N>) on the medium pile, community size
stats {count, modularity, size Gini, max, median, p95}. Then every eligible
question is probed ONCE (shipped pipeline, H382 gate active) and its render
replayed offline under each arm:
  baseline  - uncapped shipped render
  cap_g<N>  - keep blocks whose entity shares the top seed's cid_g<N>
  doc_cap   - H518 heresy: keep blocks whose entity shares >= 1 source doc
              with the top seed ((e)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(d))
Per arm: prober-criterion pass rate + render tokens p50/p95/p99. The
mandatory user metrics table prints at the end and lands in the JSON.
EM/F1 columns: absent by design - no reader in this loop (noted per bar).
Size-constrained Leiden arm: SKIPPED - this GDS build rejects
maxCommunitySize on gds.leiden (recorded, not hidden).

H515 consequence honored: arms are render caps only, propagation untouched.

Registered: docs/experiments/kgf-redesign-experiments.md R48-H516..H519.
Usage: python scripts/experiments/r48_h516_balance_sweep.py [config] [questions] [max]
Writes: reports/experiments/r48/h516-balance-sweep-<ts>.json
"""

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import tiktoken  # noqa: E402
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402
from r48_h514_gate import HEADER, crit_pass  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
GAMMAS = [1.0, 2.0, 4.0, 8.0]
ENC = tiktoken.get_encoding("cl100k_base")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def gini(sizes: list[int]) -> float:
    xs = sorted(sizes)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return round((2 * cum) / (n * sum(xs)) - (n + 1) / n, 4)


def pct(vals: list[int], p: float) -> int:
    if not vals:
        return 0
    xs = sorted(vals)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def leiden(session, prop: str, gamma: float) -> dict:
    session.run("CALL gds.graph.drop('kgf_sweep', false)").consume()
    session.run(
        "CALL gds.graph.project('kgf_sweep','Entity',"
        "{ALL:{type:'*',orientation:'UNDIRECTED'}})"
    ).consume()
    rec = session.run(
        "CALL gds.leiden.write('kgf_sweep',{writeProperty:$prop, gamma:$g}) "
        "YIELD communityCount, modularity",
        prop=prop, g=gamma,
    ).single()
    sizes = [
        r["n"] for r in session.run(
            f"MATCH (e:Entity) WHERE e.`{prop}` IS NOT NULL "
            f"WITH e.`{prop}` AS c, count(*) AS n RETURN n"
        )
    ]
    session.run("CALL gds.graph.drop('kgf_sweep', false)").consume()
    return {
        "gamma": gamma,
        "communities": rec["communityCount"],
        "modularity": round(rec["modularity"], 4),
        "size_gini": gini(sizes),
        "max_size": max(sizes),
        "median_size": statistics.median(sizes),
        "p95_size": pct(sizes, 0.95),
    }


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    with Foundry(st) as f:
        with f.driver.session() as s:
            stats = []
            gprops = {}
            for g in GAMMAS:
                prop = f"cid_g{int(g*10)}"
                gprops[g] = prop
                stats.append(leiden(s, prop, g))
                print(f"leiden gamma={g}: {stats[-1]}", flush=True)
            cid_maps = {
                g: {
                    _norm(r["name"]): r["c"]
                    for r in s.run(
                        f"MATCH (e:Entity) WHERE e.`{p}` IS NOT NULL "
                        f"RETURN e.name AS name, e.`{p}` AS c"
                    )
                }
                for g, p in gprops.items()
            }
            docs_map: dict[str, set] = {}
            for r in s.run(
                "MATCH (e:Entity)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(d:KGFDocument) "
                "RETURN e.name AS name, collect(DISTINCT d.name) AS docs"
            ):
                docs_map[_norm(r["name"])] = set(r["docs"])

        titles = ingested_titles(f, load_slices())
        full = [
            q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"h516 sweep {run_id}: {len(eligible)} eligible probes", flush=True)

        arms = ["baseline"] + [f"cap_g{int(g*10)}" for g in GAMMAS] + ["doc_cap"]
        agg = {a: {"pass": 0, "n": 0, "tokens": []} for a in arms}
        for k, q in enumerate(eligible):
            try:
                res = f.probe(q["question"])
            except Exception as exc:
                print(f"probe error {q.get('_id')}: {exc}", flush=True)
                continue
            blocks = res["context_lines"]
            top_seed = _norm(res["supporting_names"][0]) if res["supporting_names"] else None
            names = [
                (_norm(m.group(1)) if (m := HEADER.match(b)) else None) for b in blocks
            ]

            def arm_blocks(keep_fn):
                return [
                    b for b, nm in zip(blocks, names)
                    if nm is None or keep_fn(nm)  # headerless (Facts/passages) always kept
                ]

            variants = {"baseline": blocks}
            for g in GAMMAS:
                cm = cid_maps[g]
                tc = cm.get(top_seed)
                variants[f"cap_g{int(g*10)}"] = (
                    arm_blocks(lambda nm, cm=cm, tc=tc: cm.get(nm) == tc)
                    if tc is not None else blocks
                )
            tdocs = docs_map.get(top_seed, set())
            variants["doc_cap"] = (
                arm_blocks(lambda nm, td=tdocs: bool(docs_map.get(nm, set()) & td))
                if tdocs else blocks
            )
            for a, bl in variants.items():
                agg[a]["n"] += 1
                agg[a]["pass"] += bool(crit_pass(q, bl))
                agg[a]["tokens"].append(sum(toks(b) for b in bl))
            if (k + 1) % 20 == 0:
                print(f"[{k+1}/{len(eligible)}] probed", flush=True)

    table = []
    for a in arms:
        d = agg[a]
        table.append({
            "arm": a,
            "n": d["n"],
            "pass_rate": round(d["pass"] / d["n"], 4) if d["n"] else None,
            "passes": d["pass"],
            "tokens_p50": pct(d["tokens"], 0.50),
            "tokens_p95": pct(d["tokens"], 0.95),
            "tokens_p99": pct(d["tokens"], 0.99),
        })
    out = {
        "run_id": run_id,
        "config": str(CONFIG),
        "community_stats": stats,
        "arms": table,
        "notes": [
            "EM/F1 absent by design: no reader in the loop; criterion = prober answer_in_context instrument",
            "size-constrained Leiden arm SKIPPED: GDS build rejects maxCommunitySize on gds.leiden",
            "arms are render caps only (H515: propagation masking falsified)",
            "recall@16 seed-level reference: dense_seed_gold_recall 0.433 (h515 report), arm-independent",
        ],
    }
    outdir = Path("reports/experiments/r48")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"h516-balance-sweep-{run_id}.json"
    path.write_text(json.dumps(out, indent=1))

    print("\n| setting | communities | modularity | Gini | max/median | p95 |", flush=True)
    print("|---|---|---|---|---|---|", flush=True)
    for srow in stats:
        print(f"| gamma={srow['gamma']} | {srow['communities']} | {srow['modularity']} "
              f"| {srow['size_gini']} | {srow['max_size']}/{srow['median_size']} "
              f"| {srow['p95_size']} |", flush=True)
    print("\n| arm | pass rate | tokens p50 | p95 | p99 |", flush=True)
    print("|---|---|---|---|---|", flush=True)
    for row in table:
        print(f"| {row['arm']} | {row['pass_rate']} ({row['passes']}/{row['n']}) "
              f"| {row['tokens_p50']} | {row['tokens_p95']} | {row['tokens_p99']} |",
              flush=True)
    print(f"\nWROTE {path}", flush=True)


if __name__ == "__main__":
    main()

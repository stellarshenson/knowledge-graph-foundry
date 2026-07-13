"""R50-H585 relation-linker feasibility gate.

Can the gold query-implied relation vocabulary (mother, father, director, date
of death, ...) be ALIGNED to the native extracted relation-type vocabulary of
the medium graph above a usable cosine threshold? This is a vocabulary-
alignability census - a prerequisite for any non-oracle relation mechanism
(H592/H593), NOT a retrieval mechanism itself (H468 refuted relation boosting
at fanout; this measures whether the vocabularies are even mappable).

Bar (registered): >= 60% of distinct gold evidence relation types align
(name+context cosine >= 0.6) to a native edge type at a threshold yielding
<= 20% false-alignment on a 30-pair hand-checked sample -> OPEN; < 40%
coverage at any usable threshold -> KILL / GATE-BEHIND-CONSOLIDATION.

Machinery:
  - Native vocab: MATCH ()-[r]->() WHERE type(r) <> 'SIMILAR_TO' on the medium
    graph (bolt://172.19.0.9:7687, READ-ONLY). One example triple per type.
  - Gold vocab: 2wiki gold evidence triples ([subject, relation, object]) for
    the medium corpus; eligible = questions whose gold titles are all ingested
    (r48 convention). Per-relation question counts + one example gold triple.
  - Embeddings: Bedrock Titan v2 (r47/r48 convention) over relation NAMES and a
    CONTEXT form (name + one example triple verbalized). Both arms reported.
  - Alignment matrix: gold x native cosine; threshold sweep; unweighted +
    question-weighted coverage; exact/normalized string-match baseline.
  - 30-pair hand-check: candidates emitted for deterministic human judgment of
    false-alignment (does the native type's example triple express the gold
    relation?); verdicts injected via tmp/results/r50/handcheck_verdicts.json.

Registered: docs/experiments/kgf-redesign-experiments.md R50-H585.
Usage: .venv/bin/python scripts/experiments/r50_h585_relation_linker.py
Writes: reports/experiments/r50/h585-relation-linker-<ts>.json
"""

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from neo4j import GraphDatabase

sys.path.insert(0, "scripts/experiments")
sys.path.insert(0, "notebooks")
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry.extraction.embeddings import _embed_bedrock_texts  # noqa: E402

NEO4J = ("bolt://172.19.0.9:7687", "neo4j", "kgfoundry")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
TITAN = "amazon.titan-embed-text-v2:0"
CACHE = Path("tmp/results/r50")
OUT = Path("reports/experiments/r50")
VERDICTS = CACHE / "handcheck_verdicts.json"
THRESHOLDS = [round(0.40 + 0.05 * i, 2) for i in range(11)]  # 0.40 .. 0.90


def hum(t: str) -> str:
    return t.lower().replace("_", " ").strip()


def norm(t: str) -> str:
    return " ".join(hum(t).split())


# ------------------------------------------------------------------ native vocab
def load_native() -> tuple[list[dict], dict]:
    """All native types (excl SIMILAR_TO) + example triple + reconciliation stats."""
    cache = CACHE / "native_vocab.json"
    drv = GraphDatabase.driver(NEO4J[0], auth=(NEO4J[1], NEO4J[2]))
    with drv.session() as s:
        rows = s.run(
            "MATCH ()-[r]->() WHERE type(r) <> 'SIMILAR_TO' "
            "RETURN type(r) AS t, count(*) AS c ORDER BY c DESC"
        ).data()
        native = []
        for row in rows:
            t = row["t"]
            ex = s.run(
                f"MATCH (a:Entity)-[r:`{t}`]->(b:Entity) "
                "RETURN a.name AS s, b.name AS o LIMIT 1"
            ).single()
            if not ex:
                ex = s.run(
                    f"MATCH (a)-[r:`{t}`]->(b) RETURN "
                    "coalesce(a.name, head(labels(a))) AS s, "
                    "coalesce(b.name, head(labels(b))) AS o LIMIT 1"
                ).single()
            native.append({
                "type": t, "count": row["c"],
                "ex_s": ex["s"] if ex else None, "ex_o": ex["o"] if ex else None,
            })
        # reconciliation: entity-entity semantic subset vs full
        ee = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) WHERE type(r) <> 'SIMILAR_TO' "
            "RETURN type(r) AS t, count(*) AS c"
        ).data()
    drv.close()

    def entropy(counts):
        tot = sum(counts)
        return round(-sum((c / tot) * math.log2(c / tot) for c in counts if c > 0), 3)

    full_counts = [n["count"] for n in native]
    ee_counts = [r["c"] for r in ee]
    stats = {
        "full_query": "MATCH ()-[r]->() WHERE type(r) <> 'SIMILAR_TO'",
        "full_distinct_types": len(native),
        "full_total_edges": sum(full_counts),
        "full_entropy_bits": entropy(full_counts),
        "entity_entity_distinct_types": len(ee),
        "entity_entity_total_edges": sum(ee_counts),
        "entity_entity_entropy_bits": entropy(ee_counts),
        "h395_reference": {"native_types": 334, "entropy_bits": 6.22},
        "reconciliation": (
            "Full registered query yields 599 types but entropy only 3.16 bits - "
            "dominated by 3 provenance mega-types (ABOUT 11853, MENTIONED_IN 8299, "
            "ANSWERABLE_FROM 7995) that are entity<->chunk/question edges, not "
            "semantic relations. Restricting to entity-entity endpoints gives 597 "
            "types at entropy 6.32 bits, matching H395's 6.22-bit regime. The type "
            "COUNT grew (334->597) with the graph state (H395 predates the full "
            "1000-doc medium); the entropy match confirms the same proliferating "
            "open-vocabulary regime. Alignment runs over the full registered vocab; "
            "provenance mega-types can only depress precision, never inflate coverage."
        ),
    }
    Path(cache).write_text(json.dumps(native, indent=1))
    return native, stats


# -------------------------------------------------------------------- gold vocab
def load_gold() -> tuple[dict, dict, int, int]:
    bench = json.loads(QUESTIONS.read_text())
    st_slices = load_slices()
    # eligibility needs a driver-bound Foundry; reuse ingested_titles via a light driver
    from knowledge_graph_foundry import load_settings
    from knowledge_graph_foundry.pipeline import Foundry
    settings = load_settings(Path("config/experiments/config-bench-medium.yml"))
    settings.event_log = None
    with Foundry(settings) as f:
        titles = ingested_titles(f, st_slices)
    eligible = [
        q for q in bench
        if gold_titles(q) and all(t in titles for t in gold_titles(q)) and q.get("evidences")
    ]

    def vocab(qs):
        qcount, example = Counter(), {}
        for q in qs:
            rels = set()
            for tr in q["evidences"]:
                if len(tr) == 3:
                    s_, r_, o_ = tr
                    rels.add(r_)
                    example.setdefault(r_, (s_, r_, o_))
            for r_ in rels:
                qcount[r_] += 1
        return qcount, example

    qc_el, ex_el = vocab(eligible)
    qc_all, ex_all = vocab([q for q in bench if q.get("evidences")])
    gold_el = {
        r_: {"q_count": qc_el[r_], "example": list(ex_el[r_])} for r_ in qc_el
    }
    gold_all = {
        r_: {"q_count": qc_all[r_], "example": list(ex_all[r_])} for r_ in qc_all
    }
    return gold_el, gold_all, len(eligible), sum(qc_el.values())


# -------------------------------------------------------------------- embeddings
def embed_cached(texts: list[str], tag: str) -> np.ndarray:
    cache = CACHE / f"emb_{tag}.npy"
    keys = CACHE / f"emb_{tag}_keys.json"
    if cache.exists() and keys.exists() and json.loads(keys.read_text()) == texts:
        return np.load(cache)
    vecs = np.array(_embed_bedrock_texts(texts, TITAN), dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    np.save(cache, vecs)
    keys.write_text(json.dumps(texts))
    return vecs


def native_texts(native: list[dict]) -> tuple[list[str], list[str]]:
    names, ctxs = [], []
    for n in native:
        h = hum(n["type"])
        names.append(h)
        if n["ex_s"] and n["ex_o"]:
            ctxs.append(f"{h}. example: {n['ex_s']} {h} {n['ex_o']}")
        else:
            ctxs.append(h)
    return names, ctxs


def gold_texts(gold: dict) -> tuple[list[str], list[str], list[str]]:
    rels, names, ctxs = [], [], []
    for r_, meta in gold.items():
        rels.append(r_)
        names.append(r_)
        s_, _, o_ = meta["example"]
        ctxs.append(f"{r_}. example: {s_} {r_} {o_}")
    return rels, names, ctxs


# ---------------------------------------------------------------------- coverage
def coverage_curve(best_cos: np.ndarray, qcounts: np.ndarray, tot_q: int) -> list[dict]:
    n = len(best_cos)
    curve = []
    for t in THRESHOLDS:
        aligned = best_cos >= t
        curve.append({
            "threshold": t,
            "n_aligned": int(aligned.sum()),
            "coverage_unweighted": round(float(aligned.sum()) / n, 4),
            "coverage_qweighted": round(float(qcounts[aligned].sum()) / tot_q, 4),
        })
    return curve


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    native, nat_stats = load_native()
    gold_el, gold_all, n_eligible, tot_slots = load_gold()
    print(f"native types: {len(native)}; gold eligible relations: {len(gold_el)} "
          f"({tot_slots} slots over {n_eligible} probes)", flush=True)

    nat_names, nat_ctxs = native_texts(native)
    rels, g_names, g_ctxs = gold_texts(gold_el)
    qcounts = np.array([gold_el[r]["q_count"] for r in rels], dtype=np.float32)

    print("embedding native (name)...", flush=True)
    NN = embed_cached(nat_names, "native_name")
    print("embedding native (context)...", flush=True)
    NC = embed_cached(nat_ctxs, "native_ctx")
    print("embedding gold (name)...", flush=True)
    GN = embed_cached(g_names, "gold_name")
    print("embedding gold (context)...", flush=True)
    GC = embed_cached(g_ctxs, "gold_ctx")

    sim_name = GN @ NN.T   # gold x native
    sim_ctx = GC @ NC.T
    best_name = sim_name.max(axis=1)
    best_ctx = sim_ctx.max(axis=1)
    arg_name = sim_name.argmax(axis=1)
    arg_ctx = sim_ctx.argmax(axis=1)

    curve_name = coverage_curve(best_name, qcounts, tot_slots)
    curve_ctx = coverage_curve(best_ctx, qcounts, tot_slots)

    # per-gold best matches (both arms)
    per_gold = []
    for i, r in enumerate(rels):
        # top-2 context natives for handcheck fill
        order = np.argsort(-sim_ctx[i])
        top2 = [int(order[0]), int(order[1])]
        per_gold.append({
            "gold": r,
            "q_count": int(qcounts[i]),
            "gold_example": gold_el[r]["example"],
            "best_name_type": native[int(arg_name[i])]["type"],
            "best_name_cos": round(float(best_name[i]), 4),
            "best_ctx_type": native[int(arg_ctx[i])]["type"],
            "best_ctx_cos": round(float(best_ctx[i]), 4),
            "ctx_top2": [
                {"type": native[j]["type"], "cos": round(float(sim_ctx[i][j]), 4),
                 "native_example": [native[j]["ex_s"], native[j]["ex_o"]]}
                for j in top2
            ],
        })

    # exact / normalized string-match baseline (zero-embedding)
    nat_norm = {norm(n["type"]): n["type"] for n in native}
    nat_norm_set = set(nat_norm)
    exact_rows, exact_hits, exact_qhits = [], 0, 0.0
    contain_hits, contain_qhits = 0, 0.0
    for i, r in enumerate(rels):
        gn = norm(r)
        exact = gn in nat_norm_set
        # token-containment: all gold tokens appear as tokens in some native type
        gt = set(gn.split())
        contain = None
        for n in native:
            nt = set(norm(n["type"]).split())
            if gt and gt.issubset(nt):
                contain = n["type"]
                break
        exact_hits += exact
        exact_qhits += float(qcounts[i]) if exact else 0.0
        contain_hits += bool(contain)
        contain_qhits += float(qcounts[i]) if contain else 0.0
        exact_rows.append({
            "gold": r, "exact_match": nat_norm.get(gn) if exact else None,
            "token_containment": contain,
        })

    # ---- 30-pair hand-check candidates ----
    # Cover the actual alignment DECISIONS of both arms: the 23 name-arm best
    # pairs (the stronger arm) + the highest-cosine context-arm best pairs whose
    # native pick DIFFERS from the name arm (captures the context arm's spurious
    # high-cosine matches). Judge false-alignment on the union.
    name_pairs = [{
        "gold": r, "native": native[int(arg_name[i])]["type"], "arm": "name",
        "name_cos": round(float(best_name[i]), 4),
        "ctx_cos": round(float(sim_ctx[i][int(arg_name[i])]), 4),
        "gold_example": gold_el[r]["example"],
        "native_example": [native[int(arg_name[i])]["ex_s"], native[int(arg_name[i])]["ex_o"]],
    } for i, r in enumerate(rels)]
    ctx_extra = []
    for i, r in enumerate(rels):
        j = int(arg_ctx[i])
        if j != int(arg_name[i]):
            ctx_extra.append({
                "gold": r, "native": native[j]["type"], "arm": "context",
                "name_cos": round(float(sim_name[i][j]), 4),
                "ctx_cos": round(float(best_ctx[i]), 4),
                "gold_example": gold_el[r]["example"],
                "native_example": [native[j]["ex_s"], native[j]["ex_o"]],
            })
    ctx_extra.sort(key=lambda p: -p["ctx_cos"])
    handcheck = name_pairs + ctx_extra[:7]
    for k, p in enumerate(handcheck):
        p["pair_id"] = k

    result = {
        "run_id": run_id,
        "hypothesis": "R50-H585 relation-linker feasibility gate",
        "native_vocab_stats": nat_stats,
        "gold_vocab": {
            "eligible_relations": len(gold_el),
            "eligible_probes": n_eligible,
            "eligible_slots": tot_slots,
            "all_relations": len(gold_all),
            "per_relation_eligible": gold_el,
        },
        "coverage_curve": {"name_arm": curve_name, "context_arm": curve_ctx},
        "coverage_at_0.6": {
            "name_arm": next(c for c in curve_name if c["threshold"] == 0.6),
            "context_arm": next(c for c in curve_ctx if c["threshold"] == 0.6),
        },
        "exact_match_baseline": {
            "exact_coverage_unweighted": round(exact_hits / len(rels), 4),
            "exact_coverage_qweighted": round(exact_qhits / tot_slots, 4),
            "token_containment_unweighted": round(contain_hits / len(rels), 4),
            "token_containment_qweighted": round(contain_qhits / tot_slots, 4),
            "rows": exact_rows,
        },
        "per_gold": per_gold,
        "handcheck_candidates": handcheck,
    }

    # inject hand-check verdicts if present -> false-alignment + proposed verdict
    if VERDICTS.exists():
        verdicts = json.loads(VERDICTS.read_text())
        judged = []
        for p in handcheck:
            key = f"{p['gold']}||{p['native']}"
            v = verdicts.get(key)
            row = dict(p)
            row["expresses_gold"] = v["expresses"] if v else None
            row["judge_note"] = v["note"] if v else None
            judged.append(row)
        result["handcheck_judged"] = judged
        result["handcheck_unjudged"] = [r["pair_id"] for r in judged if r["expresses_gold"] is None]

        # verdict lookup on the NAME arm best pick per gold (the stronger arm)
        name_verdict = {}
        for i, r in enumerate(rels):
            key = f"{r}||{native[int(arg_name[i])]['type']}"
            v = verdicts.get(key)
            name_verdict[r] = v["expresses"] if v else None

        # precision-controlled coverage sweep on the name arm: at each threshold,
        # aligned = golds with best_name >= t; TRUE = judged-expresses; precision
        # = TRUE / aligned; coverage counts only TRUE alignments (correct links)
        prec_sweep = []
        for t in THRESHOLDS:
            aligned = [r for i, r in enumerate(rels) if best_name[i] >= t]
            true_al = [r for r in aligned if name_verdict.get(r) is True]
            false_al = [r for r in aligned if name_verdict.get(r) is False]
            n_al = len(aligned)
            fa = len(false_al) / n_al if n_al else 0.0
            prec_sweep.append({
                "threshold": t,
                "n_aligned": n_al,
                "false_alignments": len(false_al),
                "false_alignment_rate": round(fa, 4),
                "coverage_raw_unweighted": round(n_al / len(rels), 4),
                "coverage_true_unweighted": round(len(true_al) / len(rels), 4),
                "coverage_true_qweighted": round(
                    sum(gold_el[r]["q_count"] for r in true_al) / tot_slots, 4),
                "precision_ok_le20pct": fa <= 0.20,
            })
        result["name_arm_precision_sweep"] = prec_sweep

        # 30-pair false-alignment summary + at the registered 0.6 anchor
        n_true = sum(1 for r in judged if r["expresses_gold"] is True)
        n_false = sum(1 for r in judged if r["expresses_gold"] is False)
        counted06 = [r for r in judged if r["arm"] == "name" and r["name_cos"] >= 0.6]
        false06 = [r for r in counted06 if r["expresses_gold"] is False]
        result["false_alignment_summary"] = {
            "sample_size": len(judged),
            "true": n_true, "false": n_false,
            "sample_false_rate": round(n_false / len(judged), 4),
            "counted_alignments_name_arm_0.6": len(counted06),
            "false_among_counted_0.6": len(false06),
            "false_rate_at_0.6": round(len(false06) / len(counted06), 4) if counted06 else None,
            "note": (
                "30-pair sample = 23 name-arm best picks + 7 highest-cosine "
                "context-arm best picks that differ from the name arm. Judge = "
                "executor, deterministic: does the native type's example triple "
                "express the gold relation? Per-threshold false-alignment in "
                "name_arm_precision_sweep."
            ),
        }

        # best achievable coverage at <=20% false-alignment (any usable threshold)
        usable = [s for s in prec_sweep if s["precision_ok_le20pct"]]
        best_usable = max(usable, key=lambda s: s["coverage_true_unweighted"]) if usable else None
        # ceiling of correct coverage over ALL thresholds (ignoring precision)
        ceiling_true = max(s["coverage_true_unweighted"] for s in prec_sweep)
        result["decision"] = {
            "anchor_0.6_name_coverage": next(
                c["coverage_unweighted"] for c in curve_name if c["threshold"] == 0.6),
            "anchor_0.6_context_coverage": next(
                c["coverage_unweighted"] for c in curve_ctx if c["threshold"] == 0.6),
            "best_true_coverage_at_le20pct_false": (
                best_usable["coverage_true_unweighted"] if best_usable else 0.0),
            "best_usable_threshold": best_usable["threshold"] if best_usable else None,
            "best_usable_qweighted": (
                best_usable["coverage_true_qweighted"] if best_usable else 0.0),
            "correct_coverage_ceiling_any_threshold": ceiling_true,
        }
    Path(OUT / f"h585-relation-linker-{run_id}.json").write_text(json.dumps(result, indent=1))
    print("WROTE", OUT / f"h585-relation-linker-{run_id}.json", flush=True)
    print("context@0.6:", result["coverage_at_0.6"]["context_arm"], flush=True)
    print("name@0.6:", result["coverage_at_0.6"]["name_arm"], flush=True)
    print("exact:", result["exact_match_baseline"]["exact_coverage_unweighted"],
          "containment:", result["exact_match_baseline"]["token_containment_unweighted"], flush=True)


if __name__ == "__main__":
    main()

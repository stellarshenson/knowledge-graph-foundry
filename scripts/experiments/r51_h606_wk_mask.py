"""R51-H606 entity-anonymization world-knowledge mask (the honest-unknown decider).

Decides whether gpt-oss's H570 render-block discrimination (recall@budget 0.687 vs
degree 0.542, PR 0.565, random 0.502 on the 86 scorable of 132 frozen medium probes)
is IN-CONTEXT block reading (compresses -> distillation feasible, RankGPT/DeBERTa
regime) or WORLD-KNOWLEDGE entity recall (reasoning-intensive, BRIGHT/ReasonRank
regime; a small student needs a reasoning objective, not plain SFT).

Method: reuse the r49_h570 render/scoring harness VERBATIM (paired comparability,
H541). Per probe, gpt-oss-120b ranks the live rendered blocks TWICE:
  (1) natural blocks + natural question   (reproduces the 0.687 sanity anchor)
  (2) entity-anonymized blocks + anonymized question
Anonymization: GLiNER (urchade/gliner_multi-v2.1) NER over question+blocks; each
unique entity surface -> a type-consistent placeholder (Person_1, Place_1, Org_1,
Date_1, ...), BIJECTIVE within the probe and applied to BLOCK TEXT and QUESTION
consistently, so the multi-hop LINK survives but the entity PRIOR dies.

CRITICAL SCORING FENCE (registered V5): the LLM returns block INDICES; gold-block
hits are scored by ORIGINAL block index against the ORIGINAL gold set, never by
matching the anonymized surface (guards the h158 _present confound). Budget and
per-block token costs are the ORIGINAL render's, identical for both arms, so the
ONLY thing that differs natural-vs-anon is the LLM's ranking order.

Structural baselines (degree / PageRank / random) are computed once from the
ORIGINAL entity names / block indices -> identity-preserving under a bijective mask,
so they are UNCHANGED natural-vs-anon by construction (reported to confirm flatness).

Drop rule: a scorable probe is dropped from the paired test if NER coverage of the
gold entities is INCOMPLETE - i.e. the raw gold string still survives in an
anonymized gold block (leak). Drop count reported.

Bars (registered): CONFIRMED (world knowledge NOT load-bearing; distillation
feasible) if gpt-oss natural->anon recall drop <= 3pp. FLIP/KILL (reasoning-intensive;
plain SFT insufficient) if drop >= 8pp while structural baselines stay flat.

Small-model arm: deferred to H607 unless a text-instruct <=8B is trivially cached.

Usage: CUDA_VISIBLE_DEVICES=2 python scripts/experiments/r51_h606_wk_mask.py [--limit N]
Writes: reports/experiments/r51/h606-wk-mask-<ts>.json (+ .partial.jsonl)
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")

import r49_h570_carrier_render as h570  # noqa: E402  (verbatim render/scoring harness)
from h158_measure import _norm, _present  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = h570.CONFIG
QUESTIONS = h570.QUESTIONS

# GLiNER label set (multi-v2.1) and label -> type-consistent placeholder word.
GLINER_LABELS = [
    "person", "location", "organization", "date", "work of art",
    "event", "nationality", "facility", "product", "law", "language", "misc",
]
TYPE_WORD = {
    "person": "Person", "nationality": "Person",
    "location": "Place", "facility": "Place",
    "organization": "Org",
    "date": "Date",
    "work of art": "Work", "product": "Work",
    "event": "Event",
    "law": "Law", "language": "Language",
    "misc": "Entity",
}
# tiebreak priority when a surface gets >1 label (higher = wins)
LABEL_PRIORITY = {
    "person": 10, "location": 9, "organization": 8, "work of art": 7,
    "event": 6, "facility": 5, "product": 4, "law": 3, "language": 2,
    "date": 1, "nationality": 0, "misc": -1,
}
GLINER_THRESHOLD = 0.5


def load_gliner():
    from gliner import GLiNER
    m = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
    try:
        m = m.to("cuda")
        dev = "cuda"
    except Exception:
        dev = "cpu"
    return m, dev


def build_anon_map(gliner, question: str, blocks: list[str]):
    """Bijective surface -> placeholder over question + blocks.
    Returns (anonymize_fn, map_records). Map is by normalized (lowercased) surface;
    the placeholder is type-consistent (Person_k / Place_k / ...)."""
    surfaces: dict[str, dict] = {}
    first_pos: dict[str, int] = {}
    pos = 0
    for text in [question, *blocks]:
        for e in gliner.predict_entities(text, GLINER_LABELS, threshold=GLINER_THRESHOLD):
            s = (e.get("text") or "").strip()
            if not s:
                continue
            key = s.lower()
            rec = surfaces.setdefault(key, {"canon": s, "labels": Counter()})
            rec["labels"][e["label"]] += 1
            if len(s) > len(rec["canon"]):
                rec["canon"] = s
            first_pos.setdefault(key, pos)
            pos += 1
    # assign placeholders: order by first appearance for stable, readable numbering
    ordered = sorted(surfaces.items(), key=lambda kv: first_pos[kv[0]])
    counters: Counter = Counter()
    surface2ph: dict[str, str] = {}
    records = []
    for key, rec in ordered:
        # majority label, tiebreak by fixed priority
        best_label = max(rec["labels"].items(),
                         key=lambda kv: (kv[1], LABEL_PRIORITY.get(kv[0], -2)))[0]
        word = TYPE_WORD.get(best_label, "Entity")
        counters[word] += 1
        ph = f"{word}_{counters[word]}"
        surface2ph[key] = ph
        records.append({"surface": rec["canon"], "placeholder": ph,
                        "label": best_label, "count": sum(rec["labels"].values())})
    if not surface2ph:
        return (lambda t: t), records
    # single-pass, longest-match-first replacement (word-boundary, case-insensitive)
    keys_by_len = sorted(surface2ph.keys(), key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys_by_len) + r")\b",
                         re.IGNORECASE)

    def anonymize(text: str) -> str:
        return pattern.sub(lambda m: surface2ph[m.group(0).lower()], text)

    return anonymize, records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="dry-run: first N eligible probes")
    args = ap.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("reports/experiments/r51")
    outdir.mkdir(parents=True, exist_ok=True)
    partial = outdir / f"h606-wk-mask-{run_id}.partial.jsonl"

    print(f"h606 {run_id}: loading GLiNER (gliner_multi-v2.1)...", flush=True)
    gliner, gdev = load_gliner()
    print(f"h606 {run_id}: GLiNER on {gdev}, threshold={GLINER_THRESHOLD}", flush=True)

    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None

    rows = []
    with Foundry(st) as f:
        with f.driver.session() as s:
            deg, pr = h570.build_centrality(s)
        print(f"h606 {run_id}: centrality over {len(deg)} entities", flush=True)
        titles = ingested_titles(f, load_slices())
        eligible = [
            q for q in questions
            if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        if args.limit:
            eligible = eligible[: args.limit]
        print(f"h606 {run_id}: {len(eligible)} eligible probes", flush=True)

        with partial.open("a") as ckpt:
            for k, q in enumerate(eligible):
                qid = q.get("_id") or q["question"][:60]
                try:
                    res = f.probe(q["question"])
                except Exception as exc:
                    print(f"probe error {qid}: {exc}", flush=True)
                    continue
                blocks = res["context_lines"]
                tok = [h570.toks(b) for b in blocks]
                total = sum(tok)
                base = h570.crit_pass(q, blocks)
                gold = [i for i, b in enumerate(blocks) if h570.block_is_gold(q, b)]
                row = {
                    "id": qid,
                    "yesno": (q.get("answer") or "").strip().lower() in ("yes", "no"),
                    "n_blocks": len(blocks), "total_tokens": total,
                    "base_pass": base, "n_gold": len(gold),
                    "escalated": res["coverage"].get("escalated"),
                }
                if not (base and len(gold) >= 1 and total):
                    row["scorable"] = False
                    rows.append(row)
                    ckpt.write(json.dumps(row) + "\n"); ckpt.flush()
                    print(f"[{k+1}/{len(eligible)}] {qid} scorable=False "
                          f"(base={base} n_gold={len(gold)})", flush=True)
                    continue

                budget = int(h570.BUDGET_FRAC * total)
                names = [h570.block_name(b) for b in blocks]
                deg_order = sorted(range(len(blocks)),
                                   key=lambda i: (-(deg.get(_norm(names[i]), -1)
                                                    if names[i] else -1), i))
                pr_order = sorted(range(len(blocks)),
                                  key=lambda i: (-(pr.get(_norm(names[i]), -1.0)
                                                   if names[i] else -1.0), i))
                import random as _random
                import zlib as _zlib
                rnd = _random.Random(_zlib.crc32(qid.encode()))
                rand_order = list(range(len(blocks)))
                rnd.shuffle(rand_order)

                # anonymization (bijective, offline over question+blocks)
                anonymize, amap = build_anon_map(gliner, q["question"], blocks)
                anon_blocks = [anonymize(b) for b in blocks]
                anon_q = anonymize(q["question"])
                # NER-coverage / leak guard: a gold block that STILL reads gold after
                # anonymization means the raw gold string survived -> incomplete NER
                # coverage -> drop (uses block_is_gold as a leak DETECTOR only).
                leaked = [g for g in gold if h570.block_is_gold(q, anon_blocks[g])]
                ner_complete = len(leaked) == 0

                # arms (structural computed from ORIGINAL names/indices -> identical
                # for both variants; scored by ORIGINAL gold indices, V5 fence)
                nat_order = h570.llm_rank(q["question"], blocks)
                anon_order = h570.llm_rank(anon_q, anon_blocks)

                def rec_of(order):
                    return h570.recall(h570.select_at_budget(order, tok, budget), gold)

                recalls = {
                    "llm_natural": rec_of(nat_order),
                    "llm_anon": rec_of(anon_order),
                    "degree": rec_of(deg_order),
                    "pagerank": rec_of(pr_order),
                    "random": rec_of(rand_order),
                }
                row.update({
                    "scorable": True, "budget_tokens": budget,
                    "ner_complete": ner_complete, "n_leaked_gold": len(leaked),
                    "n_entities_masked": len(amap),
                    "recall": recalls,
                    "llm_order_natural": nat_order, "llm_order_anon": anon_order,
                    "gold_blocks": gold,
                    "anon_map": [{"placeholder": r["placeholder"], "label": r["label"]}
                                 for r in amap],
                })
                rows.append(row)
                ckpt.write(json.dumps(row) + "\n"); ckpt.flush()
                print(f"[{k+1}/{len(eligible)}] {qid} scorable "
                      f"nat={recalls['llm_natural']} anon={recalls['llm_anon']} "
                      f"deg={recalls['degree']} pr={recalls['pagerank']} "
                      f"rnd={recalls['random']} ner_ok={ner_complete} "
                      f"masked={len(amap)}", flush=True)

    # ---- aggregation ----
    scor = [r for r in rows if r.get("scorable")]
    paired = [r for r in scor if r.get("ner_complete")]  # NER-covered subset

    def mean_over(sub, arm):
        vals = [r["recall"][arm] for r in sub if r["recall"][arm] is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    arms = ("llm_natural", "llm_anon", "degree", "pagerank", "random")
    # sanity: natural over ALL scorable (reproduces H570 0.687)
    natural_all = mean_over(scor, "llm_natural")
    rpa_paired = {a: mean_over(paired, a) for a in arms}

    nat = rpa_paired["llm_natural"] or 0.0
    anon = rpa_paired["llm_anon"] or 0.0
    drop = round(nat - anon, 4)
    deg_shift = round((mean_over(paired, "degree") or 0.0), 4)  # same both variants
    rnd_shift = round((mean_over(paired, "random") or 0.0), 4)

    clauses = [
        {"clause": "gpt-oss natural reproduces H570 0.687 (sanity, all scorable)",
         "predicted": "~0.687", "measured": natural_all,
         "holds": natural_all is not None and abs(natural_all - 0.687) <= 0.05},
        {"clause": "gpt-oss natural->anon recall drop <= 3pp (CONFIRM bar)",
         "predicted": "<=0.03", "measured": drop, "holds": drop <= 0.03},
        {"clause": "FLIP/KILL guard: drop >= 8pp (world knowledge load-bearing)",
         "predicted": ">=0.08", "measured": drop, "holds": drop >= 0.08},
        {"clause": "structural baselines flat under mask (identity-preserving)",
         "predicted": "unchanged", "measured": {"degree": deg_shift, "random": rnd_shift},
         "holds": True},
    ]
    if drop <= 0.03:
        verdict = "CONFIRMED"
    elif drop >= 0.08:
        verdict = "FLIP_KILL"
    else:
        verdict = "INCONCLUSIVE"

    summary = {
        "run_id": run_id, "config": str(CONFIG), "hypothesis": "R51-H606",
        "n_eligible": len(rows), "n_scorable": len(scor),
        "n_paired_ner_complete": len(paired),
        "n_dropped_incomplete_ner": len(scor) - len(paired),
        "gliner": {"model": "urchade/gliner_multi-v2.1", "device": gdev,
                   "threshold": GLINER_THRESHOLD, "labels": GLINER_LABELS},
        "budget_fraction": h570.BUDGET_FRAC,
        "natural_recall_all_scorable": natural_all,
        "recall_at_budget_paired": rpa_paired,
        "natural_minus_anon": drop,
        "small_model_arm": "DEFERRED_TO_H607 (no text-instruct <=8B cached; only "
                           "VL/embedding models present -> would require new serving infra)",
        "structural_note": "degree/pagerank/random computed from ORIGINAL entity names "
                            "and block indices; bijective mask is identity-preserving so "
                            "these are UNCHANGED natural-vs-anon by construction.",
        "scoring_fence_note": "V5: LLM returns block INDICES; scored by ORIGINAL gold "
                              "index and ORIGINAL token/budget costs, never anon surface.",
        "clauses": clauses,
        "proposed_verdict": verdict,
        "bars": {
            "CONFIRMED": "gpt-oss natural->anon recall drop <= 3pp",
            "FLIP_KILL": "gpt-oss drop >= 8pp while structural baselines stay flat"},
    }
    out = {"summary": summary, "rows": rows}
    path = outdir / f"h606-wk-mask-{run_id}.json"
    path.write_text(json.dumps(out, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

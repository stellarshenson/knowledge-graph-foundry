#!/usr/bin/env python3
"""R49-H578 - span-entailment triage classifier prices out ARTIFACT/ELSEWHERE before scheduling.

Registered prediction:
  - AUC >= 0.75 over the census + miss lists (predicted-repairable vs actual repair outcome)
  - >= 80% of the ~14% residue lands predicted-unrepairable
  Bar: KILLED if AUC < 0.65 OR > 25% of genuinely-repaired facts flagged ARTIFACT (BOILERPLATE)

Population (H546 census, 2wiki-medium):
  - 48 recovered facts (repair ledger) -> actual repairable = 1 (positives)
  - 17 residual misses (H448 classes ARTIFACT/ELSEWHERE/ABSENT on final H389 cert) -> actual repairable = 0

Classifier (REGISTERED-NLI DEVIATION - no trained cross-encoder in venv):
  - gpt-oss-120b @ localhost:8010, temp 0, entailment judge: (span, fact) -> ENTAILED / NOT-ENTAILED / SPAN-IS-BOILERPLATE
  - deterministic content-word alias-presence backstop (fraction of fact content words in span)
  - predicted-repairable := label == ENTAILED
  - NO generation beyond the label.

Source span := the doc's Chunk text on the R45 pile (bolt://172.19.0.101:7687), READ-ONLY.
Incremental checkpoint to the OUT jsonl per fact; final scoring appended as a summary line.
"""
import json, re, os, sys, datetime, urllib.request

ROOT = "/home/lab/workspace/learning/projects/knowledge-graph-foundry"
H546 = f"{ROOT}/reports/experiments/r49/h546-rai-class-20260713T180017Z.json"
BOLT = "bolt://172.19.0.101:7687"
AUTH = ("neo4j", "kgfoundry")
LLM_URL = "http://localhost:8010/v1/chat/completions"
LLM_MODEL = "gpt-oss-120b"
TS = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = f"{ROOT}/reports/experiments/r49/h578-triage-{TS}.jsonl"

STOP = set("a an the of in on at to for and or but is was were be been being he she it "
           "they them his her its their as by with from that this which who whom whose "
           "are had has have will would can could s".split())


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).lower().replace("‑", "-").strip()


def content_words(s):
    return [w for w in re.findall(r"[a-z0-9]+", norm(s)) if w not in STOP and len(w) > 1]


def alias_overlap(fact, span):
    fw = content_words(fact)
    if not fw:
        return 0.0
    sw = set(content_words(span))
    return sum(1 for w in fw if w in sw) / len(fw)


def llm_entail(span, fact):
    prompt = (
        "You are a strict entailment judge for a knowledge-graph repair scheduler. "
        "Given a SOURCE PASSAGE and a CANDIDATE FACT, decide whether the passage supports "
        "attaching the fact as a genuine, source-grounded fact.\n"
        "Return exactly ONE label (nothing else):\n"
        "  ENTAILED             - the passage explicitly states or logically entails the candidate fact.\n"
        "  NOT-ENTAILED         - the passage does not state/entail it, or it concerns a different subject.\n"
        "  SPAN-IS-BOILERPLATE  - the candidate is not a genuine standalone assertion: a bare date/name "
        "fragment, a disambiguation/list stub, a section header, or a non-assertional artifact.\n\n"
        f"SOURCE PASSAGE:\n{span}\n\nCANDIDATE FACT:\n{fact}\n\nAnswer with ONE label:"
    )
    body = json.dumps({
        "model": LLM_MODEL, "temperature": 0, "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    try:
        req = urllib.request.Request(LLM_URL, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.load(r)
        content = (resp["choices"][0]["message"].get("content") or "").strip()
        up = content.upper()
        # order matters: boilerplate before not-entailed before entailed
        if "BOILERPLATE" in up:
            return "SPAN-IS-BOILERPLATE", content
        if "NOT-ENTAILED" in up or "NOT ENTAILED" in up:
            return "NOT-ENTAILED", content
        if "ENTAILED" in up:
            return "ENTAILED", content
        return "PARSE-FAIL", content
    except Exception as e:
        return "ERR", f"{type(e).__name__}: {e}"


def main():
    from neo4j import GraphDatabase
    h546 = json.load(open(H546))

    rows = []
    for r in h546["recovered_records"]:
        rows.append({"fact": r["fact"], "doc": r["doc"], "carrier": r.get("carrier"),
                     "actual_repairable": 1, "actual_class": r["class"]})
    for r in h546["residual_records"]:
        rows.append({"fact": r["miss"], "doc": r["doc"], "carrier": None,
                     "actual_repairable": 0, "actual_class": "residual/" + r["class"]})

    drv = GraphDatabase.driver(BOLT, auth=AUTH)
    span_cache = {}
    with drv.session() as s:
        def span_for(doc):
            if doc in span_cache:
                return span_cache[doc]
            txts = [x["t"] for x in s.run(
                "MATCH (ch:Chunk)-[:PART_OF]->(:KGFDocument {id:$doc}) RETURN ch.text AS t", doc=doc)]
            span = "\n".join(t for t in txts if t)
            span_cache[doc] = span
            return span

        done = 0
        with open(OUT, "w") as out:
            for i, row in enumerate(rows):
                span = span_for(row["doc"])
                label, raw = llm_entail(span, row["fact"])
                aov = alias_overlap(row["fact"], span)
                rec = {
                    **row,
                    "span_present_overlap": round(aov, 3),
                    "alias_present": bool(aov >= 0.6),
                    "llm_label": label,
                    "predicted_repairable": bool(label == "ENTAILED"),
                }
                out.write(json.dumps(rec) + "\n")
                out.flush()
                done += 1
                print(f"[{done}/{len(rows)}] {row['actual_class']:24s} label={label:20s} "
                      f"aov={aov:.2f} :: {row['fact'][:70]}", flush=True)
    drv.close()

    # ---- scoring ----
    recs = [json.loads(l) for l in open(OUT) if l.strip()]
    from sklearn.metrics import roc_auc_score

    def score(entailed):  # continuous score for AUC
        return 1.0 if entailed else 0.0

    y_true = [r["actual_repairable"] for r in recs]
    y_ent = [1.0 if r["llm_label"] == "ENTAILED" else 0.0 for r in recs]
    y_alias = [1.0 if r["alias_present"] else 0.0 for r in recs]
    y_comb = [0.5 * a + 0.5 * b for a, b in zip(y_ent, y_alias)]

    def safe_auc(yt, ys):
        try:
            return round(float(roc_auc_score(yt, ys)), 4)
        except Exception as e:
            return f"n/a ({e})"

    auc_ent = safe_auc(y_true, y_ent)
    auc_alias = safe_auc(y_true, y_alias)
    auc_comb = safe_auc(y_true, y_comb)

    residual = [r for r in recs if r["actual_repairable"] == 0]
    recovered = [r for r in recs if r["actual_repairable"] == 1]
    residue_pred_unrep = sum(1 for r in residual if not r["predicted_repairable"])
    residue_capture = residue_pred_unrep / len(residual) if residual else None
    fa_boiler = sum(1 for r in recovered if r["llm_label"] == "SPAN-IS-BOILERPLATE")
    fa_any_unrep = sum(1 for r in recovered if not r["predicted_repairable"])
    false_abstention_boiler = fa_boiler / len(recovered) if recovered else None
    false_abstention_any = fa_any_unrep / len(recovered) if recovered else None

    import collections
    by_label = collections.Counter(r["llm_label"] for r in recs)
    residue_by_class = collections.Counter(
        (r["actual_class"], r["llm_label"]) for r in residual)

    summary = {
        "summary": True, "hypothesis": "R49-H578", "ts": TS,
        "registered_nli_deviation": "gpt-oss-120b entailment judge + content-word alias regex "
                                    "(no trained NLI cross-encoder in venv)",
        "n_total": len(recs), "n_recovered_pos": len(recovered), "n_residual_neg": len(residual),
        "auc_entailment_primary": auc_ent,
        "auc_alias_deterministic": auc_alias,
        "auc_combined": auc_comb,
        "residue_capture": round(residue_capture, 4) if residue_capture is not None else None,
        "residue_pred_unrepairable": f"{residue_pred_unrep}/{len(residual)}",
        "false_abstention_boilerplate": round(false_abstention_boiler, 4) if false_abstention_boiler is not None else None,
        "false_abstention_any_unrepairable": round(false_abstention_any, 4) if false_abstention_any is not None else None,
        "label_distribution": dict(by_label),
        "residual_label_by_class": {f"{k[0]}|{k[1]}": v for k, v in residue_by_class.items()},
        "bars": {"auc_confirm": 0.75, "auc_kill": 0.65, "residue_capture_target": 0.80,
                 "false_abstention_kill": 0.25},
    }
    with open(OUT, "a") as out:
        out.write(json.dumps(summary) + "\n")
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()

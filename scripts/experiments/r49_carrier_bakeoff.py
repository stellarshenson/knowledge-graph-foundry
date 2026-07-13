"""R49 carrier bakeoff: H564 feature scorer, H565 degree-anti, H567 artifact
gate, H568 LLM attacher, H569 anchor-co-occurrence rule.

Eval substrate: reports/experiments/r49/carrier-gold-12.json (hand-adjudicated)
+ the full 51-row R45 census (reports/experiments/r45/repair-ledger.jsonl).
Candidates per case = entities MENTIONED_IN the doc's chunks on the live
medium bench graph. Span window = matched sentence + preceding sentence.
H566 (coref) NOT run - fastcoref/spacy absent from the venv (dependency gap,
recorded); the gold's mechanism counts stand but the recovery clause needs a
real resolver.

LLM arms use the local vLLM OpenAI endpoint (gpt-oss-120b, temp 0).

Registered: docs/experiments/kgf-redesign-experiments.md R49-H564..H569.
Usage: python scripts/experiments/r49_carrier_bakeoff.py
Writes: reports/experiments/r49/carrier-bakeoff-<ts>.json
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.extraction import generate_embeddings
from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.pipeline import Foundry

GOLD = Path("reports/experiments/r49/carrier-gold-12.json")
LEDGER = Path("reports/experiments/r45/repair-ledger.jsonl")
CONFIG = Path("config/experiments/config-bench-medium.yml")
VLLM = "http://localhost:8010/v1/chat/completions"
ARTIFACT_RE = re.compile(r"^(this is a list|.* may refer to:?$|list of )", re.I)


def llm(prompt: str, max_tokens: int = 1024) -> str:
    # gpt-oss-120b reasons in a separate channel; content is None if reasoning
    # consumes the budget - give headroom and fall back to reasoning_content
    r = requests.post(VLLM, json={
        "model": "gpt-oss-120b", "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]}, timeout=300)
    r.raise_for_status()
    m = r.json()["choices"][0]["message"]
    text = m.get("content") or m.get("reasoning_content") or ""
    return text.strip().splitlines()[-1].strip() if text.strip() else "ABSTAIN-EMPTY"


def window(case: dict) -> str:
    span = case.get("span", "")
    return f"{case.get('doc_title','')}. {span}"


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gold = json.loads(GOLD.read_text())["cases"]
    census = [json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
    st = load_settings(CONFIG)
    st.event_log = None

    with Foundry(st) as f, f.driver.session() as s:
        cands_by_doc = {}
        for c in gold:
            if c["doc"] in cands_by_doc:
                continue
            rows = s.run(
                "MATCH (e:Entity)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->"
                "(d:KGFDocument {id:$doc}) "
                "RETURN DISTINCT e.name AS name, e.embedding AS emb, "
                "count{(e)--()} AS deg", doc=c["doc"]).data()
            cands_by_doc[c["doc"]] = rows
        # fact embeddings through the shipped channel
        facts = [Entity.create(c["fact"][:80], types=["Fact"], description=c["fact"])
                 for c in gold]
        fembs = [np.array(e.embedding, dtype=np.float32)
                 for e in generate_embeddings(facts, st.embeddings)]

    per_case = []
    for c, fv in zip(gold, fembs):
        cands = cands_by_doc.get(c["doc"], [])
        fv = fv / (np.linalg.norm(fv) + 1e-9)
        win = window(c).lower()
        scored = []
        for r in cands:
            ev = np.array(r["emb"], dtype=np.float32)
            ev /= np.linalg.norm(ev) + 1e-9
            name_in_win = r["name"].lower() in win
            cos = float(fv @ ev)
            score = 2.0 * name_in_win + cos + 0.1 * math.log(r["deg"] + 1)
            scored.append({"name": r["name"], "deg": r["deg"],
                           "name_in_win": name_in_win, "cos": round(cos, 3),
                           "score": round(score, 3)})
        scored.sort(key=lambda x: -x["score"])
        feat_pick = None
        if scored and (scored[0]["name_in_win"] or scored[0]["cos"] >= 0.35):
            feat_pick = scored[0]["name"]
        # H569 anchor rule: alias co-occurrence in the window, tie -> longest name
        anchored = [r for r in scored if r["name_in_win"]]
        anchored.sort(key=lambda x: -len(x["name"]))
        anchor_pick = anchored[0]["name"] if anchored else None
        # H565 degree rank of gold among candidates
        gold_name = c["gold_carrier"]
        deg_sorted = sorted(scored, key=lambda x: -x["deg"])
        gold_rank = next((i for i, r in enumerate(deg_sorted)
                          if r["name"] == gold_name), None)
        # H568 LLM attacher
        opts = ", ".join(r["name"] for r in scored[:12]) or "(none)"
        ans = llm(
            f"Source text: \"{window(c)}\"\nExtracted fact: \"{c['fact']}\"\n"
            f"Candidate entities: {opts}\n"
            "Which single candidate entity is this fact ABOUT (its subject)? "
            "If the fact is page boilerplate (a list or disambiguation line) with "
            "no legitimate subject, answer exactly ABSTAIN. "
            "Answer with only the entity name or ABSTAIN.")
        llm_pick = None if ans.upper().startswith("ABSTAIN") else ans.strip().strip('"')

        def correct(pick):
            if gold_name is None:
                return pick is None
            return pick is not None and pick.lower() == gold_name.lower()

        per_case.append({
            "fact": c["fact"][:80], "gold": gold_name, "class": c["gold_class"],
            "n_candidates": len(scored),
            "feat_pick": feat_pick, "feat_ok": correct(feat_pick),
            "anchor_pick": anchor_pick, "anchor_ok": correct(anchor_pick),
            "llm_pick": llm_pick, "llm_ok": correct(llm_pick),
            "gold_degree_rank": gold_rank,
            "gold_in_lower_half": (gold_rank is not None
                                   and gold_rank >= len(deg_sorted) / 2),
            "top3_by_score": scored[:3],
        })
        print(json.dumps({k: per_case[-1][k] for k in
                          ("fact", "feat_ok", "anchor_ok", "llm_ok")}), flush=True)

    # H567 artifact gate over the full 51-row census
    name_match = [r for r in census if r.get("carrier_selection") == "name_match"]
    fallback = [r for r in census if r.get("carrier_selection") == "fallback_largest"]
    gate_hits, false_abstains = [], []
    for r in census:
        rx = bool(ARTIFACT_RE.match(r["fact"].strip()))
        verdict = rx
        if rx:  # LLM confirm only regex candidates (cheap)
            a = llm(f"Sentence: \"{r['fact']}\"\nIs this sentence page boilerplate "
                    "(a list header or disambiguation line) rather than a fact about "
                    "a specific real-world entity? Answer yes or no.", 512)
            verdict = a.lower().startswith("y")
        if verdict:
            (gate_hits if r in fallback else false_abstains).append(r["fact"])

    carrier_cases = [p for p in per_case if p["gold"] is not None]
    art_cases = [p for p in per_case if p["gold"] is None]
    summary = {
        "run_id": run_id, "config": str(CONFIG), "n_gold": len(per_case),
        "baseline_labeled_correct": 3,
        "h564_featscore_correct": sum(p["feat_ok"] for p in per_case),
        "h569_anchor_correct": sum(p["anchor_ok"] for p in per_case),
        "h568_llm_correct": sum(p["llm_ok"] for p in per_case),
        "h565": {
            "carrier_cases": len(carrier_cases),
            "gold_in_lower_degree_half": sum(p["gold_in_lower_half"] for p in carrier_cases),
            "gold_strict_highest": sum(p["gold_degree_rank"] == 0 for p in carrier_cases),
            "deviation": "computed over the 8 carrier-bearing cases; 4 artifact rows have no gold carrier",
        },
        "h567": {
            "artifact_rows_in_gold": len(art_cases),
            "gate_flags_on_fallback": len(set(gate_hits)),
            "false_abstains_on_name_match": len(false_abstains),
            "false_abstain_facts": false_abstains[:5],
        },
        "h566": "NOT RUN - fastcoref/spacy absent (dependency gap); gold mechanism count: 7/12 anaphora",
        "bars": {
            "h564": "CONFIRMED >= 9/12 and >= baseline+3; KILLED <= baseline+1",
            "h565": "CONFIRMED lower-half >= 8/12 and strict-highest <= 3/12; KILLED highest >= 6/12",
            "h567": "CONFIRMED >= 3 artifacts flagged, 0 false-abstains; KILLED < 2 or >= 2 false-abstains",
            "h568": "CONFIRMED >= 11/12 and >= featscore+2; KILLED <= featscore",
            "h569": "CONFIRMED >= 10/12 anchored; KILLED > 4/12 with no alias in span",
        },
    }
    out = {"summary": summary, "cases": per_case}
    outdir = Path("reports/experiments/r49")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"carrier-bakeoff-{run_id}.json"
    path.write_text(json.dumps(out, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

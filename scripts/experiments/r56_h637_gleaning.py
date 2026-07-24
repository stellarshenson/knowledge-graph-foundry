"""R56-H637: gleaning pass recovers the absent golds (extraction-recall money test).

Question: H631/H632 proved 5 gold entities were never extracted into the medium
graph. Does a GraphRAG-style gleaning pass over ONLY the source chunk recover them
in joinable form?

  3 genuinely-absent:  Beatrice I, Countess of Burgundy;
                       John Ernest, Duke of Saxe-Eisenach; Abdul-Aziz bin Muhammad
  2 same-name-DIFFERENT (graph has a namesake, not the gold entity):
                       Aleksander Koniecpolski (1620-1659);
                       Louis, Dauphin of France (son of Louis XV)

Design (isolated, per registration):
  - shipped extractor + shipped prompts (recipe=enumerate, split_entity_relation,
    gleaning) run over ONLY each gold's own source document (1 chunk each - the 2wiki
    passages are short). No speculative cross-doc context.
  - baseline pass = _first_pass (enumerate: stage-1 names, stage-2 extract). Run TWICE
    to bound MoE run-variance at temp 0.
  - gleaning pass = gleaning_messages continuation, up to 2 rounds, starting from the
    baseline rep-A entities.
  - join test = goldjoin-v2 ladder lifted from r55_h632 (r0 exact / r1 paren-strip /
    r2 fold / r3 fuzzy>=0.92), gold TITLE vs the emitted entity names.

Substrate:
  - corpus = pilot-200 + medium-rows200-999 (the cumulative 1,000-doc medium pile);
    all 5 golds ARE present as documents (verified) -> no corpus-coverage miss,
    denominator stays 5.
  - purpose = the verbatim bench init string.
  - LLM = local vLLM gpt-oss-120b, temp 0.0.

SERVER DEVIATION (see report surprises): no server on :8010; the only running
gpt-oss-120b is on localhost:8081 (a co-tenant's server, GPU1 full -> a second
server would OOM). Identical model/weights; used read-only. Model routed as
"openai/openai/gpt-oss-120b" so litellm delivers the served id "openai/gpt-oss-120b".

Run (project venv, DETACHED):
  setsid nohup .venv/bin/python scripts/experiments/r56_h637_gleaning.py \
      > logs/r56-h637.log 2>&1 &
Writes: reports/experiments/r56/h637-gleaning-<UTC ts>.json (+ .checkpoint.jsonl)
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry.engines.local_gpu import LocalGpuEngine
from knowledge_graph_foundry.extraction.extractor import WireExtraction, _first_pass
from knowledge_graph_foundry.extraction.prompts import gleaning_messages
from knowledge_graph_foundry.ingest.chunking import chunk_document
from knowledge_graph_foundry.models import Chunk, Document, Ontology, entity_id
from knowledge_graph_foundry.settings import ExtractionSettings, LLMSettings

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
OUT = ROOT / "reports/experiments/r56"
PILOT = ROOT / "data/interim/bench/2wiki-pilot-200.json"
MEDIUM = ROOT / "data/interim/bench/2wiki-medium-rows200-999.json"

PURPOSE = "answer multi-hop questions over an open-domain encyclopedia corpus"
BASE_URL = "http://localhost:8081/v1"
MODEL = "openai/openai/gpt-oss-120b"  # -> served id 'openai/gpt-oss-120b' on :8081
TEMPERATURE = 0.0
TIMEOUT = 3600
GLEAN_ROUNDS = 2
FUZZ = 0.92

# the 5 absent golds + their probe ids + classification (from H631/H632)
GOLDS = [
    ("Beatrice I, Countess of Burgundy", "3a3c2efe0bdc11eba7f7acde48001122", "genuinely_absent"),
    ("John Ernest, Duke of Saxe-Eisenach", "62a9cd640bb011ebab90acde48001122", "genuinely_absent"),
    ("Abdul-Aziz bin Muhammad", "b642318c0bdd11eba7f7acde48001122", "genuinely_absent"),
    ("Aleksander Koniecpolski (1620–1659)", "1c0dd3b00bdc11eba7f7acde48001122",
     "same_name_different_namesake"),
    ("Louis, Dauphin of France (son of Louis XV)", "84c99c760bb011ebab90acde48001122",
     "same_name_different_namesake"),
]

# ---- goldjoin-v2 ladder (lifted from r55_h632_gold_join.py) ------------------
PAREN_TRAIL = re.compile(r"\s*\([^()]*\)\s*$")
DASHES = "‐‑‒–—−"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.casefold()).strip()


def paren_strip(tn: str) -> str:
    return PAREN_TRAIL.sub("", tn).strip()


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for d in DASHES:
        s = s.replace(d, "-")
    s = re.sub(r"\s*&\s*", " and ", s)
    s = s.replace(",", "").replace(".", "")
    return re.sub(r"\s+", " ", s).strip().casefold()


def goldjoin(gold_title: str, names: list[str]) -> dict:
    """Join gold TITLE to the best-matching emitted name via the r0..r3 ladder."""
    gn = _norm(gold_title)
    gps = paren_strip(gn)
    name_norms = [(nm, _norm(nm)) for nm in names]
    # r0 exact
    for nm, nn in name_norms:
        if nn == gn:
            return {"joinable": True, "rung": "r0", "matched": nm, "ratio": 1.0}
    # r1 paren-strip (either side)
    for nm, nn in name_norms:
        if paren_strip(nn) == gps or nn == gps:
            return {"joinable": True, "rung": "r1", "matched": nm, "ratio": 1.0}
    # r2 fold
    gf = fold(gps)
    for nm, nn in name_norms:
        if fold(paren_strip(nn)) == gf or fold(nn) == gf:
            return {"joinable": True, "rung": "r2", "matched": nm, "ratio": 1.0}
    # r3 fuzzy on fold(parenstrip)
    best = {"joinable": False, "rung": None, "matched": None, "ratio": 0.0}
    for nm, nn in name_norms:
        r = difflib.SequenceMatcher(None, gf, fold(paren_strip(nn))).ratio()
        if r > best["ratio"]:
            best = {"joinable": r >= FUZZ, "rung": "r3" if r >= FUZZ else None,
                    "matched": nm, "ratio": round(r, 3)}
    return best


# ---- corpus ------------------------------------------------------------------
def load_corpus() -> dict[str, dict]:
    docs = json.loads(PILOT.read_text()) + json.loads(MEDIUM.read_text())
    return {_norm(d["title"]): d for d in docs}


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    ckpt_path = OUT / f"h637-gleaning-{run_id}.checkpoint.jsonl"
    out_path = OUT / f"h637-gleaning-{run_id}.json"

    def log(m: str) -> None:
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z] {m}", flush=True)

    corpus = load_corpus()
    log(f"corpus loaded: {len(corpus)} docs")

    engine = LocalGpuEngine(LLMSettings(
        engine="local-gpu", model=MODEL, base_url=BASE_URL,
        temperature=TEMPERATURE, timeout=TIMEOUT, max_retries=3))
    cfg = ExtractionSettings(recipe="enumerate", split_entity_relation=True,
                             gleaning_rounds=1, union_k=1, chunk_size=2000,
                             chunk_overlap=200, header_carryover=True)
    ontology = Ontology(purpose=PURPOSE)

    def extract_names(chunks: list[Chunk]) -> list[str]:
        names: list[str] = []
        for ch in chunks:
            wire = _first_pass(ch.text, PURPOSE, ontology, engine, cfg)
            names.extend(we.name for we in wire.entities)
        # order-preserving dedup by entity_id
        seen, out = set(), []
        for nm in names:
            eid = entity_id(nm)
            if eid not in seen:
                seen.add(eid)
                out.append(nm)
        return out

    results = []
    for gold_title, pid, klass in GOLDS:
        gn = _norm(gold_title)
        gps = paren_strip(gn)
        doc_row = corpus.get(gn) or corpus.get(gps)
        rec: dict = {"gold_title": gold_title, "pid": pid, "classification": klass}
        if doc_row is None:
            rec.update({"in_corpus": False, "note": "CORPUS-COVERAGE MISS - excluded"})
            results.append(rec)
            _dump(ckpt_path, rec)
            log(f"{gold_title}: NOT IN CORPUS")
            continue
        rec["in_corpus"] = True
        rec["source_doc_title"] = doc_row["title"]
        doc = Document(id=f"h637-{pid}", path=doc_row["title"], format="text",
                       text=doc_row["text"])
        chunks = chunk_document(doc, cfg.chunk_size, cfg.chunk_overlap, cfg.header_carryover)
        rec["n_chunks"] = len(chunks)
        rec["doc_chars"] = len(doc_row["text"])

        # BASELINE rep A + rep B (bound run-variance)
        try:
            base_a = extract_names(chunks)
            base_b = extract_names(chunks)
        except Exception as exc:  # noqa: BLE001
            rec.update({"error": f"baseline failed: {exc}"})
            results.append(rec)
            _dump(ckpt_path, rec)
            log(f"{gold_title}: BASELINE ERROR {exc}")
            continue
        join_a = goldjoin(gold_title, base_a)
        join_b = goldjoin(gold_title, base_b)
        rec["baseline_rep_a"] = {"n_entities": len(base_a), "names": base_a, "join": join_a}
        rec["baseline_rep_b"] = {"n_entities": len(base_b), "names": base_b, "join": join_b}
        rec["baseline_joinable_either_rep"] = bool(join_a["joinable"] or join_b["joinable"])

        # GLEANING (start from baseline rep-A entities)
        existing = list(base_a)
        existing_ids = {entity_id(x) for x in existing}
        glean_added: list[str] = []
        rounds_used = 0
        try:
            for _ in range(GLEAN_ROUNDS):
                round_added: list[str] = []
                for ch in chunks:
                    glean = engine.complete(
                        gleaning_messages(ch.text, existing, PURPOSE, ontology), WireExtraction)
                    for we in glean.entities:
                        eid = entity_id(we.name)
                        if eid not in existing_ids:
                            existing_ids.add(eid)
                            existing.append(we.name)
                            round_added.append(we.name)
                rounds_used += 1
                glean_added.extend(round_added)
                if not round_added:
                    break
        except Exception as exc:  # noqa: BLE001
            rec["gleaning_error"] = str(exc)
        post_names = existing  # baseline_A union gleaning
        join_post = goldjoin(gold_title, post_names)
        rec["gleaning"] = {
            "rounds_used": rounds_used,
            "newly_added_names": glean_added,
            "post_gleaning_n_entities": len(post_names),
            "join": join_post,
        }
        rec["recovered_post_gleaning"] = bool(join_post["joinable"])
        rec["attributed_to_gleaning"] = bool(join_post["joinable"] and not join_a["joinable"])
        results.append(rec)
        _dump(ckpt_path, rec)
        log(f"{gold_title}: base_join_A={join_a['joinable']}({join_a['rung']}) "
            f"base_join_B={join_b['joinable']} | glean_rounds={rounds_used} added={len(glean_added)} "
            f"| post_join={join_post['joinable']}({join_post['rung']} r={join_post['ratio']})")

    # ---- verdict over the in-corpus (gleanable) set --------------------------
    eligible = [r for r in results if r.get("in_corpus")]
    denom = len(eligible)
    recovered = sum(1 for r in eligible if r.get("recovered_post_gleaning"))
    base_recovered = sum(1 for r in eligible if r.get("baseline_joinable_either_rep"))
    by_gleaning = sum(1 for r in eligible if r.get("attributed_to_gleaning"))

    if recovered >= 3:
        verdict = "CONFIRMED"
    elif recovered <= 1:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    payload = {
        "hypothesis": "R56-H637",
        "run_id": run_id,
        "substrate": ("medium 2wiki corpus (pilot-200 + medium-rows200-999 = 1,000 docs); "
                      "isolated single-doc extraction, no speculative context"),
        "server": {"declared": "http://localhost:8010/v1",
                   "actual_used": BASE_URL, "model_served_id": "openai/gpt-oss-120b",
                   "deviation": ("no server on :8010; only running gpt-oss-120b is a co-tenant's "
                                 "on :8081; GPU1 full so a second server would OOM. Identical "
                                 "model/weights, read-only use.")},
        "params": {"temperature": TEMPERATURE, "recipe": cfg.recipe,
                   "split_entity_relation": cfg.split_entity_relation,
                   "gleaning_rounds_max": GLEAN_ROUNDS, "purpose": PURPOSE,
                   "ontology": "empty (fresh types) - each doc read cold",
                   "join_version": "goldjoin-v2", "fuzz": FUZZ},
        "denominator": denom,
        "counts": {"recovered_post_gleaning": recovered,
                   "baseline_joinable_either_rep": base_recovered,
                   "attributed_to_gleaning_specifically": by_gleaning},
        "verdict": verdict,
        "verdict_note": (f"{recovered}/{denom} joinable after gleaning "
                         f"(bar: >=3 CONFIRMED, <=1 KILLED). Of these, {base_recovered} already "
                         f"joined at BASELINE (run-variance / not-extraction-hard), "
                         f"{by_gleaning} attributable to the gleaning continuation."),
        "per_gold": results,
        "script": "scripts/experiments/r56_h637_gleaning.py",
    }
    out_path.write_text(json.dumps(payload, indent=1))
    log(f"VERDICT {verdict}: {recovered}/{denom} recovered post-gleaning "
        f"(baseline {base_recovered}, by-gleaning {by_gleaning})")
    log(f"wrote {out_path}")


def _dump(path: Path, rec: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()

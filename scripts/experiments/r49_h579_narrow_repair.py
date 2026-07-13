"""R49-H579: ledgered narrow-question source repair vs blind re-extraction.

Hypothesis (registered R49-H579): targeted repair recovers far more ABSENT
facts than the blind second pass (H450: 12/48 = 25%), touching only gap spans.
Mechanism: retrieve the ledgered exact span, ask ONE narrow question, KEEP/
REVISE-write to the anchor-chosen carrier - bypasses generation-selection loss.
Prediction: >= 60% ABSENT recovery at <= 20% of one full re-extraction pass's
tokens; probe-flip >= 50% of flippable gaps.
Bar: CONFIRMED per prediction; KILLED if recovery < 40% OR cost > 50% of a full
pass OR probe-flip < 25% despite coverage recovery.

Substrate: the exact H450 pass-2 set = every unique class==ABSENT (doc, miss)
pair across the R44 h448 decompositions (reports/experiments/r44/
h448-decomposition-*.jsonl) - reconstructed with r45_pass2.absent_targets logic,
48 facts / 20 docs. Blind pass-2 recovered 12/48 = 25% (the baseline to beat).

Graph: R45 PILOT pile, config-bench-pilot.yml (bolt://172.19.0.101), READ-ONLY.
The span is pulled from Chunk.text (raw source, unaffected by repair); the
probe-flip is simulated IN MEMORY (H547 pattern) - NO graph writes anywhere.

Method per fact:
  1. SPAN - best-matching sentence window (matched sentence + preceding) of the
     doc's source chunk text vs the miss fact (content-term Jaccard). This is
     the ledgered exact span.
  2. NARROW QUESTION - ONE gpt-oss call: span + candidate fact -> strict KEEP/
     REVISE/ABSENT grounding decision (selection pressure removed).
  3. RECOVERY - decision in {KEEP,REVISE} AND supported(gold_fact, stated, 0.8),
     the SAME H389/H450 certificate term-share rule the blind baseline used
     (apples-to-apples). ABSENT or drifted REVISE = non-recovery.
  4. ANCHOR CARRIER - H569 name-match fast path (candidate whose name occurs in
     the span, longest wins) over the doc's MENTIONED_IN entities; H568-style
     LLM attacher only when no name matches.
  5. PROBE-FLIP - H547 in-memory render simulation: probe(doc_title); strip the
     R45-written segment for the pre-repair baseline (supA); flippable = fact
     absent from the pre-repair render; re-attach the recovered fact to the
     anchor carrier IFF its block survives the render; supB. flip = flippable
     and supB. probe_flip_rate = flips / flippable.

Cost: narrow-repair tokens (summed vLLM usage) vs one full re-extraction pass =
the exact multi-stage extract_chunk cost over the 20 source chunks (litellm
success-callback usage), the same production path blind pass-2 ran.

Usage: python scripts/experiments/r49_h579_narrow_repair.py
Writes: reports/experiments/r49/h579-narrow-repair-<UTC ts>.json
        + a per-fact checkpoint jsonl alongside it.
"""

import glob
import importlib.util
import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, "src")
from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.extraction.extractor import extract_chunk
from knowledge_graph_foundry.models import Chunk, Ontology
from knowledge_graph_foundry.pipeline import Foundry

# reuse the exact H389 certificate machinery verbatim
_spec = importlib.util.spec_from_file_location(
    "r39_h389", "scripts/experiments/r39_h389_coverage_audit.py"
)
_r39 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r39)
supported = _r39.supported          # supported(probe, graph_text, threshold=0.8)
content_terms = _r39.content_terms

CONFIG = Path("config/experiments/config-bench-pilot.yml")
DECOMPS = "reports/experiments/r44/h448-decomposition-*.jsonl"
LEDGER = Path("reports/experiments/r45/repair-ledger.jsonl")
BENCH_DIR = Path("data/interim/bench")
VLLM = "http://localhost:8010/v1/chat/completions"
OUT = Path("reports/experiments/r49")
THRESHOLD = 0.8
_SENT = re.compile(r"(?<=[.!?])\s+")


# ---------------------------------------------------------------- substrate ---
def absent_targets() -> list[dict]:
    """Exact r45_pass2.absent_targets set: unique class==ABSENT (doc, miss)."""
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []
    for fp in sorted(glob.glob(DECOMPS)):
        for line in open(fp):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["class"] == "ABSENT" and (r["doc"], r["miss"]) not in seen:
                seen.add((r["doc"], r["miss"]))
                rows.append(r)
    return rows


def ledger_carriers() -> dict[tuple[str, str], str]:
    """R45's written carrier per (doc, fact) - for the pre-repair segment strip."""
    out: dict[tuple[str, str], str] = {}
    for line in open(LEDGER):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("template") == "write_property" and "doc" in r:
            out[(r["doc"], r["fact"])] = r.get("entity_name")
    return out


# ------------------------------------------------------------------- helpers ---
def jaccard(a: str, b: str) -> float:
    ta, tb = set(content_terms(a)), set(content_terms(b))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 0.0


def best_span(fact: str, source_text: str) -> str:
    """Matched sentence + preceding sentence (the ledgered exact span)."""
    sents = [s.strip() for s in _SENT.split(source_text.replace("\n", " ")) if s.strip()]
    if not sents:
        return source_text.strip()
    best_i, best_j = 0, -1.0
    for i, s in enumerate(sents):
        j = jaccard(fact, s)
        if j > best_j:
            best_i, best_j = i, j
    lo = max(0, best_i - 1)
    return " ".join(sents[lo:best_i + 1])


def block_present(name: str, ctx: str) -> bool:
    return name is not None and f"## {name} (".lower() in ctx.lower()


def strip_fact(ctx: str, fact: str) -> str:
    for rem in (" | " + fact, fact):
        if rem in ctx:
            return ctx.replace(rem, " ", 1)
    return ctx


def llm(prompt: str, max_tokens: int = 512) -> tuple[str, int, int]:
    """One gpt-oss call; returns (last-line text, prompt_tokens, completion_tokens).
    gpt-oss reasons in a separate channel - give headroom, fall back to
    reasoning_content (r49_carrier_bakeoff pattern)."""
    r = requests.post(VLLM, json={
        "model": "gpt-oss-120b", "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]}, timeout=300)
    r.raise_for_status()
    j = r.json()
    m = j["choices"][0]["message"]
    text = (m.get("content") or m.get("reasoning_content") or "").strip()
    u = j.get("usage") or {}
    last = text.splitlines()[-1].strip() if text else "ABSTAIN-EMPTY"
    return last, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))


def narrow_repair(span: str, fact: str) -> tuple[str, str, int, int]:
    """ONE narrow KEEP/REVISE/ABSENT call. Returns (decision, stated, ptoks, ctoks)."""
    prompt = (
        f'Source span: "{span}"\n'
        f'Candidate fact: "{fact}"\n'
        "Judge the candidate fact STRICTLY against the source span only - no "
        "outside knowledge, no inference beyond what the span states.\n"
        "- If the span directly states this fact, reply: KEEP <the fact, using "
        "only words that appear in the span>\n"
        "- If the span states a corrected or more precise version, reply: "
        "REVISE <corrected fact grounded in the span>\n"
        "- If the span does not support the fact, reply exactly: ABSENT\n"
        "Reply with ONE line only."
    )
    line, pt, ct = llm(prompt)
    up = line.upper()
    if up.startswith("ABSENT") or up.startswith("ABSTAIN"):
        return "ABSENT", "", pt, ct
    if up.startswith("KEEP"):
        return "KEEP", line[4:].strip().strip('"'), pt, ct
    if up.startswith("REVISE"):
        return "REVISE", line[6:].strip().strip('"'), pt, ct
    return "UNPARSED", line.strip().strip('"'), pt, ct


def anchor_pick(span: str, fact: str, cands: list[dict]) -> tuple[str, str, int, int]:
    """H569 name-match fast path; H568 LLM attacher for ambiguous.
    Returns (carrier_or_None, mode, ptoks, ctoks)."""
    win = span.lower()
    named = [c for c in cands if c["name"].lower() in win]
    if named:
        named.sort(key=lambda c: -len(c["name"]))
        return named[0]["name"], "name_match", 0, 0
    if not cands:
        return None, "no_candidates", 0, 0
    opts = ", ".join(c["name"] for c in sorted(cands, key=lambda c: -c["deg"])[:12])
    line, pt, ct = llm(
        f'Source text: "{span}"\nExtracted fact: "{fact}"\n'
        f"Candidate entities: {opts}\n"
        "Which single candidate entity is this fact ABOUT (its subject)? "
        "If the fact is page boilerplate with no legitimate subject, answer "
        "exactly ABSTAIN. Answer with only the entity name or ABSTAIN.", 512)
    if line.upper().startswith("ABSTAIN") or line.upper().startswith("ABSENT"):
        return None, "llm_abstain", pt, ct
    return line.strip().strip('"'), "llm_attacher", pt, ct


# ---------------------------------------------------------------------- main ---
def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    ckpt = OUT / f"h579-narrow-repair-{ts}.checkpoint.jsonl"
    targets = absent_targets()
    lcar = ledger_carriers()
    print(f"H579: {len(targets)} ABSENT facts / "
          f"{len({t['doc'] for t in targets})} docs (baseline 12/48=25%)", flush=True)

    st = load_settings(CONFIG)
    st.event_log = None

    # ---- read-only graph pull: source text, MENTIONED_IN candidates, titles ---
    src_text: dict[str, str] = {}
    cands_by_doc: dict[str, list[dict]] = {}
    chunk_rows: dict[str, Chunk] = {}
    docs = list({t["doc"] for t in targets})
    # doc -> (bench_file, row) from the h448 `name` field
    docsrc = {t["doc"]: t["name"] for t in targets}
    bench_cache: dict[str, list] = {}
    doc_title: dict[str, str] = {}
    for d, nm in docsrc.items():
        f_, row = nm.split("#row")
        if f_ not in bench_cache:
            bench_cache[f_] = json.loads((BENCH_DIR / f_).read_text())
        doc_title[d] = bench_cache[f_][int(row)]["title"]

    with Foundry(st) as f:
        with f.driver.session() as s:
            for d in docs:
                rows = s.run(
                    "MATCH (c:Chunk)-[:PART_OF]->(dd:KGFDocument {id:$d}) "
                    "RETURN c.id AS id, c.index AS idx, c.text AS text ORDER BY c.index",
                    d=d).data()
                src_text[d] = " ".join((r["text"] or "") for r in rows)
                if rows:
                    r0 = rows[0]
                    chunk_rows[d] = Chunk(
                        id=r0["id"], document_id=d, index=r0["idx"] or 0,
                        text=src_text[d], token_count=len(src_text[d].split()))
                cands_by_doc[d] = s.run(
                    "MATCH (e:Entity)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->"
                    "(dd:KGFDocument {id:$d}) "
                    "RETURN DISTINCT e.name AS name, count{(e)--()} AS deg, "
                    "[l IN labels(e) WHERE l<>'Entity'] AS labels", d=d).data()
            # graph-wide label prevalence (per-type deficit signal for H580)
            label_counts = {r["l"]: r["c"] for r in s.run(
                "MATCH (e:Entity) UNWIND [l IN labels(e) WHERE l<>'Entity'] AS l "
                "RETURN l AS l, count(*) AS c").data()}

        # ---- full re-extraction pass cost: exact multi-stage extract_chunk over
        #      the 20 source chunks with a litellm usage callback (production path,
        #      same as blind pass-2; read-only w.r.t. the graph) ------------------
        import litellm
        usage_log: list = []
        lock = threading.Lock()

        def _cb(kwargs, resp, start, end):
            try:
                u = resp.usage
                with lock:
                    usage_log.append((int(u.prompt_tokens), int(u.completion_tokens)))
            except Exception:
                pass
        litellm.success_callback = [_cb]

        state = f._load_state()
        ontology = Ontology(**state["ontology"])
        purpose = state.get("purpose", "")
        engine = f.extraction_engine
        print(f"cost basis: full-pass extract_chunk over {len(chunk_rows)} chunks",
              flush=True)
        for d, ch in chunk_rows.items():
            try:
                extract_chunk(ch, purpose, ontology, engine, st.extraction)
            except Exception as exc:
                print(f"  extract_chunk {d} failed: {exc}", flush=True)
        litellm.success_callback = []
        full_pass_prompt = sum(p for p, _ in usage_log)
        full_pass_completion = sum(c for _, c in usage_log)
        full_pass_tokens = full_pass_prompt + full_pass_completion
        print(f"full pass: {len(usage_log)} calls, {full_pass_tokens} tokens "
              f"(p={full_pass_prompt} c={full_pass_completion})", flush=True)

        # ---- narrow-repair loop (48 facts), checkpointed per fact --------------
        cases = []
        nr_p = nr_c = at_p = at_c = 0
        with ckpt.open("w") as fh:
            for i, t in enumerate(targets):
                d, fact = t["doc"], t["miss"]
                span = best_span(fact, src_text.get(d, ""))
                decision, stated, pt, ct = narrow_repair(span, fact)
                nr_p += pt
                nr_c += ct
                recovered = decision in ("KEEP", "REVISE", "UNPARSED") and bool(
                    stated) and supported(fact, stated, THRESHOLD)
                carrier, cmode, apt, act = anchor_pick(span, fact, cands_by_doc.get(d, []))
                at_p += apt
                at_c += act
                # anchor carrier labels (for H580 type-deficit) + rarity
                clabels = next((c["labels"] for c in cands_by_doc.get(d, [])
                                if c["name"] == carrier), [])
                lab_min = min((label_counts.get(l, 10**9) for l in clabels),
                              default=None)
                rec = {
                    "doc": d, "fact": fact, "doc_title": doc_title.get(d),
                    "span": span, "decision": decision, "stated": stated,
                    "recovered": recovered, "carrier": carrier,
                    "carrier_mode": cmode, "carrier_labels": clabels,
                    "carrier_label_min_count": lab_min,
                    "ledger_carrier": lcar.get((d, fact)),
                    "narrow_prompt_tokens": pt, "narrow_completion_tokens": ct,
                }
                cases.append(rec)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"[{i+1}/{len(targets)}] {decision:7s} rec={int(recovered)} "
                      f"car={carrier} :: {fact[:52]}", flush=True)

        # ---- probe-flip simulation (H547 pattern, in-memory, read-only) --------
        f.settings.graphrag.render_budget = f.settings.graphrag.render_budget  # shipped
        for rec in cases:
            d, fact = rec["doc"], rec["fact"]
            title = rec["doc_title"]
            res = f.probe(title) if title else {"context_lines": []}
            ctx_A = " ".join(res.get("context_lines", []))
            # pre-repair baseline: strip R45's written segment for THIS fact
            ctx_A_clean = strip_fact(ctx_A, fact)
            supA = supported(fact, ctx_A_clean, THRESHOLD)
            flippable = rec["recovered"] and (not supA)
            anchor_in = block_present(rec["carrier"], ctx_A_clean)
            move = rec["stated"] or fact
            ctx_B = (ctx_A_clean + " | " + move) if anchor_in else ctx_A_clean
            supB = supported(fact, ctx_B, THRESHOLD)
            flip = bool(flippable and supB)
            rec.update({
                "probe_supA": bool(supA), "pre_repair_absent": bool(not supA),
                "anchor_block_in_render": bool(anchor_in),
                "probe_supB": bool(supB), "flippable": bool(flippable),
                "flip": flip, "n_render_lines": len(res.get("context_lines", [])),
            })

    # -------------------------------------------------------------- aggregate ---
    n = len(cases)
    n_rec = sum(c["recovered"] for c in cases)
    recovery_rate = n_rec / n if n else 0.0
    narrow_tokens = nr_p + nr_c
    repair_tokens = narrow_tokens + at_p + at_c   # repair = narrow + attacher
    cost_fraction_narrow = narrow_tokens / full_pass_tokens if full_pass_tokens else None
    cost_fraction_repair = repair_tokens / full_pass_tokens if full_pass_tokens else None
    flippable = [c for c in cases if c["flippable"]]
    flips = [c for c in cases if c["flip"]]
    probe_flip_rate = (len(flips) / len(flippable)) if flippable else 0.0

    clauses = [
        {"clause": "recovery >= 60% (CONFIRM) / < 40% (KILL); beats blind 25%",
         "measured": round(recovery_rate, 4), "n_recovered": n_rec, "n": n,
         "confirm": recovery_rate >= 0.60, "kill": recovery_rate < 0.40},
        {"clause": "cost <= 20% of one full pass (CONFIRM) / > 50% (KILL)",
         "measured_narrow": (round(cost_fraction_narrow, 4)
                             if cost_fraction_narrow is not None else None),
         "measured_repair_incl_attacher": (round(cost_fraction_repair, 4)
                                           if cost_fraction_repair is not None else None),
         "confirm": (cost_fraction_repair is not None and cost_fraction_repair <= 0.20),
         "kill": (cost_fraction_repair is not None and cost_fraction_repair > 0.50)},
        {"clause": "probe-flip >= 50% of flippable (CONFIRM) / < 25% (KILL)",
         "measured": round(probe_flip_rate, 4), "n_flips": len(flips),
         "n_flippable": len(flippable),
         "confirm": probe_flip_rate >= 0.50, "kill": probe_flip_rate < 0.25},
    ]
    # verdict per registered bar
    kill = (recovery_rate < 0.40
            or (cost_fraction_repair is not None and cost_fraction_repair > 0.50)
            or (probe_flip_rate < 0.25))
    confirm = (recovery_rate >= 0.60
               and cost_fraction_repair is not None and cost_fraction_repair <= 0.20
               and probe_flip_rate >= 0.50)
    verdict = "CONFIRMED" if confirm else ("KILLED" if kill else "PARTIAL")

    summary = {
        "hypothesis": "R49-H579", "run_id": ts, "config": str(CONFIG),
        "neo4j_uri": st.neo4j.uri, "pile": "R45 PILOT (172.19.0.101), read-only",
        "n": n, "baseline_blind_pass2": "12/48 = 0.25",
        "recovery_rate": round(recovery_rate, 4), "n_recovered": n_rec,
        "match_criterion": "H389/H450 supported(gold_fact, stated, 0.8) AND "
                           "decision in {KEEP,REVISE}; same term-share rule as blind pass-2",
        "cost": {
            "narrow_repair_tokens": narrow_tokens,
            "attacher_tokens": at_p + at_c,
            "repair_total_tokens": repair_tokens,
            "full_pass_tokens": full_pass_tokens,
            "full_pass_calls": len(usage_log),
            "full_pass_chunks": len(chunk_rows),
            "cost_fraction_narrow_only": (round(cost_fraction_narrow, 4)
                                          if cost_fraction_narrow is not None else None),
            "cost_fraction_repair": (round(cost_fraction_repair, 4)
                                     if cost_fraction_repair is not None else None),
            "basis": "full pass = exact multi-stage extract_chunk (enumeration + "
                     "extraction + gleaning) over the 20 source chunks via litellm "
                     "usage callback - the production path blind pass-2 ran",
        },
        "probe_flip": {
            "rate": round(probe_flip_rate, 4), "n_flips": len(flips),
            "n_flippable": len(flippable),
            "note": "H547 in-memory sim: recovered fact reaches the doc_title "
                    "render iff the anchor carrier block survives; flippable = "
                    "recovered AND absent from pre-repair render",
        },
        "carrier_modes": {m: sum(c["carrier_mode"] == m for c in cases)
                          for m in {c["carrier_mode"] for c in cases}},
        "decision_dist": {dd: sum(c["decision"] == dd for c in cases)
                          for dd in {c["decision"] for c in cases}},
        "clauses": clauses, "proposed_verdict": verdict,
    }
    out_path = OUT / f"h579-narrow-repair-{ts}.json"
    out_path.write_text(json.dumps({"summary": summary, "cases": cases},
                                   indent=1, ensure_ascii=False))
    print("\nSUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    print(f"WROTE {out_path}", flush=True)


if __name__ == "__main__":
    main()

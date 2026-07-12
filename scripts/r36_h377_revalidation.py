"""R36-H377: revalidation, not regeneration - the groundedness gate as a
staleness detector on H376's dirty set.

H376's E2 event (re-version of d_a2b1f7a495a9deda, the SleepStyle 200 manual)
dirty-flags every D-sourced derived object. The derived TEXT objects on the
pile are the entity DESCRIPTIONS (stored propositions: none - H376 census).
This A/B builds a real v2 of the document (spec values in half the chunks
perturbed deterministically) and, on a stratified sample of dirty
descriptions, compares:

  gate arm      - one entailment call per object: "does the v2 source still
                  support every claim in this description?" -> keep/regenerate
  reference arm - regenerate the description from the v2 source, then an
                  equivalence judge decides whether regeneration changed the
                  object -> the ground-truth keep/regenerate decision

Registered clauses: >= 90% decision agreement, >= 50% rescued (kept),
gate cost <= 1/10 of regeneration. REFUTED if agreement < 80%.

Regeneration is priced two ways: (a) the in-engine unit - re-extraction of the
changed chunk (the pipeline's actual generator; cost amortized over the dirty
objects in that chunk), the primary comparator; (b) description-only regen,
the conservative lower bound. All LLM calls go to the local vLLM
(gpt-oss-120b, http://localhost:8010) with 600s client timeouts.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import time

from neo4j import GraphDatabase
import requests

URI = "bolt://172.19.0.100:7687"  # neo4j4 - verified, .env override bypassed (DEF-4)
DOC = "d_a2b1f7a495a9deda"
LLM = "http://localhost:8010/v1/chat/completions"
MODEL = "gpt-oss-120b"
TIMEOUT = 600
SAMPLE_N = 48
SEED = 36377
SRC_CAP = 6000  # chars of source shown per call

_UNIT_NUM = re.compile(
    r"(?<![A-Za-z0-9.\-])(\d+(?:\.\d+)?)(\s*)"
    r"(kg|g|mg|w|watts|cm|mm|m|db\(a\)|dba|db|l|ml|hz|khz|hours|hour|hrs|"
    r"minutes|minute|mins|min|seconds|°c|°f|%|v|volts|va|psi|kpa|hpa|lpm|bpm)\b",
    re.IGNORECASE,
)


def perturb(text: str) -> tuple[str, int]:
    """v2 edit: every unit-carrying spec value shifted (x2 + 1 on the integer
    part) - a deterministic, unambiguous fact change."""
    n = 0

    def repl(m):
        nonlocal n
        n += 1
        val = m.group(1)
        if "." in val:
            head, tail = val.split(".", 1)
            new = f"{int(head) * 2 + 1}.{tail}"
        else:
            new = str(int(val) * 2 + 1)
        return f"{new}{m.group(2)}{m.group(3)}"

    return _UNIT_NUM.sub(repl, text), n


def llm(system: str, user: str) -> dict:
    t0 = time.time()
    last = None
    for _ in range(3):
        try:
            r = requests.post(LLM, json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "max_tokens": 4096,
            }, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()
            u = body["usage"]
            return {
                "text": body["choices"][0]["message"]["content"] or "",
                "prompt_tokens": u["prompt_tokens"],
                "completion_tokens": u["completion_tokens"],
                "total_tokens": u["total_tokens"],
                "seconds": round(time.time() - t0, 2),
            }
        except Exception as exc:  # queue latency is not failure - retry
            last = exc
            time.sleep(5)
    raise RuntimeError(f"LLM call failed after retries: {last}")


def parse_bool(text: str, key: str) -> bool:
    m = re.search(rf'"{key}"\s*:\s*(true|false)', text, re.IGNORECASE)
    if m:
        return m.group(1).lower() == "true"
    # lenient fallback: last standalone yes/no or true/false
    low = text.strip().lower()
    for token, val in (("true", True), ("false", False), ("yes", True), ("no", False)):
        if re.search(rf"\b{token}\b", low.split("}")[-1] or low):
            return val
    return "true" in low and "false" not in low


GATE_SYS = (
    "You are a groundedness gate for a knowledge graph. You are given a SOURCE "
    "text (the current version of a document) and a stored DESCRIPTION of an "
    "entity that was derived from an earlier version. Decide whether the source "
    "still fully supports every factual claim in the description. Changed "
    "numeric values, contradicted claims, or claims about the entity that the "
    "source no longer supports mean NOT supported. Paraphrase is fine. "
    'Answer with JSON only: {"supported": true} or {"supported": false}.'
)

REGEN_SYS = (
    "You write entity descriptions for a knowledge graph. From the SOURCE text "
    "only, write a 1-3 sentence factual description of the named entity. Use "
    "only facts present in the source. If the entity is not mentioned, say "
    "exactly: NOT MENTIONED."
)

JUDGE_SYS = (
    "You compare two descriptions of the same entity. Decide whether they make "
    "the same factual claims. Wording differences and minor omissions are "
    "equivalent; any changed value, contradicted fact, or claim present in A "
    "but impossible per B means NOT equivalent. "
    'Answer with JSON only: {"equivalent": true} or {"equivalent": false}.'
)

EXTRACT_SYS = (
    "You are a knowledge-graph extractor. From the given text extract every "
    "entity as JSON: {\"entities\": [{\"name\": str, \"types\": [str], "
    "\"description\": str, \"properties\": {}}], \"relationships\": "
    "[{\"source\": str, \"target\": str, \"type\": str}]}. Be exhaustive."
)


def main():
    rng = random.Random(SEED)
    driver = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with driver.session() as s:
        chunks = {r["id"]: r["text"] for r in s.run(
            "MATCH (c:Chunk)-[:PART_OF]->(:KGFDocument {id:$d}) "
            "RETURN c.id AS id, c.text AS text ORDER BY c.id", d=DOC)}
        ents = s.run(
            "MATCH (e:Entity) WHERE $d IN e.source_documents "
            "AND e.description IS NOT NULL AND e.description <> '' "
            "RETURN e.id AS id, e.name AS name, labels(e) AS types, "
            "e.description AS description, e.source_chunks AS source_chunks, "
            "size(e.source_documents) AS ndocs ORDER BY e.id", d=DOC).data()
    driver.close()

    # v2 of the document: perturb spec values in every second chunk
    chunk_ids = sorted(chunks)
    v2, edits = {}, {}
    for i, cid in enumerate(chunk_ids):
        if i % 2 == 0:
            v2[cid], edits[cid] = perturb(chunks[cid])
        else:
            v2[cid], edits[cid] = chunks[cid], 0
    print(f"v2 built: {sum(edits.values())} spec edits across "
          f"{sum(1 for e in edits.values() if e)} of {len(chunk_ids)} chunks", flush=True)

    single = [e for e in ents if e["ndocs"] == 1]
    multi = [e for e in ents if e["ndocs"] > 1]
    k_single = min(len(single), round(SAMPLE_N * len(single) / len(ents)))
    sample = rng.sample(single, k_single) + rng.sample(multi, SAMPLE_N - k_single)
    print(f"dirty descriptions: {len(ents)} ({len(single)} single-doc); "
          f"sampled {len(sample)} ({k_single} single-doc)", flush=True)

    def v2_source(e):
        parts = [v2[c] for c in (e["source_chunks"] or []) if c in v2]
        if not parts:  # source chunks outside D (multi-doc): D's v2 text is the trigger
            parts = [v2[c] for c in chunk_ids]
        src = "\n---\n".join(parts)
        return src[:SRC_CAP]

    def run_object(e):
        name = e["name"]
        types = ", ".join(t for t in e["types"] if t != "Entity") or "Entity"
        src = v2_source(e)
        gate = llm(GATE_SYS, f"SOURCE:\n{src}\n\nENTITY: {name} ({types})\n"
                             f"DESCRIPTION:\n{e['description']}")
        regen = llm(REGEN_SYS, f"SOURCE:\n{src}\n\nENTITY: {name} ({types})")
        judge = llm(JUDGE_SYS, f"ENTITY: {name}\nDESCRIPTION A (stored):\n"
                               f"{e['description']}\n\nDESCRIPTION B (regenerated "
                               f"from current source):\n{regen['text'].strip()}")
        gate_keep = parse_bool(gate["text"], "supported")
        regen_missing = "NOT MENTIONED" in regen["text"].upper()
        ref_keep = (not regen_missing) and parse_bool(judge["text"], "equivalent")
        return {
            "id": e["id"], "name": name, "ndocs": e["ndocs"],
            "gate_decision": "keep" if gate_keep else "regenerate",
            "reference_decision": "keep" if ref_keep else "regenerate",
            "regen_not_mentioned": regen_missing,
            "regenerated": regen["text"].strip()[:300],
            "gate_usage": {k: gate[k] for k in
                           ("prompt_tokens", "completion_tokens", "total_tokens", "seconds")},
            "regen_usage": {k: regen[k] for k in
                            ("prompt_tokens", "completion_tokens", "total_tokens", "seconds")},
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_object, sample))
    for r in results:
        mark = "==" if r["gate_decision"] == r["reference_decision"] else "!="
        print(f"  {r['name'][:40]:<40} gate={r['gate_decision']:<10} "
              f"{mark} ref={r['reference_decision']}", flush=True)

    # true in-engine regeneration unit: re-extraction of each dirty chunk,
    # amortized over the sampled dirty objects sourced from it
    dirty_chunks = sorted({c for e in sample for c in (e["source_chunks"] or []) if c in v2})
    with ThreadPoolExecutor(max_workers=4) as pool:
        extractions = list(pool.map(
            lambda cid: (cid, llm(EXTRACT_SYS, v2[cid][:SRC_CAP])), dirty_chunks))
    extract_usage = {cid: {k: u[k] for k in
                           ("prompt_tokens", "completion_tokens", "total_tokens", "seconds")}
                     for cid, u in extractions}
    per_chunk_objects = {cid: sum(1 for e in ents if cid in (e["source_chunks"] or []))
                         for cid in dirty_chunks}

    # ---- adjudication ----
    n = len(results)
    agree = sum(r["gate_decision"] == r["reference_decision"] for r in results)
    rescued = sum(r["gate_decision"] == "keep" for r in results)
    ref_keep = sum(r["reference_decision"] == "keep" for r in results)

    def tot(key, field):
        return sum(r[key][field] for r in results)

    gate_total = tot("gate_usage", "total_tokens")
    regen_desc_total = tot("regen_usage", "total_tokens")
    # amortized re-extraction cost per sampled object: its chunks' extraction
    # cost split over ALL dirty objects those chunks source
    regen_extract_total = 0.0
    for e in [x for x in sample]:
        for cid in (e["source_chunks"] or []):
            if cid in extract_usage:
                regen_extract_total += (
                    extract_usage[cid]["total_tokens"] / per_chunk_objects[cid])

    metrics = {
        "n": n,
        "agreement": round(agree / n, 4),
        "rescued_fraction": round(rescued / n, 4),
        "reference_keep_fraction": round(ref_keep / n, 4),
        "gate_tokens_total": gate_total,
        "gate_completion_tokens": tot("gate_usage", "completion_tokens"),
        "regen_desc_tokens_total": regen_desc_total,
        "regen_desc_completion_tokens": tot("regen_usage", "completion_tokens"),
        "regen_extract_tokens_amortized": round(regen_extract_total, 1),
        "cost_ratio_vs_desc_regen_total": round(gate_total / regen_desc_total, 4),
        "cost_ratio_vs_desc_regen_completion": round(
            tot("gate_usage", "completion_tokens")
            / max(1, tot("regen_usage", "completion_tokens")), 4),
        "cost_ratio_vs_extract_regen": round(
            gate_total / regen_extract_total, 4) if regen_extract_total else None,
        "gate_wallclock_s": round(tot("gate_usage", "seconds"), 1),
        "regen_desc_wallclock_s": round(tot("regen_usage", "seconds"), 1),
    }
    clauses = {
        "agreement_ge_90": metrics["agreement"] >= 0.90,
        "agreement_ge_80_floor": metrics["agreement"] >= 0.80,
        "rescued_ge_50": metrics["rescued_fraction"] >= 0.50,
        "cost_le_tenth_of_regeneration": (
            metrics["cost_ratio_vs_extract_regen"] is not None
            and metrics["cost_ratio_vs_extract_regen"] <= 0.10),
        "cost_le_tenth_of_desc_regen_lower_bound":
            metrics["cost_ratio_vs_desc_regen_total"] <= 0.10,
    }
    if not clauses["agreement_ge_80_floor"]:
        verdict = "REFUTED"  # registered: gate unreliable -> regenerate-always
    elif clauses["agreement_ge_90"] and clauses["rescued_ge_50"] and \
            clauses["cost_le_tenth_of_regeneration"]:
        verdict = "CONFIRMED"
    else:
        verdict = "PARTIAL"

    print(json.dumps(metrics, indent=2), flush=True)
    print("clauses:", json.dumps(clauses), flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r36-h377-revalidation-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R36-H377 groundedness gate as staleness revalidator",
        "generated": ts, "graph_uri": URI, "doc": DOC, "model": MODEL,
        "seed": SEED, "sample_n": n,
        "v2_edits": {"total_spec_edits": sum(edits.values()),
                     "edited_chunks": sum(1 for e in edits.values() if e),
                     "chunks": len(chunk_ids), "per_chunk": edits},
        "metrics": metrics, "clauses": clauses, "verdict": verdict,
        "extraction_usage_per_chunk": extract_usage,
        "objects_per_dirty_chunk": per_chunk_objects,
        "decisions": results,
    }, indent=2, default=str))
    print(f"\nH377 REVALIDATION COMPLETE -> {out} verdict={verdict}", flush=True)


if __name__ == "__main__":
    main()

"""R49-H545: heretic panel test - do per-region structural metrics predict
probe pass/fail above chance, or beyond the per-doc certificate?

H37/R08 doctrine: a metric earns its place only if it predicts probe outcomes,
triggers maintenance earlier/cheaper, or improves a decision at matched budget.
This harness prices the five R45 structural metrics (per-REGION versions) as
probe-outcome predictors against the powered n=132 medium screen, and asks
whether any adds signal over the per-doc certificate coverage (H484).

Region per probe = union over the probe's gold docs of {entities MENTIONED_IN
the doc's chunk} plus their 1-hop Entity-neighbours, induced Entity subgraph.

The five metrics (per-region, mirroring scripts/experiments/r45_metric_sweep.py):
  assortativity (H473)  nx.degree_assortativity_coefficient(region)
  hub condensation (H475)  max_deg / m  (share of region edges on top-degree node)
  description length (H480)  mean len(e.description) over region entities
  rel-vocab entropy (H481)  Shannon entropy (bits) of region edge relationship types
  Forman-Ricci mean (H486)  mean over region edges of 4 - deg(u) - deg(v)  (region-induced deg)
Conditioning metric = per-doc certificate coverage (H484), per-probe = mean over gold docs.

Modes:
  cert     scoped LLM certificate pass over the 132 probes' gold docs (launch DETACHED)
  analyze  build regions/metrics, read certificate jsonl, compute AUC / partial-r, write result JSON

Usage:
  python scripts/experiments/r49_h545_panel_h37.py cert
  python scripts/experiments/r49_h545_panel_h37.py analyze reports/experiments/r49/h545-cert-<ts>.jsonl

READ-ONLY on Neo4j (MATCH/RETURN only). No writes anywhere in the graph.
"""

import argparse
import glob
import json
import math
import re
import statistics as st
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np
from neo4j import GraphDatabase

NEO4J_URI = "bolt://172.19.0.9:7687"
AUTH = ("neo4j", "kgfoundry")
SCREEN = Path("reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
SLICE_DIR = Path("data/interim/bench")
OUT = Path("reports/experiments/r49")
CONFIG = Path("config/experiments/config-bench-medium.yml")
H389_GLOB = "reports/experiments/r39/h389-coverage-*.jsonl"

# ---- certificate term machinery (verbatim from r39_h389_coverage_audit.py) ----
_STOP = frozenset(
    "a an the of in on at to for with and or is are was were be been has have had by from as its it this that".split()
)


def _norm_terms(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())


def content_terms(s: str) -> list[str]:
    return [
        t for t in _norm_terms(s).split()
        if t not in _STOP and (len(t) > 2 or any(ch.isdigit() for ch in t))
    ]


def grounded(probe: str, chunk_text: str) -> bool:
    chunk_terms = set(_norm_terms(chunk_text).split())
    terms = content_terms(probe)
    return bool(terms) and all(t in chunk_terms for t in terms)


def supported(probe: str, graph_text: str, threshold: float = 0.8) -> bool:
    terms = content_terms(probe)
    if not terms:
        return False
    graph_terms = set(_norm_terms(graph_text).split())
    return sum(t in graph_terms for t in terms) / len(terms) >= threshold


GEN_SYSTEM = (
    "You extract short factual statements from text. Each statement must use ONLY "
    "words that literally appear in the given text - no paraphrase, no synonyms, no "
    "inference. One statement per line, no numbering, at most {k} statements."
)


# ---- probe / gold-doc mapping ----
def load_off_probes() -> list[dict]:
    probes = []
    for line in SCREEN.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["arm"] == "off":
            probes.append({"id": r["id"], "question": r["question"], "pass": bool(r["pass"])})
    return probes


def gold_titles(q: dict) -> list[str]:
    out = []
    for it in (q.get("supporting_facts") or []):
        t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
        if t and t not in out:
            out.append(t)
    return out


def load_slices() -> dict[str, list[str]]:
    return {p.name: [r["title"] for r in json.loads(p.read_text())] for p in SLICE_DIR.glob("2wiki-*.json")}


def build_title2name(graph_names: set[str], slices: dict[str, list[str]]) -> dict[str, str]:
    """title -> graph docname, built ONLY from doc names present in the graph
    (guarantees the mapped doc exists), mirroring the screen's ingested_titles."""
    t2n = {}
    for n in graph_names:
        m = re.match(r"^(.+\.json)#row(\d+)$", n or "")
        if not m:
            continue
        titles = slices.get(m.group(1))
        idx = int(m.group(2))
        if titles and idx < len(titles):
            t2n.setdefault(titles[idx], n)
    return t2n


def probe_gold_doc_ids(probes: list[dict], name2id: dict[str, str]) -> dict[str, list[str]]:
    Q = {q["_id"]: q for q in json.loads(QUESTIONS.read_text())}
    slices = load_slices()
    t2n = build_title2name(set(name2id), slices)
    out = {}
    for p in probes:
        q = Q.get(p["id"])
        dids = []
        if q:
            for t in gold_titles(q):
                n = t2n.get(t)
                if n and n in name2id and name2id[n] not in dids:
                    dids.append(name2id[n])
        out[p["id"]] = dids
    return out


# ---- certificate mode ----
def _cert_one(engine, name, chunks, ent_text):
    probes_txt, misses = [], []
    for chunk in chunks:
        raw = engine.complete_text(
            GEN_SYSTEM.format(k=5),
            f"Text:\n{chunk}\n\nStatements (verbatim words only):",
        )
        gens = [ln.strip("-* ").strip() for ln in raw.splitlines() if ln.strip()]
        for p in [g for g in gens if grounded(g, chunk)][:5]:
            probes_txt.append(p)
            if not supported(p, ent_text):
                misses.append(p)
    coverage = round(1 - len(misses) / len(probes_txt), 4) if probes_txt else None
    return {"probes": len(probes_txt), "coverage": coverage, "misses": misses}


def run_cert(resume_path=None, concurrency=8):
    """Scoped certificate over the 132 probes' gold docs. Concurrent client-side
    (vLLM batches the requests) and RESUMABLE - docs already in resume_path are
    skipped, honouring the detached-compute checkpoint rule. The sibling H548
    cert job shares the same vLLM; vLLM schedules both fairly."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    from knowledge_graph_foundry import load_settings
    from knowledge_graph_foundry.engines import create_engine
    from knowledge_graph_foundry.pipeline import Foundry

    OUT.mkdir(parents=True, exist_ok=True)
    if resume_path:
        out_path = Path(resume_path)
        done = set()
        if out_path.exists():
            for line in out_path.read_text().splitlines():
                if line.strip():
                    done.add(json.loads(line)["doc"])
        print(f"h545 cert RESUME into {out_path}: {len(done)} docs already done", flush=True)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = OUT / f"h545-cert-{ts}.jsonl"
        done = set()

    settings = load_settings(CONFIG)
    settings.event_log = None
    engine = create_engine(settings.llm)

    probes = load_off_probes()
    with Foundry(settings) as f, f.driver.session() as s:
        name2id = dict(s.run("MATCH (d:KGFDocument) RETURN d.name AS n, d.id AS id").values("n", "id"))
        pg = probe_gold_doc_ids(probes, name2id)
        gold_ids = sorted({d for ds in pg.values() for d in ds})
        todo = [d for d in gold_ids if d not in done]
        print(f"h545 cert: {len(probes)} probes -> {len(gold_ids)} gold docs, {len(todo)} to do -> {out_path}", flush=True)
        # prefetch graph payloads sequentially (cheap), then LLM in parallel
        payloads = {}
        for did in todo:
            row = s.run(
                "MATCH (d:KGFDocument {id:$d})<-[:PART_OF]-(c:Chunk) "
                "RETURN d.name AS name, collect(c.text) AS chunks",
                d=did,
            ).single()
            ents = s.run(
                "MATCH (e:Entity) WHERE $d IN e.source_documents "
                "RETURN e.name AS n, e.description AS de, properties(e) AS p",
                d=did,
            ).data()
            parts = []
            for e in ents:
                parts.append(e["n"] or "")
                parts.append(e["de"] or "")
                parts.append(json.dumps({k: v for k, v in (e["p"] or {}).items() if isinstance(v, str)}))
            payloads[did] = (row["name"], row["chunks"], " ".join(parts))

    lock = Lock()
    counter = {"n": 0}

    def work(did):
        name, chunks, ent_text = payloads[did]
        r = _cert_one(engine, name, chunks, ent_text)
        rec = {"doc": did, "name": name, **r}
        with lock:
            with out_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            counter["n"] += 1
            print(f"[{counter['n']}/{len(todo)}] {name}: coverage={r['coverage']} probes={r['probes']}", flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(work, d) for d in todo]
        for _ in as_completed(futs):
            pass
    print(f"H545 CERT COMPLETE -> {out_path}", flush=True)


# ---- analysis helpers ----
def roc_auc(y: list[int], x: list[float]) -> float:
    """AUC via rank statistic (Mann-Whitney). Ties averaged. sklearn fallback-free."""
    order = sorted(range(len(x)), key=lambda i: x[i])
    ranks = [0.0] * len(x)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    pos = [ranks[i] for i in range(len(y)) if y[i] == 1]
    n_pos = len(pos)
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return (sum(pos) - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return float("nan")
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def partial_r(x: list[float], y: list[float], c: list[float]) -> float:
    """Partial Pearson r of x with y controlling for c."""
    rxy, rxc, ryc = pearson(x, y), pearson(x, c), pearson(y, c)
    if any(math.isnan(v) for v in (rxy, rxc, ryc)):
        return float("nan")
    denom = math.sqrt((1 - rxc ** 2) * (1 - ryc ** 2))
    if denom == 0:
        return float("nan")
    return (rxy - rxc * ryc) / denom


# ---- analyze mode ----
def run_analyze(cert_path: Path):
    probes = load_off_probes()
    driver = GraphDatabase.driver(NEO4J_URI, auth=AUTH)
    with driver.session() as s:
        edges = s.run("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id AS a, b.id AS b, type(r) AS t").data()
        desc = dict(s.run("MATCH (e:Entity) RETURN e.id AS id, size(coalesce(e.description,'')) AS dl").values("id", "dl"))
        name2id = dict(s.run("MATCH (d:KGFDocument) RETURN d.name AS n, d.id AS id").values("n", "id"))
        core_rows = s.run(
            "MATCH (d:KGFDocument)<-[:PART_OF]-(c:Chunk)<-[:MENTIONED_IN]-(e:Entity) "
            "RETURN d.id AS did, collect(DISTINCT e.id) AS ents"
        ).data()
    driver.close()
    doccore = {r["did"]: set(r["ents"]) for r in core_rows}

    G = nx.Graph()
    reltypes: dict[frozenset, list[str]] = {}
    for e in edges:
        u, v, t = e["a"], e["b"], e["t"]
        if u == v:
            continue
        G.add_edge(u, v)
        reltypes.setdefault(frozenset((u, v)), []).append(t)

    pg = probe_gold_doc_ids(probes, name2id)

    # certificate coverage per doc: fresh scoped run first, existing h389 as fallback
    cov: dict[str, float] = {}
    if cert_path and cert_path.exists():
        for line in cert_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("coverage") is not None:
                    cov[r["doc"]] = r["coverage"]
    for f in glob.glob(H389_GLOB):
        for line in Path(f).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("coverage") is not None:
                    cov.setdefault(r["doc"], r["coverage"])

    def region_metrics(gold_ids: list[str]) -> dict:
        nodes = set()
        for did in gold_ids:
            nodes |= doccore.get(did, set())
        hop = set(nodes)
        for u in nodes:
            if u in G:
                hop |= set(G.neighbors(u))
        H = G.subgraph(hop)
        n, m = H.number_of_nodes(), H.number_of_edges()
        degs = [d for _, d in H.degree()]
        try:
            asort = nx.degree_assortativity_coefficient(H)
            if isinstance(asort, float) and math.isnan(asort):
                asort = None
        except Exception:
            asort = None
        hub = (max(degs) / m) if (m > 0 and degs) else None
        dl = st.mean(desc.get(u, 0) for u in H.nodes()) if n > 0 else None
        tc = Counter()
        for u, v in H.edges():
            for t in reltypes.get(frozenset((u, v)), []):
                tc[t] += 1
        tot = sum(tc.values())
        ent = (-sum((c / tot) * math.log2(c / tot) for c in tc.values())) if tot > 0 else None
        frc = [4 - H.degree(u) - H.degree(v) for u, v in H.edges()]
        fr = st.mean(frc) if frc else None
        return {"n_region": n, "m_region": m, "n_core": len(nodes),
                "assortativity": asort, "hub_condensation": hub, "desc_length": dl,
                "rel_entropy": ent, "forman_ricci": fr}

    METRICS = ["assortativity", "hub_condensation", "desc_length", "rel_entropy", "forman_ricci"]
    per_probe = []
    for p in probes:
        gids = pg[p["id"]]
        rm = region_metrics(gids)
        cvals = [cov[d] for d in gids if d in cov]
        cert = st.mean(cvals) if cvals else None
        per_probe.append({
            "id": p["id"], "question": p["question"], "pass": int(p["pass"]),
            "n_gold_docs": len(gids), "n_gold_docs_with_cert": len(cvals),
            "certificate_coverage": cert, **rm,
        })

    # per-metric AUC + partial r conditioned on certificate
    per_metric = {}
    for mkey in METRICS:
        rows = [r for r in per_probe if r[mkey] is not None]
        y = [r["pass"] for r in rows]
        x = [r[mkey] for r in rows]
        auc = roc_auc(y, x)
        auc_or = max(auc, 1 - auc) if not math.isnan(auc) else float("nan")
        prows = [r for r in rows if r["certificate_coverage"] is not None]
        pr = partial_r([r[mkey] for r in prows], [float(r["pass"]) for r in prows],
                       [r["certificate_coverage"] for r in prows]) if len(prows) >= 3 else float("nan")
        per_metric[mkey] = {
            "n": len(rows), "auc": None if math.isnan(auc) else round(auc, 4),
            "auc_oriented": None if math.isnan(auc_or) else round(auc_or, 4),
            "partial_r_given_cert": None if math.isnan(pr) else round(pr, 4),
            "abs_partial_r": None if math.isnan(pr) else round(abs(pr), 4),
            "n_partial": len(prows),
        }

    crows = [r for r in per_probe if r["certificate_coverage"] is not None]
    cy = [r["pass"] for r in crows]
    cx = [r["certificate_coverage"] for r in crows]
    cauc = roc_auc(cy, cx)
    cauc_or = max(cauc, 1 - cauc) if not math.isnan(cauc) else float("nan")
    certificate_auc = {
        "n": len(crows), "auc": None if math.isnan(cauc) else round(cauc, 4),
        "auc_oriented": None if math.isnan(cauc_or) else round(cauc_or, 4),
        "cert_min": round(min(cx), 4) if cx else None, "cert_max": round(max(cx), 4) if cx else None,
        "cert_mean": round(st.mean(cx), 4) if cx else None,
        "cert_frac_below_1": round(sum(1 for v in cx if v < 1.0) / len(cx), 4) if cx else None,
    }

    # clause + verdict logic
    def clears_auc(mkey):
        v = per_metric[mkey]["auc_oriented"]
        return v is not None and v >= 0.65

    def keeps_partial(mkey):
        v = per_metric[mkey]["abs_partial_r"]
        return v is not None and v >= 0.15

    n_auc = sum(clears_auc(m) for m in METRICS)
    n_partial = sum(keeps_partial(m) for m in METRICS)
    n_both = sum(clears_auc(m) and keeps_partial(m) for m in METRICS)
    cert_alone = certificate_auc["auc_oriented"]

    clauses = [
        {"clause": "P1: none of the five reaches AUC >= 0.65 (oriented)",
         "predicted": "all five AUC_oriented < 0.65",
         "measured": f"{n_auc}/5 metrics clear 0.65; max={max((per_metric[m]['auc_oriented'] or 0) for m in METRICS):.4f}",
         "holds": n_auc == 0},
        {"clause": "P2: none retains partial |r| >= 0.15 given certificate",
         "predicted": "all five |partial r| < 0.15",
         "measured": f"{n_partial}/5 metrics keep |partial r| >= 0.15; max={max((per_metric[m]['abs_partial_r'] or 0) for m in METRICS):.4f}",
         "holds": n_partial == 0},
        {"clause": "P3: certificate alone AUC >= 0.70",
         "predicted": ">= 0.70",
         "measured": f"cert AUC_oriented={cert_alone}",
         "holds": cert_alone is not None and cert_alone >= 0.70},
    ]

    if n_both >= 3:
        verdict = "SURVIVES"
    elif n_auc <= 1 and n_partial == 0:
        verdict = "KILLED-panel"
    else:
        verdict = "INCONCLUSIVE"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "hypothesis": "R49-H545",
        "generated": ts,
        "config": str(CONFIG),
        "screen": str(SCREEN),
        "cert_source": str(cert_path) if cert_path else None,
        "n_probes": len(per_probe),
        "n_pass": sum(r["pass"] for r in per_probe),
        "n_fail": sum(1 - r["pass"] for r in per_probe),
        "metrics": METRICS,
        "conventions": {
            "region": "union over probe gold docs of MENTIONED_IN entities + 1-hop, induced Entity subgraph",
            "hub_condensation": "max_deg / m_region",
            "forman_ricci": "mean over region edges of 4 - deg(u) - deg(v), region-induced degrees",
            "auc_oriented": "max(auc, 1-auc) - direction-agnostic discrimination, steelmans the panel",
            "certificate_per_probe": "mean per-doc certificate coverage over gold docs",
        },
        "per_metric": per_metric,
        "certificate_auc": certificate_auc,
        "counts": {"n_auc_ge_0.65": n_auc, "n_partial_ge_0.15": n_partial, "n_both": n_both},
        "clauses": clauses,
        "proposed_verdict": verdict,
        "per_probe": per_probe,
    }
    out_path = OUT / f"h545-panel-h37-{ts}.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in
                      ["hypothesis", "n_probes", "n_pass", "per_metric", "certificate_auc",
                       "counts", "proposed_verdict"]}, indent=2))
    print(f"\nWROTE {out_path}", flush=True)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["cert", "analyze"])
    ap.add_argument("cert_path", nargs="?", default=None)
    ap.add_argument("concurrency", nargs="?", type=int, default=8)
    a = ap.parse_args()
    if a.mode == "cert":
        run_cert(resume_path=a.cert_path, concurrency=a.concurrency)
    else:
        run_analyze(Path(a.cert_path) if a.cert_path else None)


if __name__ == "__main__":
    main()

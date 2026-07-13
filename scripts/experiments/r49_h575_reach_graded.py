"""R49-H575: graded retrievability r(f) + Gini retrieval-bias vs a binary certificate.

Contrarian test of the binary reachability column (H530: misaligned neighborhoods
still pass at 0.909 - reachability is graded, not a boolean). Two claims:

  (1) GRADED beats BINARY as a probe-outcome predictor. For every fact (2wiki
      benchmark question, OFF-arm labels), graded r(f) = the fraction of the
      fact's ANTICIPATED questions (the KGFQuestion nodes Doc2Query-generated
      from the carrier's own document) whose dense top-c entity retrieval
      SURFACES the gold carrier entity. The binary comparator is the H530-style
      certificate: 1 iff every gold carrier sits inside dense top-16 seeds or
      one hop from a seed, else 0. Predictor quality = AUC against the probe
      pass/fail label. Prediction: AUC(graded) >= AUC(binary) + 0.05.

  (2) Azzopardi retrieval-bias Gini over the per-document r(doc) distribution
      RISES monotonically scout -> small -> medium (scale-induced dilution,
      H468: the carrier drops out of top-c for more of its own questions as the
      competition pool grows). Prediction: Gini(scout) < Gini(small) <
      Gini(medium).

Retrievability is pure cosine arithmetic over the STORED Titan embeddings
(entity index space; KGFQuestion nodes carry embeddings in the same space) -
no LLM for the graded arm. The binary arm embeds the 132 held-out probes via
the shipped Bedrock/Titan path (r47/r48 convention) for dense seeds + a
scipy-free 1-hop over the live Entity-Entity adjacency (SIMILAR_TO and closed
edges excluded, matching the engine projection).

Cutoff c = 16 (shipped graphrag.top_k); sensitivity at c = 8.

DEVIATION: the small rung has no standalone live graph (nested into medium).
The small point is computed over the MEDIUM graph RESTRICTED to the
first-200-doc (2wiki-pilot-200.json) subset: the retrieval competition pool is
masked to entities mentioned in those 200 docs, and the doc population is those
200 docs. Recorded in the report.

Read-only on all Neo4j. Graphs: medium bolt://172.19.0.9:7687, scout
bolt://172.19.0.8:7687 (config-bench-scout.yml).

Usage: python scripts/experiments/r49_h575_reach_graded.py
Writes: reports/experiments/r49/h575-reach-graded-<ts>.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from neo4j import GraphDatabase

sys.path.insert(0, "src")
sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402

MEDIUM_URI = "bolt://172.19.0.9:7687"
SCOUT_URI = "bolt://172.19.0.8:7687"
AUTH = ("neo4j", "kgfoundry")
LABELS = Path("reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
PILOT_PREFIX = "2wiki-pilot-200.json#"  # the nested small-200 doc set
C_PRIMARY = 16
C_ALT = 8


def gini(xs: list[float]) -> float | None:
    """Azzopardi retrieval-bias Gini over a retrievability distribution."""
    xs = sorted(float(x) for x in xs)
    n = len(xs)
    if n == 0:
        return None
    s = sum(xs)
    if s == 0:
        return 0.0
    num = sum((i + 1) * x for i, x in enumerate(xs))
    return round((2 * num) / (n * s) - (n + 1) / n, 4)


def auc(scores: list[float], labels: list[bool]) -> float | None:
    """Mann-Whitney AUC with 0.5 tie credit. labels True = probe passed."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    return round(wins / (len(pos) * len(neg)), 4)


class Graph:
    """Read-only in-memory view of one KGF graph: normalized entity embeddings,
    per-doc anticipated-question embeddings, doc titles, and adjacency."""

    def __init__(self, uri: str, slices: dict[str, list[str]]):
        self.uri = uri
        d = GraphDatabase.driver(uri, auth=AUTH)
        with d.session() as s:
            ents = s.run(
                "MATCH (e:Entity) WHERE e.embedding IS NOT NULL "
                "RETURN e.id AS id, e.name AS name, e.embedding AS emb"
            ).data()
            qrows = s.run(
                "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(:Chunk)-[:PART_OF]->(d:KGFDocument) "
                "WHERE q.embedding IS NOT NULL "
                "RETURN d.name AS doc, q.id AS qid, q.embedding AS emb"
            ).data()
            pilot = s.run(
                "MATCH (e:Entity)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(d:KGFDocument) "
                "WHERE d.name STARTS WITH $p RETURN DISTINCT e.id AS id",
                p=PILOT_PREFIX,
            ).value()
            edges = s.run(
                "MATCH (a:Entity)-[r]-(b:Entity) WHERE r.valid_to IS NULL "
                "AND type(r) <> 'SIMILAR_TO' RETURN a.id AS a, b.id AS b"
            ).data()
        d.close()

        self.row = {e["id"]: i for i, e in enumerate(ents)}
        self.name_row: dict[str, int] = {}
        for e in ents:  # first occurrence wins; _norm exact-name carrier resolution
            self.name_row.setdefault(_norm(e["name"]), self.row[e["id"]])
        E = np.asarray([e["emb"] for e in ents], dtype=np.float32)
        E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-12
        self.E = E
        self.n = len(ents)

        # doc -> list of unique anticipated-question embeddings (normalized)
        seen: dict[str, set[str]] = {}
        doc_q: dict[str, list[list[float]]] = {}
        for r in qrows:
            if r["qid"] in seen.setdefault(r["doc"], set()):
                continue
            seen[r["doc"]].add(r["qid"])
            doc_q.setdefault(r["doc"], []).append(r["emb"])
        self.doc_qmat: dict[str, np.ndarray] = {}
        for doc, embs in doc_q.items():
            M = np.asarray(embs, dtype=np.float32)
            M /= np.linalg.norm(M, axis=1, keepdims=True) + 1e-12
            self.doc_qmat[doc] = M

        # doc -> title from slices
        self.doc_title: dict[str, str] = {}
        for doc in doc_q:
            slice_name, _, tail = doc.partition("#row")
            titles = slices.get(slice_name)
            if titles and tail.isdigit() and int(tail) < len(titles):
                self.doc_title[doc] = titles[int(tail)]

        # pilot-200 pool mask (small-rung restriction)
        self.pilot_mask = np.zeros(self.n, dtype=bool)
        for eid in pilot:
            if eid in self.row:
                self.pilot_mask[self.row[eid]] = True

        # adjacency for the binary 1-hop
        self.adj: dict[str, set[str]] = {}
        for e in edges:
            self.adj.setdefault(e["a"], set()).add(e["b"])
            self.adj.setdefault(e["b"], set()).add(e["a"])
        self.id_by_row = {i: eid for eid, i in self.row.items()}

    def surfaced(self, qmat: np.ndarray, carrier_row: int, c: int,
                 mask: np.ndarray | None = None) -> np.ndarray:
        """Per-question boolean: is carrier within the top-c entities for that
        anticipated question? Vectorized rank via a count of higher-scoring
        entities. ``mask`` restricts the competition pool (small rung)."""
        sims = qmat @ self.E.T  # (nq, n)
        if mask is not None:
            sims = np.where(mask[None, :], sims, -np.inf)
        carrier_sim = sims[:, carrier_row]
        higher = (sims > carrier_sim[:, None]).sum(axis=1)
        return higher < c

    def r_doc(self, doc: str, c: int, mask: np.ndarray | None = None) -> float | None:
        """Retrievability of a doc's title-carrier via its own anticipated
        questions. None when the title-entity is unresolved or no questions."""
        title = self.doc_title.get(doc)
        if title is None:
            return None
        crow = self.name_row.get(_norm(title))
        if crow is None or (mask is not None and not mask[crow]):
            return None
        qmat = self.doc_qmat.get(doc)
        if qmat is None or len(qmat) == 0:
            return None
        return float(self.surfaced(qmat, crow, c, mask).mean())

    def carrier_r(self, title: str, c: int, mask: np.ndarray | None = None) -> float:
        """Graded retrievability for a benchmark carrier title. Unresolved
        carrier or no anticipated questions -> 0.0 (genuinely unretrievable)."""
        crow = self.name_row.get(_norm(title))
        if crow is None or (mask is not None and not mask[crow]):
            return 0.0
        docs = [d for d, t in self.doc_title.items() if _norm(t) == _norm(title)]
        qmats = [self.doc_qmat[d] for d in docs if d in self.doc_qmat]
        if not qmats:
            return 0.0
        qmat = np.vstack(qmats)
        return float(self.surfaced(qmat, crow, c, mask).mean())

    def dense_seeds(self, qv: np.ndarray, c: int) -> list[int]:
        sims = self.E @ (qv / (np.linalg.norm(qv) + 1e-12))
        return list(np.argsort(-sims)[:c])

    def reachable(self, carrier_title: str, seed_rows: list[int]) -> bool:
        """Binary hop-distance: carrier in seeds or 1-hop from a seed."""
        crow = self.name_row.get(_norm(carrier_title))
        if crow is None:
            return False
        cid = self.id_by_row[crow]
        seed_ids = {self.id_by_row[r] for r in seed_rows}
        if cid in seed_ids:
            return True
        nbrs: set[str] = set()
        for sid in seed_ids:
            nbrs |= self.adj.get(sid, set())
        return cid in nbrs


def gini_rungs(scout: Graph, medium: Graph, c: int) -> dict:
    """All-doc (Azzopardi corpus) Gini over r(doc) per rung + doc coverage."""
    out = {}
    # scout: native pool
    rs = [scout.r_doc(d, c) for d in scout.doc_qmat]
    rs = [x for x in rs if x is not None]
    out["scout"] = {"gini": gini(rs), "n_docs": len(rs), "mean_r": round(float(np.mean(rs)), 4)}
    # small: medium graph, pilot-200 docs, pilot pool mask
    rsm = [
        medium.r_doc(d, c, mask=medium.pilot_mask)
        for d in medium.doc_qmat
        if d.startswith(PILOT_PREFIX)
    ]
    rsm = [x for x in rsm if x is not None]
    out["small"] = {"gini": gini(rsm), "n_docs": len(rsm), "mean_r": round(float(np.mean(rsm)), 4)}
    # medium: full pool, all docs
    rmd = [medium.r_doc(d, c) for d in medium.doc_qmat]
    rmd = [x for x in rmd if x is not None]
    out["medium"] = {"gini": gini(rmd), "n_docs": len(rmd), "mean_r": round(float(np.mean(rmd)), 4)}
    return out


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slices = load_slices()
    print(f"h575 {run_id}: loading graphs", flush=True)
    medium = Graph(MEDIUM_URI, slices)
    scout = Graph(SCOUT_URI, slices)
    print(f"medium n={medium.n} pilot_pool={int(medium.pilot_mask.sum())} docs={len(medium.doc_qmat)}; "
          f"scout n={scout.n} docs={len(scout.doc_qmat)}", flush=True)

    # --- probe labels + gold carriers (medium AUC) ---
    labels = [json.loads(x) for x in LABELS.read_text().splitlines()]
    off = [r for r in labels if r["arm"] == "off"]
    ds = {q.get("_id"): q for q in json.loads(QUESTIONS.read_text())}
    probes = []
    for r in off:
        q = ds.get(r["id"])
        if q:
            probes.append({"id": r["id"], "q": q, "pass": bool(r["pass"]),
                           "carriers": gold_titles(q)})
    print(f"{len(probes)} probes joined (pass={sum(p['pass'] for p in probes)})", flush=True)

    st = load_settings(Path("config/experiments/config-bench-medium.yml"))
    st.event_log = None

    rows = []
    for k, p in enumerate(probes):
        probe = Entity.create(p["q"]["question"][:80], types=["Query"],
                              description=p["q"]["question"])
        qv = np.asarray(generate_embeddings([probe], st.embeddings)[0].embedding,
                        dtype=np.float32)
        rec = {"id": p["id"], "pass": p["pass"], "n_carriers": len(p["carriers"])}
        for c in (C_PRIMARY, C_ALT):
            graded = [medium.carrier_r(t, c) for t in p["carriers"]]
            seeds = medium.dense_seeds(qv, c)
            reach = [medium.reachable(t, seeds) for t in p["carriers"]]
            rec[f"graded_mean_c{c}"] = round(float(np.mean(graded)), 4)
            rec[f"graded_min_c{c}"] = round(float(min(graded)), 4)
            rec[f"binary_all_c{c}"] = 1.0 if all(reach) else 0.0
            rec[f"binary_frac_c{c}"] = round(sum(reach) / len(reach), 4)
        rows.append(rec)
        if (k + 1) % 25 == 0:
            print(f"[{k+1}/{len(probes)}] probes embedded+scored", flush=True)

    labels_y = [r["pass"] for r in rows]
    auc_block = {}
    for c in (C_PRIMARY, C_ALT):
        auc_block[f"c{c}"] = {
            "auc_graded_mean": auc([r[f"graded_mean_c{c}"] for r in rows], labels_y),
            "auc_graded_min": auc([r[f"graded_min_c{c}"] for r in rows], labels_y),
            "auc_binary_all": auc([r[f"binary_all_c{c}"] for r in rows], labels_y),
            "auc_binary_frac": auc([r[f"binary_frac_c{c}"] for r in rows], labels_y),
            "binary_all_pass_rate": round(
                sum(r[f"binary_all_c{c}"] for r in rows) / len(rows), 4
            ),
        }

    # --- Gini by rung ---
    gini_block = {"c16": gini_rungs(scout, medium, C_PRIMARY),
                  "c8": gini_rungs(scout, medium, C_ALT)}

    # --- verdict clauses ---
    g_mean = auc_block["c16"]["auc_graded_mean"]
    b_all = auc_block["c16"]["auc_binary_all"]
    gi = gini_block["c16"]
    clause_auc = g_mean is not None and b_all is not None and g_mean >= b_all + 0.05
    gv = [gi["scout"]["gini"], gi["small"]["gini"], gi["medium"]["gini"]]
    clause_gini = all(a is not None for a in gv) and gv[0] < gv[1] < gv[2]
    clauses = [
        {"clause": "AUC(graded_mean) >= AUC(binary_all) + 0.05 @ c=16",
         "predicted": f">= {round((b_all or 0) + 0.05, 4)}",
         "measured": f"graded={g_mean} binary={b_all}", "holds": bool(clause_auc)},
        {"clause": "Gini(r(doc)) monotone scout < small < medium @ c=16",
         "predicted": "scout < small < medium",
         "measured": f"{gv[0]} < {gv[1]} < {gv[2]}", "holds": bool(clause_gini)},
    ]
    if clause_auc and clause_gini:
        verdict = "CONFIRMED"
    elif (b_all is not None and g_mean is not None and b_all >= g_mean) or not clause_gini:
        verdict = "KILLED"
    else:
        verdict = "PARTIAL"

    summary = {
        "run_id": run_id,
        "cutoffs": {"primary": C_PRIMARY, "alt": C_ALT},
        "n_probes": len(rows),
        "n_pass": sum(labels_y),
        "auc": auc_block,
        "gini_by_rung": gini_block,
        "clauses": clauses,
        "proposed_verdict": verdict,
        "deviation": (
            "small rung has no standalone live graph (nested into medium); the "
            "small point is medium RESTRICTED to the 2wiki-pilot-200 subset - "
            "competition pool masked to entities mentioned in those 200 docs, "
            "doc population those 200 docs. scout is its own 50-row slice "
            "(distinct rows from pilot/medium) per the scale-ladder design."
        ),
        "conventions": (
            "graded r(f): stored Titan embeddings, cosine top-c entity rank, "
            "carrier = exact _norm entity-name match (unresolved -> r=0); "
            "binary_all = H530 certificate (all carriers in dense top-16 or "
            "1-hop); adjacency = live Entity-Entity excl SIMILAR_TO; AUC = "
            "Mann-Whitney vs probe pass/fail; Gini over all-doc r(doc) dist."
        ),
    }
    out = Path("reports/experiments/r49")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"h575-reach-graded-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "probe_rows": rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

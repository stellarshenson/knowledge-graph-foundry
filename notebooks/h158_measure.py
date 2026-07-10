"""R15-H158 measurement helpers: SAME_AS precision proxy from the ingest event
log, and pure-seed recall@k from a graph. Imported by identity_stack_h158.ipynb
and runnable as scripts so v1 recall can be captured before the scratch wipe.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from knowledge_graph_foundry.models import entity_id  # noqa: E402

BENCH_PATH = "reports/identity-benchmark-h101-20260707-094448.json"


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def precision_proxy(event_log: str, bench_path: str = BENCH_PATH) -> dict:
    """Precision of the resolver's merges against the 298 adjudicated labels.

    A benchmark pair (a, b) counts as merged if a and b land in the same
    merge-connected component (transitive union of resolution.merge events).
    """
    bench = json.load(open(bench_path))
    uf = _UF()
    merges = defers = blocks = vetoes = 0
    ts_first = ts_last = None
    for line in Path(event_log).read_text().splitlines():
        rec = json.loads(line)
        ev = rec.get("event", "")
        if ev == "resolution.merge":
            uf.union(rec["left_id"], rec["right_id"])
            merges += 1
        elif ev == "resolution.defer":
            defers += 1
        elif ev == "resolution.block":
            blocks += 1
        elif ev == "resolution.veto":
            vetoes += 1
        if ev.startswith("resolution."):
            ts = rec.get("ts")
            if ts:
                ts_first = ts_first or ts
                ts_last = ts

    tp = fp = fn = tn = 0
    unresolved = 0
    for p in bench["pairs"]:
        if p["model_verdict"] not in ("YES", "NO"):
            continue
        eid_a, eid_b = entity_id(p["a"]), entity_id(p["b"])
        merged = eid_a != eid_b and uf.find(eid_a) == uf.find(eid_b)
        same = p["model_verdict"] == "YES"
        if merged and same:
            tp += 1
        elif merged and not same:
            fp += 1
        elif not merged and same:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "event_log": event_log,
        "merges_total": merges, "defers_total": defers,
        "blocks_total": blocks, "nli_vetoes": vetoes,
        "proxy_tp": tp, "proxy_fp": fp, "proxy_fn": fn, "proxy_tn": tn,
        "same_as_precision": round(precision, 4),
        "false_merges": fp,
        "proxy_recall": round(recall, 4),
        "resolution_ts_first": ts_first, "resolution_ts_last": ts_last,
    }


# -- pure-seed recall@k (H34/H53 convention, from three_arm_benchmark) ---------
import re  # noqa: E402


def _norm(s):
    return re.sub(r"\s+", " ", s.casefold())


_UNIT = r"(?<=\d)\s*(mm|cm|dba|db\(a\)|db|kg|g|oz|ml|l|w|hz|mins|min|m)\b"


def _present(gold, ctx):
    ng = _norm(gold)
    if ng in ctx:
        return True
    squashed = re.sub(r"[\s,()]", "", ctx)
    skeleton = re.sub(r"[\s,()]", "", re.sub(_UNIT, "", ng))
    if any(c.isdigit() for c in skeleton) and len(skeleton) >= 5 and skeleton in squashed:
        return True
    toks = re.findall(r"[\w.\-/]*\d[\w.\-/]*", gold)
    if toks:
        hit = sum(1 for t in toks if _norm(t) in ctx or re.sub(r"[\s,()]", "", _norm(t)) in squashed)
        return hit >= max(1, len(toks) // 2 + (len(toks) % 2))
    words = set(re.findall(r"[a-z][a-z0-9\-]{2,}", ng))
    cw = set(re.findall(r"[a-z][a-z0-9\-]{2,}", ctx))
    return bool(words) and len(words & cw) / len(words) >= 0.6


def _render_nodes(session, node_ids):
    blocks = []
    for nid in node_ids:
        row = session.run(
            "MATCH (e:Entity {id:$id}) RETURN e.name AS name, labels(e) AS types, "
            "e.description AS description, properties(e) AS props", id=nid).single()
        if row is None:
            continue
        spec = {k.removeprefix("prop_"): v for k, v in row["props"].items() if k.startswith("prop_")}
        rels = session.run(
            "MATCH (e:Entity {id:$id})-[r]-(n:Entity) WHERE r.valid_to IS NULL "
            "AND type(r) <> 'SIMILAR_TO' RETURN type(r) AS rel, n.name AS name LIMIT 15", id=nid).data()
        blocks.append(
            f"## {row['name']} ({', '.join(row['types'])})\n{row['description'] or ''}\n"
            f"Properties: {json.dumps(spec, default=str)}\n"
            "Relations: " + "; ".join(f"{r['rel']} -> {r['name']}" for r in rels))
    return _norm("\n".join(blocks))


def recall_at_k(uri: str, top_k: int, label: str,
                probes_path: str = "tests/probes/cpap-probe-set.yml",
                overfetch_factor: int = None) -> dict:
    """DEF-14: default retrieval is ENGINE PARITY - overfetch top_k*factor then
    truncate, exactly as the shipped read path (R15-H195a). Pass
    overfetch_factor=1 to reproduce the pre-parity instrument for
    comparability with maps measured before 2026-07-10."""
    from copy import deepcopy

    import yaml
    from knowledge_graph_foundry import load_settings
    from knowledge_graph_foundry.extraction import generate_embeddings
    from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query
    from knowledge_graph_foundry.models import Entity
    from knowledge_graph_foundry.pipeline import Foundry

    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    factor = base.graphrag.overfetch_factor if overfetch_factor is None else overfetch_factor
    probes = [p for p in yaml.safe_load(Path(probes_path).read_text()) if p.get("gold_evidence")]
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = uri, "neo4j", "kgfoundry"
    st.graphrag.top_k = top_k
    per = {}
    with Foundry(st) as f:
        with f.driver.session() as s:
            ents = s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
            rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            docs = s.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"]
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            seeds = [s["id"] for s in overfetch_seeds(
                lambda k: vector_query(f.driver, emb, vec, top_k=k), top_k, factor)]
            with f.driver.session() as sess:
                ctx = _render_nodes(sess, seeds)
            golds = p["gold_evidence"]
            per[p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
    mean = sum(per.values()) / len(per)
    return {
        "label": label, "uri": uri, "top_k": top_k, "overfetch_factor": factor,
        "entities": ents, "relationships": rels, "documents": docs,
        "mean_recall": round(mean, 4),
        "fully_covered": sum(1 for v in per.values() if v == 1.0),
        "n_probes": len(per), "per_probe": {k: round(v, 4) for k, v in per.items()},
    }


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "precision":
        out = precision_proxy(sys.argv[2])
    elif cmd == "recall":
        out = recall_at_k(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        raise SystemExit(f"unknown command {cmd}")
    dest = sys.argv[-1] if sys.argv[-1].endswith(".json") else None
    print(json.dumps(out, indent=2))
    if dest:
        Path(dest).write_text(json.dumps(out, indent=2))

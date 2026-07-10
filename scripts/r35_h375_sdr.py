"""R35-H375: SDR-overlap identity signatures vs cosine blocking - head-to-head
candidate-generation recall on the H107 same-type pair benchmark.

True set: the 66 adjudicated same-type pairs from the R11 identity forensics
(all cosine 0.901-0.993 - findable by the shipped blocking) PLUS the two
H364/H365 series-fragment pairs the resolver measurably missed because their
cosine sits below every threshold (0.747, 0.597). The fragment pairs are the
discriminating probes: H375's claim is that bit-overlap on salient tokens
recalls variance-drifted duplicates that dense cosine cannot.

Methods, matched candidate budget:
  cosine  - kNN over the entity vector index (k=10 per entity), pairs ranked
            by similarity (the shipped blocking's exact machinery)
  sdr     - sparse signature per entity: normalized name tokens + model codes
            + prop keys + salient prop-value tokens + model codes of PART_OF
            neighbours; ubiquitous tokens (df > 50) dropped (SDR sparsity);
            pairs ranked by raw bit-overlap, ties by Jaccard

Metric: recall of the true set at equal candidate-set size N (the false-match
budget proxy: same N implies the same number of admitted non-true pairs up to
the small true-count difference). Bar: SDR recalls >= 10% more true pairs at
matched budget -> candidate-generation stage; loses -> Hawkins substrate
retired.
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from neo4j import GraphDatabase

URI = "bolt://172.19.0.4:7687"
FORENSICS = Path("reports/identity-forensics-r11-final-20260706-205147.json")
FRAGMENT_PAIRS = [
    ("HC230-Series", "HC230 Product Range"),
    ("Sleep Style 200 Series", "HC230-Series"),
]
DF_CAP = 50  # tokens on more entities than this carry no identity signal
KNN = 10
BUDGETS = [500, 1000, 2000, 5000, 10000]

MODEL_RE = re.compile(r"\b([a-z]{1,4}[- ]?\d{2,4}[a-z]{0,3})\b")
STOP = {"the", "and", "for", "with", "of", "a", "an", "to", "in", "on", "pack"}


def tokens(name, props, neighbours):
    out = set()
    low = name.lower()
    out.update(t for t in re.findall(r"[a-z0-9][a-z0-9\-]{1,}", low) if t not in STOP)
    out.update("mc:" + re.sub(r"[- ]", "", m) for m in MODEL_RE.findall(low))
    for k, v in props.items():
        if not k.startswith("prop_"):
            continue
        out.add("pk:" + k.removeprefix("prop_"))
        for t in re.findall(r"[a-z0-9][a-z0-9.\-/]{1,}", str(v).lower()):
            if any(c.isdigit() for c in t):
                out.add("pv:" + t)
    for n in neighbours:
        out.update("nb:" + re.sub(r"[- ]", "", m) for m in MODEL_RE.findall(n.lower()))
    return out


def recall_at(ranked_pairs, true_ids, budgets):
    got, out, seen = set(), {}, 0
    budget_iter = iter(sorted(budgets))
    nxt = next(budget_iter)
    for pair in ranked_pairs:
        seen += 1
        if pair in true_ids:
            got.add(pair)
        if seen == nxt:
            out[nxt] = len(got)
            nxt = next(budget_iter, None)
            if nxt is None:
                break
    for b in budgets:
        out.setdefault(b, len(got))
    return out


def main():
    forensics = json.loads(FORENSICS.read_text())
    true_names = [(p["a"], p["b"]) for p in forensics["pairs"]] + FRAGMENT_PAIRS

    drv = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with drv.session() as s:
        rows = s.run(
            "MATCH (e:Entity) "
            "OPTIONAL MATCH (e)-[:PART_OF]-(n:Entity) "
            "RETURN e.id AS id, e.name AS name, properties(e) AS props, "
            "collect(DISTINCT n.name) AS neighbours"
        ).data()
        # pre-repair arm: the pile carries the H365 prototype marks (bridge
        # edges + hoisted props) which would contaminate exactly the fragment
        # pairs under test - rebuild signatures as the graph stood before
        clean_rows = s.run(
            "MATCH (e:Entity) "
            "OPTIONAL MATCH (e)-[r:PART_OF]-(n:Entity) WHERE r.h365 IS NULL "
            "RETURN e.id AS id, e.name AS name, properties(e) AS props, "
            "collect(DISTINCT n.name) AS neighbours, e.h365_hoisted AS hoisted"
        ).data()
        for r in clean_rows:
            if r["hoisted"]:
                r["props"] = {k: v for k, v in r["props"].items() if k not in r["hoisted"]}
        print(f"entities: {len(rows)}", flush=True)

        name_ids = defaultdict(set)
        for r in rows:
            name_ids[r["name"]].add(r["id"])
        true_ids = set()
        missing = []
        for a, b in true_names:
            if name_ids[a] and name_ids[b]:
                for ia in name_ids[a]:
                    for ib in name_ids[b]:
                        true_ids.add(frozenset((ia, ib)))
            else:
                missing.append((a, b))
        print(f"true pairs mapped: {len(true_names) - len(missing)}/{len(true_names)} "
              f"(missing: {missing})", flush=True)

        # arm 1: cosine kNN via the entity vector index (shipped blocking)
        cos_pairs = {}
        for i, r in enumerate(rows):
            hits = s.run(
                "MATCH (e:Entity {id: $id}) WHERE e.embedding IS NOT NULL "
                "CALL db.index.vector.queryNodes('kgf_entity_embeddings', $k, e.embedding) "
                "YIELD node, score WHERE node.id <> $id "
                "RETURN node.id AS id, score",
                id=r["id"], k=KNN + 1,
            ).data()
            for h in hits:
                key = frozenset((r["id"], h["id"]))
                if cos_pairs.get(key, 0) < h["score"]:
                    cos_pairs[key] = h["score"]
            if (i + 1) % 1000 == 0:
                print(f"cosine kNN: {i + 1}/{len(rows)}", flush=True)
    drv.close()

    cos_ranked = sorted(cos_pairs, key=cos_pairs.get, reverse=True)
    print(f"cosine candidates: {len(cos_ranked)}", flush=True)

    # arm 2: SDR signatures (contemporary graph + pre-repair clean arm)
    def sdr_rank(source_rows, label):
        sigs = {
            r["id"]: tokens(r["name"], r["props"], [n for n in r["neighbours"] if n])
            for r in source_rows
        }
        df = defaultdict(int)
        for sig in sigs.values():
            for t in sig:
                df[t] += 1
        sigs = {eid: {t for t in sig if df[t] <= DF_CAP} for eid, sig in sigs.items()}
        inv = defaultdict(list)
        for eid, sig in sigs.items():
            for t in sig:
                inv[t].append(eid)
        overlap = defaultdict(int)
        for t, ids in inv.items():
            if len(ids) < 2:
                continue
            for a, b in combinations(ids, 2):
                overlap[frozenset((a, b))] += 1
        ranked = sorted(
            overlap,
            key=lambda p: (
                overlap[p],
                overlap[p] / len(set().union(*(sigs[e] for e in p))) if any(sigs[e] for e in p) else 0,
            ),
            reverse=True,
        )
        print(f"sdr[{label}] candidates: {len(ranked)}", flush=True)
        return ranked, overlap

    sdr_ranked, overlap = sdr_rank(rows, "post-repair")
    sdr_clean_ranked, overlap_clean = sdr_rank(clean_rows, "pre-repair")

    cos_recall = recall_at(cos_ranked, true_ids, BUDGETS)
    sdr_recall = recall_at(sdr_ranked, true_ids, BUDGETS)
    sdr_clean_recall = recall_at(sdr_clean_ranked, true_ids, BUDGETS)
    n_true = len(true_ids)
    # fragment-pair specific check
    frag_ids = set()
    for a, b in FRAGMENT_PAIRS:
        for ia in name_ids[a]:
            for ib in name_ids[b]:
                frag_ids.add(frozenset((ia, ib)))
    frag_cos = {tuple(sorted(p)): (p in set(cos_ranked[:10000])) for p in frag_ids}
    frag_sdr_rank = {
        tuple(sorted(p)): (sdr_ranked.index(p) if p in overlap else None) for p in frag_ids
    }
    frag_clean_rank = {
        tuple(sorted(p)): (sdr_clean_ranked.index(p) if p in overlap_clean else None)
        for p in frag_ids
    }

    print(f"\ntrue pairs: {n_true}")
    for b in BUDGETS:
        print(
            f"N={b}: cosine {cos_recall[b]}/{n_true}, sdr {sdr_recall[b]}/{n_true}, "
            f"sdr-pre-repair {sdr_clean_recall[b]}/{n_true}",
            flush=True,
        )
    print(f"fragment pairs in cosine top-10k: {frag_cos}", flush=True)
    print(f"fragment pair sdr ranks (post-repair): {frag_sdr_rank}", flush=True)
    print(f"fragment pair sdr ranks (pre-repair): {frag_clean_rank}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r35-h375-sdr-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R35-H375 SDR signature overlap vs cosine blocking",
        "generated": ts,
        "graph_uri": URI,
        "true_pairs": n_true,
        "true_pairs_unmapped": missing,
        "budgets": BUDGETS,
        "cosine_recall": cos_recall,
        "sdr_recall": sdr_recall,
        "sdr_pre_repair_recall": sdr_clean_recall,
        "cosine_candidates": len(cos_ranked),
        "sdr_candidates": len(sdr_ranked),
        "fragment_in_cosine_top10k": {str(k): v for k, v in frag_cos.items()},
        "fragment_sdr_rank": {str(k): v for k, v in frag_sdr_rank.items()},
        "fragment_sdr_rank_pre_repair": {str(k): v for k, v in frag_clean_rank.items()},
        "df_cap": DF_CAP, "knn": KNN,
    }, indent=2))
    print(f"\nH375 SDR COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

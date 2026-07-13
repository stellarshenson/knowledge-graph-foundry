"""R50-H583/H584/H586: FREE offline oracle-ceiling gates for the R50 topology/type axis.

Pure offline, READ-ONLY on Neo4j (one typed-edge + label pull cached to
tmp/results/r50; no writes, no containers). Reuses the R47-H582 harness module
verbatim for shared structures (entity matrix, undirected Entity adjacency,
326 carriers over the 132 off-arm frozen probes, Titan probe embeddings) so the
Titan carrier_recall@16 == 0.6012 sanity gate reproduces bit-identically.

Serves three registered gates:

  H583 CRUX - topology / relation-path oracle ceiling.
    (a) gold-path-resolvability: does the extracted graph contain the gold
        2wiki relation SEQUENCE? Reported three ways on entity-entity gold hops:
        structural (an edge connects the endpoints, relation-agnostic), typed
        exact-normalized relation-name match (the sanctioned oracle convention),
        typed curated-synonym-oracle (a hand map bracketing the best a relation
        linker could do). Per-probe chain resolvability + per-2wiki-class strata.
        HARD SUB-CAP: gold relation-sequence resolvability < 50% on
        compositional/bridge = gold topology unbuildable on the self-extracted
        graph (H107 broke it) -> axis dies at the premise.
    (b) reachability oracle (H515 all-golds-in-region convention, paired on the
        frozen probes): isotropic question-seed PPR baseline vs the gold
        meta-match (seed from the gold SOURCE entities = oracle entity-linking of
        the question anchors; PPR restricted to the gold-path node-type region),
        measured over all in-graph carriers AND over the hard BRIDGE carriers.
        recall@16 oracle: candidate pool restricted to gold-path node types,
        top-16 by cosine, vs isotropic 0.6012.

  H584 CRUX - type-constraint oracle ceiling. Restrict the dense candidate pool
    to entities whose cured type == the ORACLE query answer-type, top-16 by
    cosine; carrier recall@16 delta vs 0.6012 on the 132 paired frozen probes.
    Recoverable fraction = dense-missed in-graph carriers whose type matches the
    answer-type, sitting at cosine rank 17-50.

  H586 - type-separability / informativeness null (single-entity-answer subset).
    recall horn (carriers off-type), informativeness horn (answer-type sub-pool
    mass), separability horn (missed carrier shares answer-type with >=3 top-16
    crowd-out distractors).

Answer-type convention (uniform, H584+H586): the resolved gold answer entity's
cured type; if the answer is a literal (date/boolean/number, non-resolving) the
deepest resolvable gold-evidence entity's type. On the single-entity-answer
subset (H586) the answer always resolves, so it is exactly the answer entity type.

Cured type = first non-Entity node label (H582 convention). Relation alignment =
exact match on [^a-z0-9]-stripped casefold. PPR = h515/h573 scipy (damping 0.85,
50 iters, top_n 15), Entity-only adjacency, SIMILAR_TO excluded, no valid_to.

Usage:  python scripts/experiments/r50_h583_topology_ceiling.py
Writes: reports/experiments/r50/h583-topology-ceiling-<ts>.json
        reports/experiments/r50/h584-typeceiling-<ts>.json
        reports/experiments/r50/h586-separability-<ts>.json
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "scripts/experiments")
import r47_h582_embedder_swap as H  # noqa: E402  (harness reuse: _norm, ppr, mcnemar, boot_ci)

ROOT = H.ROOT
CACHE = H.CACHE                      # tmp/results/r47
R50 = ROOT / "tmp/results/r50"       # typed-edge + label cache (built read-only)
OUT = ROOT / "reports/experiments/r50"
H501_RECALL = 0.5982
TITAN_TARGET = 0.6012
ISO_REACH_REF = 0.622                # H515 all-golds reachability (127-probe set)
TOP_K = H.TOP_K                      # 16
PPR_TOP_N = H.PPR_TOP_N              # 15

# curated relation-synonym oracle (best a relation linker could plausibly do;
# brackets the exact-norm 0% floor - shows the sub-cap is not a normalization
# artifact). gold Wikidata relation -> set of aligned native extracted types.
SYN = {
    "director": {"DIRECTED", "DIRECTED_BY", "DIRECTOR_OF", "CO_DIRECTED_BY"},
    "mother": {"CHILD_OF", "MOTHER_OF", "PARENT_OF", "DAUGHTER_OF", "SON_OF"},
    "father": {"CHILD_OF", "FATHER_OF", "PARENT_OF", "SON_OF", "DAUGHTER_OF"},
    "child": {"CHILD_OF", "PARENT_OF", "FATHER_OF", "MOTHER_OF"},
    "spouse": {"MARRIED_TO", "SPOUSE_OF"},
    "sibling": {"SIBLING_OF"},
    "performer": {"PERFORMED_BY", "PERFORMER_OF", "SANG_BY"},
    "composer": {"COMPOSED_BY", "COMPOSER_OF"},
    "publisher": {"PUBLISHED_BY", "PUBLISHER_OF"},
    "founded by": {"FOUNDED_BY", "FOUNDER_OF"},
    "employer": {"EMPLOYED_BY", "WORKED_FOR", "MEMBER_OF", "PLAYED_FOR"},
    "educated at": {"ATTENDED", "EDUCATED_AT", "STUDIED_AT"},
    "place of birth": {"BORN_IN", "RESIDES_IN", "LOCATED_IN"},
    "place of death": {"DIED_IN", "RESIDES_IN", "LOCATED_IN"},
    "country": {"LOCATED_IN", "PART_OF", "COUNTRY_OF"},
    "country of citizenship": {"CITIZEN_OF", "RESIDES_IN", "NATIONALITY_OF", "LOCATED_IN"},
    "country of origin": {"LOCATED_IN", "PART_OF", "ORIGIN_OF"},
}


def norm_rel(r: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (r or "").casefold())


def gold_titles(q):
    sf = q.get("supporting_facts") or []
    ts = []
    for it in sf:
        t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
        if t and t not in ts:
            ts.append(t)
    return ts


def ppr_masked(adj, seed_idx, node_mask=None):
    """H515 power-iteration PPR; node_mask (bool) zeros transition rows/cols
    outside the kept set and drops off-region seeds."""
    n = adj.shape[0]
    if node_mask is not None:
        keep = node_mask.astype(float)
        adj = adj.multiply(keep[:, None]).multiply(keep[None, :]).tocsr()
        seed_idx = [i for i in seed_idx if node_mask[i]]
    if not seed_idx:
        return np.zeros(n)
    out = np.asarray(adj.sum(axis=1)).ravel()
    out[out == 0] = 1.0
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(H.ITERS):
        r = (1 - H.DAMPING) * p + H.DAMPING * (adj.T @ (r / out))
    return r


def region(r, seeds):
    return set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(seeds)


def frac(num, den):
    return round(num / den, 4) if den else None


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)

    # ---------------- shared structures (H582 harness) ----------------
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    titan = np.load(CACHE / "titan_emb.npy")
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    name_norms = [H._norm(m["name"]) if m["name"] else "" for m in meta]
    graph_norms = set(name_norms)
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)
    type_of = [(m["types"][0] if m["types"] else "Entity") for m in meta]

    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    out_deg = np.asarray(adj.sum(axis=1)).ravel()
    out_deg[out_deg == 0] = 1.0

    def one_hop(sd):
        hop = set(sd)
        for u in sd:
            hop |= set(adj.indices[adj.indptr[u]:adj.indptr[u + 1]].tolist())
        return hop

    # typed directed edges (relation-name per endpoint pair)
    edges_typed = json.loads((R50 / "edges_typed.json").read_text())
    pair_rels = defaultdict(set)
    for a, rt, b in edges_typed:
        ia, ib = idx_of_id[a], idx_of_id[b]
        pair_rels[(min(ia, ib), max(ia, ib))].add(rt)

    # ---------------- probes / carriers ----------------
    off_ids = [json.loads(l)["id"] for l in H.SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    Q = {q.get("_id"): q for q in json.loads(H.QUESTIONS.read_text())}
    probes = [Q[i] for i in off_ids if i in Q]

    def resolve(name):
        return name_row.get(H._norm(name))

    carriers = []
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in gold_titles(q):
            tn = H._norm(t)
            carriers.append({"probe": pid, "carrier": t, "tnorm": tn,
                             "in_graph": tn in graph_norms, "carrier_idx": name_row.get(tn)})
    in_graph_mask = [c["in_graph"] for c in carriers]

    # Titan matrices + probe embeds (cached)
    d = np.load(CACHE / "titan_probe_emb.npz", allow_pickle=True)
    titan_probe = {pid: d[pid] for pid in off_ids}
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    titan_probe_n = {pid: v / (np.linalg.norm(v) + 1e-9) for pid, v in titan_probe.items()}

    # ---- harness sanity: reproduce Titan recall@16 = 0.6012 ----
    t_rec, t_r1, t_rp = H.arm_metrics(titan_n, titan_probe_n, carriers, name_norms,
                                      name_row, adj, out_deg, n, one_hop)
    titan_recall16 = round(float(np.mean(t_rec)), 4)
    titan_region_ppr = round(float(np.mean(t_rp)), 4)
    harness_ok = abs(titan_recall16 - TITAN_TARGET) <= 0.02
    harness_sanity = {
        "titan_carrier_recall@16": titan_recall16, "target": TITAN_TARGET,
        "h501_reference": H501_RECALL, "region_hit_ppr": titan_region_ppr,
        "reproduced_within_2pts": bool(harness_ok),
    }
    print(f"HARNESS titan recall@16={titan_recall16} (target {TITAN_TARGET}) ok={harness_ok}", flush=True)
    if not harness_ok:
        (OUT / f"h583-topology-ceiling-{run_id}.json").write_text(json.dumps(
            {"ABORTED": "harness broke", "harness_sanity": harness_sanity}, indent=1))
        print("HARNESS BROKEN - abort", flush=True)
        return

    # per-probe dense seeds (question) + cosine ranking (reused across gates)
    seeds_q, cos_rank = {}, {}
    for pid in off_ids:
        sims = titan_n @ titan_probe_n[pid]
        order = np.argsort(-sims)
        seeds_q[pid] = [int(x) for x in order[:TOP_K]]
        cos_rank[pid] = order  # full descending order of entity idx

    # answer-type per probe (uniform convention)
    def answer_type(q):
        ai = resolve(q.get("answer"))
        if ai is not None:
            return type_of[ai]
        for (s_, r_, o_) in reversed(q.get("evidences") or []):
            oi = resolve(o_)
            if oi is not None:
                return type_of[oi]
            si = resolve(s_)
            if si is not None:
                return type_of[si]
        return None

    atype = {q["_id"]: answer_type(q) for q in probes}
    qclass = {q["_id"]: q.get("type") for q in probes}
    type_members = defaultdict(list)   # type -> [entity idx]
    for i, t in enumerate(type_of):
        type_members[t].append(i)

    # ==================================================================
    #                              H583
    # ==================================================================
    # ---- (a) resolvability over entity-entity gold hops ----
    hop_struct = defaultdict(lambda: [0, 0])   # class -> [ok, tot]
    hop_typed = defaultdict(lambda: [0, 0])
    hop_syn = defaultdict(lambda: [0, 0])
    probe_chain = {}   # pid -> dict(structural, typed, syn) full-chain over EE hops
    src_of, bridge_of = {}, {}
    for q in probes:
        pid = q["_id"]
        evs = q.get("evidences") or []
        subs = {H._norm(s_) for (s_, r_, o_) in evs}
        objs = {H._norm(o_) for (s_, r_, o_) in evs}
        # source = gold carrier that is a subject and never an object; bridge = object
        srcs, brs = [], []
        for t in gold_titles(q):
            tn = H._norm(t)
            ci = name_row.get(tn)
            if ci is None:
                continue
            if tn in objs:
                brs.append(ci)
            elif tn in subs:
                srcs.append(ci)
            else:
                srcs.append(ci)  # unclassified given entity -> treat as source
        src_of[pid], bridge_of[pid] = srcs, brs
        cs = ct = csyn = True
        any_ee = False
        for (s_, r_, o_) in evs:
            si, oi = resolve(s_), resolve(o_)
            if si is None or oi is None:
                continue  # literal-terminating hop: not an entity-entity edge
            any_ee = True
            rels = pair_rels.get((min(si, oi), max(si, oi)), set())
            st = len(rels) > 0
            gr = norm_rel(r_)
            ty = any(norm_rel(x) == gr for x in rels)
            syn = ty or bool(rels & SYN.get((r_ or "").casefold(), set()))
            c = q["type"]
            hop_struct[c][1] += 1; hop_struct[c][0] += st
            hop_typed[c][1] += 1; hop_typed[c][0] += ty
            hop_syn[c][1] += 1; hop_syn[c][0] += syn
            cs &= st; ct &= ty; csyn &= syn
        probe_chain[pid] = {"has_ee_hops": any_ee,
                            "structural": bool(any_ee and cs),
                            "typed": bool(any_ee and ct),
                            "syn": bool(any_ee and csyn)}

    def class_frac(d):
        return {c: frac(v[0], v[1]) for c, v in d.items()}

    # per-probe chain resolvability by class (only probes with entity-entity hops)
    chain_by_class = defaultdict(lambda: {"struct": [0, 0], "typed": [0, 0], "syn": [0, 0]})
    for q in probes:
        pc = probe_chain[q["_id"]]
        if not pc["has_ee_hops"]:
            continue
        b = chain_by_class[q["type"]]
        b["struct"][1] += 1; b["struct"][0] += pc["structural"]
        b["typed"][1] += 1; b["typed"][0] += pc["typed"]
        b["syn"][1] += 1; b["syn"][0] += pc["syn"]
    chain_resolv = {c: {"n": v["struct"][1],
                        "structural": frac(v["struct"][0], v["struct"][1]),
                        "typed_exact": frac(v["typed"][0], v["typed"][1]),
                        "typed_curated_oracle": frac(v["syn"][0], v["syn"][1])}
                    for c, v in chain_by_class.items()}

    # HARD SUB-CAP: gold relation-SEQUENCE (typed) resolvability on compositional/bridge
    comp_bridge = [q["_id"] for q in probes
                   if q["type"] in ("compositional", "bridge_comparison")
                   and probe_chain[q["_id"]]["has_ee_hops"]]
    cb_typed = frac(sum(probe_chain[p]["typed"] for p in comp_bridge), len(comp_bridge))
    cb_syn = frac(sum(probe_chain[p]["syn"] for p in comp_bridge), len(comp_bridge))
    cb_struct = frac(sum(probe_chain[p]["structural"] for p in comp_bridge), len(comp_bridge))
    subcap_fires = (cb_typed is not None and cb_typed < 0.50)

    # ---- (b) reachability oracle (H515 all-golds convention, paired) ----
    def probe_carriers_in_graph(pid):
        return [c["carrier_idx"] for c in carriers if c["probe"] == pid and c["in_graph"]]

    reach_rows = []
    for q in probes:
        pid = q["_id"]
        cis = probe_carriers_in_graph(pid)
        if not cis:
            continue
        brs = [b for b in bridge_of[pid] if b is not None]
        srcs = [s for s in src_of[pid] if s is not None]
        # isotropic: question dense@16 seeds + isotropic PPR
        sd = seeds_q[pid]
        r_iso = H.ppr(adj, out_deg, sd, n)
        reg_iso = region(r_iso, sd)
        # oracle: seed from gold SOURCE entities (oracle entity-linking) + isotropic PPR
        oseed = srcs if srcs else sd
        r_os = H.ppr(adj, out_deg, oseed, n)
        reg_os = region(r_os, oseed)
        # oracle + node-type region (charitable typed ceiling): keep nodes whose
        # cured type is one of this probe's gold-path node types
        path_types = {type_of[i] for i in (cis + srcs + brs)}
        node_mask = np.array([type_of[i] in path_types for i in range(n)])
        r_ot = ppr_masked(adj, oseed, node_mask)
        reg_ot = region(r_ot, [s for s in oseed if node_mask[s]])
        # oracle + relation-aligned-edge region (strict typed walk): keep only
        # edges whose relation aligns (curated-oracle) to a gold relation here
        gold_rel_syn = set()
        for (s_, r_, o_) in q.get("evidences") or []:
            gr = norm_rel(r_)
            gold_rel_syn |= {gr}
            gold_rel_syn |= {norm_rel(x) for x in SYN.get((r_ or "").casefold(), set())}
        # build a masked adjacency keeping aligned edges only
        keep_ij = [[u, v] for (u, v), rels in pair_rels.items()
                   if any(norm_rel(x) in gold_rel_syn for x in rels)]
        if keep_ij:
            kij = np.array(keep_ij)
            kadj = csr_matrix((np.ones(len(kij)), (kij[:, 0], kij[:, 1])), shape=(n, n))
            kadj = ((kadj + kadj.T) > 0).astype(float).tocsr()
        else:
            kadj = csr_matrix((n, n))
        r_re = ppr_masked(kadj, oseed, None)
        reg_re = region(r_re, oseed)

        def allin(reg, tgt):
            return bool(tgt) and all(t in reg for t in tgt)

        reach_rows.append({
            "probe": pid, "class": q["type"],
            "n_carriers": len(cis), "n_bridge": len(brs), "n_source": len(srcs),
            # all-golds reachability
            "iso_all": allin(reg_iso, cis),
            "oracle_seed_all": allin(reg_os, cis),
            "oracle_typed_all": allin(reg_ot, cis),
            "oracle_reledge_all": allin(reg_re, cis),
            # bridge-only reachability (the hard carriers)
            "has_bridge": len(brs) > 0,
            "iso_bridge": allin(reg_iso, brs) if brs else None,
            "oracle_seed_bridge": allin(reg_os, brs) if brs else None,
            "oracle_typed_bridge": allin(reg_ot, brs) if brs else None,
            "oracle_reledge_bridge": allin(reg_re, brs) if brs else None,
        })

    def reach_rate(key, subset=None):
        rows = [r for r in reach_rows if (subset is None or r[subset])]
        vals = [r[key] for r in rows if r[key] is not None]
        return frac(sum(vals), len(vals)), len(vals)

    reach = {}
    for key in ("iso_all", "oracle_seed_all", "oracle_typed_all", "oracle_reledge_all"):
        rate, nn = reach_rate(key)
        reach[key] = {"rate": rate, "n": nn}
    for key in ("iso_bridge", "oracle_seed_bridge", "oracle_typed_bridge", "oracle_reledge_bridge"):
        rate, nn = reach_rate(key, subset="has_bridge")
        reach[key] = {"rate": rate, "n": nn}

    # paired all-golds: oracle_typed vs iso
    iso_all = [r["iso_all"] for r in reach_rows]
    orc_all = [r["oracle_typed_all"] for r in reach_rows]
    b_all, c_all, p_all = H.mcnemar(iso_all, orc_all)
    reach_delta_all = round((np.mean(orc_all) - np.mean(iso_all)) * 100, 2)
    # paired bridge: oracle_typed_bridge vs iso_bridge (probes with bridge)
    br = [r for r in reach_rows if r["has_bridge"]]
    iso_br = [r["iso_bridge"] for r in br]
    orc_br = [r["oracle_typed_bridge"] for r in br]
    b_br, c_br, p_br = H.mcnemar(iso_br, orc_br)
    reach_delta_br = round((np.mean(orc_br) - np.mean(iso_br)) * 100, 2) if br else None

    # per-class reachability strata (all-golds)
    reach_class = {}
    for c in ("compositional", "comparison", "bridge_comparison", "inference"):
        rows = [r for r in reach_rows if r["class"] == c]
        if rows:
            reach_class[c] = {
                "n": len(rows),
                "iso_all": frac(sum(r["iso_all"] for r in rows), len(rows)),
                "oracle_typed_all": frac(sum(r["oracle_typed_all"] for r in rows), len(rows)),
            }

    # ---- recall@16 oracle: candidate pool = gold-path node types ----
    rec_iso, rec_typed = [], []
    for c in carriers:
        pid = c["probe"]
        q = Q[pid]
        cis = [name_row.get(H._norm(t)) for t in gold_titles(q)]
        srcs = [s for s in src_of[pid]]
        brs = [b for b in bridge_of[pid]]
        path_types = {type_of[i] for i in cis + srcs + brs if i is not None}
        order = cos_rank[pid]
        # type-restricted top-16 (pool = gold-path node types)
        pool = [int(i) for i in order if type_of[i] in path_types][:TOP_K]
        pool_norms = {name_norms[i] for i in pool}
        iso_norms = {name_norms[i] for i in seeds_q[pid]}
        rec_iso.append(1 if c["tnorm"] in iso_norms else 0)
        rec_typed.append(1 if c["tnorm"] in pool_norms else 0)
    recall_iso = round(float(np.mean(rec_iso)), 4)
    recall_typed = round(float(np.mean(rec_typed)), 4)
    b_r, c_r, p_r = H.mcnemar(rec_iso, rec_typed)
    recall_delta = round((recall_typed - recall_iso) * 100, 2)

    # ---- H583 clauses / verdict ----
    reach_lift = reach_delta_all      # primary: charitable node-type oracle, all-golds
    clauses583 = [
        {"clause": "reachability lift >= +8pp (paired McNemar p<0.05) [charitable node-type oracle, all-golds]",
         "predicted": ">= +8pp & p<0.05",
         "measured": f"{reach_lift}pp (iso {reach['iso_all']['rate']} -> oracle {reach['oracle_typed_all']['rate']}), McNemar p={p_all}",
         "holds": bool(reach_lift is not None and reach_lift >= 8.0 and p_all < 0.05)},
        {"clause": "recall@16 lift >= +8pp [gold-path node-type pool]",
         "predicted": ">= +8pp",
         "measured": f"{recall_delta}pp (iso {recall_iso} -> typed {recall_typed}), McNemar p={p_r}",
         "holds": bool(recall_delta >= 8.0)},
        {"clause": "KILL: lift < +3pp on BOTH reachability and recall@16",
         "predicted": "kill if both < +3pp",
         "measured": f"reach {reach_lift}pp / recall {recall_delta}pp",
         "holds": bool((reach_lift is not None and reach_lift < 3.0) and recall_delta < 3.0)},
        {"clause": "HARD SUB-CAP: gold relation-sequence resolvability < 50% on compositional/bridge",
         "predicted": "axis dies at premise if < 50%",
         "measured": f"typed-exact {cb_typed} (curated-oracle {cb_syn}) over {len(comp_bridge)} comp/bridge chains",
         "holds": bool(subcap_fires)},
    ]
    if subcap_fires:
        verdict583 = "KILLED (HARD SUB-CAP: gold topology unbuildable)"
    elif reach_lift is not None and reach_lift >= 8.0 and p_all < 0.05 and recall_delta >= 8.0:
        verdict583 = "CONFIRMED"
    elif (reach_lift is not None and reach_lift < 3.0) and recall_delta < 3.0:
        verdict583 = "KILLED"
    else:
        verdict583 = "INDETERMINATE"

    h583 = {
        "run_id": run_id, "hypothesis": "R50-H583", "scoring_fence": "retrieval-level only",
        "harness_sanity": harness_sanity,
        "n_probes": len(probes), "n_carriers": len(carriers),
        "n_carriers_in_graph": int(sum(in_graph_mask)),
        "resolvability": {
            "note": "entity-entity gold hops only (literal-terminating hops cannot be "
            "entity edges); structural=edge exists (relation-agnostic); typed_exact="
            "gold relation-name exact-normalized match (sanctioned oracle convention); "
            "typed_curated_oracle=hand synonym map bracketing a best-case relation linker",
            "hop_structural_by_class": class_frac(hop_struct),
            "hop_typed_exact_by_class": class_frac(hop_typed),
            "hop_typed_curated_oracle_by_class": class_frac(hop_syn),
            "per_probe_chain_by_class": chain_resolv,
            "hard_subcap_comp_bridge": {
                "n_chains": len(comp_bridge),
                "structural": cb_struct,
                "typed_exact": cb_typed,
                "typed_curated_oracle": cb_syn,
                "fires_below_0.50": bool(subcap_fires),
            },
        },
        "reachability": {
            "convention": "H515 all-golds-in-region (top-15 PPR u seeds), paired on frozen probes; "
            "oracle seeds from gold SOURCE entities (oracle entity-linking of question anchors)",
            "iso_reference_h515": ISO_REACH_REF,
            "rates": reach,
            "all_golds_delta_pp": reach_delta_all,
            "all_golds_mcnemar": {"b_iso_only": b_all, "c_oracle_only": c_all, "p": p_all},
            "bridge_only_delta_pp": reach_delta_br,
            "bridge_only_mcnemar": {"b_iso_only": b_br, "c_oracle_only": c_br, "p": p_br},
            "by_class_all_golds": reach_class,
        },
        "recall16_oracle": {
            "pool": "gold-path node-type-restricted top-16 by question cosine",
            "iso": recall_iso, "typed_pool": recall_typed, "delta_pp": recall_delta,
            "mcnemar": {"b_iso_only": b_r, "c_typed_only": c_r, "p": p_r},
        },
        "clauses": clauses583,
        "acceptance_bar": "CONFIRMED reach&recall lift>=+8pp p<0.05; KILL both<+3pp; "
        "HARD SUB-CAP typed resolvability<50% comp/bridge = axis dies at premise",
        "proposed_verdict": verdict583,
    }

    # ==================================================================
    #                              H584
    # ==================================================================
    # hard type-restricted top-16 (pool = answer-type entities), all 326 carriers
    h584_iso, h584_typed = [], []
    recoverable_num = recoverable_den = 0
    at_carrier_iso, at_carrier_typed = [], []   # carriers whose type == answer-type
    for c in carriers:
        pid = c["probe"]
        at = atype[pid]
        order = cos_rank[pid]
        iso_norms = {name_norms[i] for i in seeds_q[pid]}
        h584_iso.append(1 if c["tnorm"] in iso_norms else 0)
        if at is None:
            h584_typed.append(1 if c["tnorm"] in iso_norms else 0)
            continue
        pool = [int(i) for i in order if type_of[i] == at][:TOP_K]
        pool_norms = {name_norms[i] for i in pool}
        hit_typed = 1 if c["tnorm"] in pool_norms else 0
        h584_typed.append(hit_typed)
        # recoverable fraction: dense-missed in-graph carrier, type==answer-type, rank 17-50
        ci = c["carrier_idx"]
        if c["in_graph"] and ci is not None and c["tnorm"] not in iso_norms and type_of[ci] == at:
            recoverable_den += 1
            rank = int(np.where(order == ci)[0][0])  # 0-based cosine rank
            if 16 <= rank <= 49:
                recoverable_num += 1
        # answer-type-carrier subset recall (the helpable carriers)
        if c["in_graph"] and ci is not None and type_of[ci] == at:
            at_carrier_iso.append(1 if c["tnorm"] in iso_norms else 0)
            at_carrier_typed.append(1 if c["tnorm"] in pool_norms else 0)
    r584_iso = round(float(np.mean(h584_iso)), 4)
    r584_typed = round(float(np.mean(h584_typed)), 4)
    b584, c584, p584 = H.mcnemar(h584_iso, h584_typed)
    delta584 = round((r584_typed - r584_iso) * 100, 2)
    recoverable = frac(recoverable_num, recoverable_den)
    at_iso = round(float(np.mean(at_carrier_iso)), 4) if at_carrier_iso else None
    at_typed = round(float(np.mean(at_carrier_typed)), 4) if at_carrier_typed else None

    # per-class delta strata
    class584 = {}
    for cc in ("compositional", "comparison", "bridge_comparison", "inference"):
        idxs = [k for k, c in enumerate(carriers) if qclass.get(c["probe"]) == cc]
        if idxs:
            iso = np.mean([h584_iso[k] for k in idxs])
            typ = np.mean([h584_typed[k] for k in idxs])
            class584[cc] = {"n_carriers": len(idxs), "iso": round(float(iso), 4),
                            "typed": round(float(typ), 4),
                            "delta_pp": round(float(typ - iso) * 100, 2)}

    if delta584 >= 3.0:
        verdict584 = "DOMAIN-OPEN"
    elif delta584 < 2.0:
        verdict584 = "DOMAIN-CLOSED (KILL)"
    else:
        verdict584 = "INDETERMINATE"
    clauses584 = [
        {"clause": "oracle type-restricted recall@16 delta >= +3.0pp (DOMAIN-OPEN)",
         "predicted": "+2 to +6pp", "measured": f"{delta584}pp (iso {r584_iso} -> typed {r584_typed}), p={p584}",
         "holds": bool(delta584 >= 3.0)},
        {"clause": "DOMAIN-CLOSED/KILL: delta < +2.0pp (type already priced into dense, H174 generalizes)",
         "predicted": "kill if < +2pp", "measured": f"{delta584}pp",
         "holds": bool(delta584 < 2.0)},
        {"clause": "recoverable fraction (dense-missed in-graph carriers type-matched at rank 17-50) in 0.3-0.5",
         "predicted": "0.3-0.5", "measured": f"{recoverable} ({recoverable_num}/{recoverable_den})",
         "holds": bool(recoverable is not None and 0.3 <= recoverable <= 0.5)},
    ]
    h584 = {
        "run_id": run_id, "hypothesis": "R50-H584", "scoring_fence": "retrieval-level only",
        "harness_sanity": harness_sanity,
        "answer_type_convention": "resolved gold answer entity cured type; literal -> deepest "
        "resolvable gold-evidence entity type; first non-Entity label",
        "answer_type_dist": dict(Counter(atype.values())),
        "n_carriers": len(carriers),
        "hard_type_restricted": {
            "iso_recall16": r584_iso, "typed_recall16": r584_typed, "delta_pp": delta584,
            "mcnemar": {"b_iso_only": b584, "c_typed_only": c584, "p": p584},
        },
        "recoverable_fraction": {"value": recoverable, "num": recoverable_num, "den": recoverable_den,
                                 "note": "of dense-missed in-graph carriers whose type==answer-type, "
                                 "fraction sitting at full-cosine rank 17-50"},
        "answer_type_carrier_subset": {"iso": at_iso, "typed": at_typed,
                                       "n": len(at_carrier_iso),
                                       "note": "recall restricted to carriers whose type==answer-type "
                                       "(the subset hard-restriction can help)"},
        "by_class": class584,
        "clauses": clauses584,
        "acceptance_bar": "DOMAIN-OPEN if delta>=+3.0pp; DOMAIN-CLOSED/KILL if <+2.0pp",
        "proposed_verdict": verdict584,
    }

    # ==================================================================
    #                    H586 (single-entity-answer subset)
    # ==================================================================
    se_probes = [q for q in probes if resolve(q.get("answer")) is not None]
    se_ids = {q["_id"] for q in se_probes}
    se_atype = {q["_id"]: type_of[resolve(q["answer"])] for q in se_probes}

    # recall horn: fraction of gold carriers (single-entity subset) with type != answer-type
    off_type = tot_carr = 0
    for c in carriers:
        if c["probe"] not in se_ids or not c["in_graph"] or c["carrier_idx"] is None:
            continue
        tot_carr += 1
        if type_of[c["carrier_idx"]] != se_atype[c["probe"]]:
            off_type += 1
    recall_horn_frac = frac(off_type, tot_carr)
    recall_horn_holds = bool(recall_horn_frac is not None and recall_horn_frac >= 0.10)
    recall_horn_clears = bool(recall_horn_frac is not None and recall_horn_frac < 0.05)

    # informativeness horn: median over probes of (answer-type pool size / n)
    pool_frac = [len(type_members[se_atype[q["_id"]]]) / n for q in se_probes]
    median_pool = round(float(np.median(pool_frac)), 4) if pool_frac else None
    info_horn_holds = bool(median_pool is not None and median_pool >= 0.60)
    info_horn_clears = bool(median_pool is not None and median_pool < 0.30)

    # separability horn: dense-missed in-graph carriers where >=3 of top-16 crowd-out
    # distractors share the carrier's answer-type
    sep_num = sep_den = 0
    sep_detail = []
    for c in carriers:
        pid = c["probe"]
        if pid not in se_ids or not c["in_graph"] or c["carrier_idx"] is None:
            continue
        seeds = seeds_q[pid]
        iso_norms = {name_norms[i] for i in seeds}
        if c["tnorm"] in iso_norms:
            continue  # not a miss
        sep_den += 1
        at = se_atype[pid]
        shared = sum(1 for i in seeds if type_of[i] == at)
        holds = shared >= 3
        sep_num += holds
        sep_detail.append({"probe": pid, "carrier": c["carrier"], "answer_type": at,
                           "shared_distractors": shared})
    separability = frac(sep_num, sep_den)
    sep_holds = bool(separability is not None and separability >= 0.70)
    sep_below_50 = bool(separability is not None and separability < 0.50)

    if sep_holds or info_horn_holds or recall_horn_holds:
        verdict586 = "NULL CONFIRMED"
    elif sep_below_50 and recall_horn_clears and info_horn_clears:
        verdict586 = "FALSIFIED-OPEN"
    else:
        verdict586 = "INDETERMINATE"
    clauses586 = [
        {"clause": "recall horn: >=10% of gold carriers carry a type disagreeing with the query answer-type",
         "predicted": ">=10% off-type", "measured": f"{recall_horn_frac} ({off_type}/{tot_carr})",
         "holds": recall_horn_holds},
        {"clause": "informativeness horn: query-answer-type sub-pool >=60% of entities (median)",
         "predicted": ">=60%", "measured": f"median {median_pool}",
         "holds": info_horn_holds},
        {"clause": "separability horn: >=70% of dense-missed in-graph carriers share answer-type with >=3 top-16 distractors",
         "predicted": ">=70%", "measured": f"{separability} ({sep_num}/{sep_den})",
         "holds": sep_holds},
        {"clause": "FALSIFIED-OPEN gate: separability <50% AND recall horn clears (<5% off-type) AND matched-pool <30%",
         "predicted": "open if all three", "measured": f"sep {separability} / off-type {recall_horn_frac} / pool {median_pool}",
         "holds": bool(sep_below_50 and recall_horn_clears and info_horn_clears)},
    ]
    h586 = {
        "run_id": run_id, "hypothesis": "R50-H586", "scoring_fence": "retrieval-level only",
        "subset": "single-entity-answer (gold answer resolves to a graph entity)",
        "n_single_entity_probes": len(se_probes),
        "answer_type_dist_subset": dict(Counter(se_atype.values())),
        "recall_horn": {"off_type_carrier_frac": recall_horn_frac, "off_type": off_type,
                        "total_carriers": tot_carr, "holds": recall_horn_holds,
                        "clears_below_5pct": recall_horn_clears},
        "informativeness_horn": {"median_answer_type_pool_frac": median_pool,
                                 "holds_ge_60pct": info_horn_holds, "clears_below_30pct": info_horn_clears},
        "separability_horn": {"value": separability, "num": sep_num, "den": sep_den,
                              "holds_ge_70pct": sep_holds, "below_50pct": sep_below_50},
        "clauses": clauses586,
        "acceptance_bar": "NULL CONFIRMED if separability>=70% OR either horn holds; "
        "FALSIFIED-OPEN if separability<50% AND both horns clear (off-type<5% AND pool<30%)",
        "proposed_verdict": verdict586,
        "separability_detail_sample": sep_detail[:20],
    }

    # ---------------- write ----------------
    p583 = OUT / f"h583-topology-ceiling-{run_id}.json"
    p584 = OUT / f"h584-typeceiling-{run_id}.json"
    p586 = OUT / f"h586-separability-{run_id}.json"
    p583.write_text(json.dumps(h583, indent=1))
    p584.write_text(json.dumps(h584, indent=1))
    p586.write_text(json.dumps(h586, indent=1))
    print("H583 " + json.dumps({"verdict": verdict583, "reach_all_delta_pp": reach_delta_all,
                                "reach_p": p_all, "recall16_delta_pp": recall_delta,
                                "subcap_typed_comp_bridge": cb_typed, "subcap_fires": subcap_fires}))
    print("H584 " + json.dumps({"verdict": verdict584, "delta_pp": delta584,
                                "recoverable": recoverable}))
    print("H586 " + json.dumps({"verdict": verdict586, "separability": separability,
                                "recall_horn": recall_horn_frac, "median_pool": median_pool}))
    print(f"WROTE {p583}\nWROTE {p584}\nWROTE {p586}")


if __name__ == "__main__":
    main()

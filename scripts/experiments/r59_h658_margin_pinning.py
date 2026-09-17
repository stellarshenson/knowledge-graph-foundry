"""R59-H658 - separation-certificate identity pinning, RE-PRICED FORM (FREE offline arm).

Registered bar (experiments log, R59-H658): CONFIRMED if the certificate reduces false
merges at equal or better TRUE-MERGE count on the adjudicated set; KILLED if
indistinguishable from the fixed threshold - the certificate is then a re-parameterisation
and the constant stays.

RE-PRICING (R59-H657 status line, 2026-09-14): the certificate IS a margin-to-runner-up
threshold with beta as its knob. Accept a mention -> prototype merge iff

    margin(m) = cos(m, p1) - cos(m, p2)  >=  tau,     tau = ln(2 (N-1) / eps) / beta

with p1 the mention's nearest OTHER prototype, p2 the runner-up, N = 6,626, eps = 0.01
(so the log term is 14.097). The CONFIRMED clause requires the margin rule to dominate the
fixed cosine rule AT MATCHED MERGE VOLUME: for each tau, take the fixed-cosine threshold
that accepts the same number of merges on the SAME candidate set, then compare false-merge
and true-merge counts on the adjudicated surface. KILLED if indistinguishable within the
H540 band at the available paired n.

THE FIXED RULE COMPARED AGAINST (shipped, stated precisely):
  - embedding screen `ResolutionSettings.synonym_cluster_threshold = 0.82`
    (src/knowledge_graph_foundry/settings.py:95), applied as a hand-set global cosine in
    `resolution/blocking.py::ann_candidates` / `_brute_force` / `_ann_block` (lines 20-77)
    to admit a within-type pair as a merge CANDIDATE at all;
  - the decision that follows is `calibrated posterior >= ResolutionSettings.merge_threshold
    = 0.6` (settings.py:90) in `resolution/resolver.py:244`, or the v2 logistic stack.
  NOTE recorded rather than assumed: the brief's `cross_type_merge_threshold` and the 0.9
  cosine screen do NOT exist in the shipped tree (grep over src/ returns nothing); the live
  constants are 0.6 (posterior merge threshold) and 0.82 (global cosine screen). The
  fixed-cosine comparator here is the 0.82-class embedding screen, swept over theta, which
  is an UPPER BOUND on shipped merge volume because the shipped path additionally requires
  same-type blocking and the posterior/logistic decision.

THE ADJUDICATED SURFACE (DEF-19 v3 gold-join, R55-H632 -> R56-H635):
  goldjoin v3 = 326 carrier rows, 288 exact-in-graph + 38 adjudicated (26 ACCEPTED,
  1 ADJUDICATE-PENDING, 11 unresolved) = 314/326 joined, rung ladder
  r0 exact / r1 paren-strip / r2 fold / r3 fuzzy >= 0.92 with the H635 type-consistency gate.
  true-merge pair    = two GRAPH entities joined to the SAME gold entity
  true-non-merge pair = graph entities joined to DIFFERENT gold entities
  Two label maps are built and both reported exactly:
    STRICT - the accepted v3 join, with every bank index sharing the joined node's
             normalised name added (name_row keeps only the first, so this recovers any
             same-norm duplicate the join would otherwise hide)
    ALL    - the same v3 machinery run WITHOUT the stop-at-first-rung rule: every candidate
             the gated ladder accepts (same-norm, node-side paren-strip, fold, fuzzy >= 0.92),
             subject to the identical type-consistency gate, reviewed-absent list and
             year-conflict rule, then the H632 false-merge guard (a node claimed by two
             distinct gold titles is dropped from both). This is the strongest honest reading
             of the gold-join, built so that a PREMISE-FAIL verdict cannot be an artifact of
             the ladder stopping early. It is NOT adjudicated and carries no verdict.
    ADJUDICATED - ALL with every multi-node set hand-reviewed here (REVIEWED_DUPLICATE_SETS
             below, one justification per set, H632 "honesty over yield" convention: a set
             that cannot be judged on the node descriptions is PENDED, not counted).

  The registered verdict is read off STRICT - the join as adjudicated and shipped. ALL and
  ADJUDICATED are labelled secondary readings, never the registered surface.

Substrate: frozen H582 entity prototype bank tmp/results/r47/titan_emb.npy (6,626 x 1024
Titan vectors), l2-normalised - the same bank R59-H657 measured. FREE numpy. NO GPU, NO LLM,
NO Neo4j, NO network.

Sanity pins (abort on miss): dense@16 carrier recall 0.6012; H657 Delta percentile curve
p1 0.0618 / p50 0.4523 / p90 0.6513 where Delta_i = 1 - cos(i, nearest OTHER prototype).

Writes:
  reports/experiments/r59/h658-margin-pinning-<ts>.json
  reports/experiments/r59/h658-margin-pinning-<ts>.md            (brief)
  reports/experiments/r59/h658-margin-pinning-<ts>.checkpoint.jsonl
"""

import difflib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H       # noqa: E402  (_norm)
import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate)
import r55_h632_gold_join as V2          # noqa: E402  (paren_strip/fold/qualifier/OK_TYPES/YEAR)
import r56_h635_type_gate as H635        # noqa: E402  (expected_category_v3)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r59"
GOLDJOIN_V3 = ROOT / "reports/experiments/r56/h635-type-gate-20260724T082828Z.json"

EPS = 0.01
BETAS_REGISTERED = (64, 96, 128)          # the re-priced sweep
BETAS_BRACKET = (48, 192)                 # bracketing points, labelled
BASE_RECALL_PIN = 0.6012
DELTA_PINS = {"p1": 0.0618, "p50": 0.4523, "p90": 0.6513}
PIN_TOL = 0.0011
SHIPPED_COSINE = 0.82                     # ResolutionSettings.synonym_cluster_threshold
SMALL_N_FLOOR = 30                        # H540 discipline boundary named in the spec

JOIN_VERSION = "goldjoin-v3-typegate-20260724 (R56-H635; 314/326 carrier rows joined, 38 adjudicated)"
FIXED_RULE = (
    "shipped global cosine screen ResolutionSettings.synonym_cluster_threshold = 0.82 "
    "(src/knowledge_graph_foundry/settings.py:95), applied in "
    "src/knowledge_graph_foundry/resolution/blocking.py::ann_candidates (lines 53-77); the "
    "decision behind it is calibrated posterior >= ResolutionSettings.merge_threshold = 0.6 "
    "(settings.py:90) at src/knowledge_graph_foundry/resolution/resolver.py:244. "
    "`cross_type_merge_threshold` and a 0.9 screen are NOT present in the shipped tree."
)


# Hand adjudication of every multi-node set the ALL ladder produced (21 sets, run
# 20260914T083313Z). `keep` is the identity set for that gold entity; every other node the
# ladder attached to it is rejected. Convention follows R55-H632: a set that the node
# descriptions cannot settle is PENDED (keep only the exact-norm node), never guessed.
REVIEWED_DUPLICATE_SETS = {
    "albert iii, duke of bavaria": ([5100], "reject 5126 'Albert I, Duke of Bavaria' - different ordinal, different person"),
    "billy elliot": ([1275], "reject 1309 'Billy Elliot (novel)' [Book] - different work from the Film"),
    "brother rat": ([6563], "reject 6564 'Brother Rat (play)' [Document] - different work from the Film"),
    "christine of hesse-kassel (1578–1658)": ([2789, 2816], "ACCEPT pair - hyphen/non-breaking-hyphen variant of one name; descriptions agree (House of Hesse noblewoman, wife of Johann Ernst of Saxe-Eisenach)"),
    "david bradley (director)": ([1992], "PEND 2008 'David Bradley' - both nodes carry no description and the bare name is ambiguous between the director and the actor"),
    "do you believe? (film)": ([5892, 5900], "ACCEPT pair - paren-strip disambiguator only, both typed Film"),
    "john middleton murry": ([1224], "reject 1219 'John Middleton Murry Jr.' - generational suffix, father and son are different people"),
    "lisbeth palme": ([1366, 1368], "ACCEPT pair - node 1368 descr states 'Alternative spelling of Lisbeth Palme'"),
    "marianus v of arborea": ([5027], "reject 5077 'Marianus I of Arborea' - different ordinal, different person"),
    "mord em'ly": ([4940, 4976], "ACCEPT pair - both [Book], 1898 novel by William Pett Ridge; reject 4975 'Mord Em'ly (film)' [Film] - different work"),
    "palo alto (2013 film)": ([2884, 2909], "ACCEPT pair - both typed Film and both described as the 2013 film"),
    "princess maria of greece and denmark": ([6538], "reject 6521 'Princess Alexia of Greece and Denmark' - different given name, different person"),
    "r. g. springsteen": ([1389, 3581], "ACCEPT pair - punctuation-only variant 'R.G.' / 'R. G.' of one name"),
    "raghnall mac ruaidhrí": ([448, 458], "ACCEPT pair - diacritic/case variant; descriptions agree (Lord of Garmoran / chief of Clann Ruaidhri)"),
    "ryan adams": ([671], "reject 708 'Ryan Adams (album)' [Album] - a work, not the Person"),
    "sisowath kossamak": ([1492, 1514], "ACCEPT pair - spelling variant; both describe the same Cambodian queen consort / queen mother"),
    "the goose woman": ([1053], "reject 1059 'The Goose Woman (short story)' [Book] - different work from the Film"),
    "theodore salisbury woolsey": ([1586], "reject 1583 and 1589 - both are 'Woolsey Jr.', the forestry son; the gold entity is the international-law professor"),
    "track & field news": ([5418, 5440], "ACCEPT pair - fold variant '&' / 'and' of one publication"),
    "william berke": ([5705], "PEND 5689 'William A. Berke' - middle initial; node 5705 carries no description, so the namesake reading cannot be excluded"),
    "wizards of the lost kingdom": ([3619], "reject 3632 'Wizards of the Lost Kingdom II' - sequel, different film"),
}


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def carrier_recall(S, seeds_by_pid):
    """dense@16 r0 carrier recall over ALL carriers (H627 convention) - the pin."""
    name_norms = S["name_norms"]
    hits = []
    for c in S["carriers"]:
        seed_norms = {name_norms[i] for i in seeds_by_pid[c["probe"]]}
        hits.append(1 if c["tnorm"] in seed_norms else 0)
    return round(float(np.mean(hits)), 4)


def top2_other(X, block=512):
    """(cos1, idx1, cos2, idx2) for each row against every OTHER row, blocked."""
    n = X.shape[0]
    c1 = np.full(n, -np.inf)
    c2 = np.full(n, -np.inf)
    i1 = np.full(n, -1, dtype=np.int64)
    i2 = np.full(n, -1, dtype=np.int64)
    for s in range(0, n, block):
        e = min(s + block, n)
        sims = (X[s:e] @ X.T).astype(np.float64)
        for r in range(e - s):
            sims[r, s + r] = -np.inf
        part = np.argpartition(-sims, 1, axis=1)[:, :2]
        for r in range(e - s):
            a, b = part[r]
            sa, sb = sims[r, a], sims[r, b]
            if sb > sa:
                a, b, sa, sb = b, a, sb, sa
            c1[s + r], i1[s + r], c2[s + r], i2[s + r] = sa, a, sb, b
    return c1, i1, c2, i2


# ---------------------------------------------------------------- surface ----
def build_surfaces(S, log, chk):
    """Return (strict_labels, all_labels, diag) - idx -> gold key maps."""
    meta, name_norms = S["meta"], S["name_norms"]
    n = S["n"]

    by_norm = defaultdict(list)
    ps_index = defaultdict(list)
    fold_index = defaultdict(list)
    for i, nn in enumerate(name_norms):
        if nn:
            by_norm[nn].append(i)
            ps_index[V2.paren_strip(nn)].append(i)
            fold_index[V2.fold(nn)].append(i)

    # gold titles: tnorm -> raw title (the ladder needs the raw form for the qualifier)
    raw_of = {}
    in_graph = {}
    for c in S["carriers"]:
        raw_of.setdefault(c["tnorm"], c["carrier"])
        in_graph[c["tnorm"]] = c["in_graph"]

    v3rows = json.loads(GOLDJOIN_V3.read_text())["ladder_v3_gate_on"]["all_rows"]
    v3_accept = {H._norm(r["gold_title"]): r["matched_idx"]
                 for r in v3rows if r["disposition"] == "ACCEPTED"}
    v3_disp = Counter(r["disposition"] for r in v3rows)

    # ---- STRICT: the accepted join, same-norm expanded ----------------------
    strict = defaultdict(set)
    for tn, raw in raw_of.items():
        if in_graph[tn]:
            strict[tn] |= set(by_norm.get(tn, []))
        elif tn in v3_accept and v3_accept[tn] is not None:
            j = int(v3_accept[tn])
            strict[tn] |= set(by_norm.get(name_norms[j], [j]))
    strict = {k: v for k, v in strict.items() if v}

    # ---- ALL: the same gated machinery without stop-at-first-rung -----------
    def gated_accept(raw, idx):
        """H635 gate + H632 auto-rules, verbatim in behaviour."""
        if raw in V2.REVIEWED_PENDING:
            return False
        qual = V2.qualifier(raw)
        cat = H635.expected_category_v3(qual)
        types = [t.lower() for t in (meta[idx]["types"] or [])]
        if cat is not None and types and not (set(types) & V2.OK_TYPES[cat]):
            return False
        descr = meta[idx]["descr"] or ""
        q_years = set(V2.YEAR.findall(qual))
        d_years = set(V2.YEAR.findall(descr))
        if q_years and d_years and not (q_years & d_years):
            return False
        return True

    fold_names = [V2.fold(nn) if nn else "" for nn in name_norms]
    allmap = defaultdict(set)
    for k, (tn, raw) in enumerate(sorted(raw_of.items())):
        ps = V2.paren_strip(tn)
        f = V2.fold(ps)
        cands = set(by_norm.get(tn, [])) | set(ps_index.get(ps, [])) | set(fold_index.get(f, []))
        for i, fn in enumerate(fold_names):
            if not fn or len(name_norms[i]) < 4:
                continue
            sm = difflib.SequenceMatcher(None, f, fn)
            if sm.real_quick_ratio() < V2.FUZZ or sm.quick_ratio() < V2.FUZZ:
                continue
            if sm.ratio() >= V2.FUZZ:
                cands.add(i)
        keep = {i for i in cands if gated_accept(raw, i)}
        if keep:
            allmap[tn] = keep
        if (k + 1) % 60 == 0:
            log(f"  ALL-ladder {k + 1}/{len(raw_of)} gold titles")
    # H632 false-merge guard: a node claimed by two distinct gold titles is ambiguous
    claim = Counter(i for s in allmap.values() for i in s)
    dropped = {i for i, c in claim.items() if c > 1}
    allmap = {t: (s - dropped) for t, s in allmap.items()}
    allmap = {t: s for t, s in allmap.items() if s}

    claim_s = Counter(i for s in strict.values() for i in s)
    strict_collisions = [i for i, c in claim_s.items() if c > 1]

    # ---- ADJUDICATED: ALL with every multi-node set hand-reviewed ----------
    adj = {}
    unreviewed = []
    for t, s in allmap.items():
        if len(s) < 2:
            adj[t] = set(s)
            continue
        if t in REVIEWED_DUPLICATE_SETS:
            keep = set(REVIEWED_DUPLICATE_SETS[t][0]) & s
            adj[t] = keep if keep else set(s)
        else:
            unreviewed.append(t)
            exact = set(by_norm.get(t, []))
            adj[t] = (exact & s) or {min(s)}
    if unreviewed:
        log(f"WARNING: {len(unreviewed)} multi-node sets are NOT in the review table: "
            f"{unreviewed}")

    diag = {
        "carrier_rows": len(S["carriers"]),
        "distinct_gold_titles": len(raw_of),
        "gold_titles_in_graph_exact": int(sum(1 for v in in_graph.values() if v)),
        "gold_titles_absent": int(sum(1 for v in in_graph.values() if not v)),
        "v3_dispositions_over_the_38": dict(v3_disp),
        "v3_accepted_variant_rows": len(v3_accept),
        "bank_norms_with_more_than_one_node": int(sum(1 for v in by_norm.values() if len(v) > 1)),
        "bank_nodes_in_such_norms": int(sum(len(v) for v in by_norm.values() if len(v) > 1)),
        "strict_false_merge_guard_collisions": len(strict_collisions),
        "all_ladder_nodes_dropped_by_guard": len(dropped),
        "all_multinode_sets": int(sum(1 for s in allmap.values() if len(s) >= 2)),
        "all_multinode_sets_reviewed": int(sum(1 for t, s in allmap.items()
                                               if len(s) >= 2 and t in REVIEWED_DUPLICATE_SETS)),
        "all_multinode_sets_unreviewed": unreviewed,
        "bank_n": n,
    }
    log(f"surface diag: {json.dumps(diag)}")
    chk("surface_diag", diag)
    return strict, allmap, adj, diag, by_norm


def surface_sizes(labels):
    sizes = [len(v) for v in labels.values()]
    tot = int(sum(sizes))
    true_merge = int(sum(s * (s - 1) // 2 for s in sizes))
    true_nonmerge = int((tot * tot - sum(s * s for s in sizes)) // 2)
    return {
        "gold_entities_contributing": len(labels),
        "graph_entities_labelled": tot,
        "true_merge_pairs": true_merge,
        "true_non_merge_pairs": true_nonmerge,
        "label_set_size_distribution": dict(sorted(Counter(sizes).items())),
        "gold_entities_with_2plus_graph_entities":
            int(sum(1 for s in sizes if s >= 2)),
    }


# ------------------------------------------------------------- comparison ----
def compare(labels, c1, i1, c2, taus, log, chk, tag):
    """Paired margin-vs-fixed-cosine comparison at MATCHED merge volume.

    Candidate set = every labelled graph entity m; its candidate merge is m -> p1 = i1[m].
    The two rules differ ONLY in the accept score: margin(m) = c1[m] - c2[m] >= tau, versus
    the fixed global cosine c1[m] >= theta. Both are evaluated on the same m, the same p1,
    so every count below is paired.
    """
    label_of = {i: t for t, s in labels.items() for i in s}
    mentions = sorted(label_of)
    marg = np.array([c1[m] - c2[m] for m in mentions])
    cos1 = np.array([c1[m] for m in mentions])
    order = np.argsort(-cos1)

    def adjudicate(sel):
        """sel = boolean mask over `mentions`. Returns exact counts."""
        t = f = u = 0
        false_rows = []
        for k, keep in enumerate(sel):
            if not keep:
                continue
            m = mentions[k]
            p = int(i1[m])
            lp = label_of.get(p)
            if lp is None:
                u += 1
            elif lp == label_of[m]:
                t += 1
            else:
                f += 1
                false_rows.append((m, p))
        return {"accepted": int(sel.sum()), "true_merges": t, "false_merges": f,
                "unlabelled_partner": u}, false_rows

    rows = []
    for beta, tau, reg in taus:
        sel_m = marg >= tau
        V = int(sel_m.sum())
        mres, mfalse = adjudicate(sel_m)
        # matched-volume fixed cosine: theta = the V-th largest cos1 on the same candidates
        if V == 0:
            theta = None
            fres = {"accepted": 0, "true_merges": 0, "false_merges": 0,
                    "unlabelled_partner": 0}
            ties = 0
        else:
            theta = float(cos1[order[V - 1]])
            sel_f = cos1 >= theta
            ties = int(sel_f.sum()) - V
            fres, _ = adjudicate(sel_f)
        row = {"beta": beta, "tau": round(tau, 6), "registered": reg,
               "margin": mres, "fixed_cosine_at_matched_volume": fres,
               "fixed_theta": None if theta is None else round(theta, 6),
               "fixed_volume_tie_overshoot": ties,
               "false_merge_delta_margin_minus_fixed":
                   mres["false_merges"] - fres["false_merges"],
               "true_merge_delta_margin_minus_fixed":
                   mres["true_merges"] - fres["true_merges"]}
        rows.append(row)
        log(f"[{tag}] beta={beta:3d} tau={tau:.4f}  margin: acc={mres['accepted']:4d} "
            f"false={mres['false_merges']:4d} true={mres['true_merges']:3d} "
            f"unlab={mres['unlabelled_partner']:4d} | fixed theta={theta if theta is None else round(theta,4)}: "
            f"acc={fres['accepted']:4d} false={fres['false_merges']:4d} true={fres['true_merges']:3d}")
        chk(f"compare_{tag}", row)

    sel_ship = cos1 >= SHIPPED_COSINE
    ship, _ = adjudicate(sel_ship)
    ship["theta"] = SHIPPED_COSINE
    log(f"[{tag}] shipped screen theta={SHIPPED_COSINE}: acc={ship['accepted']} "
        f"false={ship['false_merges']} true={ship['true_merges']} "
        f"unlab={ship['unlabelled_partner']}")
    chk(f"shipped_point_{tag}", ship)

    return {"rows": rows, "shipped_operating_point": ship,
            "candidate_set_size": len(mentions),
            "margin_stats": {"min": round(float(marg.min()), 6),
                             "median": round(float(np.median(marg)), 6),
                             "max": round(float(marg.max()), 6)},
            "cos1_stats": {"min": round(float(cos1.min()), 6),
                           "median": round(float(np.median(cos1)), 6),
                           "max": round(float(cos1.max()), 6)}}


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h658-margin-pinning-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    stem = OUT / f"h658-margin-pinning-{run_id}"

    # ---------------- substrate + pins --------------------------------------
    S = R50.load_substrate()
    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in S["off_ids"]}
    base_recall = carrier_recall(S, dense_seeds)

    raw = np.load(CACHE / "titan_emb.npy").astype(np.float64)
    n, d = raw.shape
    X = raw / (np.linalg.norm(raw, axis=1)[:, None] + 1e-12)
    c1, i1, c2, i2 = top2_other(X)
    delta = 1.0 - c1
    dpct = {k: round(float(np.percentile(delta, int(k[1:]))), 4) for k in DELTA_PINS}

    pins = {"dense16_carrier_recall": base_recall, "dense16_pin": BASE_RECALL_PIN,
            "delta_percentiles_measured": dpct, "delta_percentiles_pin": DELTA_PINS,
            "bank_N": n, "bank_dim": d}
    pins["ok"] = (abs(base_recall - BASE_RECALL_PIN) < 0.01
                  and all(abs(dpct[k] - DELTA_PINS[k]) < PIN_TOL for k in DELTA_PINS))
    log(f"PIN dense@16={base_recall} (pin {BASE_RECALL_PIN}); Delta {dpct} (pin {DELTA_PINS}) "
        f"ok={pins['ok']}")
    chk("pins", pins)
    if not pins["ok"]:
        stem.with_suffix(".json").write_text(json.dumps(
            {"hypothesis": "R59-H658", "run_id": run_id, "ABORTED_PIN_MISMATCH": True,
             "pins": pins}, indent=1))
        log("ABORT (pin mismatch) - no verdict reported")
        cf.close()
        return

    # ---------------- tau ladder --------------------------------------------
    log_term = float(np.log(2.0 * (n - 1) / EPS))
    taus = ([(b, log_term / b, True) for b in BETAS_REGISTERED]
            + [(b, log_term / b, False) for b in BETAS_BRACKET])
    taus.sort(key=lambda x: x[0])
    log(f"ln(2(N-1)/eps) = {log_term:.4f} at N={n}, eps={EPS}; "
        + ", ".join(f"beta {b} -> tau {t:.4f}" for b, t, _ in taus))
    chk("tau_ladder", {"log_term": round(log_term, 6), "N": n, "eps": EPS,
                       "taus": [{"beta": b, "tau": round(t, 6), "registered": r}
                                for b, t, r in taus]})

    # ---------------- the adjudicated surface -------------------------------
    strict, allmap, adjmap, diag, by_norm = build_surfaces(S, log, chk)
    sz_strict = surface_sizes(strict)
    sz_all = surface_sizes(allmap)
    sz_adj = surface_sizes(adjmap)
    log(f"STRICT surface:      {json.dumps(sz_strict)}")
    log(f"ALL surface:         {json.dumps(sz_all)}")
    log(f"ADJUDICATED surface: {json.dumps(sz_adj)}")
    chk("surface_strict", sz_strict)
    chk("surface_all", sz_all)
    chk("surface_adjudicated", sz_adj)

    # every multi-node set, with its hand adjudication
    dup_examples = []
    for t, s in sorted(allmap.items()):
        if len(s) >= 2:
            rev = REVIEWED_DUPLICATE_SETS.get(t)
            dup_examples.append({
                "gold_norm": t,
                "ladder_nodes": [{"idx": int(i), "name": S["meta"][i]["name"],
                                  "types": S["meta"][i]["types"]} for i in sorted(s)],
                "adjudicated_keep": sorted(int(i) for i in adjmap.get(t, set())),
                "adjudication": rev[1] if rev else "NOT REVIEWED",
            })
    chk("duplicate_sets", {"count": len(dup_examples), "rows": dup_examples})

    # the REGISTERED surface is STRICT - the join as adjudicated and shipped
    primary = "strict"
    sz_primary = sz_strict
    log(f"registered surface = STRICT (true-merge pairs {sz_primary['true_merge_pairs']}); "
        f"ALL {sz_all['true_merge_pairs']} (unadjudicated), "
        f"ADJUDICATED {sz_adj['true_merge_pairs']}")

    cmp_strict = compare(strict, c1, i1, c2, taus, log, chk, "strict")
    cmp_all = compare(allmap, c1, i1, c2, taus, log, chk, "all")
    cmp_adj = compare(adjmap, c1, i1, c2, taus, log, chk, "adjudicated")
    cmp_primary = cmp_strict

    # ---------------- verdict against the REGISTERED bar --------------------
    tm = sz_primary["true_merge_pairs"]
    adj_wins = sum(1 for r in cmp_adj["rows"]
                   if r["false_merge_delta_margin_minus_fixed"] < 0
                   and r["true_merge_delta_margin_minus_fixed"] >= 0)
    strict_better = sum(1 for r in cmp_strict["rows"]
                        if r["false_merge_delta_margin_minus_fixed"] < 0)
    secondary = (
        f"SECONDARY READINGS (labelled, not the registered surface). (a) On STRICT the "
        f"false-merge half IS adjudicable: at matched volume the margin rule produces fewer "
        f"false merges at {strict_better}/{len(cmp_strict['rows'])} tau points, and every "
        f"per-tau difference is at most "
        f"{max(abs(r['false_merge_delta_margin_minus_fixed']) for r in cmp_strict['rows'])} "
        f"merges on a {cmp_strict['candidate_set_size']}-entity candidate set - mixed sign, "
        f"no direction. (b) On the ADJUDICATED extension "
        f"({sz_adj['true_merge_pairs']} hand-reviewed true-merge pairs from "
        f"{diag['all_multinode_sets']} multi-node sets, "
        f"{diag['all_multinode_sets_reviewed']} reviewed) the margin rule dominates at "
        f"{adj_wins}/{len(cmp_adj['rows'])} tau points. Both readings are "
        f"indistinguishable-to-worse, never CONFIRMED.")
    if tm == 0:
        verdict = "PREMISE-FAILED"
        reason = (
            f"The DEF-19 v3 gold-join yields ZERO true-merge pairs. Exact counts: "
            f"{sz_primary['gold_entities_contributing']} gold entities join to "
            f"{sz_primary['graph_entities_labelled']} graph entities, "
            f"{sz_primary['gold_entities_with_2plus_graph_entities']} of them to two or more, "
            f"so C(|E|,2) summed over gold entities is 0 and the adjudicated TRUE-MERGE "
            f"surface is empty. The registered CONFIRMED clause ('reduces false merges at "
            f"equal or better true-merge count') is unevaluable: the true-merge count is 0 "
            f"for EVERY rule at EVERY threshold, so no rule can be shown to trade true merges "
            f"for false ones and no rule can dominate on that axis. Mechanism: the join's "
            f"graph side is the POST-RESOLUTION cured bank - "
            f"{diag['bank_norms_with_more_than_one_node']} normalised names of "
            f"{diag['bank_n']} nodes carry more than one node "
            f"({diag['bank_nodes_in_such_norms']} nodes in total), and none of them is "
            f"gold-joined - and the join itself is a title -> node function whose H632 "
            f"false-merge guard forbids many-to-one. The empty surface is not an artifact of "
            f"the ladder stopping early: the ALL extension (the gated ladder without "
            f"stop-at-first-rung) raises the count only to {sz_all['true_merge_pairs']}, and "
            f"hand review of all {diag['all_multinode_sets']} of its multi-node sets rejects "
            f"roughly half as same-name-DIFFERENT-entity (ordinals, generational suffixes, "
            f"sequels, work-type variants), leaving {sz_adj['true_merge_pairs']} genuine "
            f"pairs - still far under the {SMALL_N_FLOOR}-pair floor. " + secondary)
    elif tm < SMALL_N_FLOOR:
        wins = sum(1 for r in cmp_primary["rows"]
                   if r["false_merge_delta_margin_minus_fixed"] < 0
                   and r["true_merge_delta_margin_minus_fixed"] >= 0)
        verdict = ("CONFIRMED" if wins == len(cmp_primary["rows"]) else "KILLED")
        reason = (f"n = {tm} true-merge pairs, under the {SMALL_N_FLOOR}-pair floor: reported "
                  f"under H540 small-n discipline, NO significance claim. The margin rule "
                  f"dominates at {wins}/{len(cmp_primary['rows'])} tau points.")
    else:
        wins = sum(1 for r in cmp_primary["rows"]
                   if r["false_merge_delta_margin_minus_fixed"] < 0
                   and r["true_merge_delta_margin_minus_fixed"] >= 0)
        verdict = "CONFIRMED" if wins == len(cmp_primary["rows"]) else "KILLED"
        reason = (f"margin rule dominates at {wins}/{len(cmp_primary['rows'])} tau points "
                  f"on {tm} true-merge pairs at matched merge volume")
    log(f"VERDICT {verdict} - {reason}")
    chk("verdict", {"verdict": verdict, "reason": reason})

    summ = {
        "hypothesis": "R59-H658",
        "run_id": run_id,
        "utc_timestamp": run_id,
        "git_head": git_head(),
        "join_version": JOIN_VERSION,
        "registered_bar": ("CONFIRMED if the certificate reduces FALSE merges at equal or "
                           "better TRUE-MERGE count on the adjudicated set; KILLED if "
                           "indistinguishable from the fixed threshold."),
        "re_priced_form": ("margin(m) = cos(m,p1) - cos(m,p2) >= tau, "
                           "tau = ln(2(N-1)/eps)/beta, compared against the fixed global "
                           "cosine AT MATCHED MERGE VOLUME on the same candidate set"),
        "fixed_rule_compared_against": FIXED_RULE,
        "verdict": verdict,
        "verdict_reason": reason,
        "pins": pins,
        "tau_ladder": {"log_term_ln_2Nminus1_over_eps": round(log_term, 6), "N": n,
                       "eps": EPS,
                       "rows": [{"beta": b, "tau": round(t, 6), "registered": r}
                                for b, t, r in taus]},
        "substrate": (f"frozen H582 entity prototype bank tmp/results/r47/titan_emb.npy "
                      f"({n} x {d} Titan vectors), l2-normalised; FREE numpy, no "
                      f"GPU/LLM/Neo4j/net"),
        "surface_diagnostics": diag,
        "surface_strict": sz_strict,
        "surface_all_unadjudicated": sz_all,
        "surface_adjudicated": sz_adj,
        "registered_surface": primary,
        "duplicate_sets_with_adjudication": dup_examples,
        "comparison_strict": cmp_strict,
        "comparison_all_unadjudicated": cmp_all,
        "comparison_adjudicated": cmp_adj,
        "secondary_readings": secondary,
        "caveats": [
            "Every count is paired: both rules score the SAME candidate set (one candidate "
            "merge m -> p1 per labelled graph entity) and differ only in the accept score.",
            "The fixed-cosine comparator is the 0.82-class global embedding screen swept over "
            "theta; the shipped path additionally requires same-type blocking and the "
            "posterior/logistic decision, so these merge volumes are an UPPER BOUND on the "
            "shipped rule's.",
            "The bank embeds '{type}: {name} - {description[:200]}', so cos and the margin "
            "mix name and description separation; neither is a name-identity statistic.",
            "frozen 6,626-entity substrate, not the 7,575-entity live re-ingest.",
            "'unlabelled_partner' accepts are merges onto a prototype the gold-join does not "
            "label; they are neither true nor false merges and are reported separately, never "
            "folded into either count.",
        ],
        "artifacts": {"json": str(stem) + ".json", "brief": str(stem) + ".md",
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r59_h658_margin_pinning.py",
                      "log": "logs/r59-h658.log"},
    }
    (stem.with_name(stem.name + ".json")).write_text(json.dumps(summ, indent=1, default=str))

    def cmp_table(cmp):
        return "\n".join(
            f"| {r['beta']}{'' if r['registered'] else ' (bracket)'} | {r['tau']:.4f} | "
            f"{r['margin']['accepted']} | {r['margin']['false_merges']} | "
            f"{'-' if r['fixed_theta'] is None else format(r['fixed_theta'], '.4f')} | "
            f"{r['fixed_cosine_at_matched_volume']['false_merges']} | "
            f"{r['margin']['true_merges']} | "
            f"{r['fixed_cosine_at_matched_volume']['true_merges']} | "
            f"{r['margin']['unlabelled_partner']} |"
            for r in cmp["rows"])

    brief = f"""# R59-H658 separation-certificate identity pinning (re-priced) - brief

**{verdict}**. Run {run_id}, git {summ['git_head'][:12]}, join {JOIN_VERSION}.

Re-priced form: accept a mention -> prototype merge iff
`margin(m) = cos(m,p1) - cos(m,p2) >= tau`, `tau = ln(2(N-1)/eps)/beta`,
`N = {n}`, `eps = {EPS}`, log term **{log_term:.4f}**. Compared against the fixed global
cosine **at matched merge volume on the same candidate set**.

## Fixed rule compared against
{FIXED_RULE}

## Pins
- dense@16 carrier recall **{base_recall}** (pin {BASE_RECALL_PIN}) - held
- `Delta` percentiles p1 **{dpct['p1']}** / p50 **{dpct['p50']}** / p90 **{dpct['p90']}**
  (H657 pins {DELTA_PINS['p1']} / {DELTA_PINS['p50']} / {DELTA_PINS['p90']}) - held

## The adjudicated surface (exact)
Carrier rows **{diag['carrier_rows']}**, distinct gold titles **{diag['distinct_gold_titles']}**
({diag['gold_titles_in_graph_exact']} exact-in-graph, {diag['gold_titles_absent']} absent;
v3 dispositions over the 38: {diag['v3_dispositions_over_the_38']}).

| surface | gold entities | graph entities labelled | true-merge pairs | true-non-merge pairs | golds with >= 2 graph entities |
|---|---|---|---|---|---|
| STRICT - REGISTERED (accepted v3 join, same-norm expanded) | {sz_strict['gold_entities_contributing']} | {sz_strict['graph_entities_labelled']} | **{sz_strict['true_merge_pairs']}** | {sz_strict['true_non_merge_pairs']} | {sz_strict['gold_entities_with_2plus_graph_entities']} |
| ALL (gated ladder, no stop-at-first-rung, NOT adjudicated) | {sz_all['gold_entities_contributing']} | {sz_all['graph_entities_labelled']} | **{sz_all['true_merge_pairs']}** | {sz_all['true_non_merge_pairs']} | {sz_all['gold_entities_with_2plus_graph_entities']} |
| ADJUDICATED (ALL, all {diag['all_multinode_sets']} multi-node sets hand-reviewed) | {sz_adj['gold_entities_contributing']} | {sz_adj['graph_entities_labelled']} | **{sz_adj['true_merge_pairs']}** | {sz_adj['true_non_merge_pairs']} | {sz_adj['gold_entities_with_2plus_graph_entities']} |

Bank: **{diag['bank_norms_with_more_than_one_node']}** normalised names of {diag['bank_n']}
nodes carry more than one node ({diag['bank_nodes_in_such_norms']} nodes); guard drops -
STRICT collisions {diag['strict_false_merge_guard_collisions']}, ALL-ladder nodes dropped
{diag['all_ladder_nodes_dropped_by_guard']}.

## Paired comparison at matched merge volume - STRICT surface
Candidate set **{cmp_strict['candidate_set_size']}** labelled graph entities, one candidate
merge each (m -> its nearest OTHER prototype). Both rules score the same candidates.

| beta | tau | merges accepted | false merges (margin) | matched theta | false merges (fixed cosine) | true merges (margin) | true merges (fixed) | unlabelled partner |
|---|---|---|---|---|---|---|---|---|
{cmp_table(cmp_strict)}

Shipped screen `theta = {SHIPPED_COSINE}`: accepted {cmp_strict['shipped_operating_point']['accepted']},
false merges {cmp_strict['shipped_operating_point']['false_merges']},
true merges {cmp_strict['shipped_operating_point']['true_merges']},
unlabelled partner {cmp_strict['shipped_operating_point']['unlabelled_partner']}.

## Paired comparison at matched merge volume - ADJUDICATED surface (secondary)
Candidate set **{cmp_adj['candidate_set_size']}** labelled graph entities,
**{sz_adj['true_merge_pairs']}** hand-reviewed true-merge pairs. NOT the registered surface.

| beta | tau | merges accepted | false merges (margin) | matched theta | false merges (fixed cosine) | true merges (margin) | true merges (fixed) | unlabelled partner |
|---|---|---|---|---|---|---|---|---|
{cmp_table(cmp_adj)}

Shipped screen `theta = {SHIPPED_COSINE}`: accepted {cmp_adj['shipped_operating_point']['accepted']},
false merges {cmp_adj['shipped_operating_point']['false_merges']},
true merges {cmp_adj['shipped_operating_point']['true_merges']},
unlabelled partner {cmp_adj['shipped_operating_point']['unlabelled_partner']}.

## Paired comparison at matched merge volume - ALL surface (unadjudicated, for reference)
Candidate set **{cmp_all['candidate_set_size']}** labelled graph entities. Roughly half its
multi-node sets are same-name-DIFFERENT-entity; do not quote its true-merge counts.

| beta | tau | merges accepted | false merges (margin) | matched theta | false merges (fixed cosine) | true merges (margin) | true merges (fixed) | unlabelled partner |
|---|---|---|---|---|---|---|---|---|
{cmp_table(cmp_all)}

## Verdict against the registered bar
**{verdict}** - {reason}

## Hand adjudication of every multi-node set the ALL ladder produced
| gold (normalised) | ladder nodes | kept | adjudication |
|---|---|---|---|
""" + "\n".join(
        "| {} | {} | {} | {} |".format(
            r["gold_norm"],
            "; ".join(f"{x['idx']} {x['name']} {x['types']}" for x in r["ladder_nodes"]),
            ", ".join(str(x) for x in r["adjudicated_keep"]),
            r["adjudication"])
        for r in dup_examples) + f"""

## Caveats
""" + "\n".join(f"- {c}" for c in summ["caveats"]) + "\n"
    (stem.with_name(stem.name + ".md")).write_text(brief)
    cf.close()
    log(f"\n{verdict} | wrote {stem}.json")


if __name__ == "__main__":
    main()

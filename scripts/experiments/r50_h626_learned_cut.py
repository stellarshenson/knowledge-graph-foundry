"""R40x-H626 learned cut-point detector vs max-gap adaptive-k anchor seeder.

A small multi-task net, trained ONLY on synthetic score-curve families with
known-by-construction optimal cuts, selects per-query anchor counts k. It is
dropped in exactly where max-gap sits in the H623 reachability pipeline (same
candidate lists, same PPR replay, same reset_region_union region) - ONLY the
cut rule changes. Primary readout: full-127 PER-PROBE PAIRED reachability,
learned vs max-gap (control 0.8740). Real gold is NEVER in training; the only
calibration that touches real data is the flat-line head threshold on the H623
78-span cal split - the cut head (used in the 127-probe eval) is synthetic-only,
so the full-127 comparison is legitimate.

Substrate (candidate lists, adj/PPR, dense seeds, reach harness, sigma, cal/hold
split) is lifted verbatim from r50_h623_elbow_battery. READ-ONLY replay: no Neo4j,
no LLM, no network. Writes reports/experiments/r50/h626-learned-cut-<ts>.json.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "scripts/experiments")
import r47_h582_embedder_swap as H  # noqa: E402
import r50_h623_elbow_battery as B  # noqa: E402  (substrate: detectors, params, loaders)
from rapidfuzz import fuzz, process  # noqa: E402

# ---- torch (GPU idx 1 = RTX PRO 6000); pure-numpy fallback if broken ----
TORCH_OK = True
try:
    import torch
    import torch.nn as nn

    TORCH_OK = torch.cuda.is_available()
except Exception:
    TORCH_OK = False

# ---- reused substrate handles (byte-identical detector + params) ----
_norm01 = B._norm01
detect_maxgap = B.detect_maxgap
tok = B.tok
frac = B.frac
ROOT, CACHE = H.ROOT, H.CACHE
OUT = ROOT / "reports/experiments/r50"
SPAN_CACHE = B.SPAN_CACHE
H619_ART = B.H619_ART
TOP_K, PPR_TOP_N = H.TOP_K, H.PPR_TOP_N
CAND_FLOOR, CAND_CAP = B.CAND_FLOOR, B.CAND_CAP
K1, BB = B.K1, B.B
ALPHA, N_BOOT, SEED = B.ALPHA, B.N_BOOT, B.SEED

# ---- expected constants (sanity gate) ----
REF_MAXGAP_REACH = 0.8740
REF_FIXEDK1_REACH = 0.8661
REF_MAXGAP_CUTVAR = 6.6883
REF_SPLINE_CUTVAR = 12.7401  # cited from H623 artifact
ORACLE_CEIL = 0.898
# frontier point cited from registration (max-gap lambda=0.30)
REF_FRONTIER_REACH, REF_FRONTIER_ABSTAIN, REF_FRONTIER_CLEANREC = 0.8819, 0.033, 0.9924

# ---- learned-model seeds ----
SYN_SEED = 20240724
TORCH_SEED = 7
BOOT_SEED = 20260724
N_SYNTH = 40000


# ======================================================================
#  Substrate build (lifted verbatim from r50_h623_elbow_battery.main)
# ======================================================================
def build_substrate():
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    name_norms = [H._norm(m["name"]) if m["name"] else "" for m in meta]
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)

    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    out_deg = np.asarray(adj.sum(axis=1)).ravel()
    out_deg[out_deg == 0] = 1.0

    off_ids = [json.loads(l)["id"] for l in H.SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    Q = {q.get("_id"): q for q in json.loads(H.QUESTIONS.read_text())}
    probes = [Q[i] for i in off_ids if i in Q]
    graph_norms = set(name_norms)

    def gold_titles(q):
        sf = q.get("supporting_facts") or []
        ts = []
        for it in sf:
            t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
            if t and t not in ts:
                ts.append(t)
        return ts

    src_of, bridge_of, gold_idx_of = {}, {}, {}
    for q in probes:
        pid = q["_id"]
        evs = q.get("evidences") or []
        objs = {H._norm(o_) for (s_, r_, o_) in evs}
        srcs, brs, golds = [], [], []
        for t in gold_titles(q):
            tn = H._norm(t)
            ci = name_row.get(tn)
            if ci is None:
                continue
            golds.append(ci)
            if tn in objs:
                brs.append(ci)
            else:
                srcs.append(ci)
        src_of[pid], bridge_of[pid], gold_idx_of[pid] = srcs, brs, golds

    carriers = []
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in gold_titles(q):
            tn = H._norm(t)
            carriers.append({"probe": pid, "tnorm": tn,
                             "in_graph": tn in graph_norms, "carrier_idx": name_row.get(tn)})
    probe_has_carrier = {pid: [c["carrier_idx"] for c in carriers
                               if c["probe"] == pid and c["in_graph"]] for pid in off_ids}
    reach_pids = [pid for pid in off_ids if probe_has_carrier[pid]]

    titan = np.load(CACHE / "titan_emb.npy")
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    d = np.load(CACHE / "titan_probe_emb.npz", allow_pickle=True)
    seeds_q = {}
    for pid in off_ids:
        v = d[pid]
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = titan_n @ v
        order = np.argsort(-sims)
        seeds_q[pid] = [int(x) for x in order[:TOP_K]]

    # BM25 over entity names (Okapi, numpy)
    docs = [tok(nn) for nn in name_norms]
    df = Counter()
    for dd in docs:
        for t in set(dd):
            df[t] += 1
    Nd = len(docs)
    dl = np.array([len(x) for x in docs], dtype=float)
    avgdl = dl.mean()
    idf = {t: np.log(1 + (Nd - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    term_docs = defaultdict(list)
    for i, dd in enumerate(docs):
        for t, f in Counter(dd).items():
            term_docs[t].append((i, f))
    denom_base = K1 * (1 - BB + BB * dl / avgdl)
    bm25_cache = {}

    def bm25_term_vec(t):
        if t in bm25_cache:
            return bm25_cache[t]
        v = np.zeros(Nd)
        if t in idf:
            for i, f in term_docs[t]:
                v[i] = idf[t] * (f * (K1 + 1)) / (f + denom_base[i])
        bm25_cache[t] = v
        return v

    def bm25_score(qtoks):
        v = np.zeros(Nd)
        for t in set(qtoks):
            v += bm25_term_vec(t)
        return v

    names_arr = name_norms

    def candidate_list(span_norm):
        L = len(span_norm)
        fr = np.asarray(process.cdist([span_norm], names_arr, scorer=fuzz.ratio)[0]) / 100.0
        cont = np.zeros(Nd)
        if L >= 3:
            for i in range(Nd):
                nn = names_arr[i]
                if len(nn) >= 3 and (span_norm in nn or nn in span_norm):
                    cont[i] = min(len(nn), L) / max(len(nn), L)
        bm = bm25_score(tok(span_norm))
        bmn = bm / bm.max() if bm.max() > 0 else bm
        exact = np.zeros(Nd)
        if span_norm in name_row:
            exact[name_row[span_norm]] = 1.0
        blended = np.maximum.reduce([exact, cont, fr, bmn])
        idx = np.where(blended >= CAND_FLOOR)[0]
        if len(idx) == 0:
            idx = np.array([int(np.argmax(blended))])
        idx = idx[np.argsort(-blended[idx])][:CAND_CAP]
        return idx, blended[idx]

    spans_by_pid = json.loads(SPAN_CACHE.read_text())
    lexicon = set(json.loads(H619_ART.read_text())["stoplist_lexicon"])

    spanrecs = []
    for pid in off_ids:
        sp = spans_by_pid.get(pid, [])
        for text, gscore in sp:
            sn = H._norm(text)
            idx, blended = candidate_list(sn)
            norm_scores = _norm01(blended)
            golds = set(gold_idx_of[pid])
            gold_targets = [int(i) for i in idx.tolist() if int(i) in golds]
            exact_idx = name_row.get(sn)
            n_exact = int(sn in name_row)
            is_role = sn in lexicon
            if is_role or len(gold_targets) == 0:
                subset, ideal = "tie", "abstain"
            elif (len(gold_targets) == 1 and exact_idx is not None
                  and exact_idx in gold_targets and n_exact == 1
                  and int(idx[0]) == exact_idx):
                subset, ideal = "clean", "keep_gold"
            else:
                subset, ideal = "tie", "keep_gold"
            spanrecs.append({
                "pid": pid, "span": text, "span_norm": sn,
                "cand_idx": idx.tolist(), "raw_scores": blended.tolist(),
                "norm_scores": norm_scores.tolist(),
                "gold_targets": gold_targets, "is_role": is_role,
                "subset": subset, "ideal": ideal, "exact_idx": exact_idx,
            })

    # sigma for stability (residual dispersion) - identical to H623
    resid = []
    for r in spanrecs:
        for gt in r["gold_targets"]:
            if gt in r["cand_idx"]:
                pos = r["cand_idx"].index(gt)
                resid.append(1.0 - r["raw_scores"][pos])
    sigma = float(np.std(resid)) if resid else 0.05

    return dict(n=n, adj=adj, out_deg=out_deg, reach_pids=reach_pids,
                probe_has_carrier=probe_has_carrier, bridge_of=bridge_of,
                seeds_q=seeds_q, spanrecs=spanrecs, sigma=sigma)


# ======================================================================
#  Synthetic training-curve generator (known-by-construction cuts)
# ======================================================================
FAMILIES = ["sharp_elbow", "double_elbow", "flat", "noisy_decay", "heavy_tie_top"]


def sample_length(rng):
    m = int(round(1 + rng.gamma(2.2, 3.0)))
    return max(1, min(15, m))


def gen_curve(rng):
    """Return (raw_desc_values, optimal_k, is_flat, family). raw in [0,1] descending."""
    fam = FAMILIES[rng.integers(len(FAMILIES))]
    m = sample_length(rng)
    noise = float(rng.uniform(0.02, 0.18))  # brackets real sigma 0.0892
    if fam == "sharp_elbow":
        k = int(rng.integers(1, min(3, m) + 1))
        top = rng.uniform(0.80, 1.0, size=k)
        tail = rng.uniform(0.0, 0.45, size=max(0, m - k))
        raw = np.concatenate([top, tail]); is_flat = 0
    elif fam == "double_elbow":
        if m < 3:
            k = 1; raw = rng.uniform(0.7, 1.0, size=m)
        else:
            k = int(rng.integers(1, min(3, m - 1) + 1))
            g2 = int(rng.integers(1, max(1, m - k - 1) + 1)) if m - k >= 2 else 1
            top = rng.uniform(0.85, 1.0, size=k)
            mid = rng.uniform(0.45, 0.62, size=min(g2, m - k))
            rest = max(0, m - k - len(mid))
            tail = rng.uniform(0.0, 0.28, size=rest)
            raw = np.concatenate([top, mid, tail])
        is_flat = 0
    elif fam == "flat":
        base = float(rng.uniform(0.30, 0.92))
        raw = base + rng.normal(0, 0.02, size=m)
        k = 1; is_flat = 1
    elif fam == "noisy_decay":
        x = np.linspace(0, 1, m)
        rate = float(rng.uniform(0.6, 1.6))
        raw = np.exp(-rate * x) * float(rng.uniform(0.7, 1.0))
        k = 1; is_flat = 0
    else:  # heavy_tie_top
        t = int(rng.integers(2, min(4, m) + 1)) if m >= 2 else 1
        top = np.full(t, float(rng.uniform(0.82, 0.98))) + rng.normal(0, 0.01, size=t)
        tail = rng.uniform(0.0, 0.4, size=max(0, m - t))
        raw = np.concatenate([top, tail]); k = t; is_flat = 0
    raw = raw + rng.normal(0, noise, size=len(raw))
    raw = np.clip(raw, 0.0, 1.0)
    raw = np.sort(raw)[::-1]              # candidate-list invariant: descending
    k = max(1, min(k, len(raw)))
    return raw.astype(np.float32), k, is_flat, fam


def featurize(norm_scores):
    ns = np.asarray(norm_scores, dtype=np.float32)
    m = len(ns)
    padded = np.zeros(16, dtype=np.float32)
    padded[:min(16, m)] = ns[:16]
    top_gap = float(ns[0] - ns[1]) if m >= 2 else 1.0
    feat = np.array([m / 16.0, top_gap, float(ns.mean()), float(ns.std())], dtype=np.float32)
    return np.concatenate([padded, feat]), m


def build_synth(rng):
    X, cut_lab, flat_lab, lens, fam_count = [], [], [], [], Counter()
    for _ in range(N_SYNTH):
        raw, k, is_flat, fam = gen_curve(rng)
        ns = _norm01(raw)                # pipeline min-max normalization
        x, m = featurize(ns)
        X.append(x); cut_lab.append(k - 1); flat_lab.append(float(is_flat)); lens.append(m)
        fam_count[fam] += 1
    return (np.stack(X), np.array(cut_lab, dtype=np.int64),
            np.array(flat_lab, dtype=np.float32), np.array(lens, dtype=np.int64), fam_count)


# ======================================================================
#  Detector (torch multi-task net; pure-numpy MLP fallback)
# ======================================================================
def length_mask(lens_np):
    m = np.full((len(lens_np), 16), -1e9, dtype=np.float32)
    for i, L in enumerate(lens_np):
        m[i, :min(16, L)] = 0.0
    return m


class _TorchNet:
    def __init__(self):
        self.dev = torch.device("cuda:0")
        torch.manual_seed(TORCH_SEED)
        self.net = nn.Sequential(nn.Linear(20, 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU()).to(self.dev)
        self.cut = nn.Linear(64, 16).to(self.dev)
        self.flat = nn.Linear(64, 1).to(self.dev)

    def train(self, X, cut_lab, flat_lab, lens):
        mask = length_mask(lens)
        Xt = torch.tensor(X, device=self.dev)
        yc = torch.tensor(cut_lab, device=self.dev)
        yf = torch.tensor(flat_lab, device=self.dev)
        Mt = torch.tensor(mask, device=self.dev)
        params = list(self.net.parameters()) + list(self.cut.parameters()) + list(self.flat.parameters())
        opt = torch.optim.Adam(params, lr=1e-3)
        ce = nn.CrossEntropyLoss(); bce = nn.BCEWithLogitsLoss()
        N = len(X); bs = 512
        g = torch.Generator(device="cpu"); g.manual_seed(TORCH_SEED)
        last = 0.0
        for ep in range(60):
            perm = torch.randperm(N, generator=g)
            tot = 0.0
            for s in range(0, N, bs):
                bi = perm[s:s + bs]
                h = self.net(Xt[bi])
                lc = self.cut(h) + Mt[bi]
                lf = self.flat(h).squeeze(-1)
                loss = ce(lc, yc[bi]) + bce(lf, yf[bi])
                opt.zero_grad(); loss.backward(); opt.step()
                tot += float(loss) * len(bi)
            last = tot / N
        return last

    @torch.no_grad()
    def predict_k(self, norm_scores):
        x, m = featurize(norm_scores)
        xt = torch.tensor(x[None, :], device=self.dev)
        h = self.net(xt)
        logits = self.cut(h)[0].cpu().numpy()
        logits[m:] = -1e9
        return int(np.argmax(logits)) + 1

    @torch.no_grad()
    def flat_score(self, norm_scores):
        x, _ = featurize(norm_scores)
        xt = torch.tensor(x[None, :], device=self.dev)
        h = self.net(xt)
        return float(torch.sigmoid(self.flat(h)[0, 0]).cpu())


class _NumpyNet:
    """Tiny 2-layer MLP + two heads, manual SGD. Fallback when torch/CUDA broken."""
    def __init__(self):
        rng = np.random.default_rng(TORCH_SEED)
        self.W1 = rng.normal(0, 0.2, (20, 64)); self.b1 = np.zeros(64)
        self.W2 = rng.normal(0, 0.2, (64, 64)); self.b2 = np.zeros(64)
        self.Wc = rng.normal(0, 0.2, (64, 16)); self.bc = np.zeros(16)
        self.Wf = rng.normal(0, 0.2, (64, 1)); self.bf = np.zeros(1)

    def _fwd(self, X):
        z1 = X @ self.W1 + self.b1; a1 = np.maximum(z1, 0)
        z2 = a1 @ self.W2 + self.b2; a2 = np.maximum(z2, 0)
        return a1, a2, a2 @ self.Wc + self.bc, a2 @ self.Wf + self.bf

    def train(self, X, cut_lab, flat_lab, lens):
        mask = length_mask(lens); N = len(X); bs = 512; lr = 0.05
        rng = np.random.default_rng(TORCH_SEED + 1); last = 0.0
        for ep in range(60):
            perm = rng.permutation(N); tot = 0.0
            for s in range(0, N, bs):
                bi = perm[s:s + bs]
                Xb, cb, fb, mb = X[bi], cut_lab[bi], flat_lab[bi], mask[bi]
                a1, a2, lc, lf = self._fwd(Xb)
                lc = lc + mb
                lc -= lc.max(1, keepdims=True); ex = np.exp(lc); sm = ex / ex.sum(1, keepdims=True)
                pf = 1 / (1 + np.exp(-lf[:, 0]))
                B_ = len(bi)
                onehot = np.zeros_like(sm); onehot[np.arange(B_), cb] = 1
                dlc = (sm - onehot) / B_
                dlf = ((pf - fb) / B_)[:, None]
                tot += float(-np.log(sm[np.arange(B_), cb] + 1e-9).mean())
                dWc = a2.T @ dlc; dbc = dlc.sum(0)
                dWf = a2.T @ dlf; dbf = dlf.sum(0)
                da2 = dlc @ self.Wc.T + dlf @ self.Wf.T
                da2[a2 <= 0] = 0
                dW2 = a1.T @ da2; db2 = da2.sum(0)
                da1 = da2 @ self.W2.T; da1[a1 <= 0] = 0
                dW1 = Xb.T @ da1; db1 = da1.sum(0)
                for P, G in ((self.Wc, dWc), (self.bc, dbc), (self.Wf, dWf), (self.bf, dbf),
                             (self.W2, dW2), (self.b2, db2), (self.W1, dW1), (self.b1, db1)):
                    P -= lr * G
            last = tot
        return last

    def predict_k(self, norm_scores):
        x, m = featurize(norm_scores)
        _, _, lc, _ = self._fwd(x[None, :]); lc = lc[0]; lc[m:] = -1e9
        return int(np.argmax(lc)) + 1

    def flat_score(self, norm_scores):
        x, _ = featurize(norm_scores)
        _, _, _, lf = self._fwd(x[None, :])
        return float(1 / (1 + np.exp(-lf[0, 0])))


# ======================================================================
def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return None
    u = sum((sp > sn) + 0.5 * (sp == sn) for sp in pos for sn in neg)
    return round(u / (len(pos) * len(neg)), 4)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"[{run_id}] building substrate ...", flush=True)
    S = build_substrate()
    n, adj, out_deg = S["n"], S["adj"], S["out_deg"]
    reach_pids, probe_has_carrier, bridge_of = S["reach_pids"], S["probe_has_carrier"], S["bridge_of"]
    seeds_q, spanrecs, sigma = S["seeds_q"], S["spanrecs"], S["sigma"]
    n_spans = len(spanrecs)
    gold_spans = [r for r in spanrecs if r["gold_targets"]]
    print(f"spans={n_spans} gold_spans={len(gold_spans)} reach_pids={len(reach_pids)} sigma={sigma:.4f}", flush=True)

    # ---------- reach harness (returns per-probe boolean vector) ----------
    def region(r, seeds):
        return set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(seeds)

    def probe_anchors(keep_fn):
        pa = defaultdict(set)
        for r in spanrecs:
            for k in keep_fn(r):
                pa[r["pid"]].add(r["cand_idx"][k])
        return pa

    def reach_vec(pa):
        vec = []
        for pid in reach_pids:
            la = list(pa.get(pid, set()))
            dense = seeds_q[pid]
            seeds = la if la else dense
            r = H.ppr(adj, out_deg, seeds, n)
            reg = region(r, seeds) | set(dense)      # reset_region_union
            cis = probe_has_carrier[pid]
            vec.append(bool(cis) and all(t in reg for t in cis))
        return vec

    def reach_all(vec):
        return round(sum(vec) / len(vec), 4)

    # ---- cut rules ----
    def keep_maxgap(r):
        ck, st = detect_maxgap(r["norm_scores"])   # lambda=0.0 -> never abstains
        return list(range(ck))

    def keep_maxgap_lam(lam):
        def f(r):
            ck, st = detect_maxgap(r["norm_scores"])
            return list(range(ck)) if st >= lam else []
        return f

    def keep_fixed_k1(r):
        return list(range(min(1, len(r["cand_idx"]))))

    # ---------- SANITY GATE ----------
    mg_pa = probe_anchors(keep_maxgap)
    mg_vec = reach_vec(mg_pa)
    mg_reach = reach_all(mg_vec)
    fk1_vec = reach_vec(probe_anchors(keep_fixed_k1))
    fk1_reach = reach_all(fk1_vec)

    # max-gap bootstrap cut-index variance: reproduce H623 rng consumption exactly
    rng = np.random.default_rng(SEED)
    gs_ids = list(range(len(gold_spans)))
    rng.shuffle(gs_ids)                       # H623 cal/hold shuffle (consumes rng first)
    half = len(gs_ids) // 2
    cal_spans = [gold_spans[i] for i in gs_ids[:half]]
    hold_spans = [gold_spans[i] for i in gs_ids[half:]]
    mg_cutvars = []
    for r in spanrecs:                        # maxgap = first detector in H623 stability loop
        cuts = []
        for _ in range(N_BOOT):
            pert = np.asarray(r["raw_scores"]) + rng.normal(0, sigma, size=len(r["raw_scores"]))
            ns = _norm01(pert)
            ck, st = detect_maxgap(ns)
            cuts.append(ck)                   # lam=0.0 -> keep always non-empty
        mg_cutvars.append(float(np.var(cuts)))
    mg_cutvar = round(float(np.mean(mg_cutvars)), 4)

    sanity = {
        "maxgap_reach_all": {"measured": mg_reach, "expected": REF_MAXGAP_REACH,
                             "ok": abs(mg_reach - REF_MAXGAP_REACH) <= 5e-4},
        "fixed_k1_reach_all": {"measured": fk1_reach, "expected": REF_FIXEDK1_REACH,
                               "ok": abs(fk1_reach - REF_FIXEDK1_REACH) <= 5e-4},
        "maxgap_bootstrap_cut_index_variance": {"measured": mg_cutvar, "expected": REF_MAXGAP_CUTVAR,
                                                "ok": abs(mg_cutvar - REF_MAXGAP_CUTVAR) <= 5e-3},
    }
    sanity_pass = all(v["ok"] for v in sanity.values())
    print("SANITY:", json.dumps(sanity), "PASS" if sanity_pass else "FAIL", flush=True)
    if not sanity_pass:
        art = {"run_id": run_id, "hypothesis": "R40x-H626", "sanity": sanity,
               "sanity_pass": False, "aborted": True,
               "note": "sanity gate mismatch - substrate does not reproduce H623 constants; that is the finding.",
               "script": "scripts/experiments/r50_h626_learned_cut.py"}
        p = OUT / f"h626-learned-cut-{run_id}.json"
        p.write_text(json.dumps(art, indent=1, default=float))
        print(f"ABORT wrote {p}", flush=True)
        return

    # ---------- TRAIN synthetic detector ----------
    print("training learned detector (synthetic-only) ...", flush=True)
    syn_rng = np.random.default_rng(SYN_SEED)
    X, cut_lab, flat_lab, lens, fam_count = build_synth(syn_rng)
    net = _TorchNet() if TORCH_OK else _NumpyNet()
    final_loss = net.train(X, cut_lab, flat_lab, lens)
    backend = "torch/cuda:1(PCI_BUS_ID)" if TORCH_OK else "numpy-MLP"
    print(f"trained ({backend}) final_loss={final_loss:.4f} families={dict(fam_count)}", flush=True)

    def keep_learned(r):
        k = net.predict_k(r["norm_scores"])
        return list(range(min(k, len(r["cand_idx"]))))

    # ---------- PRIMARY: full-127 paired learned vs max-gap ----------
    learned_pa = probe_anchors(keep_learned)
    learned_vec = reach_vec(learned_pa)
    learned_reach = reach_all(learned_vec)
    b = sum(1 for lw, mw in zip(learned_vec, mg_vec) if lw and not mw)   # learned-only wins
    c = sum(1 for lw, mw in zip(learned_vec, mg_vec) if mw and not lw)   # maxgap-only wins
    net_probes = b - c
    disc_learned_only = [reach_pids[i] for i in range(len(reach_pids)) if learned_vec[i] and not mg_vec[i]]
    disc_maxgap_only = [reach_pids[i] for i in range(len(reach_pids)) if mg_vec[i] and not learned_vec[i]]
    total_anchors_learned = sum(len(v) for v in learned_pa.values())
    total_anchors_maxgap = sum(len(v) for v in mg_pa.values())

    primary = {
        "n_probes": len(reach_pids),
        "reach_all_learned": learned_reach,
        "reach_all_maxgap": mg_reach,
        "discordant_b_learned_only": b, "discordant_c_maxgap_only": c,
        "net_probes": net_probes,
        "discordant_learned_only_pids": disc_learned_only,
        "discordant_maxgap_only_pids": disc_maxgap_only,
        "total_anchors_learned": total_anchors_learned,
        "total_anchors_maxgap": total_anchors_maxgap,
        "legitimacy": "cut head trained on synthetic curves only; calibration touched only the 78-span "
                      "cal split (flat-line head, datum). Full-127 comparison is legitimate.",
    }
    print("PRIMARY:", json.dumps(primary), flush=True)

    # ---------- SECONDARY (labelled separately) ----------
    # vs fixed_k1
    b1 = sum(1 for lw, fw in zip(learned_vec, fk1_vec) if lw and not fw)
    c1 = sum(1 for lw, fw in zip(learned_vec, fk1_vec) if fw and not lw)
    vs_fixed_k1 = {"reach_all_learned": learned_reach, "reach_all_fixed_k1": fk1_reach,
                   "discordant_b_learned_only": b1, "discordant_c_fixed_k1_only": c1, "net_probes": b1 - c1}

    # vs max-gap lambda=0.30 frontier (computed on substrate + cited registration point)
    fr_pa = probe_anchors(keep_maxgap_lam(0.30))
    fr_vec = reach_vec(fr_pa)
    fr_reach = reach_all(fr_vec)
    n_abstain_030 = sum(1 for r in spanrecs if detect_maxgap(r["norm_scores"])[1] < 0.30)
    bfr = sum(1 for lw, fw in zip(learned_vec, fr_vec) if lw and not fw)
    cfr = sum(1 for lw, fw in zip(learned_vec, fr_vec) if fw and not lw)
    vs_frontier = {"reach_all_learned": learned_reach,
                   "reach_all_maxgap_lam0.30_computed": fr_reach,
                   "n_spans_abstained_lam0.30": n_abstain_030,
                   "discordant_b_learned_only": bfr, "discordant_c_frontier_only": cfr,
                   "net_probes": bfr - cfr,
                   "registration_frontier_ref": {"reach_all": REF_FRONTIER_REACH,
                                                 "tie_abstention": REF_FRONTIER_ABSTAIN,
                                                 "clean_recall": REF_FRONTIER_CLEANREC}}

    # hold-split-only cut-quality view (span-level precision/recall of the pick, learned vs maxgap vs fixed_k1)
    def score_arm(keep_fn, span_set):
        tp = fp = gp = gk = 0
        for r in span_set:
            kept = {r["cand_idx"][k] for k in keep_fn(r)}
            golds = set(r["gold_targets"])
            tp += len(kept & golds); fp += len(kept - golds)
            gp += len(golds); gk += len(kept & golds)
        return {"precision": frac(tp, tp + fp), "recall": frac(gk, gp),
                "tp": tp, "fp": fp, "gold_present": gp, "gold_kept": gk, "n_spans": len(span_set)}

    hold_view = {
        "n_hold_gold_spans": len(hold_spans),
        "learned": score_arm(keep_learned, hold_spans),
        "maxgap": score_arm(keep_maxgap, hold_spans),
        "fixed_k1": score_arm(keep_fixed_k1, hold_spans),
    }

    # ---------- STABILITY: learned bootstrap cut-index variance ----------
    brng = np.random.default_rng(BOOT_SEED)
    learned_cutvars = []
    for r in spanrecs:
        cuts = []
        for _ in range(N_BOOT):
            pert = np.asarray(r["raw_scores"]) + brng.normal(0, sigma, size=len(r["raw_scores"]))
            ns = _norm01(pert)
            cuts.append(net.predict_k(ns))
        learned_cutvars.append(float(np.var(cuts)))
    learned_cutvar = round(float(np.mean(learned_cutvars)), 4)
    stability = {"learned_mean_cut_index_variance": learned_cutvar,
                 "learned_median_cut_index_variance": round(float(np.median(learned_cutvars)), 4),
                 "maxgap_mean_cut_index_variance": mg_cutvar,
                 "spline_mean_cut_index_variance_h623ref": REF_SPLINE_CUTVAR,
                 "sigma": round(sigma, 4), "n_boot": N_BOOT, "boot_seed": BOOT_SEED}
    print("STABILITY:", json.dumps(stability), flush=True)

    # ---------- flat-line head AUC datum (role/ambiguous vs clean) ----------
    amb = [r for r in spanrecs if r["ideal"] == "abstain"]
    clean = [r for r in spanrecs if r["subset"] == "clean"]
    fl_scores = [net.flat_score(r["norm_scores"]) for r in amb] + [net.flat_score(r["norm_scores"]) for r in clean]
    fl_labels = [1] * len(amb) + [0] * len(clean)
    flat_auc = auc(fl_scores, fl_labels)
    # cal-split-calibrated flat threshold (datum-only; cal = 78 gold spans, all non-abstain)
    cal_flat = sorted(net.flat_score(r["norm_scores"]) for r in cal_spans)
    q = cal_flat[min(len(cal_flat) - 1, int(np.ceil((1 - ALPHA) * len(cal_flat))) - 1)] if cal_flat else 0.5
    t_star = float(q)
    fires_clean = sum(1 for r in clean if net.flat_score(r["norm_scores"]) >= t_star)
    fires_amb = sum(1 for r in amb if net.flat_score(r["norm_scores"]) >= t_star)
    flat_datum = {
        "flat_head_auc_role_vs_clean": flat_auc,
        "h623_ref_auc": {"spline": 0.849, "maxgap": 0.755},
        "n_ambiguous": len(amb), "n_clean": len(clean),
        "cal_calibrated_threshold": round(t_star, 4),
        "flat_fires_on_ambiguous_at_tstar": fires_amb,
        "flat_fires_on_clean_at_tstar": fires_clean,
        "note": "DATUM ONLY - no abstention claim (H624 alpha=0.10 wall stands). threshold cal on 78-span cal split.",
    }
    print("FLAT_DATUM:", json.dumps(flat_datum), flush=True)

    # ---------- VERDICT ----------
    unoffset_regression = c > b and c > 0   # learned loses net probes
    if net_probes >= 2 and c == 0 and learned_reach >= 0.889:
        verdict = "CONFIRMED"
        why = f"net +{net_probes} probes vs max-gap (b={b}, c={c}), zero regressions, reach {learned_reach} >= ~0.890"
    elif net_probes >= 2 and learned_reach >= 0.889:
        verdict = "CONFIRMED (with offset regressions)"
        why = f"net +{net_probes} probes (b={b}, c={c}) and reach {learned_reach}; regressions present but offset"
    elif net_probes < 0:
        verdict = "KILLED"
        why = f"net {net_probes} probes vs max-gap (b={b}, c={c}) - learned cut regresses reachability"
    else:  # net_probes in {0, +1}
        verdict = "INDETERMINATE-AT-CEILING"
        why = (f"net {net_probes:+d} probes vs max-gap (b={b}, c={c}) - honestly-expected tie; "
               f"learned cut retires at-ceiling (control 0.874, oracle {ORACLE_CEIL})")
    if learned_reach > ORACLE_CEIL:
        verdict = "HARNESS-BUG-SUSPECT"
        why = f"learned reach {learned_reach} exceeds oracle ceiling {ORACLE_CEIL} - investigate before reporting"
    print(f"VERDICT: {verdict} :: {why}", flush=True)

    art = {
        "run_id": run_id, "hypothesis": "R40x-H626",
        "title": "learned cut-point detector (synthetic-trained) vs max-gap adaptive-k anchor seeder",
        "scoring_fence": "reset_region_union reachability, full-127 per-probe paired; dense@16 adaptive-k axis OUT OF SCOPE",
        "backend": backend,
        "seeds": {"substrate_seed": SEED, "synth_seed": SYN_SEED, "torch_seed": TORCH_SEED,
                  "boot_seed": BOOT_SEED, "n_synth": N_SYNTH},
        "sanity": sanity, "sanity_pass": True,
        "training": {"families": FAMILIES, "family_counts": dict(fam_count),
                     "n_curves": N_SYNTH, "curve_length_range": [1, 15],
                     "noise_range": [0.02, 0.18], "real_sigma": round(sigma, 4),
                     "net": "MLP 20->64->64 + cut head(16 keep-counts, length-masked) + flat head(1); "
                            "multi-task CE(cut)+BCE(flat); Adam 1e-3, 60 epochs, bs512",
                     "input": "per-query min-max normalized score curve padded to 16 + [len/16, top_gap, mean, std]",
                     "final_train_loss": round(float(final_loss), 4)},
        "primary": primary,
        "secondary": {"vs_fixed_k1": vs_fixed_k1, "vs_maxgap_lambda0.30_frontier": vs_frontier,
                      "hold_split_only_cut_quality": hold_view, "stability": stability,
                      "flat_line_datum": flat_datum},
        "bars": {
            "CONFIRMED": "net >= +2 probes (b-c>=2), zero unoffset regressions, reach >= ~0.890",
            "KILLED": "net <= 0... (net < 0 here); exact tie treated as INDETERMINATE per registration",
            "INDETERMINATE-AT-CEILING": "net +1 or exact tie (honestly-expected)",
            "oracle_ceiling": ORACLE_CEIL},
        "proposed_verdict": verdict, "verdict_reason": why,
        "artifact": str(OUT / f"h626-learned-cut-{run_id}.json"),
        "script": "scripts/experiments/r50_h626_learned_cut.py",
    }
    p = OUT / f"h626-learned-cut-{run_id}.json"
    p.write_text(json.dumps(art, indent=1, default=float))
    print(f"WROTE {p} verdict={verdict}", flush=True)


if __name__ == "__main__":
    main()

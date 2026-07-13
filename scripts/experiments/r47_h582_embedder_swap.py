"""R47-H582: stronger retrieval embedder over the SAME medium graph - dump re-embed replay.

Pure offline, READ-ONLY on Neo4j (one MATCH/RETURN pull, cached to disk; no graph
writes, no containers). Swaps ONLY the vector space: re-embeds the 6,626 entity texts
(engine convention "type: name - description[:200]", embeddings.py:48) and the 132
frozen off-arm probes with candidate embedders, replays dense@16 seed landing and
region-hit over the FIXED adjacency, and pairs every metric per-carrier vs the Titan
incumbent (H541 mandate).

Metrics per arm (all in numpy):
  (i)   carrier recall@16   - H501 name-set convention: _norm(gold title) in the
        _norm names of the dense top-16 seeds. Denominator = all 326 carriers
        (out-of-graph carriers are constant misses, exactly as H501).
  (ii)  region-hit@seeds+1hop - carrier entity idx in seeds u 1-hop(seeds) over the
        undirected Entity adjacency (type(r)<>'SIMILAR_TO', no valid_to - absent here).
  (iii) region-hit@PPR      - carrier idx in top-ppr_top_n(PPR(seeds)) u seeds
        (H515/h573 scipy PPR: damping 0.85, 50 iters).

Baseline arm = STORED Titan vectors (from the graph) + Titan probe embeddings via the
r47/r48 Bedrock path; must reproduce H501's 0.5982 carrier recall as a harness gate.

Carried arms (best candidate + Titan): H40 answer-form (gpt-oss-120b declarative draft
embedded instead of the question); H41 split name/description two-channel union
(top-8 name-channel + top-8 desc-channel vs mixed top-16 at budget 16).

Usage:
  python scripts/experiments/r47_h582_embedder_swap.py                 # orchestrate
  python scripts/experiments/r47_h582_embedder_swap.py worker <model> <in.json> <out.npy> <device>
Writes: reports/experiments/r47/h582-embedder-swap-<UTC ts>.json
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r47"
SCREEN = ROOT / "reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl"
QUESTIONS = ROOT / "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
CONFIG = ROOT / "config/experiments/config-bench-medium.yml"
H501_RECALL = 0.5982

TOP_K = 16
PPR_TOP_N = 15
DAMPING = 0.85
ITERS = 50
DEVICE = "2"  # RTX 5000 Ada sm_89 (avoid card 1 = vLLM 96GB, card 0 = Blackwell gte-assert)
GPT_OSS = "http://localhost:8010/v1"

CANDIDATES = [
    # (arm_name, hf_model, entity_prefix, probe_prefix, extra_worker_flags)
    ("bge-m3", "BAAI/bge-m3", "", "", {}),
    ("e5-large-v2", "intfloat/e5-large-v2", "passage: ", "query: ", {}),
    ("gte-large-en-v1.5", "Alibaba-NLP/gte-large-en-v1.5", "", "", {"trust_remote_code": True, "eager": True}),
]


# ---------------------------------------------------------------- worker mode
def worker(model_name: str, in_json: str, out_npy: str, device: str) -> None:
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = device
    import torch
    from sentence_transformers import SentenceTransformer

    spec = json.loads(Path(in_json).read_text())
    texts = spec["texts"]
    model_kwargs = {"torch_dtype": torch.bfloat16}
    config_kwargs = {}
    st_kwargs = {}
    if spec.get("trust_remote_code"):
        st_kwargs["trust_remote_code"] = True
    if spec.get("eager"):
        model_kwargs["attn_implementation"] = "eager"
        config_kwargs = {"unpad_inputs": False, "use_memory_efficient_attention": False}
    model = SentenceTransformer(
        model_name, device="cuda", model_kwargs=model_kwargs,
        config_kwargs=config_kwargs or None, **st_kwargs,
    )
    t0 = time.time()
    emb = model.encode(
        texts, batch_size=128, normalize_embeddings=True,
        show_progress_bar=True, convert_to_numpy=True,
    )
    np.save(out_npy, emb.astype(np.float32))
    print(f"WORKER {model_name} -> {out_npy} shape={emb.shape} in {round(time.time()-t0,1)}s", flush=True)


# ------------------------------------------------------------- shared helpers
def _norm(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", s.casefold())


def build_probe_text(question: str) -> str:
    """Replicate H501: Entity.create(q[:80], types=['Query'], description=q) -> _entity_text."""
    return f"Query: {question[:80]} - {question[:200]}"


def build_entity_text(types, name, descr) -> str:
    """Replicate embeddings.py:_entity_text = '{type}: {name} - {description[:200]}'."""
    t = types[0] if types else "Entity"
    return f"{t}: {name} - {(descr or '')[:200]}"


def ppr(adj, out_deg, seed_idx, n):
    if not seed_idx:
        return np.zeros(n)
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (adj.T @ (r / out_deg))
    return r


def mcnemar(titan_hits, cand_hits):
    """Exact two-sided McNemar on paired binaries. Returns (b, c, p)."""
    from scipy.stats import binomtest
    b = sum(1 for t, c in zip(titan_hits, cand_hits) if t and not c)  # titan-only
    c = sum(1 for t, k in zip(titan_hits, cand_hits) if not t and k)  # cand-only
    if b + c == 0:
        return b, c, 1.0
    p = binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue
    return b, c, round(float(p), 5)


def boot_ci(titan_hits, cand_hits, iters=5000, seed=0):
    """Paired bootstrap 95% CI on mean(cand) - mean(titan)."""
    rng = np.random.default_rng(seed)
    t = np.array(titan_hits, dtype=float)
    c = np.array(cand_hits, dtype=float)
    n = len(t)
    deltas = np.empty(iters)
    for i in range(iters):
        idx = rng.integers(0, n, n)
        deltas[i] = c[idx].mean() - t[idx].mean()
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


# ------------------------------------------------------ metrics for one arm
def arm_metrics(ent_emb, probe_emb, carriers, name_norms_by_idx, name_row,
                adj, out_deg, n, one_hop_fn):
    """Return per-carrier binary rows for the three metrics given an arm's
    entity matrix (normalized) and probe matrix (normalized, aligned to probe_ids)."""
    # per-probe seed sets (top-16 entity indices) + seed norm-name sets
    probe_ids = list(probe_emb.keys())
    seeds_idx = {}
    seeds_norm = {}
    region_1hop = {}
    region_ppr = {}
    for pid in probe_ids:
        qv = probe_emb[pid]
        sims = ent_emb @ qv
        sd = np.argpartition(-sims, TOP_K)[:TOP_K]
        sd = sd[np.argsort(-sims[sd])]
        sd = [int(x) for x in sd]
        seeds_idx[pid] = set(sd)
        seeds_norm[pid] = {name_norms_by_idx[i] for i in sd}
        region_1hop[pid] = one_hop_fn(sd)
        r = ppr(adj, out_deg, sd, n)
        region_ppr[pid] = set(np.argsort(-r)[:PPR_TOP_N].tolist()) | seeds_idx[pid]

    rec, r1, rp = [], [], []
    for c in carriers:
        pid = c["probe"]
        tn = c["tnorm"]
        cidx = c["carrier_idx"]
        rec.append(1 if tn in seeds_norm[pid] else 0)
        r1.append(1 if (cidx is not None and cidx in region_1hop[pid]) else 0)
        rp.append(1 if (cidx is not None and cidx in region_ppr[pid]) else 0)
    return rec, r1, rp


def summarize_arm(name, rec, r1, rp, in_graph_mask):
    ig = np.array(in_graph_mask, dtype=bool)
    def m(v):
        return round(float(np.mean(v)), 4)
    def mig(v):
        va = np.array(v)[ig]
        return round(float(np.mean(va)), 4) if len(va) else None
    return {
        "arm": name,
        "carrier_recall@16": m(rec),
        "region_hit_1hop": m(r1),
        "region_hit_ppr": m(rp),
        "region_hit_1hop_ingraph": mig(r1),
        "region_hit_ppr_ingraph": mig(rp),
    }


# ------------------------------------------------------------- orchestrate
def spawn_worker(model, texts, out_npy, extra):
    in_json = CACHE / (Path(out_npy).stem + "_in.json")
    payload = {"texts": texts, **extra}
    in_json.write_text(json.dumps(payload))
    cmd = [sys.executable, str(ROOT / "scripts/experiments/r47_h582_embedder_swap.py"),
           "worker", model, str(in_json), str(out_npy), DEVICE]
    log = ROOT / "logs/r47-h582.log"
    with log.open("a") as lf:
        lf.write(f"\n=== worker {model} -> {out_npy} @ {datetime.now(timezone.utc).isoformat()} ===\n")
        lf.flush()
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
    return r.returncode == 0 and Path(out_npy).exists()


def draft_answer_forms(probe_ids, questions_by_id):
    """H40: one hypothetical declarative answer sentence per probe via gpt-oss-120b
    (temp 0, short). The model NEVER sees the gold answer - it hallucinates a plausible
    declarative form; that surrogate is embedded instead of the interrogative."""
    import urllib.request
    drafts = {}
    for pid in probe_ids:
        q = questions_by_id[pid]["question"]
        prompt = (
            "Rewrite the question as a single short declarative sentence that states a "
            "plausible answer in the form an encyclopedia would use. Output only the "
            "sentence, no preamble.\n\nQuestion: " + q
        )
        body = json.dumps({
            "model": "gpt-oss-120b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0, "max_tokens": 512,  # gpt-oss reasons before content; 64 truncates
        }).encode()
        req = urllib.request.Request(GPT_OSS + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out = json.loads(resp.read())
            msg = out["choices"][0]["message"]
            content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            drafts[pid] = content if content else q
        except Exception as exc:
            print(f"H40 draft failed {pid}: {exc}", flush=True)
            drafts[pid] = q  # fall back to the question
    return drafts


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    # ---- load cache ----
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    titan = np.load(CACHE / "titan_emb.npy")
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    names = [m["name"] for m in meta]
    name_norms_by_idx = [_norm(nm) if nm else "" for nm in names]
    graph_norms = set(name_norms_by_idx)
    name_row = {}
    for i, nn in enumerate(name_norms_by_idx):
        name_row.setdefault(nn, i)

    from scipy.sparse import csr_matrix
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

    # ---- probes + carriers (132 off-arm, gold titles from 2wiki json) ----
    off_ids = [json.loads(l)["id"] for l in SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    off_pass = {json.loads(l)["id"]: json.loads(l)["pass"]
                for l in SCREEN.read_text().splitlines()
                if l.strip() and json.loads(l)["arm"] == "off"}
    Q = {q.get("_id"): q for q in json.loads(QUESTIONS.read_text())}
    questions_by_id = {pid: Q[pid] for pid in off_ids if pid in Q}

    def gold_titles(q):
        sf = q.get("supporting_facts") or []
        titles = []
        for item in sf:
            t = item[0] if isinstance(item, (list, tuple)) else item.get("title")
            if t and t not in titles:
                titles.append(t)
        return titles

    carriers = []
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in gold_titles(q):
            tn = _norm(t)
            carriers.append({
                "probe": pid, "carrier": t, "tnorm": tn,
                "in_graph": tn in graph_norms,
                "carrier_idx": name_row.get(tn),
            })
    in_graph_mask = [c["in_graph"] for c in carriers]
    print(f"probes={len(off_ids)} carriers={len(carriers)} in_graph={sum(in_graph_mask)}", flush=True)

    # ---- Titan probe embeddings (r47/r48 Bedrock path; cached) ----
    titan_probe_cache = CACHE / "titan_probe_emb.npz"
    if titan_probe_cache.exists():
        d = np.load(titan_probe_cache, allow_pickle=True)
        titan_probe = {pid: d[pid] for pid in off_ids}
    else:
        sys.path.insert(0, str(ROOT / "notebooks"))
        sys.path.insert(0, str(ROOT / "scripts/experiments"))
        from knowledge_graph_foundry import load_settings
        from knowledge_graph_foundry.extraction import generate_embeddings
        from knowledge_graph_foundry.models import Entity
        st = load_settings(CONFIG)
        st.event_log = None
        titan_probe = {}
        for pid in off_ids:
            q = questions_by_id[pid]["question"]
            probe = Entity.create(q[:80], types=["Query"], description=q)
            titan_probe[pid] = np.array(
                generate_embeddings([probe], st.embeddings)[0].embedding, dtype=np.float32)
        np.savez(titan_probe_cache, **{pid: titan_probe[pid] for pid in off_ids})
    # normalize titan entity + probe matrices
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    titan_probe_n = {pid: v / (np.linalg.norm(v) + 1e-9) for pid, v in titan_probe.items()}

    # ---- baseline arm (harness gate) ----
    t_rec, t_r1, t_rp = arm_metrics(titan_n, titan_probe_n, carriers,
                                    name_norms_by_idx, name_row, adj, out_deg, n, one_hop)
    titan_sum = summarize_arm("titan", t_rec, t_r1, t_rp, in_graph_mask)
    repro_delta = round(titan_sum["carrier_recall@16"] - H501_RECALL, 4)
    harness_ok = abs(repro_delta) <= 0.02
    print(f"TITAN carrier_recall@16={titan_sum['carrier_recall@16']} (H501={H501_RECALL}, "
          f"delta={repro_delta}, ok={harness_ok})", flush=True)
    harness_sanity = {
        "titan_carrier_recall@16": titan_sum["carrier_recall@16"],
        "h501_reference": H501_RECALL,
        "delta_pts": round(repro_delta * 100, 2),
        "reproduced_within_2pts": bool(harness_ok),
    }
    # checkpoint titan
    (OUT / f"h582-titan-{run_id}.json").write_text(json.dumps(
        {"harness_sanity": harness_sanity, "titan": titan_sum}, indent=1))
    if not harness_ok:
        print("HARNESS BROKEN - aborting before candidates", flush=True)
        (OUT / f"h582-embedder-swap-{run_id}.json").write_text(json.dumps({
            "run_id": run_id, "ABORTED": "harness did not reproduce H501 within 2 pts",
            "harness_sanity": harness_sanity, "titan": titan_sum}, indent=1))
        return

    # ---- entity texts (candidate re-embed) ----
    entity_texts = [build_entity_text(m["types"], m["name"], m["descr"]) for m in meta]
    probe_texts = {pid: build_probe_text(questions_by_id[pid]["question"]) for pid in off_ids}

    per_arm = [titan_sum]
    paired = []
    cand_hits_store = {}  # arm -> (rec, r1, rp)
    for arm, model, epfx, ppfx, extra in CANDIDATES:
        ent_npy = CACHE / f"ent_{arm}.npy"
        prb_npy = CACHE / f"prb_{arm}.npy"
        ok = True
        if not ent_npy.exists():
            ok = spawn_worker(model, [epfx + t for t in entity_texts], str(ent_npy), extra)
        if ok and not prb_npy.exists():
            ok = spawn_worker(model, [ppfx + probe_texts[pid] for pid in off_ids], str(prb_npy), extra)
        if not ok or not ent_npy.exists() or not prb_npy.exists():
            print(f"CANDIDATE {arm} DROPPED (worker crash/missing output)", flush=True)
            per_arm.append({"arm": arm, "DROPPED": True})
            continue
        ent = np.load(ent_npy)
        prb = np.load(prb_npy)
        ent = ent / (np.linalg.norm(ent, axis=1, keepdims=True) + 1e-9)
        pemb = {pid: prb[i] / (np.linalg.norm(prb[i]) + 1e-9) for i, pid in enumerate(off_ids)}
        c_rec, c_r1, c_rp = arm_metrics(ent, pemb, carriers, name_norms_by_idx,
                                        name_row, adj, out_deg, n, one_hop)
        s = summarize_arm(arm, c_rec, c_r1, c_rp, in_graph_mask)
        cand_hits_store[arm] = (c_rec, c_r1, c_rp)
        # paired deltas vs titan
        for metric, tv, cv in (("carrier_recall@16", t_rec, c_rec),
                               ("region_hit_1hop", t_r1, c_r1),
                               ("region_hit_ppr", t_rp, c_rp)):
            b, cc, p = mcnemar(tv, cv)
            lo, hi = boot_ci(tv, cv)
            s[metric + "_delta_vs_titan"] = round(s[metric] - titan_sum[metric], 4)
            s[metric + "_mcnemar_b_titanonly"] = b
            s[metric + "_mcnemar_c_candonly"] = cc
            s[metric + "_mcnemar_p"] = p
            s[metric + "_boot95"] = [lo, hi]
        per_arm.append(s)
        paired.append(s)
        (OUT / f"h582-arm-{arm}-{run_id}.json").write_text(json.dumps(s, indent=1))
        print(f"ARM {arm}: recall@16={s['carrier_recall@16']} "
              f"(d={s['carrier_recall@16_delta_vs_titan']}) "
              f"1hop={s['region_hit_1hop']} ppr={s['region_hit_ppr']}", flush=True)

    # ---- best candidate = highest carrier_recall@16 among survivors ----
    survivors = [s for s in paired if "carrier_recall@16" in s]
    best = max(survivors, key=lambda s: s["carrier_recall@16"]) if survivors else None
    best_arm = best["arm"] if best else None

    # ---- carried arms on best candidate + titan ----
    carried = {"h40": {}, "h41": {}}
    if best_arm:
        bmodel = {c[0]: (c[1], c[2], c[3], c[4]) for c in CANDIDATES}
        model, epfx, ppfx, extra = bmodel[best_arm]

        # ---------- H40 answer-form transform ----------
        drafts = draft_answer_forms(off_ids, questions_by_id)
        (CACHE / f"h40_drafts_{run_id}.json").write_text(json.dumps(drafts, indent=1))
        # titan H40 probe embeds (Bedrock)
        sys.path.insert(0, str(ROOT / "notebooks"))
        sys.path.insert(0, str(ROOT / "scripts/experiments"))
        from knowledge_graph_foundry import load_settings
        from knowledge_graph_foundry.extraction import generate_embeddings
        from knowledge_graph_foundry.models import Entity
        st = load_settings(CONFIG)
        st.event_log = None
        titan_h40 = {}
        for pid in off_ids:
            d = drafts[pid]
            probe = Entity.create(d[:80], types=["Query"], description=d)
            v = np.array(generate_embeddings([probe], st.embeddings)[0].embedding, dtype=np.float32)
            titan_h40[pid] = v / (np.linalg.norm(v) + 1e-9)
        th_rec, th_r1, th_rp = arm_metrics(titan_n, titan_h40, carriers, name_norms_by_idx,
                                           name_row, adj, out_deg, n, one_hop)
        titan_h40_sum = summarize_arm("titan+h40", th_rec, th_r1, th_rp, in_graph_mask)
        titan_h40_sum["carrier_recall@16_delta_vs_titan_q"] = round(
            titan_h40_sum["carrier_recall@16"] - titan_sum["carrier_recall@16"], 4)

        # best-candidate H40 probe embeds (drafts embedded with candidate probe prefix)
        h40_prb_npy = CACHE / f"prb_{best_arm}_h40.npy"
        spawn_worker(model, [ppfx + build_probe_text(drafts[pid]) for pid in off_ids],
                     str(h40_prb_npy), extra)
        ent = np.load(CACHE / f"ent_{best_arm}.npy")
        ent = ent / (np.linalg.norm(ent, axis=1, keepdims=True) + 1e-9)
        prb = np.load(h40_prb_npy)
        pemb = {pid: prb[i] / (np.linalg.norm(prb[i]) + 1e-9) for i, pid in enumerate(off_ids)}
        ch_rec, ch_r1, ch_rp = arm_metrics(ent, pemb, carriers, name_norms_by_idx,
                                           name_row, adj, out_deg, n, one_hop)
        cand_h40_sum = summarize_arm(f"{best_arm}+h40", ch_rec, ch_r1, ch_rp, in_graph_mask)
        base_cand = cand_hits_store[best_arm]
        cand_h40_sum["carrier_recall@16_delta_vs_cand_q"] = round(
            cand_h40_sum["carrier_recall@16"] - summarize_arm(best_arm, *base_cand, in_graph_mask)["carrier_recall@16"], 4)
        carried["h40"] = {
            "note": "declarative answer-form draft (gpt-oss-120b, temp0) embedded instead of the question",
            "titan_question": titan_sum, "titan_answer_form": titan_h40_sum,
            "best_cand_question": summarize_arm(best_arm, *base_cand, in_graph_mask),
            "best_cand_answer_form": cand_h40_sum,
        }

        # ---------- H41 split name/description two-channel ----------
        name_npy = CACHE / f"ent_{best_arm}_name.npy"
        desc_npy = CACHE / f"ent_{best_arm}_desc.npy"
        spawn_worker(model, [epfx + (m["name"] or "") for m in meta], str(name_npy), extra)
        spawn_worker(model, [epfx + ((m["descr"] or "")[:200]) for m in meta], str(desc_npy), extra)
        name_e = np.load(name_npy); name_e = name_e / (np.linalg.norm(name_e, axis=1, keepdims=True) + 1e-9)
        desc_e = np.load(desc_npy); desc_e = desc_e / (np.linalg.norm(desc_e, axis=1, keepdims=True) + 1e-9)
        prb = np.load(CACHE / f"prb_{best_arm}.npy")
        pemb = {pid: prb[i] / (np.linalg.norm(prb[i]) + 1e-9) for i, pid in enumerate(off_ids)}

        # union top-8 name + top-8 desc seeds per probe
        def split_metrics():
            rec, r1, rp = [], [], []
            seeds_norm, region1, regionppr = {}, {}, {}
            for pid in off_ids:
                qv = pemb[pid]
                sn = np.argpartition(-(name_e @ qv), 8)[:8]
                sdd = np.argpartition(-(desc_e @ qv), 8)[:8]
                sd = list({int(x) for x in sn} | {int(x) for x in sdd})
                seeds_norm[pid] = {name_norms_by_idx[i] for i in sd}
                region1[pid] = one_hop(sd)
                r = ppr(adj, out_deg, sd, n)
                regionppr[pid] = set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(sd)
            for c in carriers:
                pid = c["probe"]; tn = c["tnorm"]; cidx = c["carrier_idx"]
                rec.append(1 if tn in seeds_norm[pid] else 0)
                r1.append(1 if (cidx is not None and cidx in region1[pid]) else 0)
                rp.append(1 if (cidx is not None and cidx in regionppr[pid]) else 0)
            return rec, r1, rp
        sp_rec, sp_r1, sp_rp = split_metrics()
        split_sum = summarize_arm(f"{best_arm}+split8+8", sp_rec, sp_r1, sp_rp, in_graph_mask)
        mixed_sum = summarize_arm(best_arm, *base_cand, in_graph_mask)
        split_sum["carrier_recall@16_delta_vs_mixed16"] = round(
            split_sum["carrier_recall@16"] - mixed_sum["carrier_recall@16"], 4)
        b, cc, p = mcnemar(base_cand[0], sp_rec)
        carried["h41"] = {
            "note": "union top-8 name-channel + top-8 desc-channel vs mixed top-16 (budget 16), same embedder",
            "best_cand_mixed16": mixed_sum, "best_cand_split8+8": split_sum,
            "mcnemar_mixed_vs_split": {"b_mixedonly": b, "c_splitonly": cc, "p": p},
        }

    # ---- clauses / verdict ----
    best_recall_delta = round((best["carrier_recall@16"] - titan_sum["carrier_recall@16"]) * 100, 2) if best else None
    # region delta: use the larger-signal region metric (ppr) for the +5 clause, report both
    best_region_ppr_delta = round((best["region_hit_ppr"] - titan_sum["region_hit_ppr"]) * 100, 2) if best else None
    best_region_1hop_delta = round((best["region_hit_1hop"] - titan_sum["region_hit_1hop"]) * 100, 2) if best else None
    best_region_delta = max(best_region_ppr_delta, best_region_1hop_delta) if best else None

    clauses = [
        {"clause": "best candidate carrier recall@16 >= +5 pts over Titan 0.598",
         "predicted": ">= +5.0 pts", "measured": f"{best_recall_delta} pts" if best else "no survivor",
         "holds": bool(best and best_recall_delta >= 5.0)},
        {"clause": "best candidate region-hit >= +5 pts over Titan (paired)",
         "predicted": ">= +5.0 pts",
         "measured": (f"ppr {best_region_ppr_delta} / 1hop {best_region_1hop_delta} pts" if best else "no survivor"),
         "holds": bool(best and best_region_delta >= 5.0)},
        {"clause": "KILL: best candidate < +2 pts carrier recall (Titan not the binding constraint)",
         "predicted": "kill if < +2.0 pts", "measured": f"{best_recall_delta} pts" if best else "no survivor",
         "holds": bool(best and best_recall_delta < 2.0)},
    ]
    if not best:
        verdict = "INCONCLUSIVE"
    elif best_recall_delta >= 5.0 and best_region_delta >= 5.0:
        verdict = "CONFIRMED"
    elif best_recall_delta < 2.0:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    result = {
        "run_id": run_id, "hypothesis": "R47-H582", "config": str(CONFIG),
        "scoring_fence": "retrieval-level only (carrier/seed/region); never end-to-end probe pass",
        "cutoffs": {"top_k": TOP_K, "ppr_top_n": PPR_TOP_N, "damping": DAMPING, "iters": ITERS},
        "node_text_convention": "'{type}: {name} - {description[:200]}' (embeddings.py:48); "
        "probe='Query: {q[:80]} - {q[:200]}' (H501/r47 path); type=first non-Entity label",
        "n_probes": len(off_ids), "n_carriers": len(carriers),
        "n_carriers_in_graph": int(sum(in_graph_mask)),
        "harness_sanity": harness_sanity,
        "per_arm": per_arm,
        "best_candidate": best_arm,
        "best_recall_delta_pts": best_recall_delta,
        "best_region_ppr_delta_pts": best_region_ppr_delta,
        "best_region_1hop_delta_pts": best_region_1hop_delta,
        "carried_arms": carried,
        "clauses": clauses,
        "proposed_verdict": verdict,
    }
    path = OUT / f"h582-embedder-swap-{run_id}.json"
    path.write_text(json.dumps(result, indent=1))
    print("VERDICT " + json.dumps({"best": best_arm, "recall_delta_pts": best_recall_delta,
                                   "region_ppr_delta_pts": best_region_ppr_delta,
                                   "proposed_verdict": verdict}), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        main()

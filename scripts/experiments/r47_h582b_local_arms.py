"""R47-H582b addendum: local-encoder COST frontier over the SAME medium graph.

H582 primary KILLED the embedder-swap quality bet (e5-large-v2 +0.92 pts n.s.,
bge-m3 -0.30 vs stored Titan; dense@16 ~0.60 bound is embedder-invariant). This
addendum re-reads that result as a COST question: e5-large already proved local
parity with Bedrock Titan - how far DOWN the encoder-size / throughput curve does
parity hold? A small local encoder at parity => the Titan embedding bill -> ~zero.

Reuses the primary harness VERBATIM for every pure convention (imports its helpers
from r47_h582_embedder_swap): same cache, same '{type}: {name} - {desc[:200]}' node
text, same 'Query: {q[:80]} - {q[:200]}' probe, same fixed adjacency, same 132 frozen
off-arm probes / 326 carriers, same dense@16 seed landing + region-hit + PPR, same
paired McNemar + bootstrap vs the STORED Titan incumbent. Titan baseline is rebuilt
entirely from disk cache (titan_emb.npy + titan_probe_emb.npz) - NO Bedrock, NO gpt-oss,
NO H40/H41 carried arms (those are already recorded in the primary run).

New arms (all GPU bf16 + sdpa, mean-pooled where raw, each in an isolated subprocess):
  a. mmBERT-base (jhu-clsp/mmBERT-base) - raw multilingual ModernBERT MLM, mean-pooled
     (SentenceTransformer default pooling); NOT retrieval-trained. Calibrates how much
     retrieval training matters. ModernBERT gotcha: config.reference_compile=False.
  b. e5-base-v2  (intfloat/e5-base-v2, ~109M)     - retrieval-trained frontier point
  c. bge-base-en-v1.5 (BAAI/bge-base-en-v1.5, ~109M) - retrieval-trained frontier point
Carried for one coherent frontier table (recomputed from primary-run npy cache, also a
cross-check that this metric path reproduces the primary e5-large-v2 numbers):
  d. e5-large-v2 (intfloat/e5-large-v2, ~335M)

Per arm: measured params + exact tokens/s + encode wall-clock (grounds the cost claim).

Usage:
  python scripts/experiments/r47_h582b_local_arms.py                  # orchestrate
  python scripts/experiments/r47_h582b_local_arms.py worker <model> <in.json> <out.npy> <dev>
Writes: reports/experiments/r47/h582b-local-arms-<UTC ts>.json
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
sys.path.insert(0, str(ROOT / "scripts/experiments"))
from r47_h582_embedder_swap import (  # noqa: E402  (pure conventions, no side effects)
    CACHE, OUT, SCREEN, QUESTIONS, DEVICE,
    _norm, build_probe_text, build_entity_text, ppr, mcnemar, boot_ci,
    arm_metrics, summarize_arm,
)

SELF = ROOT / "scripts/experiments/r47_h582b_local_arms.py"

# (arm, hf_model, entity_prefix, probe_prefix, extra_spec, note)
ARMS = [
    ("mmBERT-base-raw", "jhu-clsp/mmBERT-base", "", "",
     {"reference_compile": False, "sdpa": True},
     "raw multilingual ModernBERT MLM, mean-pooled (ST default); NOT retrieval-trained"),
    ("e5-base-v2", "intfloat/e5-base-v2", "passage: ", "query: ",
     {"sdpa": True}, "retrieval-trained (contrastive)"),
    ("bge-base-en-v1.5", "BAAI/bge-base-en-v1.5", "", "",
     {"sdpa": True}, "retrieval-trained (contrastive)"),
]
# recomputed from primary-run cache (npy present) - frontier context + harness cross-check
CARRIED = [("e5-large-v2", "passage: ", "query: ", "retrieval-trained (contrastive), primary-run cache")]


# ---------------------------------------------------------------- worker mode
def worker(model_name: str, in_json: str, out_npy: str, device: str) -> None:
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = device
    import torch
    from sentence_transformers import SentenceTransformer

    spec = json.loads(Path(in_json).read_text())
    texts = spec["texts"]
    model_kwargs = {"torch_dtype": torch.bfloat16}
    if spec.get("sdpa"):
        model_kwargs["attn_implementation"] = "sdpa"
    config_kwargs = {}
    if "reference_compile" in spec:
        config_kwargs["reference_compile"] = spec["reference_compile"]  # ModernBERT hang guard
    st_kwargs = {}
    if spec.get("trust_remote_code"):
        st_kwargs["trust_remote_code"] = True
    model = SentenceTransformer(
        model_name, device="cuda", model_kwargs=model_kwargs,
        config_kwargs=config_kwargs or None, **st_kwargs,
    )
    n_params = int(sum(p.numel() for p in model.parameters()))
    try:
        tok = model.tokenizer
        n_tokens = int(sum(len(tok.encode(t, add_special_tokens=True)) for t in texts))
    except Exception:
        n_tokens = None
    t0 = time.time()
    emb = model.encode(
        texts, batch_size=128, normalize_embeddings=True,
        show_progress_bar=True, convert_to_numpy=True,
    )
    dt = time.time() - t0
    np.save(out_npy, emb.astype(np.float32))
    meta = {
        "model": model_name, "n_texts": len(texts), "n_params": n_params,
        "n_tokens": n_tokens, "encode_seconds": round(dt, 3),
        "tokens_per_sec": round(n_tokens / dt, 1) if n_tokens else None,
        "texts_per_sec": round(len(texts) / dt, 1),
        "emb_dim": int(emb.shape[1]), "device_name": torch.cuda.get_device_name(0),
    }
    Path(out_npy + ".meta.json").write_text(json.dumps(meta, indent=1))
    print(f"WORKER {model_name} -> {out_npy} shape={emb.shape} params={n_params} "
          f"tok/s={meta['tokens_per_sec']} in {round(dt, 1)}s", flush=True)


# ------------------------------------------------------------- orchestrate
def spawn_worker(model, texts, out_npy, extra):
    in_json = CACHE / (Path(out_npy).stem + "_in.json")
    payload = {"texts": texts,
               **{k: v for k, v in extra.items()
                  if k in ("reference_compile", "sdpa", "trust_remote_code")}}
    in_json.write_text(json.dumps(payload))
    cmd = [sys.executable, str(SELF), "worker", model, str(in_json), str(out_npy), DEVICE]
    log = ROOT / "logs/r47-h582b.log"
    with log.open("a") as lf:
        lf.write(f"\n=== worker {model} -> {out_npy} @ {datetime.now(timezone.utc).isoformat()} ===\n")
        lf.flush()
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
    return r.returncode == 0 and Path(out_npy).exists()


def pair_fields(s, titan_sum, t_rows, c_rows):
    """Attach delta/mcnemar/bootstrap fields vs titan for all three metrics."""
    for metric, tv, cv in (("carrier_recall@16", t_rows[0], c_rows[0]),
                           ("region_hit_1hop", t_rows[1], c_rows[1]),
                           ("region_hit_ppr", t_rows[2], c_rows[2])):
        b, cc, p = mcnemar(tv, cv)
        lo, hi = boot_ci(tv, cv)
        s[metric + "_delta_vs_titan"] = round(s[metric] - titan_sum[metric], 4)
        s[metric + "_mcnemar_b_titanonly"] = b
        s[metric + "_mcnemar_c_candonly"] = cc
        s[metric + "_mcnemar_p"] = p
        s[metric + "_boot95"] = [lo, hi]
    return s


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    # ---- load cache (identical to primary harness) ----
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

    off_ids = [json.loads(l)["id"] for l in SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
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
            carriers.append({"probe": pid, "carrier": t, "tnorm": tn,
                             "in_graph": tn in graph_norms, "carrier_idx": name_row.get(tn)})
    in_graph_mask = [c["in_graph"] for c in carriers]
    print(f"probes={len(off_ids)} carriers={len(carriers)} in_graph={sum(in_graph_mask)}", flush=True)

    # ---- titan baseline from cache (NO Bedrock) ----
    d = np.load(CACHE / "titan_probe_emb.npz", allow_pickle=True)
    titan_probe = {pid: d[pid] for pid in off_ids}
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    titan_probe_n = {pid: v / (np.linalg.norm(v) + 1e-9) for pid, v in titan_probe.items()}
    t_rec, t_r1, t_rp = arm_metrics(titan_n, titan_probe_n, carriers, name_norms_by_idx,
                                    name_row, adj, out_deg, n, one_hop)
    titan_sum = summarize_arm("titan", t_rec, t_r1, t_rp, in_graph_mask)
    titan_sum["note"] = "stored Bedrock Titan v2 (incumbent); rebuilt from disk cache"
    print(f"TITAN carrier_recall@16={titan_sum['carrier_recall@16']}", flush=True)

    # ---- entity texts / probe texts (identical convention) ----
    entity_texts = [build_entity_text(m["types"], m["name"], m["descr"]) for m in meta]
    probe_texts = {pid: build_probe_text(questions_by_id[pid]["question"]) for pid in off_ids}
    t_rows = (t_rec, t_r1, t_rp)

    per_arm = [titan_sum]
    deviations = []

    def eval_arm(arm, model, epfx, ppfx, extra, note, carried):
        ent_npy = CACHE / f"ent_{arm}.npy"
        prb_npy = CACHE / f"prb_{arm}.npy"
        meta_path = str(ent_npy) + ".meta.json"
        ok = True
        if not carried:
            if not ent_npy.exists():
                ok = spawn_worker(model, [epfx + t for t in entity_texts], str(ent_npy), extra)
            if ok and not prb_npy.exists():
                ok = spawn_worker(model, [ppfx + probe_texts[pid] for pid in off_ids], str(prb_npy), extra)
        if not ok or not ent_npy.exists() or not prb_npy.exists():
            print(f"ARM {arm} DROPPED (worker crash / missing output)", flush=True)
            deviations.append(f"{arm} dropped: worker crash or missing npy")
            return {"arm": arm, "DROPPED": True, "note": note}
        ent = np.load(ent_npy)
        prb = np.load(prb_npy)
        ent = ent / (np.linalg.norm(ent, axis=1, keepdims=True) + 1e-9)
        pemb = {pid: prb[i] / (np.linalg.norm(prb[i]) + 1e-9) for i, pid in enumerate(off_ids)}
        c_rec, c_r1, c_rp = arm_metrics(ent, pemb, carriers, name_norms_by_idx,
                                        name_row, adj, out_deg, n, one_hop)
        s = summarize_arm(arm, c_rec, c_r1, c_rp, in_graph_mask)
        pair_fields(s, titan_sum, t_rows, (c_rec, c_r1, c_rp))
        s["note"] = note
        # cost fields from worker meta
        if Path(meta_path).exists():
            wm = json.loads(Path(meta_path).read_text())
            s["n_params"] = wm.get("n_params")
            s["emb_dim"] = wm.get("emb_dim")
            s["embed_wall_clock_s"] = wm.get("encode_seconds")
            s["tokens_per_sec"] = wm.get("tokens_per_sec")
            s["texts_per_sec"] = wm.get("texts_per_sec")
            s["n_tokens"] = wm.get("n_tokens")
            s["device_name"] = wm.get("device_name")
        else:
            s["n_params"] = None
            s["embed_wall_clock_s"] = None
            s["tokens_per_sec"] = None
            s["throughput_note"] = "carried from primary run; throughput unmeasured"
        print(f"ARM {arm}: recall@16={s['carrier_recall@16']} "
              f"(d={s['carrier_recall@16_delta_vs_titan']} p={s['carrier_recall@16_mcnemar_p']}) "
              f"1hop={s['region_hit_1hop']} ppr={s['region_hit_ppr']} "
              f"params={s.get('n_params')} tok/s={s.get('tokens_per_sec')}", flush=True)
        (OUT / f"h582b-arm-{arm}-{run_id}.json").write_text(json.dumps(s, indent=1))
        return s

    for arm, model, epfx, ppfx, extra, note in ARMS:
        per_arm.append(eval_arm(arm, model, epfx, ppfx, extra, note, carried=False))
    for arm, epfx, ppfx, note in CARRIED:
        per_arm.append(eval_arm(arm, None, epfx, ppfx, {}, note, carried=True))

    # ---- cost reading: which arms hold parity vs titan ----
    PARITY_BAND = 0.02  # +-2 pts carrier recall@16 = the primary run's own "n.s." band
    survivors = [s for s in per_arm if "carrier_recall@16" in s and s["arm"] != "titan"]
    parity = [s for s in survivors
              if abs(s.get("carrier_recall@16_delta_vs_titan", 1.0)) <= PARITY_BAND
              and (s["carrier_recall@16_mcnemar_p"] is None or s["carrier_recall@16_mcnemar_p"] > 0.05)]
    parity_sorted = sorted(parity, key=lambda s: (s.get("n_params") or 9e12))
    smallest_parity = parity_sorted[0] if parity_sorted else None

    cost_reading = {
        "parity_band": "carrier_recall@16 within +-2.0 pts of Titan AND McNemar p>0.05 (primary run's own n.s. band)",
        "titan_carrier_recall@16": titan_sum["carrier_recall@16"],
        "arms_holding_parity": [
            {"arm": s["arm"], "n_params": s.get("n_params"),
             "carrier_recall@16": s["carrier_recall@16"],
             "delta_pts": round(s["carrier_recall@16_delta_vs_titan"] * 100, 2),
             "mcnemar_p": s["carrier_recall@16_mcnemar_p"],
             "tokens_per_sec": s.get("tokens_per_sec")}
            for s in parity_sorted],
        "smallest_parity_point": (
            {"arm": smallest_parity["arm"], "n_params": smallest_parity.get("n_params"),
             "carrier_recall@16": smallest_parity["carrier_recall@16"],
             "delta_pts": round(smallest_parity["carrier_recall@16_delta_vs_titan"] * 100, 2),
             "tokens_per_sec": smallest_parity.get("tokens_per_sec")}
            if smallest_parity else None),
        "arms_below_parity": [
            {"arm": s["arm"], "n_params": s.get("n_params"),
             "carrier_recall@16": s["carrier_recall@16"],
             "delta_pts": round(s["carrier_recall@16_delta_vs_titan"] * 100, 2),
             "mcnemar_p": s["carrier_recall@16_mcnemar_p"]}
            for s in survivors if s not in parity],
    }

    result = {
        "run_id": run_id, "hypothesis": "R47-H582b (addendum to H582)",
        "question": "COST frontier: how far down the encoder-size/throughput curve does "
        "local parity with Bedrock Titan hold on carrier recall@16?",
        "scoring_fence": "retrieval-level only (carrier/seed/region); never end-to-end probe pass",
        "reuses": "r47_h582_embedder_swap.py helpers verbatim (same cache, node/probe text, "
        "fixed adjacency, 132 probes / 326 carriers, dense@16 + region-hit + PPR, McNemar + bootstrap)",
        "titan_source": "cache only (titan_emb.npy + titan_probe_emb.npz); no Bedrock/gpt-oss this run",
        "n_probes": len(off_ids), "n_carriers": len(carriers),
        "n_carriers_in_graph": int(sum(in_graph_mask)),
        "per_arm": per_arm,
        "cost_reading": cost_reading,
        "deviations": deviations,
    }
    path = OUT / f"h582b-local-arms-{run_id}.json"
    path.write_text(json.dumps(result, indent=1))
    print("DONE " + json.dumps({"smallest_parity": (smallest_parity or {}).get("arm"),
                                "n_parity": len(parity)}), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        main()

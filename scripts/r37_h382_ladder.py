"""R37-H382 ARM 1: sufficiency-gated escalation ladder, H181 top-score signal.

Ladder rungs (from the R34 composed frontier, identical construction):
  rung 0 - engine-parity retrieval (overfetch 64 -> head 16)
  rung 1 - + H367-B proposition seeds (top-8 diversified prop hits' ABOUT
           entities displace the vector tail)
  rung 2 - + H366 s900k1 query-anchored window

Signal arm 1 (this script): H181 top-seed similarity (score of the #1 vector
hit, Titan space) - the shipped, free miss-detector signal (settings
miss_threshold=0.668). Policy: signal < threshold -> escalate to rung 2,
else stay at rung 0 (binary gate; the graded per-rung variant is not
fittable on 24 probes).

Calibration clause (registered): threshold fitted on a probe split, reported
on the holdout. Implementation: 2-fold cross-calibration - folds split the
two true-need probes (P15 in A, P22 in B); fit on A -> report B, fit on B ->
report A; headline = pooled out-of-fold outcomes. Poles: never-escalate
(rung 0: 0.8958 / +0%) and always-escalate (rung 2: 0.9583 / +27.8%).
Fit objective: catch every needy fit-fold probe (rung2 > rung0 recall),
then minimize escalations. P08 (parse loss) is non-needy: no rung helps it.

Caches reused (span + prop bge-m3 embeddings); probe questions embed fresh.
Writes: NONE. LLM self-report arm runs separately post-H363.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json  # noqa: E402
import sys  # noqa: E402
from copy import deepcopy  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
from knowledge_graph_foundry.graph.propositions import (  # noqa: E402
    _split_fat_propositions,
    diversify_hits,
    render_property_sentence,
    render_relation_sentence,
)
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.4:7687"
TOP_K = 16
OVERFETCH = 64
PROP_TOP_K = 8
SPAN = 900
PROBES = Path("tests/probes/cpap-probe-set.yml")
EMB_MODEL = "BAAI/bge-m3"
SPAN_CACHE = Path("results/r34/h366-span-embs-bgem3.jsonl")
PROP_CACHE = Path("results/r34/h367-prop-embs-bgem3.jsonl")
RUNGS = ["rung0", "rung1", "rung2"]
SHIPPED_THR = 0.668  # R19-H181 miss_threshold, reference policy only


def fit_threshold(fold_ids, signal, needy):
    """Pick the threshold catching every needy fit probe at minimal escalations."""
    sigs = sorted(signal[p] for p in fold_ids)
    cands = [sigs[0] - 1e-6] + [(a + b) / 2 for a, b in zip(sigs, sigs[1:])] + [sigs[-1] + 1e-6]
    best, best_key = None, None
    for thr in cands:
        esc = {p for p in fold_ids if signal[p] < thr}
        caught = len(esc & needy)
        key = (-caught, len(esc))  # max needy caught, then min escalations
        if best_key is None or key < best_key:
            best, best_key = thr, key
    return best


def eval_policy(ids, thr, signal, recall, ctx):
    esc = [p for p in ids if signal[p] < thr]
    rec = {p: recall["rung2"][p] if p in esc else recall["rung0"][p] for p in ids}
    chars = sum(ctx["rung2"][p] if p in esc else ctx["rung0"][p] for p in ids)
    base = sum(ctx["rung0"][p] for p in ids)
    return {
        "escalated": sorted(esc),
        "escalation_rate": round(len(esc) / len(ids), 4),
        "mean_recall": round(sum(rec.values()) / len(ids), 4),
        "fully_covered": sum(1 for v in rec.values() if v == 1.0),
        "context_growth": round(chars / base - 1, 4),
        "per_probe": {p: round(rec[p], 4) for p in sorted(ids)},
    }


def main():
    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    split_max = base.graphrag.proposition_split_max_tokens
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    # span pool: rebuild texts (parse) and pair with the cached embeddings
    ex = load_settings(Path("config-r29-v1.yml")).extraction
    from knowledge_graph_foundry.ingest.chunking import chunk_document
    from knowledge_graph_foundry.ingest.readers import iter_source_files, read_document

    chunks = []
    for f in iter_source_files(Path("data/external/cpap-datasheets-and-manuals")):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            doc = read_document(f, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
            chunks.extend(chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover))
        except Exception as exc:
            print(f"skip {f.name}: {exc}", flush=True)
    span_emb = {}
    for line in SPAN_CACHE.read_text().splitlines():
        rec = json.loads(line)
        span_emb[rec["key"]] = rec["embedding"]
    spans = []
    stride = SPAN // 2
    for ch in chunks:
        for start in range(0, max(len(ch.text) - stride, 1), stride):
            piece = ch.text[start : start + SPAN]
            key = f"{ch.id}:{SPAN}:{start}"
            if piece.strip() and key in span_emb:
                spans.append({"key": key, "text": piece})
    print(f"spans: {len(spans)} (cache {len(span_emb)})", flush=True)

    prop_emb = {}
    for line in PROP_CACHE.read_text().splitlines():
        rec = json.loads(line)
        prop_emb[rec["text"]] = rec["embedding"]

    with Foundry(st) as f:
        sentences: dict[str, set[str]] = {}
        with f.driver.session() as session:
            for row in session.run(
                "MATCH (s:Entity)-[r]->(t:Entity) WHERE r.valid_to IS NULL "
                "RETURN s.id AS sid, s.name AS sname, type(r) AS rel, t.id AS tid, t.name AS tname"
            ):
                text = render_relation_sentence(row["sname"], row["rel"], row["tname"])
                sentences.setdefault(text, set()).update((row["sid"], row["tid"]))
            for row in session.run(
                "MATCH (e:Entity) WHERE any(k IN keys(e) WHERE k STARTS WITH 'prop_') "
                "RETURN e.id AS id, e.name AS name, properties(e) AS props"
            ):
                spec = {k.removeprefix("prop_"): v for k, v in row["props"].items() if k.startswith("prop_")}
                sentences.setdefault(render_property_sentence(row["name"], spec), set()).add(row["id"])
        sentences = _split_fat_propositions(sentences, split_max)
        props = [{"text": t, "entity_ids": sorted(ids)} for t, ids in sentences.items() if t in prop_emb]
        print(f"propositions: {len(props)}", flush=True)

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMB_MODEL, device="cuda")
        model.max_seq_length = 8192
        model.half()
        probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
        q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                              normalize_embeddings=True, show_progress_bar=False)
        q_by_id = {p["id"]: e for p, e in zip(probes, q_embs)}

        recall = {r: {} for r in RUNGS}
        ctx = {r: {} for r in RUNGS}
        signal = {}
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding  # Titan: entity index space
            hits = vector_query(f.driver, emb, vec, top_k=OVERFETCH)
            parity = [s["id"] for s in hits][:TOP_K]
            signal[p["id"]] = round(hits[0]["score"], 4)  # H181 top-seed similarity

            qe = q_by_id[p["id"]]
            ranked_props = sorted(props, key=lambda pr: -sum(a * b for a, b in zip(qe, prop_emb[pr["text"]])))
            prop_hits = diversify_hits(
                [{"text": pr["text"], "entity_ids": pr["entity_ids"], "score": 0.0} for pr in ranked_props[:64]],
                PROP_TOP_K,
            )
            prop_eids = []
            for h in prop_hits:
                for eid in h["entity_ids"]:
                    if eid not in prop_eids and eid not in parity:
                        prop_eids.append(eid)
            union = parity[: TOP_K - min(len(prop_eids), 4)] + prop_eids[:4]

            top_span = max(spans, key=lambda s: sum(a * b for a, b in zip(qe, span_emb[s["key"]])))
            window = _norm(top_span["text"])

            rung_def = {"rung0": (parity, ""), "rung1": (union, ""), "rung2": (union, window)}
            golds = p["gold_evidence"]
            with f.driver.session() as sess:
                for r in RUNGS:
                    ids, extra = rung_def[r]
                    text = _render_nodes(sess, ids)
                    if extra:
                        text = text + " " + extra
                    ctx[r][p["id"]] = len(text)
                    recall[r][p["id"]] = sum(_present(g, text) for g in golds) / len(golds)
            print(f"{p['id']}: signal={signal[p['id']]:.4f} " +
                  " ".join(f"{r}={recall[r][p['id']]:.2f}" for r in RUNGS), flush=True)

    ids = sorted(signal)
    n = len(ids)
    # needy = escalation actually helps (rung2 beats rung0); P08-class excluded by construction
    needy = {p for p in ids if recall["rung2"][p] > recall["rung0"][p]}
    print(f"\nneedy (rung2 > rung0): {sorted(needy)}", flush=True)

    # 2-fold cross-calibration: alternate by sorted probe order (P15 even -> A, P22 odd -> B)
    fold_a = [p for i, p in enumerate(ids) if i % 2 == 0]
    fold_b = [p for i, p in enumerate(ids) if i % 2 == 1]
    thr_a = fit_threshold(fold_a, signal, needy & set(fold_a))  # fitted on A
    thr_b = fit_threshold(fold_b, signal, needy & set(fold_b))  # fitted on B
    hold_b = eval_policy(fold_b, thr_a, signal, recall, ctx)  # A's thr judged on B
    hold_a = eval_policy(fold_a, thr_b, signal, recall, ctx)  # B's thr judged on A

    # pooled out-of-fold headline
    pooled_rec = {**hold_a["per_probe"], **hold_b["per_probe"]}
    pooled_esc = sorted(hold_a["escalated"] + hold_b["escalated"])
    pooled_chars = sum(ctx["rung2"][p] if p in pooled_esc else ctx["rung0"][p] for p in ids)
    pooled = {
        "escalated": pooled_esc,
        "escalation_rate": round(len(pooled_esc) / n, 4),
        "mean_recall": round(sum(pooled_rec.values()) / n, 4),
        "fully_covered": sum(1 for v in pooled_rec.values() if v == 1.0),
        "context_growth": round(pooled_chars / sum(ctx["rung0"].values()) - 1, 4),
    }

    poles = {
        "never_escalate": {"mean_recall": round(sum(recall["rung0"].values()) / n, 4),
                           "fully_covered": sum(1 for v in recall["rung0"].values() if v == 1.0),
                           "context_growth": 0.0},
        "always_escalate": {"mean_recall": round(sum(recall["rung2"].values()) / n, 4),
                            "fully_covered": sum(1 for v in recall["rung2"].values() if v == 1.0),
                            "context_growth": round(sum(ctx["rung2"].values()) / sum(ctx["rung0"].values()) - 1, 4)},
    }
    shipped = eval_policy(ids, SHIPPED_THR, signal, recall, ctx)

    print("\nPOLES:", json.dumps(poles), flush=True)
    print(f"folds: thr_a={thr_a:.4f} thr_b={thr_b:.4f}", flush=True)
    print("POOLED HOLDOUT:", json.dumps(pooled), flush=True)
    print(f"SHIPPED thr {SHIPPED_THR}:", json.dumps({k: shipped[k] for k in
          ('escalation_rate', 'mean_recall', 'fully_covered', 'context_growth')}), flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r37-h382-ladder-arm1-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R37-H382 arm 1 (H181 top-score threshold)",
        "generated": ts, "graph_uri": URI,
        "signals": signal,
        "needy": sorted(needy),
        "rung_recall": {r: {k: round(v, 4) for k, v in recall[r].items()} for r in RUNGS},
        "rung_ctx_chars": ctx,
        "folds": {"a": fold_a, "b": fold_b, "thr_fit_a": thr_a, "thr_fit_b": thr_b,
                  "holdout_a": hold_a, "holdout_b": hold_b},
        "pooled_holdout": pooled,
        "poles": poles,
        "shipped_threshold_policy": shipped,
    }, indent=2))
    print(f"\nH382 ARM 1 COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

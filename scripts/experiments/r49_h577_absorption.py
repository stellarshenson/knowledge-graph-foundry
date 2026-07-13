#!/usr/bin/env python3
"""R49-H577 - Resolver-absorption rate as a free saturation health signal.

Registered prediction:
  (a) per-doc absorption rate rank-correlates with (1 - normalized GLiNER residue), Spearman >= 0.5
  (b) top-absorption tercile contributes < 15% of pass-2-to-5 marginal carriers

DEPENDENCY REALITY (measured, not assumed):
  - Per-doc absorption rate lives on the 2wiki-medium corpus (R45 pass2 re-emission, d_* doc ids).
  - The registered GLiNER residue asset (H260) is per-CPAP-document (10 PDFs) - a DISJOINT corpus.
  - The registered union-K 5-pass carrier asset (R22/H231, R23) is CPAP and AGGREGATE (pooled over
    docs, union-of-5); there is NO per-doc, per-pass carrier emission on disk.
  => The registered per-doc cross-corpus Spearman and the tercile clause are BLOCKED-DEPENDENCY:
     the three per-doc vectors do not share a document key on any corpus.

This script scores what IS scorable:
  1. Per-doc absorption rate (2wiki, R45 pass2)               -> the signal itself
  2. Per-doc certificate coverage / residue (2wiki, H389)     -> a same-corpus saturation proxy
  3. Within-2wiki proxy Spearman(absorption, coverage)        -> stands in for the registered rho
  4. Aggregate CPAP context: H260 GLiNER residue, R22 union-K -> the cross-corpus numbers, reported
     as context only (cannot be joined per-doc to absorption)

READ-ONLY. No LLM. No Neo4j writes (no Neo4j needed here).
"""
import json, datetime
from scipy.stats import spearmanr

ROOT = "/home/lab/workspace/learning/projects/knowledge-graph-foundry"
PASS2 = f"{ROOT}/reports/experiments/r45/pass2-20260712T102327Z.jsonl"
CERT_POST = f"{ROOT}/reports/experiments/r39/h389-coverage-20260712T095215Z.jsonl"
H260 = f"{ROOT}/reports/experiments/adjudicated/gliner-gate-h260-20260708T065305Z.json"
R22 = f"{ROOT}/reports/experiments/adjudicated/failure-mechanism-r22-20260708T051712Z.json"
TS = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = f"{ROOT}/reports/experiments/r49/h577-absorption-{TS}.json"


def load_jsonl(p):
    out = []
    for l in open(p):
        l = l.strip()
        if l:
            out.append(json.loads(l))
    return out


# ---- 1. per-doc absorption rate (2wiki, R45 pass2 re-emission) ----
absorb = {}
for r in load_jsonl(PASS2):
    if "doc" not in r:
        continue
    absorb.setdefault(r["doc"], []).append(bool(r["pass2_hit"]))
absorb_rate = {d: sum(v) / len(v) for d, v in absorb.items()}
absorb_n = {d: len(v) for d, v in absorb.items()}

# ---- 2. per-doc certificate coverage / residue (2wiki, H389 final post-repair) ----
cov = {}
for r in load_jsonl(CERT_POST):
    cov[r["doc"]] = r["coverage"]
residue_proxy = {d: 1.0 - c for d, c in cov.items()}  # same-corpus (1 - coverage) saturation residue

# ---- 3. within-2wiki proxy Spearman(absorption, coverage) on shared docs ----
shared = sorted(set(absorb_rate) & set(cov))
xa = [absorb_rate[d] for d in shared]
xc = [cov[d] for d in shared]
rho_proxy, p_proxy = spearmanr(xa, xc)
# absorption vs (1 - residue_proxy) is identical to absorption vs coverage (monotone), reported as such

# ---- 4. aggregate CPAP context (cannot join per-doc to absorption) ----
h260 = json.load(open(H260))
gliner_recall = h260["recall_primary"]["recall"]          # 0.9524 at threshold 0.1
gliner_residue_agg = round(1.0 - gliner_recall, 4)        # ~0.0476 aggregate CPAP residue
r22 = json.load(open(R22))
h231 = r22["hypotheses"]["H231"]
union_cov = h231["union_coverage_pct"]                    # 100.0
mean_run_cov = h231["mean_run_coverage_pct"]              # 55.43
marginal_gain_pts = h231["delta_union_minus_meanrun_pts"] # 44.57 (union minus mean single run)
run_swing_pts = h231["run_swing_pts"]                     # 54.29

result = {
    "hypothesis": "R49-H577",
    "ts": TS,
    "read_only": True,
    "corpus_reality": {
        "absorption_corpus": "2wiki-medium (R45 pass2, d_* doc ids)",
        "gliner_residue_corpus": "CPAP 10 PDFs (H260) - DISJOINT from absorption docs",
        "union_k_carrier": "CPAP aggregate (R22/H231, R23 union-of-5) - no per-doc, no per-pass breakdown",
        "join_key_exists": False,
        "conclusion": "registered per-doc cross-corpus Spearman and tercile clause are BLOCKED-DEPENDENCY",
    },
    "signal_absorption_2wiki": {
        "n_docs": len(absorb_rate),
        "n_facts": sum(absorb_n.values()),
        "mean_absorption_rate": round(sum(absorb_rate.values()) / len(absorb_rate), 4),
        "per_doc": {d: {"rate": round(absorb_rate[d], 4), "n": absorb_n[d]} for d in sorted(absorb_rate)},
    },
    "saturation_proxy_2wiki": {
        "n_docs": len(cov),
        "mean_coverage": round(sum(cov.values()) / len(cov), 4),
        "mean_residue_proxy": round(sum(residue_proxy.values()) / len(residue_proxy), 4),
    },
    "within_2wiki_proxy_spearman": {
        "n_shared_docs": len(shared),
        "rho_absorption_vs_coverage": round(float(rho_proxy), 4),
        "p_value": round(float(p_proxy), 4),
        "note": "coverage == (1 - residue_proxy) monotone; this proxy stands in for the registered "
                "(1 - GLiNER residue) which is not available per-doc on this corpus",
    },
    "cpap_aggregate_context": {
        "gliner_residue_aggregate": gliner_residue_agg,
        "gliner_recall": gliner_recall,
        "union_k_union_coverage_pct": union_cov,
        "union_k_mean_single_run_pct": mean_run_cov,
        "union_k_marginal_gain_pts": marginal_gain_pts,
        "union_k_run_swing_pts": run_swing_pts,
        "note": "CPAP corpus is FAR from saturated (44.6pt union-minus-single-run marginal carrier gain, "
                "54.3pt run swing) yet GLiNER residue is only ~4.8%; these are aggregate and cannot be "
                "joined per-doc to the 2wiki absorption vector",
    },
    "clauses": {
        "spearman_ge_0.5_vs_1_minus_residue": {
            "registered": "Spearman >= 0.5 (per-doc, absorption vs 1 - normalized GLiNER residue)",
            "status": "BLOCKED-DEPENDENCY (no per-doc GLiNER residue on absorption corpus)",
            "proxy_rho": round(float(rho_proxy), 4),
            "proxy_bar": 0.5,
            "proxy_holds": bool(rho_proxy >= 0.5),
        },
        "top_tercile_lt_15pct_marginal_carriers": {
            "registered": "top-absorption tercile < 15% of pass-2-to-5 marginal carriers",
            "status": "BLOCKED-DEPENDENCY (R22 5-pass carriers are CPAP aggregate, no per-doc/per-pass)",
        },
    },
}

with open(OUT, "w") as f:
    json.dump(result, f, indent=1)
print("wrote", OUT)
print(json.dumps({
    "proxy_rho": result["within_2wiki_proxy_spearman"]["rho_absorption_vs_coverage"],
    "n_shared": len(shared),
    "mean_absorption": result["signal_absorption_2wiki"]["mean_absorption_rate"],
    "mean_coverage": result["saturation_proxy_2wiki"]["mean_coverage"],
}, indent=1))

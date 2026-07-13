"""R49-H576 diagnostic: isolate render-staging (description-only) from the mandated
re-embed, per target, one anchor at a time (no cross-target interference).

Main run (h576-reach-replicate) found: 10/10 tail targets flip fail->pass but REG-2 does
NOT, because re-embedding REG-2's anchor evicted its block from the render_budget=0.6 render
(post anchor_block=False). The main run also had a vector-index refresh confound (9/11 fresh).

This diagnostic removes both confounds by running two clean arms per target, isolated:
  ARM D (desc_only)  - SET description only, NO re-embed. The vector index is UNCHANGED, so
                       retrieval (seeds + ranks) is held FIXED and fully deterministic; only
                       the anchor block's live-read text changes. Isolates pure render-staging.
  ARM R (reembed)    - SET description + re-embed, then WAIT for index consistency (poll the
                       anchor self-retrieval up to 60s) before probing. Removes the refresh
                       nondeterminism the batch run suffered.
Each arm: snapshot one anchor -> edit -> re-probe -> RESTORE (finally) -> verify. Captures the
REG-2 post render blocks so the eviction is visible.

Read-only on every pile except the authorized medium write+restore.
Usage: python scripts/experiments/r49_h576_arms_diag.py
Writes: reports/experiments/r49/h576-arms-diag-<ts>.json
"""

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm, _present  # noqa: E402
from r46_h499_screen import score  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path("config/experiments/config-bench-medium.yml")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
OUT = Path("reports/experiments/r49")
TARGET_TAGS = {
    "1dfaa6200bdd11eba7f7acde48001122": "reg2",
    "3ce92df80bde11eba7f7acde48001122": "h573_hop_unreach",
    "f05423560bda11eba7f7acde48001122": "h573_hop_unreach",
    "748446060bdb11eba7f7acde48001122": "h573_hop_unreach",
    "2d8f3ebe0bda11eba7f7acde48001122": "h571_weak_member",
    "7cb81afc0bd911eba7f7acde48001122": "h571_weak_member",
    "914b452c0bdc11eba7f7acde48001122": "h571_weak_member",
    "49b22d0a0bde11eba7f7acde48001122": "h571_weak_member",
    "cda459160bda11eba7f7acde48001122": "h571_weak_member",
    "8e07f1f00bda11eba7f7acde48001122": "h571_weak_member",
    "b7f5f7200bdd11eba7f7acde48001122": "h571_weak_member",
}


def desc_hash(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def emb_cksum(emb):
    if emb is None:
        return "none"
    return hashlib.sha256(",".join(f"{float(x):.6f}" for x in emb).encode()).hexdigest()[:16]


def block_present(name, ctx):
    return name is not None and f"## {name} (".lower() in ctx.lower()


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    byid = {q.get("_id"): q for q in json.loads(QUESTIONS.read_text())}
    st = load_settings(CONFIG)
    st.event_log = None
    st.questions.enabled = False

    rows = []
    with Foundry(st) as f:
        def probe_ctx(question):
            res = f.probe(question)
            return res, _norm(" ".join(res["context_lines"]))

        with f.driver.session() as s:
            def resolve(nm):
                r = s.run("MATCH (e:Entity) WHERE e.name=$n RETURN e.id AS id LIMIT 1", n=nm).single()
                if r:
                    return r["id"]
                r = s.run("MATCH (e:Entity) WHERE toLower(e.name)=toLower($n) RETURN e.id AS id LIMIT 1",
                          n=nm).single()
                return r["id"] if r else None

        for pid, tag in TARGET_TAGS.items():
            q = byid[pid]
            evs = q["evidences"]
            anchor_name, rel1, carrier = evs[0][0], evs[0][1], evs[0][2]
            rel2, answer = evs[-1][1], q["answer"]
            fact = f"{anchor_name}: {rel1} {carrier}. {carrier}'s {rel2} is {answer}."
            with f.driver.session() as s:
                aid = resolve(anchor_name)
            row = {"probe": pid, "tag": tag, "answer": answer, "anchor": anchor_name,
                   "anchor_id": aid, "fact": fact}

            # ---- PRE ----
            _, pre_ctx = probe_ctx(q["question"])
            row["pre_pass"] = score(q, {"context_lines": [pre_ctx]})["pass"]
            row["pre_anchor_block"] = block_present(anchor_name, pre_ctx)
            row["pre_ans_present"] = bool(_present(answer, pre_ctx))

            with f.driver.session() as s:
                r0 = s.run("MATCH (e:Entity {id:$id}) RETURN e.name AS name, "
                           "[l IN labels(e) WHERE l<>'Entity'] AS types, e.description AS d, "
                           "e.embedding AS emb", id=aid).single()
            pre = {"name": r0["name"], "types": r0["types"], "d": r0["d"], "emb": r0["emb"],
                   "dh": desc_hash(r0["d"]), "ec": emb_cksum(r0["emb"])}
            new_desc = ((pre["d"] or "") + " " + fact).strip() if pre["d"] else fact
            typ = pre["types"][0] if pre["types"] else "Entity"

            # ---- ARM D: description only (deterministic, index unchanged) ----
            try:
                with f.driver.session() as s:
                    s.run("MATCH (e:Entity {id:$id}) SET e.description=$d", id=aid, d=new_desc)
                res, d_ctx = probe_ctx(q["question"])
                row["D_pass"] = score(q, {"context_lines": [d_ctx]})["pass"]
                row["D_anchor_block"] = block_present(anchor_name, d_ctx)
                row["D_ans_present"] = bool(_present(answer, d_ctx))
                if tag == "reg2":
                    row["D_render_blocks"] = [ln[:90] for ln in res["context_lines"]]
            finally:
                with f.driver.session() as s:
                    s.run("MATCH (e:Entity {id:$id}) SET e.description=$d", id=aid, d=pre["d"])

            # ---- ARM R: description + re-embed, wait for index consistency ----
            try:
                ent = Entity.create(pre["name"], types=[typ], description=new_desc)
                new_emb = generate_embeddings([ent], st.embeddings)[0].embedding
                with f.driver.session() as s:
                    s.run("MATCH (e:Entity {id:$id}) SET e.description=$d, e.embedding=$emb",
                          id=aid, d=new_desc, emb=list(new_emb))
                fresh = False
                for _ in range(60):
                    hits = vector_query(f.driver, list(new_emb), st.graphrag.vector_index_name, top_k=3)
                    if any(h["id"] == aid for h in hits):
                        fresh = True
                        break
                    time.sleep(1)
                row["R_index_fresh"] = fresh
                res, r_ctx = probe_ctx(q["question"])
                row["R_pass"] = score(q, {"context_lines": [r_ctx]})["pass"]
                row["R_anchor_block"] = block_present(anchor_name, r_ctx)
                row["R_ans_present"] = bool(_present(answer, r_ctx))
                if tag == "reg2":
                    row["R_render_blocks"] = [ln[:90] for ln in res["context_lines"]]
            finally:
                with f.driver.session() as s:
                    s.run("MATCH (e:Entity {id:$id}) SET e.description=$d, e.embedding=$emb",
                          id=aid, d=pre["d"], emb=pre["emb"])
                    chk = s.run("MATCH (e:Entity {id:$id}) RETURN e.description AS d, e.embedding AS emb",
                                id=aid).single()
                    row["restored_ok"] = (desc_hash(chk["d"]) == pre["dh"]
                                          and emb_cksum(chk["emb"]) == pre["ec"])
            rows.append(row)
            print(f"{pid[:12]} {tag:16} pre_pass={row['pre_pass']} "
                  f"D:pass={row.get('D_pass')} block={row.get('D_anchor_block')} | "
                  f"R:pass={row.get('R_pass')} block={row.get('R_anchor_block')} "
                  f"fresh={row.get('R_index_fresh')} restored={row['restored_ok']}", flush=True)

    tail = [r for r in rows if r["tag"] != "reg2"]
    reg2 = next(r for r in rows if r["tag"] == "reg2")
    summary = {
        "hypothesis": "R49-H576-diag", "run_id": ts,
        "D_desc_only_flips": sum(1 for r in rows if not r["pre_pass"] and r["D_pass"]),
        "R_reembed_flips": sum(1 for r in rows if not r["pre_pass"] and r["R_pass"]),
        "D_reg2_flip": bool(not reg2["pre_pass"] and reg2["D_pass"]),
        "R_reg2_flip": bool(not reg2["pre_pass"] and reg2["R_pass"]),
        "D_tail_recovery": round(sum(1 for r in tail if not r["pre_pass"] and r["D_pass"]) / len(tail), 3),
        "R_tail_recovery": round(sum(1 for r in tail if not r["pre_pass"] and r["R_pass"]) / len(tail), 3),
        "all_restored": all(r["restored_ok"] for r in rows),
        "n": len(rows),
    }
    path = OUT / f"h576-arms-diag-{ts}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False))
    print("\nSUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

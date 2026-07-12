"""R45 hand-repair batch: write the hidden facts into the graph, ledger every edit.

For each ABSENT-classified certificate miss (from the H448 decomposition):
  1. carrier selection - the entity of the miss's document whose name appears
     in the miss text (longest match); fallback: the document's largest entity
  2. template `write_property` - append the fact verbatim to the carrier's
     description, provenance-marked (`r45_repair: true` on the entity)
  3. re-embed the touched entity (H492 clause - stale embeddings)
Every edit -> results/r45/repair-ledger.jsonl (fact, entity, template, ts).
The repaired graph is a REFERENCE artifact - repairs are marker-identifiable
and reversible by dump restore.

Recovery adjudication runs separately: re-run the certificate; iterate.

Usage: python scripts/r45_hand_repair.py <decomposition.jsonl>
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.extraction import generate_embeddings
from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.pipeline import Foundry

CONFIG = Path("config/experiments/config-bench-pilot.yml")
LEDGER = Path("results/r45/repair-ledger.jsonl")


def main():
    decomp = Path(sys.argv[1])
    misses = [json.loads(l) for l in decomp.read_text().splitlines()]
    absent = [m for m in misses if m["class"] == "ABSENT"]
    # dedupe identical (doc, fact) pairs across certificate runs
    seen = set()
    targets = []
    for m in absent:
        key = (m["doc"], m["miss"])
        if key not in seen:
            seen.add(key)
            targets.append(m)
    print(f"{len(targets)} unique ABSENT facts to repair", flush=True)

    st = load_settings(CONFIG)
    st.event_log = None
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    with Foundry(st) as f, f.driver.session() as s, LEDGER.open("a") as led:
        for m in targets:
            ents = s.run(
                "MATCH (e:Entity) WHERE $d IN e.source_documents "
                "RETURN e.id AS id, e.name AS name, size(coalesce(e.description,'')) AS dlen",
                d=m["doc"],
            ).data()
            fact_l = m["miss"].lower()
            carriers = [e for e in ents if e["name"] and e["name"].lower() in fact_l]
            carrier = max(carriers, key=lambda e: len(e["name"])) if carriers else (
                max(ents, key=lambda e: e["dlen"]) if ents else None
            )
            if carrier is None:
                led.write(json.dumps({"ts": ts, "fact": m["miss"], "doc": m["doc"], "template": "SKIP_no_entity"}) + "\n")
                continue
            s.run(
                "MATCH (e:Entity {id: $id}) "
                "SET e.description = coalesce(e.description,'') + ' | ' + $fact, "
                "e.r45_repair = true",
                id=carrier["id"], fact=m["miss"],
            )
            led.write(json.dumps({
                "ts": ts, "fact": m["miss"], "doc": m["doc"],
                "entity": carrier["id"], "entity_name": carrier["name"],
                "template": "write_property", "edits": 1,
                "carrier_selection": "name_match" if carriers else "fallback_largest",
            }) + "\n")
        # re-embed all repaired entities (H492)
        repaired = s.run(
            "MATCH (e:Entity {r45_repair: true}) RETURN e.id AS id, e.name AS name, e.description AS d"
        ).data()
        print(f"re-embedding {len(repaired)} repaired entities", flush=True)
        probes = [Entity.create((r["name"] or "e")[:80], types=["X"], description=r["d"] or "") for r in repaired]
        embs = generate_embeddings(probes, f.settings.embeddings)
        for r, p in zip(repaired, embs):
            s.run("MATCH (e:Entity {id: $id}) SET e.embedding = $emb", id=r["id"], emb=p.embedding)
    print(f"REPAIR BATCH COMPLETE: {len(targets)} facts applied -> {LEDGER}", flush=True)


if __name__ == "__main__":
    main()

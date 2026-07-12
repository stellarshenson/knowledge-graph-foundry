"""R44-H448: miss-list decomposition - where does the missing 36% actually go?

Every miss from the H389 certificate runs is classified by LLM adjudication
against the SAME graph content the certificate scored it on:
  ARTIFACT   - the graph states the fact in different words (term-share
               blindness; adjusts the instrument's denominator)
  ELSEWHERE  - the fact (or its core) is present but attached to another
               entity / stored as a relationship mention (storage-shape
               class, feeds H451)
  ABSENT     - genuinely not present in any form (the true extraction loss)

Each classification carries a <=12-word evidence quote. Bar: classes
reproducible +-1 miss across two adjudication passes (run the script twice).

Usage: python scripts/r44_h448_decomposition.py
Writes: results/r44/h448-decomposition-<ts>.jsonl + class summary.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.engines import create_engine
from knowledge_graph_foundry.pipeline import Foundry

sys.path.insert(0, "scripts")
from r39_h389_coverage_audit import doc_graph_texts  # noqa: E402 - same corpus definition as the certificate

CONFIG = Path("config/experiments/config-bench-pilot.yml")
OUT = Path("results/r44")

SYSTEM = (
    "You classify why a FACT is missing from a knowledge-graph entity store. "
    "You are given the fact and the full stored content for its source document. "
    "Answer with EXACTLY one line: a class word, a pipe, and a short evidence "
    "quote or reason (<=12 words).\n"
    "Classes:\n"
    "ARTIFACT - the stored content states this fact in different words\n"
    "ELSEWHERE - a core part of the fact appears, but on a different entity or "
    "only inside a relationship/description mention, not as the fact itself\n"
    "ABSENT - the fact is genuinely not present in any form"
)


def main():
    st = load_settings(CONFIG)
    st.event_log = None
    engine = create_engine(st.llm)
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"h448-decomposition-{ts}.jsonl"

    misses = []
    for run in sorted(Path("results/r39").glob("h389-coverage-*.jsonl")):
        for line in run.read_text().splitlines():
            r = json.loads(line)
            for m in r["misses"]:
                misses.append({"doc": r["doc"], "name": r["name"], "miss": m, "run": run.name})
    print(f"decomposing {len(misses)} misses from {len(set(m['run'] for m in misses))} certificate runs", flush=True)

    counts = Counter()
    with Foundry(st) as f, f.driver.session() as s, out_path.open("w") as fh:
        cache: dict[str, str] = {}
        for i, m in enumerate(misses):
            if m["doc"] not in cache:
                ent_text, _span = doc_graph_texts(s, m["doc"])
                cache[m["doc"]] = ent_text
            raw = engine.complete_text(
                SYSTEM,
                f"FACT: {m['miss']}\n\nSTORED CONTENT for the document:\n{cache[m['doc']][:6000]}\n\nClassification:",
            ).strip().splitlines()[0]
            cls = raw.split("|")[0].strip().upper()
            if cls not in ("ARTIFACT", "ELSEWHERE", "ABSENT"):
                cls = "UNPARSED"
            evidence = raw.split("|", 1)[1].strip() if "|" in raw else ""
            counts[cls] += 1
            fh.write(json.dumps({**m, "class": cls, "evidence": evidence}) + "\n")
            if (i + 1) % 20 == 0:
                print(f"[{i+1}/{len(misses)}] {dict(counts)}", flush=True)
    total = sum(counts.values())
    print(f"H448 DECOMPOSITION COMPLETE: {dict(counts)} of {total} -> {out_path}", flush=True)
    print(
        f"true-loss share (ABSENT): {counts['ABSENT']/total:.1%}; "
        f"instrument artifacts: {counts['ARTIFACT']/total:.1%}; "
        f"storage-shape: {counts['ELSEWHERE']/total:.1%}",
        flush=True,
    )


if __name__ == "__main__":
    main()

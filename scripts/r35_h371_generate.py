"""R35-H371 stage 1: generate 8 expectation questions per chunk on the local
engine (gpt-oss-120b via vLLM), checkpointed per chunk to a JSONL so the run
survives any driver death (detached compute rule). Groundedness gating and
embedding happen downstream (r35_h371_embed_store.py) - this stage only
generates and records.

Offline prototype: reads Chunk.text from the pile, writes NOTHING to the graph.
"""

import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from neo4j import GraphDatabase

URI = "bolt://172.19.0.100:7687"
VLLM = "http://localhost:8010/v1/chat/completions"
MODEL = "gpt-oss-120b"
OUT = Path("results/r35/h371-questions.jsonl")
N_QUESTIONS = 8  # registered fixed-count budget
CONCURRENCY = 8
TIMEOUT = 600  # vLLM is shared; calls may queue

PROMPT = (
    "You write retrieval-training questions. From the passage below, generate "
    "exactly {n} question-answer pairs. Each question must be fully answerable "
    "from the passage alone and phrased the way a user would ask it (do not "
    'say "the passage" or "the document"). Each answer must be a short span '
    "or value taken verbatim from the passage. Return ONLY a JSON array of "
    'objects with keys "q" and "a".\n\nPASSAGE:\n{text}'
)


def call_llm(text: str) -> list[dict]:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(n=N_QUESTIONS, text=text[:8000])}],
        "temperature": 0.0,
        "max_tokens": 3000,
    }).encode()
    req = urllib.request.Request(VLLM, data=body, headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=TIMEOUT))
    raw = resp["choices"][0]["message"]["content"]
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {raw[:200]}")
    pairs = json.loads(raw[start : end + 1])
    return [
        {"q": str(p["q"]).strip(), "a": str(p["a"]).strip()}
        for p in pairs
        if isinstance(p, dict) and p.get("q") and p.get("a")
    ]


def main():
    driver = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with driver.session() as s:
        chunks = s.run(
            "MATCH (c:Chunk) RETURN c.id AS id, c.text AS text ORDER BY c.index"
        ).data()
    driver.close()
    print(f"chunks: {len(chunks)}", flush=True)

    done = set()
    if OUT.exists():
        keep = []
        for line in OUT.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("error"):
                continue  # retry errored chunks on rerun
            done.add(rec["chunk_id"])
            keep.append(line)
        OUT.write_text("\n".join(keep) + ("\n" if keep else ""))
    todo = [c for c in chunks if c["id"] not in done]
    print(f"todo: {len(todo)} (checkpointed: {len(done)})", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def work(ch):
        try:
            pairs = call_llm(ch["text"])
            return {"chunk_id": ch["id"], "questions": pairs}
        except Exception as exc:  # record failures honestly; retriable via rerun
            return {"chunk_id": ch["id"], "questions": [], "error": str(exc)[:300]}

    n_ok = n_err = 0
    with OUT.open("a") as fh, ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(work, ch) for ch in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if rec.get("error"):
                n_err += 1
                print(f"[{i}/{len(todo)}] {rec['chunk_id']} ERROR {rec['error'][:80]}", flush=True)
            else:
                n_ok += 1
                if i % 10 == 0 or i == len(todo):
                    print(f"[{i}/{len(todo)}] ok={n_ok} err={n_err}", flush=True)
    print(f"GENERATION COMPLETE ok={n_ok} err={n_err} -> {OUT}", flush=True)
    if n_err:
        sys.exit(1)


if __name__ == "__main__":
    main()

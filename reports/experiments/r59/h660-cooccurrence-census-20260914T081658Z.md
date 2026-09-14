# R59-H660 chunk-local co-occurrence census - brief

**Verdict recommendation: PREMISE-FAILED** (run 20260914T081658Z, git 762f31ed216a,
join goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows), region rule: H651 widened: seeds u anchors u FULL 1-hop shell u PPR-top15)

**The H661 gate does NOT open and does NOT close. It is UNDECIDED** - the census could not be
computed, so no (a), (b), (c) or `w_assoc` number exists. No substitute was improvised.

## What blocked it
The chunk -> entity mapping for the medium rung exists nowhere on disk in this repository.
`tmp/results/r47/ents_meta.json` carries only `['descr','id','name','types']` (H631 recorded
this explicitly when class (b) of its own census was declared undeterminable from the same
cache); `tmp/results/r47/edges.json` and `tmp/results/r50/edges_typed.json` carry
entity-entity pairs with no chunk field; every prior script that computed the mapping pulled
it live from Neo4j and persisted only aggregates.

No Neo4j instance is reachable. URIs attempted:
- `bolt://172.21.0.6:7687` - ServiceUnavailable: Couldn't connect to 172.21.0.6:7687 (resolved to ('172.21.0.6:7687',)):
Timed out trying to establish connection to Reso
- `bolt://user-konrad.jelen-kgf-neo4j:7687` - ServiceUnavailable: Failed to DNS resolve address user-konrad.jelen-kgf-neo4j:7687: [Errno -2] Name or service not known
- `bolt://172.19.0.101:7687` - ServiceUnavailable: Couldn't connect to 172.19.0.101:7687 (resolved to ('172.19.0.101:7687',)):
Timed out trying to establish connection to 
- `bolt://172.19.0.9:7687` - ServiceUnavailable: Couldn't connect to 172.19.0.9:7687 (resolved to ('172.19.0.9:7687',)):
Timed out trying to establish connection to Reso
- `bolt://172.19.0.8:7687` - ServiceUnavailable: Couldn't connect to 172.19.0.8:7687 (resolved to ('172.19.0.8:7687',)):
Timed out trying to establish connection to Reso
- `bolt://localhost:7687` - ServiceUnavailable: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to Res

Host state: no Neo4j container exists (`docker ps -a` lists only an unrelated onedrive bridge
and a stopped alpine probe); the hub network carrying the `.env` hostname
`user-konrad.jelen-kgf-neo4j` is gone; no neo4j image is cached locally.

## What DID reproduce (free, no Neo4j)
- dense@16 carrier recall **0.6012** (pin 0.6012)
- frozen-substrate component census: **1830** components (pin 1830),
  LCC **3162** nodes = **0.4772** (pins 3162 / 0.4772),
  isolated **1426** (pin 1426) - computed in networkx over
  5386 undirected entity-entity edges
- the **4** cross-component residual gold rows located exactly in the R57 atlas:

| carrier | role | component id | component size |
|---|---|---|---|
| Dino Risi | bridge | 363 | 7 |
| David Bradley (director) | terminal-answer | 427 | 1 |
| Puttanna Kanagal | bridge | 543 | 1 |
| Min Dikkha | terminal-answer | 1000 | 10 |

## Resume
1. Restore the medium rung into a throwaway container from
   `data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump` (966 MB; 1,000 docs / 6,626
   entities / 1,000 chunks / 7,534 questions; sidecar
   `20260713-neo4j-medium-2wiki-1000.md`, recipe in `data/interim/dumps/MANIFEST.md`) - or
   bring the live 7,575-entity re-ingest back up
2. Confirm the reached instance and its entity count (DEF-4: `.env NEO4J_URI` silently
   overrides config targets)
3. Re-run `.venv/bin/python scripts/experiments/r59_h660_cooccurrence_census.py` - it
   auto-discovers the instance from `CANDIDATE_URIS`; add the new URI there if it differs

# R59-H660 chunk-local co-occurrence census - brief

**Verdict recommendation: GATE-OPEN** (run 20260914T084903Z, git 436476afa870,
join goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows), region rule: H651 widened: seeds u anchors u FULL 1-hop shell u PPR-top15)

Instance: `bolt://localhost:7687 (inside container kgf-neo4j-medium-scratch)`, container `kgf-neo4j-medium-scratch`, image `neo4j:5.26.0`, restored from
`data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump`. Access READ-ONLY
(MATCH / RETURN only; no MERGE / CREATE / SET / DELETE, no APOC or GDS).
6626 entities, 1000 chunks,
8298 MENTIONED_IN edges,
6021 entity-entity relationships
(of which 164 SIMILAR_TO).

## Pins
- dense@16 carrier recall **0.6012** (pin 0.6012)
- frozen-substrate components **1830** (pin 1830), LCC
  **3162** = **0.4772** (pins 3162 / 0.4772),
  isolated **1426** (pin 1426)
- restored instance, primary graph (no SIMILAR_TO): **1830**
  components, LCC **3162** = **0.4772**, isolated
  **1426**, 5386 undirected edges -
  pins reproduce exactly: **True**
- restored instance, any type (incl. SIMILAR_TO): **1754**
  components, LCC **3204** = **0.4835**,
  isolated **1334**
- the 4 cross-component residual gold rows located in the R57 atlas: **4**

## Census (exact counts)
- chunks carrying at least one entity: **1000**
- chunk-local co-occurring entity pairs, total: **53952**
- **(a)** co-occurring and NOT already adjacent: **48566**
- **(b)** (a) AND the two entities in DIFFERENT components: **22910**

Sensitivity, counting the SIMILAR_TO embedding layer as adjacency and as component
structure: (a) = **48448**, (b) = **22100**.

## Baseline-subtracted association weight `w_assoc = w_raw - E[w_raw]`
Baseline `E[w_raw] = f_u f_v / C` under independence given entity chunk-frequencies, C = 1000.

| set | n | min | p10 | p50 | p90 | max | mean | > 0 | >= 0.9 |
|---|---|---|---|---|---|---|---|---|---|
| (b) pairs | 22910 | -0.749 | 0.99 | 0.999 | 0.999 | 4.793 | 1.003963 | 22908 | 22817 |
| (a) pairs | 48566 | -0.809 | 0.989 | 0.999 | 0.999 | 8.734 | 1.006609 | 48560 | 48257 |

## The 4 cross-component residual gold rows
Carrier component joined to a seed component by at least one (b)-pair:
**3/4**. Carrier itself co-mentioned with a seed by a (b)-pair:
**2/4**.

| carrier | carrier component | component joined | direct carrier-seed (b)-pair | note |
|---|---|---|---|---|
| Dino Risi | 28 | YES | YES | - |
| David Bradley (director) | 976 | YES | no | - |
| Puttanna Kanagal | 632 | YES | YES | - |
| Min Dikkha | 3 | no | no | - |

## Gate
Registered rule: H661 opens only on a non-trivial (b). (b) = **22910** -> **GATE-OPEN**.

## Process fix
Chunk -> entity mapping persisted to `/home/lab/workspace/learning/projects/knowledge-graph-foundry/tmp/results/r47/chunk_entities.json` (1000 chunks,
8298 edges), stamped with instance, counts and UTC time. Later FREE
replays read that cache and need no live instance.

## Caveats
- primary adjacency and components exclude the SIMILAR_TO embedding layer; only that
  edge set reproduces the pinned 1,830 / 3,162 / 1,426, and it is what the shipped walk
  traverses. The literal any-type reading is reported as a sensitivity, never folded in
- `w_assoc` uses the independence baseline; where per-entity chunk frequency is mostly 1 the
  baseline is near zero and `w_assoc` is close to `w_raw` - stated so it is not over-read
- the 4 gold rows are indexed against the frozen 6,626-entity cache; unresolved ids under a
  different instance are reported with an explicit note, never dropped
- AAR's INDUCTIVE null stands: the published gain came from co-occurrence as supporting facts
  FOR QUESTIONS (question supervision). A non-trivial (b) opens H661; it does not size it

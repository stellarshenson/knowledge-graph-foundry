# R54-H628 pooled-index conversion - brief

**Verdict recommendation: KILLED**  (run 20260724T132816Z, join goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows))

Question: does H627's pooled seed-landing gain (carrier recall@16 0.6012 -> 0.7147
at alpha 0.6) CONVERT to reachability and probe flips, or is it a ranking-only dashboard number?

## Pins (reproduced)
- dense carrier recall@16 0.6012 (pin 0.6012); pooled 0.7147 (pin 0.7147)
- reset_region reach_all 0.874 (pin 0.874)
- narrow region == reset_region: True; wide == reset_region_wide: True

## Primary comparison - pooled vs dense, anchors ON, WIDE region (the shipped region)
- reach_all delta **+0.00pp** (pooled 0.9606 vs dense 0.9606)
- fully-retrieved(132) delta **+0**
- net flips pooled over dense (vs recorded rru_b10): **+0**
- registered bar: reach delta >= +3pp AND net flips > 0 -> reach_ok=False flips_ok=False

## All four comparisons (pooled minus dense)
| setting | reach_all delta | fully-ret delta | net flips (pooled-dense) |
|---|---|---|---|
| anchors ON, wide (primary) | +0.00pp | +0 | +0 |
| anchors ON, narrow | +2.36pp | +4 | +1 |
| anchors OFF, wide | -1.57pp | +0 | +0 |
| anchors OFF, narrow | +25.99pp | +35 | +26 |

## Why (the H627 scope limit, measured)
- pooled top-16 lands **43** carriers dense top-16 misses;
  **43** (100.0%) were ALREADY
  reachable inside the incumbent dense+anchor+wide region - so the landing gain is a RANKING move
  inside the reachable region, not a reach gain.

## Per-arm table
| arm | rec@16 | reach_all | fr(132) | flips +/- | net |
|---|---|---|---|---|---|
| dense|anchors=off|narrow | 0.6012 | 0.6220 | 73 | +2/-30 | -28 |
| dense|anchors=off|wide | 0.6012 | 0.9606 | 116 | +3/-0 | +3 |
| dense|anchors=on|narrow | 0.6012 | 0.8740 | 104 | +0/-0 | +0 |
| dense|anchors=on|wide | 0.6012 | 0.9606 | 116 | +3/-0 | +3 |
| pooled|anchors=off|narrow | 0.7147 | 0.8819 | 108 | +3/-5 | -2 |
| pooled|anchors=off|wide | 0.7147 | 0.9449 | 116 | +3/-0 | +3 |
| pooled|anchors=on|narrow | 0.7147 | 0.8976 | 108 | +1/-0 | +1 |
| pooled|anchors=on|wide | 0.7147 | 0.9606 | 116 | +3/-0 | +3 |

## Caveats
- deterministic retrieval-level flip proxy vs recorded rru_b10 (H651 pattern); not a live re-render.
- pooled changes seeds so regressions are possible and counted.
- frozen 6,626-entity substrate, not the 7,575 live re-ingest.

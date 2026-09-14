# R59-H657 separation-certificate scale forecast - brief

**INSTRUMENT-DELIVERED** (no pass/fail). Run 20260914T081730Z, git 762f31ed216a,
join goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows), region rule: H651 widened (seeds u anchors u full 1-hop shell u PPR-top15) - not exercised by this arm.

Certificate: `Delta_required(N, eps) = (1/beta) ln(2 (N-1) M / eps)`, `eps = 0.01`,
`M = 1.0000` (l2-normalised bank). Observable: `Delta_i = 1 - cos(i, nearest OTHER prototype)`
over the frozen 6626-entity prototype bank (dim 1024).

## Pin
- dense@16 carrier recall recomputed from this bank: **0.6012** (pin 0.6012) - held

## Delta percentile curve (exact)
| p1 | p5 | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|---|
| 0.0618 | 0.1525 | 0.2102 | 0.3185 | 0.4523 | 0.5847 | 0.6513 |

- min **0.004987**, max **0.7985**, mean 0.4415, sd 0.1668
- prototypes with `Delta < 1e-6` (embedding-exact duplicates): **0**
- `Delta < 0.01`: **2**; `< 0.05`: **49**;
  `< 0.10`: **142** of 6626

## Certificate - fraction BELOW at current N and at N' = 46 N
Current N = 6626; projected N' = 304796. The requirement rises by
`ln(46)/beta = 3.8286/beta`, independent of the data.

Betas [1, 2, 4, 8, 16] are the registered sweep; rows marked `(ext)` are an extension added
because the registered sweep saturates at 100% below-certificate everywhere and would
otherwise price neither H658 nor H663.

| beta | required now | below now | required at 46N | below at 46N | newly below |
|---|---|---|---|---|---|
| 1 | 14.0969 | 6626/6626 (100.00%) | 17.9257 | 6626/6626 (100.00%) | 0 |
| 2 | 7.0485 | 6626/6626 (100.00%) | 8.9629 | 6626/6626 (100.00%) | 0 |
| 4 | 3.5242 | 6626/6626 (100.00%) | 4.4814 | 6626/6626 (100.00%) | 0 |
| 8 | 1.7621 | 6626/6626 (100.00%) | 2.2407 | 6626/6626 (100.00%) | 0 |
| 16 | 0.8811 | 6626/6626 (100.00%) | 1.1204 | 6626/6626 (100.00%) | 0 |
| 24 (ext) | 0.5874 | 5006/6626 (75.55%) | 0.7469 | 6603/6626 (99.65%) | 1597 |
| 32 (ext) | 0.4405 | 3171/6626 (47.86%) | 0.5602 | 4660/6626 (70.33%) | 1489 |
| 48 (ext) | 0.2937 | 1397/6626 (21.08%) | 0.3735 | 2320/6626 (35.01%) | 923 |
| 64 (ext) | 0.2203 | 748/6626 (11.29%) | 0.2801 | 1273/6626 (19.21%) | 525 |
| 96 (ext) | 0.1468 | 315/6626 (4.75%) | 0.1867 | 508/6626 (7.67%) | 193 |
| 128 (ext) | 0.1101 | 162/6626 (2.44%) | 0.1400 | 298/6626 (4.50%) | 136 |

- beta needed for the BEST-separated prototype to clear: **17.6541** now,
  **22.4491** at the large rung
- beta needed for the MEDIAN prototype to clear: **31.1686** now,
  **39.6342** at the large rung

## Reading against the registered prediction
Registered: under 1% projected below-certificate means identity is scale-safe on this axis;
over 10% means the large rung needs a separation intervention before ingest.

- the whole registered sweep [1, 2, 4, 8, 16] reads **100% below-certificate at both N and 46N** -
  saturated, so the registered sweep alone prices nothing, which is why the extension exists
- projected fraction first drops under **10%** at beta = **96**
- projected fraction first drops under **1%** at beta = **None**
- the projected fraction stays above 10% for every beta up to 96, first dropping under 10% at beta = 96; it never drops under 1% at any tested beta, so identity is NOT scale-safe on this axis at any beta this bank supports

## Left tail (10 least-separated prototypes)
| Delta | prototype | nearest competitor |
|---|---|---|
| 0.004987 | Juan Alfonso Pérez de Guzmán | Juan Alfonso Pérez de Guzmán, 3rd Duke of Medina Sidonia |
| 0.004987 | Juan Alfonso Pérez de Guzmán, 3rd Duke of Medina Sidonia | Juan Alfonso Pérez de Guzmán |
| 0.010283 | Nantes – La Roche-sur-Yon via Sainte-Pazanne railway | Nantes–La Roche-sur-Yon via Sainte-Pazanne railway |
| 0.010283 | Nantes–La Roche-sur-Yon via Sainte-Pazanne railway | Nantes – La Roche-sur-Yon via Sainte-Pazanne railway |
| 0.012248 | R.G. Springsteen | R. G. Springsteen |
| 0.012248 | R. G. Springsteen | R.G. Springsteen |
| 0.013952 | Run (computer programming) | Run (programming) |
| 0.013952 | Run (programming) | Run (computer programming) |
| 0.015018 | Crown Prince Pavlos of Greece | Pavlos, Crown Prince of Greece |
| 0.015018 | Pavlos, Crown Prince of Greece | Crown Prince Pavlos of Greece |

## LOWER BOUND - read this before quoting any number
Every below-certificate fraction above is a **LOWER BOUND ON THE DAMAGE**, not a prediction.
The projection holds the SHAPE of the `Delta` distribution fixed and shifts only the requirement
by `ln(r)/beta`. New documents add near-duplicate entities, which pushes the left tail down
faster than `log N` pushes the requirement up, so the true large-rung below-certificate
fraction is at least this large.

## Caveats
- capacity theorems assume random patterns and do not transfer to correlated text embeddings;
  only the Theorem-5 certificate is used, because it depends solely on observables
- `Delta_i` is one minus the runner-up cosine; the certificate adds margin- and N-awareness,
  not an independent quantity
- the bank embeds `"{type}: {name} - {description[:200]}"`, so `Delta` mixes name and
  description separation and is not a name-identity statistic
- frozen 6,626-entity substrate, not the 7,575-entity live re-ingest

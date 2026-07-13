# R43 Graph-Structure Forensics - Literature Brief (2026-07-11)

Grounding for a GRAPH-STRUCTURE FORENSICS fanout. User directive (2026-07-11, verbatim intent): research the graph structure with graph-theory-based metrics and other measurable parameters and their CHANGES during ingestion, correlated with the sharp drop at the moment gold retrieval stopped - observe anomalous behavior or an anomalous PHASE SHIFT in graph structure that may have caused it, then investigate further; this informs the retriever side of the solution.

The triggering observation (REG-1, `reports/experiments/bench/regression-ledger.md`): during the 200-passage 2wiki ingest the progressive prober caught a live regression - qid `551e...48b6` ("Do both films Interview With A Hitman and The Last Coupon have the directors from the same country?") retrieved its gold at <= 135 docs and stopped from 154 on. Root-caused half instrument artifact (yes/no token match, prober fixed), half REAL: at 200 docs retrieval surfaces both film entities but neither gold director (Perry Bhandal, Frank Launder). The pile: 200 docs → 1,389 entities (after 286 Bayesian merges), 3,433 rels, 97 labels, mean degree ~4.9. Every node carries `created_at` - the structural time series is reconstructable per-document OFFLINE, no re-ingest. Boundary dumps in `data/interim/dumps/` (200-doc, r05-precampaign, h365-repaired piles). Probe trajectory in `reports/experiments/bench/progressive-probe-trajectory.jsonl` (118 records, cycles keyed by `ingested_titles`).

Fences (already adjudicated, R09 on the CPAP graph - do NOT re-register the static claims): H61 uniform render caps vindicated (zero truncation loss); H62 neighbor-Jaccard refuted (median degree 1 starved it); H64 betweenness bottlenecks refuted (no non-trivial paths); H65 assortativity refuted AS A STATIC LEAK MARKER (noise under injection); H66 gold lives in the max core, not middle shells; H67 traversal-depth dial closed (100% of golds within 2 hops, 91% on-seed); H68 communities are documents rediscovered (NMI 0.614); H77 spectral channel weak-CONFIRMED (Fiedler falls 0.01165 → 0.00877 at 30% merge-undo injection while type-JSD stays 0.000 - low power at one eigenvalue); H80 ~20% edge dead weight. Critical scope note: every R09 verdict is a STATIC one-snapshot measurement on a star-forest-shaped CPAP graph; this round's subject is DYNAMICS OVER INGESTION on a denser Wikipedia graph - a refuted static marker may still be a live series instrument, but any such candidate must cite the R09 verdict and claim the dynamic mechanism explicitly. H47 (Heaps b = 0.771/0.803) is the standing macro marker this round extends. H370's creator-gap finding (needed parent-tier bridges absent, embedding-kNN blind to them) and H107 (71% extraction variance) are standing mechanisms candidates may cite. Measurement discipline per `docs/kgf-sota.md` Metrics: noise floors before verdicts (H351), instrument-first sequencing; statistical machinery composes with the R42 brief (paired designs, MDE, registry).

## 1. The measurable structural parameter catalog

What each metric detects, computation cost at 10k-node scale (the medium-ladder ceiling; the current pile is 1.4k nodes - everything below is cheaper there), and published evidence it couples to retrieval quality or precedes pathology. All costs are per snapshot; a 200-checkpoint replay multiplies by 200 and still lands in CPU-minutes for everything except exact betweenness.

| Metric | What it detects | Cost @10k nodes | Published evidence |
|---|---|---|---|
| Node/edge counts, densification slope a (log E vs log N) | growth-process regime change; a-breakpoint = the process changed | O(E), <1 ms; segmented regression over 200 points trivial | Leskovec 2007: real graphs hold stable a in 1.11-1.68; slope is a process fingerprint (digest) |
| Degree moments, k_max/E share, top-decile degree share | hub condensation onset (one entity absorbing attachment) | O(N), <1 ms | Bianconi-Barabasi 2001: hub share is the condensation order parameter; winner-takes-all is a PHASE |
| Component structure: giant share S, count, mean small-fragment size <s>, non-isolated share | fragmentation / gelation; gold-component membership is the retrieval-mechanism version | O(E) union-find, ~1 ms | Albert-Jeong-Barabasi 2000: <s> peaks ~2 at the fragmentation threshold; When-to-use-Graphs 2025: non-isolated 0.41 / component size 2.11 (HotpotQA) predicts graph-RAG adds noise |
| Effective diameter (90th-pct hop distance, sampled) | densification stalling, fragmentation onset | sampled BFS, ~0.1 s | Leskovec 2007: healthy growth SHRINKS diameter; reversal = anomaly |
| Clustering coefficient (avg, per-label) | schema-flood documents (triangle bursts), density regime | O(sum deg^2), ~10 ms | When-to-use-Graphs uses it as a graph-quality axis; no dynamic published use |
| Degree assortativity r (as a SERIES) | attachment-regime change | O(E), ~1 ms | R09-H65 refuted it as a static leak marker (noise under injection); no published dynamic KG use - series candidacy is exploratory, decoration risk high |
| k-core shell profile (JSD between snapshots) | density-layering regime change | O(E), ~10 ms | R09-H66: descriptive fingerprint, gold in max core; shell-JSD dynamics unmeasured |
| Laplacian top-k singular spectrum (LAD embedding) | multi-scale connectivity change; component count via zero-values | truncated sparse SVD, ~0.1-1 s | LAD (KDD 2020): dual-window Z-score on the spectrum detects planted and real change points; upgrades R09-H77's single-Fiedler weak instrument to the full spectrum |
| DELTACON similarity between consecutive snapshots + Attr | per-step structural change magnitude, with node/edge attribution | exact O(N^2) ~1 s; approx O(gE) | Koutra 2013: axioms (edge importance, sparse-graph submodularity) that summary-stat vectors fail; ENRON temporal anomalies detected |
| Betweenness distribution (approximate/sampled) | path-concentration shifts | sampled ~1-10 s (exact O(NE) minutes - use sampled) | R09-H64: premise empty on the CPAP star-forest; the 2wiki graph has real paths - dynamics unmeasured |
| Heaps/type-token per label class; new-entities-per-doc, new-labels-per-doc | vocabulary-regime change, topic-cluster arrival, resolution failure | O(1) per event from created_at, trivial | H47 (b = 0.771/0.803); Tria 2014: beta = exploration/reinforcement ratio, shuffle-null detects correlated novelty bursts |
| Community stability (Leiden re-run per checkpoint; NMI vs previous, NMI vs source doc) | community rearrangement events; provenance-braiding rate | GDS Leiden ~1 s | R09-H68: NMI(community, doc) = 0.614 static; Peel-Clauset: merges/splits are the canonical change classes scalar stats miss |
| Merge-event series (286 Bayesian merges, rate + hub-touching flag per doc) | identity-layer waves; a bad hub merge = targeted attack in reverse | log replay, trivial | AJB 2000 (hub removal doubles diameter at 5%); H91 hub-audit lineage; no published KG-ingest use |
| Edge-type entropy per document emission | schema-flood signature (burst of one relation shape) | O(E_doc), trivial | MIDAS 2020: burst-of-similar-edges is the microcluster anomaly class, chi-squared priced, O(1)/edge |
| Vector-index N_k skewness (hubness) + hub identity churn | embedding-space crowding; generic hubs capturing kNN lists | kNN over 10k vectors ~1 s FAISS / GPU | Radovanovic JMLR 2010: N_k skewness grows with intrinsic dimensionality; hubs = points near data mean; degrades retrieval regardless of query |
| Gold-carrier crowd count and rank margin (per probe: # vectors closer to query than the gold carrier) | rank dilution approaching top-k cliff | one query per probe per checkpoint, ~ms | no published equivalent (open slot S4); continuous version of the binary pass/fail probe |

Panel doctrine carries over from R09 verbatim: a metric earns a place only if it (a) predicts probe outcomes, (b) triggers a maintenance action earlier or cheaper than an existing trigger, or (c) improves a decision at matched budget - anything else is dashboard decoration and gets recorded as such.

## 2. Phase-shift science - what growing graphs actually undergo

The published transitions, with exact laws and exponents:

- **Percolation / giant-component emergence** - Erdos-Renyi: giant component appears at mean degree c = 1; near threshold the giant fraction S ~ (c − 1); at c = ln N the graph becomes fully connected. The 2wiki pile at mean degree ~4.9 is well past onset, but the PER-LABEL subgraphs (e.g. the DIRECTED_BY edge layer alone) can each sit near their own threshold - layer-wise percolation is where comparison-question answerability lives
- **Densification power law** - e(t) ∝ n(t)^a, 1 < a < 2, stable per process: arXiv citations 1.68, patents 1.66, AS graph 1.18, affiliation 1.08-1.15 (Leskovec). A slope BREAK means the growth process changed - the cleanest single-series regime-change instrument
- **Shrinking effective diameter** - healthy densifying growth decreases the 90th-percentile hop distance then stabilizes; a rising diameter during growth is anomalous (fragmentation outpacing densification)
- **Hub condensation (Bose-Einstein phase)** - fitness-based preferential attachment has three phases: scale-free, fit-get-rich (k(t) ∝ t^{f(eta)/C}), and condensate where the fittest node captures a FINITE edge share independent of N (Bianconi-Barabasi). Order parameter: k_max/E. A corpus whose entity "fitness" distribution shifts (2wiki: country and profession nodes shared by every film document) can cross into condensation mid-ingest
- **Fragmentation transition** - under node loss (or its ingest-time analogs: bad merges, fragment splits), largest-component share S collapses and mean non-giant fragment size <s> rises to a peak ≈ 2 at threshold f_c, then falls as everything atomizes (AJB). Scale-free graphs: robust to random loss (diameter flat to 5% random removal), diameter DOUBLES at ~5% targeted hub removal - hub-touching merge errors are targeted attacks
- **Heaps/Zipf coupled break** - Polya-urn-with-triggering produces both laws with beta = 1/alpha (Tria); a Heaps break WITHOUT a Zipf break (or vice versa) means the generative process changed, not just its rate; novelty events cluster (correlated novelties) - a shuffle-null test detects topic-cluster arrival
- **Hubness escalation in vector spaces** - N_k skewness grows with intrinsic dimensionality and sharpens as points accumulate in a fixed region (Radovanovic); no threshold law, but a monotone pathology with a measurable rate - the embedding-side "phase drift" that has no graph counterpart
- **What is NOT expected** - explosive/discontinuous percolation needs adversarial edge selection (Achlioptas class), not natural ingest; genuine first-order jumps in these series would themselves be findings

## 3. The forensic protocol sketch - localizing the REG-1 shift

1. **Reconstruct the filtration** - order all nodes and relationships by `created_at` (both carry it), bucket by source document (chunk provenance → doc index 1..200), and compute the cumulative graph G_1 ⊂ G_2 ⊂ ... ⊂ G_200. Honest caveat: this is the END-STATE filtration - merged-away entities and re-pointed edges appear in their post-merge form, so identity history is approximate. Two correctives: (a) the 286-merge event log replays merge timing exactly; (b) the boundary dumps in `data/interim/dumps/` are ground truth at their checkpoints - validate the reconstruction against the 200-doc dump (must match exactly) and use the r05/h365 dumps as cross-pile controls
2. **Compute the catalog** - every Section 1 series at all 200 checkpoints (CPU-minutes total at this scale); persist as one tidy per-checkpoint table in `results/` (detached-compute rule applies if any step grows)
3. **Detect change points with priced alarms** - three independent detector families: LAD dual-window Z on the Laplacian spectrum, DELTACON step series (flag steps > mean + 3 sigma of the step distribution), segmented-regression breakpoint on the densification and Heaps series; thresholds bootstrap-calibrated (Peel-Clauset pattern; H351 doctrine - no magic tolerances)
4. **Align with the probe trajectory** - REG-1's transition interval is (135, 154] in doc count; the prober cycles give per-question pass/fail at each `ingested_titles` value. A structural series indicts itself by placing a change point INSIDE the interval; a flat series exonerates its mechanism. Simultaneously track the MECHANISM series for REG-1 specifically: component membership and graph path existence for {Interview With A Hitman, The Last Coupon, Perry Bhandal, Frank Launder, their countries}, and the vector-rank margin of the two director carriers for the probe query
5. **Attribute and drill** - at the indicted checkpoint, DeltaCon-Attr names the top contributing nodes/edges; the merge-log slice for docs 136-154 names identity events; the intersection is the suspect set for the targeted audit (Family E)

## 4. Proven-novel open slots

- **S1 - Structural change-point alarms wired to a live progressive prober.** LAD, Peel-Clauset, MIDAS detect graph changes as ends in themselves; GraphRAG-Bench profiles static corpora; EraRAG/incremental-RAG systems update indexes but publish no structural monitoring; no published system runs change-point detection on a GROWING knowledge graph and couples the alarm to a retrieval-regression prober. Open
- **S2 - End-state filtration forensics.** Reconstructing the per-document structural time series from `created_at` ordering of the final graph (no re-ingest, merge-log corrected, dump-validated) is not a published method - temporal-graph work assumes the snapshot sequence was recorded live. Open
- **S3 - Hubness dynamics under corpus growth in a RAG index.** The hubness literature (Radovanovic and successors) measures static datasets; nobody publishes N_k-skewness trajectories as a vector index grows, nor couples hub-identity churn to retrieval regressions. Open
- **S4 - Continuous regression margin.** Gold-carrier rank headroom (crowd count vs top-k) as an early-warning continuous instrument for binary probe regressions - the R42 continuous-instrument doctrine applied to the prober; no published equivalent. Open
- **S5 - Layer-wise percolation for answerability.** Per-relation-type subgraph component tracking (does the DIRECTED_BY layer percolate?) as a question-class answerability predictor - percolation theory exists, the KG-RAG application does not. Open

## 5. Hypothesis candidates (H418-H447)

Thirty candidates in six families. Costs: offline-cheap = CPU on existing artifacts; offline-LLM = needs completions (local model per fleet doctrine); GPU = embedding recompute or index rebuild. Every acceptance bar inherits the H351 noise-floor rule and the R42 paired-design forms.

### Family A - structural time-series instrumentation

**H418 The filtration instrument (conformist, instrument-first)**
- Mechanism - build the created_at replay (protocol step 1): per-document cumulative graph series, merge-log aligned, validated exactly against the 200-doc boundary dump
- Grounding - S2; sota.md instrument-first rule; dumps in data/interim/dumps/
- Prediction - reconstruction matches the 200-doc dump node-for-node and edge-for-edge; per-doc bucketing is unambiguous for >= 99% of elements (chunk provenance present)
- Bar - exact dump match + ambiguity census reported; REFUTED if created_at granularity cannot separate documents (then the instrument needs ingest-side event logging and the round re-scopes)
- Cost - offline-cheap

**H419 Densification breakpoint (conformist)**
- Mechanism - segmented regression on log E vs log N over the filtration; test for a slope break inside (135, 154]
- Grounding - Leskovec: stable a = 1.11-1.68 per process; a break = process change
- Prediction - the pile shows a measurable densification slope; IF a break exists it falls inside the REG-1 interval; healthy control piles (r05 dump) show no break
- Bar - breakpoint CI (bootstrap) inside the interval + control clean; INCONCLUSIVE if slope noise swamps (small-N caveat: 200 points, early points few nodes)
- Cost - offline-cheap

**H420 Per-class Heaps break (conformist)**
- Mechanism - type-token series per label class (new PERSON/WORK/COUNTRY entities per doc) + Tria shuffle-null for correlated novelty bursts; localize WHICH vocabulary broke at the boundary
- Grounding - H47 (b = 0.771/0.803 macro); Tria beta = nu/rho, novelty clustering
- Prediction - a topic-cluster arrival (film-schema burst) shows as a correlated-novelty burst in the REG-1 window in >= 1 label class while the macro Heaps curve stays smooth - the macro marker is blind to class-local breaks
- Bar - burst detected at shuffle-null p < 0.05 inside the window; macro-vs-class dissociation shown; REFUTED if all classes track the macro curve
- Cost - offline-cheap

**H421 Component-structure series and gold membership (conformist)**
- Mechanism - S, component count, <s>, non-isolated share per checkpoint, PLUS component membership of the four REG-1 gold entities over ingest
- Grounding - AJB <s>-peak signature; When-to-use-Graphs non-isolated/component-size reference values (0.41/2.11 HotpotQA)
- Prediction - a component event (the films' components merging into a large generic component via a shared hub, or a director carrier fragmenting off) occurs inside the REG-1 window
- Bar - the membership series shows a discrete event in (135, 154]; REFUTED if gold components are stable through the window (graph-side component mechanism exonerated)
- Cost - offline-cheap

**H422 DELTACON step series with attribution (conformist)**
- Mechanism - DELTACON(G_t, G_{t+1}) for t = 1..199 (exact, O(N^2) fine at 1.4k); flag steps > 3 sigma; DeltaCon-Attr names culpable nodes/edges at flagged steps
- Grounding - Koutra axioms (edge-submodularity prices sparse-graph changes correctly); ENRON temporal precedent
- Prediction - >= 1 flagged step inside the REG-1 window, and its attribution set intersects the REG-1 entity neighborhood or the docs' merge slice
- Bar - flagged step + attribution overlap; REFUTED if the window is DELTACON-quiet while other detectors fire (then the change is spectral/identity, not affinity-structural)
- Cost - offline-cheap

**H423 Hub-condensation order parameter (follower)**
- Mechanism - k_max/E and top-decile degree share per checkpoint; test for monotone rise vs flat, and for the REG-1 window coinciding with a share acceleration
- Grounding - Bianconi-Barabasi condensation order parameter; 2wiki shared-attribute hubs (countries, professions) are the condensing class
- Prediction - shared-attribute hubs (country nodes) show accelerating share growth as film docs accumulate; director-class nodes do not
- Bar - share series with bootstrap CI; acceleration localized to hub labels; decoration verdict recorded if the series is flat (panel doctrine)
- Cost - offline-cheap

### Family B - phase-shift detection / change-points

**H424 LAD spectral change-point (conformist)**
- Mechanism - top-k Laplacian singular spectrum per checkpoint, dual-window (short l_s ~ 5 docs, long l_l ~ 20 docs) Z-score, change points where Z clears a bootstrap threshold
- Grounding - LAD (KDD 2020); upgrades R09-H77's weak single-Fiedler instrument to the full spectrum - the registered power-upgrade path
- Prediction - LAD places a change point inside (135, 154]; the spectrum channel fires where type-frequency JSD is flat (the H77 differential, now at full power)
- Bar - change point in window at priced threshold + JSD flat; REFUTED if LAD is quiet in the window on the real pile but fires on injected controls (structure did not shift; routes weight to Family D/F)
- Cost - offline-cheap

**H425 Priced alarms - bootstrap-calibrated thresholds for every detector (conformist)**
- Mechanism - for each Family A/B detector, calibrate the alarm threshold by parametric bootstrap on healthy segments (and the r05 control pile) to a registered false-alarm rate (e.g. <= 1 alarm per 200 healthy docs)
- Grounding - Peel-Clauset bootstrap calibration; H351 noise-floor doctrine; MIDAS chi-squared bound pattern
- Prediction - un-priced thresholds (3-sigma rules of thumb) misfire on healthy segments at >= 3x the registered rate for >= 2 detectors - pricing changes verdicts, not just hygiene
- Bar - per-detector measured false-alarm rate table; the misfire prediction tested; every Family A-D verdict must cite its priced threshold
- Cost - offline-cheap

**H426 Edge-burst sketch - the MIDAS analog at document granularity (follower)**
- Mechanism - per-document emission stream scored for microcluster bursts: chi-squared on (head-label, rel-type, tail-label) shape counts, current-doc vs historical mean; flag burst documents
- Grounding - MIDAS (constant-time, priced chi-squared, AUC ~0.95 class on intrusion streams); edge-type entropy row of the catalog
- Prediction - >= 1 document inside (135, 154] is a burst document (schema flood of one edge shape), and burst-doc arrival precedes the probe flip
- Bar - burst flag in window at priced threshold; temporal precedence over the flip cycle; REFUTED if bursts scatter uniformly over the ingest
- Cost - offline-cheap

**H427 Change-point congruence - one event or none (conformist)**
- Mechanism - run the independent detector families (spectral H424, affinity H422, growth-law H419/H420, burst H426) and test whether their change points CO-LOCATE within +-5 docs
- Grounding - Peel-Clauset: distinct rearrangements hide from scalar stats; congruence of independent channels is the standard multi-instrument confirmation
- Prediction - if REG-1 is a structural phase shift, >= 3 of 4 families co-locate inside the window; if detectors scatter, there was no single structural event (evidence FOR Family F)
- Bar - co-location census with priced per-detector alarms; either verdict is informative and routes the round
- Cost - offline-cheap

**H428 Merge-wave forensics (follower)**
- Mechanism - the 286-merge event series: rate per doc, hub-touching flag (merge target degree > p90), cross-label flag; change-point on the merge-rate series; slice docs 136-154
- Grounding - AJB (hub events are targeted attacks); H91 hub-audit lineage; the merge log is exact where the filtration is approximate
- Prediction - the REG-1 window contains a merge-rate anomaly or >= 1 hub-touching merge involving the REG-1 neighborhood
- Bar - window slice census + priced rate change-point; feeds H444's identity-only claim either way
- Cost - offline-cheap

### Family C - retrieval coupling: which structural changes move recall

**H429 Gold-path existence series - the mechanism localizer (conformist, flagship)**
- Mechanism - per checkpoint, test in the graph: does a path film → director → country exist for both REG-1 films; does each director entity exist as a distinct node; are film and director in the same component
- Grounding - H67 doctrine (answerability = evidence within 2 hops of a seedable node); When-to-use-Graphs (multi-hop classes need connected chains); REG-1 root-cause note (films surface, directors do not)
- Prediction - the graph-side path NEVER breaks across the window (directors present and connected throughout) - the regression is retrieval-side (seeding/ranking), not graph-side; the sharp version: the path exists at doc 200 where retrieval fails
- Bar - the path series with exact node identities; either outcome routes the entire round (path broke → Families A/B/E own it; path held → Families D/F own it)
- Cost - offline-cheap

**H430 Rank-margin trajectory - the continuous prober (conformist)**
- Mechanism - for each probe question, per checkpoint: vector-index rank of the best gold carrier and crowd count (vectors closer to the query than the gold); the binary pass/fail becomes a margin series
- Grounding - S4; R42 continuous-instruments doctrine; the prober's pass/fail is a threshold crossing of exactly this margin
- Prediction - REG-1's margin decays TOWARD the top-k boundary over multiple cycles before the flip (early warning exists), rather than jumping discontinuously at 154
- Bar - margin series reconstructed for >= 5 trajectory questions; decay-vs-jump adjudicated; if decay: lead time quantified (the alarm value); needs per-checkpoint index state - exact where dumps exist, approximate (end-state embeddings, filtration-masked index) elsewhere, approximation validated at the dumps
- Cost - offline-cheap with cached embeddings; GPU if recompute needed

**H431 The correlation screen - which series predict flips (conformist)**
- Mechanism - across ALL trajectory questions and regressions (REG-1 now, medium-ladder additions later), screen every catalog series for temporal precedence vs probe flips (lagged correlation / event-precedence count vs permutation null)
- Grounding - panel doctrine clause (a): a metric earns its place only by predicting probe outcomes; R42 paired forms
- Prediction - <= 3 of the ~16 catalog series carry independent predictive signal; the rest are decoration and get recorded as such
- Bar - precedence table with permutation p-values; the surviving series become the registered alarm panel; UNDERPOWERED verdict allowed at n = 1 regression (registers the medium-ladder replication requirement)
- Cost - offline-cheap

**H432 Component-pollution mechanism (follower)**
- Mechanism - when a gold entity's component merges with a large generic component (shared hub: country, profession), its render/rank position degrades; test on REG-1's entities and any trajectory question whose component merged
- Grounding - H421's membership series; Radovanovic (generic central nodes crowd); H68 (communities braid as cross-doc resolution proceeds)
- Prediction - questions whose gold components underwent a large merge show margin degradation (H430 series) within 20 docs of the merge, vs matched no-merge controls
- Bar - paired comparison merge-vs-control questions; REFUTED if margins are independent of component events (component structure is retrieval-inert - a strong negative worth having)
- Cost - offline-cheap

**H433 Structural profile vs published reference values (follower)**
- Mechanism - compute the When-to-use-Graphs seven-metric profile (non-isolated share, avg degree, degree>k shares, component size, clustering) for the 2wiki pile per checkpoint and at 200 docs; compare against the published HotpotQA/GraphRAG-Bench values
- Grounding - When-to-use-Graphs: non-isolated ~0.40 / component ~2.1-2.7 predicts graph adds noise; 0.66/3.99 predicts graph pays
- Prediction - the KGF 2wiki graph profiles ABOVE the published HotpotQA extraction (KGF's extraction is denser); the profile trend over ingest is toward the graph-pays region, making "the graph got structurally worse" implausible as the REG-1 cause
- Bar - profile table + trend; contextualizes every other verdict against the only published reference values
- Cost - offline-cheap

### Family D - embedding-space dynamics: crowding and hubness

**H434 Hubness trajectory (conformist)**
- Mechanism - N_k skewness (k = 10) of the entity/passage vector index per checkpoint + hub set churn (top-1% N_k identity overlap between checkpoints)
- Grounding - Radovanovic (skewness grows with intrinsic dimensionality; sharpens as points accumulate); S3 open slot
- Prediction - skewness rises monotonically with corpus size; a rise ACCELERATION or hub-identity churn event falls inside the REG-1 window
- Bar - skewness series with bootstrap CI + churn series; priced per H425; decoration verdict if flat
- Cost - offline-cheap with cached vectors, else GPU

**H435 Hub capture of the question region (conformist)**
- Mechanism - for the REG-1 query embedding, track the top-16 list composition per checkpoint: which entities ENTER between 135 and 154, their N_k (are they hubs), their label (are they generic)
- Grounding - Radovanovic (hubs match everything; anti-hubs become unretrievable); REG-1 fact: films retrieved, directors not
- Prediction - the entrants that displaced the director carriers are high-N_k generic entities (other films / country / list-like nodes) semantically irrelevant to the question
- Bar - displacement census with N_k and relevance labels; REFUTED if entrants are low-N_k and genuinely relevant (then the regression is corpus semantics, not geometry)
- Cost - offline-cheap

**H436 Crowding is thematic density, not hubness (contrarian within-family)**
- Mechanism - claim: the displacement mechanism is local crowding (2wiki's schema-uniform film passages piling into one embedding region), not global hubness - measure local intrinsic dimensionality / neighborhood density around the REG-1 query vs random queries over ingest
- Grounding - Radovanovic separates distance concentration from hubness; 2wiki docs are near-clones structurally
- Prediction - local density around film-comparison queries grows >= 3x faster than around random trajectory queries; global N_k skewness (H434) moves little - the pathology is local
- Bar - paired local-vs-global density series; whichever of H434/H436 wins owns the Family E fix design
- Cost - offline-cheap with cached vectors

**H437 Hubness-correction retro-fix (follower)**
- Mechanism - apply a standard hubness reduction (mutual proximity or local scaling re-ranking) to the frozen 200-doc index and replay the prober
- Grounding - hubness-reduction literature descended from Radovanovic (mutual proximity is the standard cheap fix); pure retriever-side lever
- Prediction - REG-1 retro-flips (director carriers re-enter top-16) with zero regressions on the passing trajectory questions
- Bar - retro-flip + zero regressions on the full trajectory set; a Family F smoking gun if it flips with the graph untouched
- Cost - offline-cheap

### Family E - causal/repair: what to do when a shift is detected

**H438 Alarm-triggered targeted audit (follower)**
- Mechanism - when a priced alarm fires, emit a suspect set = DeltaCon-Attr top nodes ∩ merge-log slice ∩ gold-neighborhood; LLM-audit only that set (<= 10 elements); repair verified by probe replay
- Grounding - DeltaCon-Attr; H91 audit lineage; the foundry self-audit doctrine (graph = quality controller)
- Prediction - for REG-1 the suspect set is <= 10 elements and contains the actionable defect (missing director link, mis-merge, or confirms no graph defect)
- Bar - suspect-set size + probe-replay outcome after repair; REFUTED if the set is large or empty of actionable defects
- Cost - offline-LLM (small)

**H439 Bridge synthesis on fragmentation alarm (follower)**
- Mechanism - when H421-class component events implicate a fragment split (the H370 creator-gap class: parent-tier bridges absent), synthesize the missing bridge edge from signature overlap and re-probe
- Grounding - H370 verdict (embedding-kNN missed exactly the parent-tier bridge that cost recall); H364/H365 fragment lineage
- Prediction - on the pile's detected fragment pairs, synthesized bridges flip >= 1 regressed question without regressions
- Bar - flip + zero-regression + bounded edge growth (<= 1%); gated on H421 actually finding fragmentation events
- Cost - offline-LLM

**H440 Ingest-time quarantine replay (contrarian on repair timing)**
- Mechanism - claim: acting AT the alarm beats repairing after - replay ingest with the burst/alarm document(s) in 136-154 quarantined (merges deferred until a post-doc probe passes); REG-1 never regresses
- Grounding - H426 burst docs; prober-in-the-loop is the S1 open slot made operational
- Prediction - quarantining the flagged docs prevents the flip at 154 while full ingest reproduces it - the regression is attributable to specific documents' immediate integration, not to cumulative mass
- Bar - two replay arms (quarantine vs control) at matched final corpus; flip prevented + no new regressions; expensive - queue behind H426/H427 verdicts
- Cost - offline-LLM (partial re-ingest)

**H441 Class-scoped k escalation on margin alarm (follower)**
- Mechanism - when the H430 margin alarm fires for a question class, escalate top_k for that class only (bounded token budget), leaving global k unchanged
- Grounding - H430 margin lead time; H53 vector@16 bar and budget discipline; escalation-gate lineage (sota.md)
- Prediction - class-scoped k = 32 retro-flips REG-1 at <= 15% mean context growth over the trajectory set, where global k = 32 costs >= 2x that
- Bar - retro A/B on the frozen pile; flip + budget clause; REFUTED if even k = 64 does not surface the directors (then ranking, not budget, is the wall - back to Family D)
- Cost - offline-cheap

### Family F - contrarian and heretical

**H442 The graph is innocent - pure index crowding (contrarian)**
- Mechanism - claim: every graph-structural series is flat through (135, 154] while the embedding-side series (H430 margin, H434/H436 density) move - the regression is entirely vector-index geometry; the "graph forensics" framing is a category error for REG-1
- Grounding - H429's sharp version (path exists at 200 docs where retrieval fails); Radovanovic; R09 precedent that structural signals underperform on this system
- Prediction - H429 path holds; H424/H422/H419 quiet in-window at priced thresholds; H430 margin decays smoothly; H437 retro-fix flips REG-1 with the graph untouched
- Bar - the conjunction above; CONFIRMED reroutes the retriever-side solution (the user's stated destination) to index geometry and demotes graph alarms for this regression class
- Cost - offline-cheap (rides A-D instruments)

**H443 The doc-counter null (contrarian)**
- Mechanism - claim: structural alarms are epiphenomena of document count - a bare doc-count threshold predicts pass→fail transitions as well as any structural series (both are monotone in t; correlation is guaranteed, information is not)
- Grounding - single-regression regime (n = 1 event) makes every monotone series a perfect retrodictor; standard confound in change-point retrodiction
- Prediction - on REG-1 alone, doc count matches every catalog series on retrodiction; only the medium-ladder multi-regression set can separate them - and there, structural series beat the counter on <= 1 of 3+ regressions
- Bar - formal null model in the H431 screen: every claimed predictor must beat the doc-counter on HELD-OUT regressions, not on REG-1; this candidate is the screen's null hypothesis made explicit
- Cost - offline-cheap

**H444 Identity event, not topology event (contrarian)**
- Mechanism - claim: the merge log ALONE localizes REG-1 - a specific Bayesian merge in docs 136-154 absorbed or re-pointed a director carrier (extraction-variance duplicate merged into the wrong parent), and no graph-level series is needed
- Grounding - H107 (71% extraction variance); 286 merges on 200 docs is a high identity-event rate; H428's exact log vs the approximate filtration
- Prediction - the merge slice for 136-154 contains >= 1 merge touching 'Perry Bhandal', 'Frank Launder', or either film's neighborhood, and reverting it retro-flips REG-1
- Bar - merge-slice census + single-revert replay; CONFIRMED routes the fix to the resolver (threshold/veto), not the retriever
- Cost - offline-cheap

**H445 There is no phase shift - smooth dilution, discrete instrument (heretical)**
- Mechanism - claim: REG-1-class regressions are continuous rank dilution crossing a discrete top-k threshold; the "sharp drop" is an artifact of binary probing; every change-point any detector reports in the window is overfitting to noise around a smooth trend
- Grounding - H430's margin construction; the prober's binary threshold; Radovanovic's monotone (not phase-like) hubness growth
- Prediction - the H430 margin series is smooth (no step > 3 sigma of its own increments) across the window for REG-1; detectors that fire in-window fire equally on permuted-order controls (H447's machinery)
- Bar - margin smoothness test + detector-on-null comparison; CONFIRMED retires "phase shift" language, makes the margin trend THE alarm, and reduces this round to Families C/D
- Cost - offline-cheap

**H446 Dense probing dominates all structural forensics (heretical)**
- Mechanism - claim: the cheapest sufficient instrument is the prober itself run every document (not every ~20) plus the margin metric - it localizes any regression to one document with zero structural machinery; the entire catalog adds nothing decision-relevant at equal cost
- Grounding - probe cost ~0.4 s/question (trajectory jsonl); 200 docs x 20 questions x 0.4 s ≈ 27 min of probing per ingest; R09's panel-doctrine precedent that structural metrics keep failing clause (a)
- Prediction - per-document probing localizes REG-1 to a single triggering document; no Family A/B series adds localization precision or lead time beyond what the margin series already gives
- Bar - head-to-head localization precision and lead time, probing-only vs probing+structure, at matched compute; CONFIRMED caps this research direction honestly (probe density is the lever, structure is decoration); REFUTED if structural alarms give >= 10-doc lead time the margin cannot
- Cost - offline-cheap

**H447 Alarms are corpus-schema signatures - the permutation control (contrarian)**
- Mechanism - claim: 2wiki's uniform film/director schema mechanically produces "anomalies" (bursts, condensation, novelty clusters) on ANY ingest order, regressions or not; re-run the filtration analysis on document-order permutations - alarms follow the schema arrival, REG-1's flip follows something else
- Grounding - H76's registered order-dependence question (identity diverges, retrieval may not); Tria (novelty bursts are corpus properties); standard permutation-null discipline
- Prediction - across >= 3 order permutations (filtration-level shuffles; full re-ingests only if promoted), alarm positions move with the documents that carry them while the regression boundary moves independently - alarm-flip co-location in the real order is coincidence unless it survives permutation
- Bar - permutation co-location test at p < 0.05; this is the specificity control every Family B candidate must eventually pass
- Cost - offline-cheap (filtration permutations); offline-LLM if re-ingest arms promoted

### Sequencing sketch

H418 first (the instrument everything rides). Then the cheap parallel batch: H419-H424, H426, H428-H430, H433-H436 (all offline on the filtration + dumps + cached embeddings). H425/H427/H431/H443/H447 are the discipline layer priced onto those series. H429 and H430 are the ROUTERS - their joint verdict (path held vs broke; margin decayed vs jumped) decides whether Families D/F or A/B/E own REG-1 before any repair candidate spends. Family E queues behind its trigger families. H442/H444/H445 adjudicate from the same artifacts at near-zero marginal cost. H446 runs last as the honest cap on the round. Medium-scale ladder replication (more regressions) is the standing dependency for H431/H443 - registered now, adjudicated when the ladder lands.

## 6. Source register

New papers archived this round (PDF + digest in `references/papers/`, %PDF verified):

1. `[paper] Graph Evolution Densification, 2006-03.pdf` - densification power law a in 1.11-1.68, shrinking effective diameter, Forest Fire model (arXiv physics/0603229)
2. `[paper] DeltaCon Graph Similarity, 2013-04.pdf` - principled O(E) graph similarity, edge-submodularity axiom, node/edge attribution (arXiv 1304.4657)
3. `[paper] LAD Laplacian Change Point Detection, 2020-07.pdf` - Laplacian singular spectrum + dual sliding windows, short-term events vs long-term regime changes (arXiv 2007.01229)
4. `[paper] Detecting Change Points in Evolving Networks, 2014-03.pdf` - GHRG + Bayes factor, bootstrap-calibrated alarms, scalar stats miss structural rearrangements (arXiv 1403.0989)
5. `[paper] Bose-Einstein Condensation in Networks, 2000-11.pdf` - fitness model phases, hub condensation, k_max/E order parameter (arXiv cond-mat/0011224)
6. `[paper] Error and Attack Tolerance, 2000-08.pdf` - robust-yet-fragile, diameter doubles at 5% targeted hub removal, <s> ~ 2 fragmentation signature (arXiv cond-mat/0008064)
7. `[paper] Dynamics of Correlated Novelties, 2013-10.pdf` - Polya urn with triggering, Heaps beta = 1/alpha Zipf coupling, shuffle-null burst test (arXiv 1310.1953)
8. `[paper] MIDAS Edge Stream Anomalies, 2019-11.pdf` - O(1)/edge CMS chi-squared burst detection, priced false-positive bounds, 162-644x faster (arXiv 1911.04464)
9. `[paper] When to use Graphs in RAG, 2025-06.pdf` - structure-based graph quality metrics, non-isolated share 0.41 / component size 2.11 (HotpotQA) predicts graph adds noise (arXiv 2506.05690)
10. `[paper] Hubs in Space kNN Hubness, 2010-09.pdf` - N_k skewness grows with intrinsic dimensionality, hubs near data mean, kNN retrieval pathology (JMLR v11)

Internal grounding: `reports/experiments/bench/regression-ledger.md` (REG-1), `reports/experiments/bench/progressive-probe-trajectory.jsonl`, `data/interim/dumps/` (three boundary dumps), `docs/experiments/kgf-redesign-experiments.md` (R09 H61-H80, H47, H91, H107, H351, H370 lineage), `docs/kgf-sota.md` (Metrics discipline), `reports/experiments/adjudicated/r42-metrics-framework-literature-brief-20260711.md` (paired designs, MDE, registry).

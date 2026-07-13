# GNN Pattern-Matching Scout Brief (R50 axis, 2026-07-14)

Scout grounding for a FUTURE GNN-pattern-matching hypothesis block, triggered by user direction (2026-07-14): "a GNN might also be able to detect patterns and match them, but it would require some different architecture that we may need to research." This is a read-only scout: it grounds the axis in external SOTA, prices it on our hardware, and drafts gated hypotheses for later registration. It registers nothing.

## Pivotal context: the R50 FREE gates already fired

The R50 oracle/feasibility gates (`reports/experiments/r50/`, dated 2026-07-13, PROPOSED verdicts pre-adjudication) largely CLOSED the exact typed-topology axis before any GNN work begins. A GNN scout has to reckon with these first:

- **H583 topology oracle - KILLED** at the HARD SUB-CAP: gold-path-resolvability < 50% on compositional/bridge. The self-extracted graph does not contain the gold relation SEQUENCES - H107 extraction variance broke buildability. The exact typed path is physically absent for most multi-hop probes
- **H584 type oracle - DOMAIN-CLOSED (KILL)**: oracle type-restricted re-rank delta < +2pp; type is already priced into dense via the '{type}:' prefix
- **H585 relation-linker - GATE-BEHIND-CONSOLIDATION band**: best true coverage 0.5217 at <=20% false-alignment, ceiling 0.5652 at any threshold - below the 60% OPEN bar, above the 40% KILL floor. Relation-first is buildable only behind a relation-consolidation round
- **H586 separability - NULL CONFIRMED**: dense@16 carrier misses are NOT recoverable by type

**Why this MOTIVATES rather than kills the GNN axis.** Every one of those gates tests whether the EXACT gold vocabulary/topology is present and useful. They failed for two reasons a learned soft matcher is built to attack: (a) the extracted relation vocabulary does not match gold names (H585 partial coverage, H583 resolvability), and (b) exact type is redundant with dense (H584/H586). A GNN pattern-matcher's entire reason to exist is SOFT, vocabulary-invariant pattern matching that tolerates the H107/H585 mismatch. So the GNN axis is not refuted by H583 - it is the named escape route from H583's failure mode. The honest boundary: H583's hard sub-cap is partly a statement about the DATA (the answer edge is often absent from the extracted graph), and no matcher, learned or not, can traverse an edge that does not exist. A GNN can only help on the residual where the answer IS reachable but the exact typed path is noisy.

## Axis findings

### Axis 1 - Expressiveness: what pattern matching actually requires

- **Can GNNs Count Substructures? (2020)** proves MPNNs / 2-WL / 2-IGN **cannot induced-subgraph-count any connected pattern of >=3 nodes** (no triangles, cycles, or 3-paths as motifs); they **can count star-shaped patterns**. k-WL / k-IGN can count at k-fold cost; Local Relational Pooling recovers counting locally
- **ESAN (2022)** is the standard escape: represent a graph as a BAG of subgraphs (egonet / node-deleted / edge-deleted policy), process with equivariant DSS layers, provably above 1-WL (DSS-WL / DS-WL). Cost is K x forward passes for K subgraphs
- **Takeaway for KGF**: the user's "different architecture" intuition is a theorem. A vanilla GNN cannot see the 2-hop bridge or two-star comparison SHAPE that defines the 2wiki classes; a KGF GNN-matcher would have to be a subgraph-GNN or higher-order. MITIGATING FACT: 91% of KGF's recalled evidence is hop-0 (star-shaped), which plain message passing CAN count - so the expensive expressiveness is needed only on the thin multi-hop / comparison residual, exactly the H592/H593 slice, exactly where training data is thinnest

### Axis 2 - Graph matching networks: the learned query-to-data alignment

- **GMN (2019)**: cross-graph attention - each node in graph A attends over all nodes in graph B at every layer, computing a pair jointly. This is the strongest form and it is PAIRWISE O(|A| x |B|), uncacheable; the indexable embedding-only variant is strictly weaker
- **NeuroMatch (2020)**: order embeddings turn subgraph containment (NP-complete) into a coordinate-wise partial-order test, **100x faster** than combinatorial matching, **+18%** over approximate baselines. A cheap "does the data graph contain this typed shape?" primitive, node-anchored
- **Takeaway for KGF**: GMN cross-graph attention is literally R50's "map the query's speculative topology onto the graph topology" - but the accurate variant is query-time and uncacheable, colliding with the fuse-never-seed / precompute-at-ingest doctrine. NeuroMatch's order-embedding containment test is the transferable, cacheable idea and maps onto H595 (structural-negative certificate) and H583 (topology existence)

### Axis 3 - Path / query-conditioned KG reasoning

- **NBFNet (2021, in library)**: learned Bellman-Ford over relation paths; inductive, interpretable evidence paths; trained per relation vocabulary
- **A*Net (2023)**: NBFNet + a learned A* priority function - visits **10% of nodes / 10% of edges** per step, first path reasoner to scale to **ogbl-wikikg2 (2.5M entities, 16M triples)**. Its learned priority is a "PPR with a brain"
- **GraIL (2020)**: scores a triple from the enclosing subgraph around the (h,t) pair using NO entity embeddings - fully inductive, represents a useful subset of first-order logic; GraIL+KGE ensembling helps on CLEAN KGs
- **Takeaway for KGF**: A*Net's headline is SCALE, which is not KGF's problem (6,626 entities - PPR is already cheap); the only question is whether a learned priority beats isotropic PPR, needing training labels we lack. GraIL is the learned form of H592's typed walk, but conditions on a clean relation type - it inherits the H585 fragmentation head-on. RED-GNN / AdaProp (not downloaded - incremental refinements of the same adaptive-propagation idea) do not change this verdict

### Axis 4 - KG foundation models with vocabulary transfer (the ULTRA line)

- **ULTRA (2023, in library)**: relation-INVARIANT - represents relations by a graph-of-relations (head-head / tail-tail co-occurrence), stores no per-graph embeddings, **177k params**, zero-shot MRR **0.395** across 57 KGs beating supervised-SOTA 0.344
- **GFM-RAG (2025, in library)**: query-dependent GNN for RAG retrieval, **8M params**, pretrained on **60 KGs / >14M triples / 700k docs**, single-step zero-shot retrieval, EXPLICITLY designed robust to graph noise and incompleteness
- See the ULTRA-vs-H585 assessment below - this is the crux zero-training arm

### Axis 5 - GNN-for-RAG hybrids

- **GNN-RAG (2024, in library)**: GNN scores answer candidates over a dense KG subgraph, verbalizes shortest paths to an LLM; beats GPT-4 ToG on WebQSP (90.7 vs 82.6 Hit) at ~9x fewer tokens - but needs THOUSANDS of QA training examples and wins on many-hop / many-entity, a bottleneck KGF does not have (91% hop-0)
- **SubgraphRAG (2024, in library)**: lightweight MLP + triple-scorer + structural distance encoding over a CURATED KG; WebQSP F1 78.2 with GPT-4o - assumes a pre-existing clean graph
- **G-Retriever (2024)**: retrieves a CONNECTED subgraph via Prize-Collecting Steiner Tree (query-relevance prizes on nodes/edges, budget-bounded connected subtree), then a GNN soft-prompt to a frozen LLM. The PCST connectivity guarantee is the transferable idea for R50's Step-2 region (bridge/comparison must link two entities); the soft-prompt arm violates Failure Mode A (no LLM in the retrieval loop)
- **Takeaway for KGF**: reported GNN-RAG deltas are all on curated Freebase-class graphs with abundant QA training, and their compute assumes a trained retriever. Their published wins are on the many-hop regime KGF lacks. A PCST-over-cosine region selector is the one training-free, LLM-free mechanism worth lifting

### Axis 6 - The contrarian file (confirmed LOW, as predicted)

- Published negative/parity results where GNN retrievers fail to beat walks/PPR/BM25 are SPARSE - the GNN-RAG literature is a win-reporting field. The honest contrarian anchors are: **When to Use Graphs in RAG (2025, in library)** - graph methods help only in specific regimes; **HippoRAG / HippoRAG-2** use isotropic PPR (no GNN) and beat many learned methods; and KGF's own nulls - **H95** (node2vec 0.365, below chance for identity at 2.8k nodes; fusion HURTS), **H545/H556/H573/H100** (every structural functional collapses to seed-hop-distance, Spearman 0.91)
- **Over-squashing is NOT the risk here.** Over-squashing (Alon-Yahav; sdrf, in library) is a LONG-range, many-hop phenomenon. At 2-hop with 91% hop-0 evidence it does not bite - which is the single point mildly FAVORING a GNN at this scale. Say so plainly

## ULTRA-vs-H585 assessment

H585 measured that only ~52-57% of gold query-implied relations align to a native extracted relation type at usable precision (<=20% false), ceiling 0.5652 - a direct read of the H107/H395 vocabulary mismatch (334 native relation types, entropy 6.22). A relation-NAME-conditioned matcher (GraIL, a relation-linker, a typed-PPR relation arm) inherits this ceiling and fragments.

ULTRA and GFM-RAG are relation-INVARIANT by construction: they never embed a relation by its name. ULTRA builds a graph-of-relations from co-occurrence topology; GFM-RAG runs a query-dependent GNN designed to be noise-robust. In principle this SIDESTEPS the H585 name-alignment wall entirely - the matcher pattern-matches on relation-INTERACTION structure, not labels, so the 334-vs-gold vocabulary mismatch never has to be resolved by name.

The honest catch: ULTRA does not escape the H107 variance, it transfers it UP one level. The graph-of-relations it builds is derived from the SAME noisy self-extracted edges - if the extraction scatters one true relation across many surface types (H395 entropy 6.22) and duplicates entities into different neighborhoods (H95's anti-correlation finding), then the relation-interaction meta-graph ULTRA reasons over is itself corrupted. ULTRA's own digest flags the degradation-toward-chance risk on thin/noisy relation graphs. So the assessment is: **ULTRA/GFM-RAG are the ONLY zero-training arms that could pattern-match on KGF's graph without paying the H585 name-alignment tax, and they are therefore the mandatory first test - but the prior is a null, because relation-invariance moves the H107 noise from the labels to the meta-topology rather than removing it.** GFM-RAG's explicit noise-robustness design claim is exactly the claim to falsify against H583's kill; it is the single most deployable checkpoint to try.

## Compute realism (our hardware)

- **Idle cards confirmed**: RTX PRO 4000 Blackwell (24GB, sm_120) idle, RTX 5000 Ada (32GB, sm_89) idle; PRO 6000 (97GB) currently 100% busy. Two idle cards for this axis
- **Zero-training inference** (ULTRA 177k params, GFM-RAG 8M params) over 6,626 entities / 35,637 rels is trivial - seconds to a few minutes on one idle card. This is the cheapest-rung arm and prices the entire axis FREE-ish before any training spend
- **Training data reality**: the labeled signal is ~132 probe-flip outcomes plus 2wiki-medium gold evidence paths (~1000 questions with gold triples). Is that enough? Honestly NO for a from-scratch GNN: GNN-RAG needs thousands of QA examples, GFM-RAG pretrains on 60 KGs / 14M triples, and H95 already showed from-scratch structural embeddings go BELOW chance at 2.8k nodes. The only admissible training route is thin FINE-TUNING of a pretrained relation-invariant head on the ~1000 gold-path pairs, and even that carries a real overfitting risk at n~1000 (expect H582-style CI straddling 0 on held-out probes). From-scratch training is infeasible and should not be proposed
- **Sequencing**: zero-training inference FIRST (kills the axis FREE if no signal), fine-tuning only on demonstrated residual, cross-graph-attention re-rank (GMN) last because it is uncacheable

## Sharpest kill-risks

1. **Data-absence dominates (the H583 kill).** Gold-path-resolvability < 50% means the answer edge is physically ABSENT from the extracted graph on the multi-hop slice. No matcher can walk a missing edge. A GNN helps only on {reachable-at-all} minus {already reached by isotropic PPR} - a thin residual that must be measured (H589 recovery-gap) before any build
2. **Expressiveness is needed exactly where data is thinnest.** The substructure-counting theorem says a plain GNN cannot match multi-node patterns, so KGF needs a subgraph-GNN - but 91% hop-0 evidence is star-shaped (plain-GNN-countable), so the costly expressiveness is spent only on the multi-hop / comparison residual, which is also the smallest labeled slice
3. **Training starvation.** n~132 probe labels is 1-2 orders of magnitude below every published GNN-retriever regime; H95 is the standing local precedent that from-scratch structure loses at this scale
4. **Vocabulary + redundancy wall.** H584/H586 say type is redundant with dense; H585 caps name-alignment at ~52-57%. Relation-conditioned matchers fragment; relation-invariant matchers (ULTRA) transfer the H107 noise to the meta-topology
5. **Honest-control collapse.** The mandated control (beat H592 typed-PPR) is itself gated on H583, which is proposed-KILLED - so H592 may never run. The honest fallback control becomes isotropic PPR (H515, reachability 0.622, +18.9pp) plus the H481 relation boost. A learned matcher that cannot beat FREE isotropic PPR at matched candidate budget is dead on the H556 rule
6. **Cacheability.** GMN cross-graph attention (the strongest learned matcher, the user's "different architecture") is O(query x region) and uncacheable - admissible only as a query-time re-rank of a bounded candidate set (H594 budget), and only if accuracy justifies abandoning precompute-at-ingest

## Draft gated hypotheses

See the accompanying scout return (final message) for the full house-template drafts HG1-HG5. In brief, gated in cheapest-first order:

- **HG1 (CRUX, zero-training)**: relation-invariant GFM-RAG/ULTRA inference recovers the reachable-but-noisy residual that H583's exact oracle could not; must beat isotropic PPR (H515) at matched budget. Gate: H583 adjudication leaves a reachable residual AND H589 shows a recovery gap. Kills the whole GNN axis FREE if no signal
- **HG2 (expressiveness necessity)**: a 1-WL plain-GNN scorer matches an ESAN subgraph-GNN on our probes (expressiveness buys nothing because evidence is star-shaped) - NULL-leaning, comparison-class the only possible win. Gate: HG1 shows signal
- **HG3 (soft negative certificate, training-free)**: NeuroMatch order-embedding containment over FROZEN embeddings beats H595's exact typed-path precision because soft geometry tolerates H585 variance. Gate: H585 partial-coverage AND H595 false-abstention residual
- **HG4 (fine-tune on residual)**: thin fine-tuning of a pretrained relation-invariant head on ~1000 2wiki gold paths lifts recovery over HG1 beyond the overfitting floor (held-out CI excludes 0). Gate: HG1 clears its bar (cheapest-rung V4 first)
- **HG5 (cross-graph attention re-rank, last)**: a GMN-style cross-graph attention re-rank of the query's speculative subgraph against seed egonets lifts comparison/bridge recall over soft-PPR at matched budget. Gate: HG1+HG4 beat PPR AND H590 attributes residual loss to region-map; admissible only as a bounded query-time re-rank

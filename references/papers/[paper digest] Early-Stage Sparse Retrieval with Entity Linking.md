**Early-Stage Sparse Retrieval with Entity Linking (2022)**

The paper expands MS MARCO queries and passages (8.8M passages) with linked entity names to narrow the effectiveness gap between BM25 and dense retrievers, tested on the Dev set (6,980 queries) plus three "Chameleons" hard-query subsets (Hard 3,119 / Harder 2,473 / Hardest 1,693 queries that resist improvement under most rankers). Best result: three-way Reciprocal Rank Fusion (no-entity + explicit-entity + hashed-entity BM25 runs) lifts recall@1000 by **3.44% (Dev), 6.97% (Hard), 7.36% (Harder), 8.38% (Hardest)** over plain BM25, all statistically significant (paired t-test, p<0.05).

**Key mechanism**
- ELQ (zero-shot end-to-end entity linking, BERT bi-encoder built on BLINK) links entity mentions in both queries and passages to Wikipedia entities in a single pass
- Passages processed with a sliding window (128-token context, 42-token stride, ~1/3 overlap) since ELQ targets short questions; the resulting entity set per passage is deduplicated
- Each retrieved entity appended once (single copy) to the query/passage text in two parallel forms: explicit word form and an MD5-hashed form - hashing gives multi-word terms a consistent single token, avoiding partial or wrong matches
- Three separate BM25 (Anserini, k1=0.82, b=0.68) runs generated - no entities, explicit entities, hashed entities - then combined with Reciprocal Rank Fusion (RRF)

**Main findings**
- Single-copy entity expansion beats weighted or constant-factor expansion (factor 5 gives worse recall than factor 3) - one clean mention per entity is optimal
- Explicit-entity BM25 alone already beats no-entity BM25 on every set: recall@1000 0.8682 vs 0.8573 (Dev), 0.7467 vs 0.7234 (Hard), 0.7079 vs 0.6849 (Harder), 0.6389 vs 0.6136 (Hardest)
- Hashed-entity BM25 alone is worse than baseline (0.8479 Dev) but fuses well: RRF of no-entity + hashed-entity already beats all three individual runs, evidence the hashed run retrieves complementary passages
- Best result is RRF across all three runs: recall@1000 0.8868 (Dev), 0.7738 (Hard), 0.7353 (Harder), 0.6650 (Hardest)
- Oracle (best of the three runs per query, upper bound) still exceeds the best RRF by 2.47% (Dev), 5.44% (Hard), 6.45% (Harder), 8.57% (Hardest) - headroom remains for smarter run selection
- Dense retrieval (ANCE) still leads outright (0.9587 Dev, 0.8753 Hardest) but the sparse-dense gap narrows once entity linking is applied
- BM25+PRF is a strong non-entity baseline (0.8759 Dev) but the three-run RRF still surpasses it on Dev/Hard/Harder; PRF edges ahead only on the Hardest set (0.6674 vs 0.6650)

**Key takeaways**
- Explicit and hashed entity-expanded runs retrieve complementary passages the original run misses - this complementarity, not the accuracy of either form alone, is what RRF exploits
- Gains are largest on the hardest query subsets, where lexical-only BM25 is weakest - entity linking directly targets the vocabulary-mismatch failure mode
- R47 relevance: direct published evidence for R47-H509's additive-coverage design - appending one explicit linked-entity form per mention to query and passage, then fusing runs, lifts first-stage recall without discarding the original lexical signal, dodging Failure Mode B (replacing rather than augmenting the base representation)

**Tags**
- #EntityLinking
- #SparseRetrieval
- #FirstStageRetrieval
- #RunFusion

**Source**
- https://arxiv.org/abs/2208.04887
- Local: [paper] Early-Stage Sparse Retrieval with Entity Linking, 2022.pdf

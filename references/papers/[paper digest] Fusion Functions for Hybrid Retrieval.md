**An Analysis of Fusion Functions for Hybrid Retrieval, Bruch (Pinecone), Gai (UC Berkeley), Ingber (Pinecone), 2023-05 (arXiv v2)**

A normalization-agnostic convex combination of lexical and semantic scores (TM2C2: alpha*sem + (1-alpha)*lex, theoretical min-max normalized) beats Reciprocal Rank Fusion on NDCG@1000 across all 9 benchmark datasets tested, with gaps as large as 0.744 vs 0.721 on FEVER and 0.699 vs 0.675 on HotpotQA (both p<0.01). The paper directly refutes an earlier claim (Chen et al. 2022) that convex combination is normalization-sensitive and that RRF is the more robust zero-shot fusion - and shows the single alpha parameter converges with under 5% of training queries.

**Key mechanism**
- Convex combination f_Convex = alpha*f_Sem + (1-alpha)*f_Lex, scores first passed through theoretical min-max normalization phi_tmm - uses the score function's true infimum (0 for BM25, -1 for cosine) rather than the min of the retrieved set, giving TM2C2 (or M2C2 with ordinary min-max when no theoretical minimum exists, e.g. Tas-B)
- Theorem 4.5 proves rank-equivalence: for any two monotone normalization choices with a uniform relative expansion rate, there exists an alpha' making the two convex combinations produce identical rankings - so min-max, z-score, and theoretical min-max only shift where the optimal alpha sits, they do not change the achievable ranking quality
- RRF is reframed as parametric rather than the "non-parametric zero-shot" view in prior literature: f_RRF = 1/(eta_Lex+pi_Lex) + 1/(eta_Sem+pi_Sem) has two free parameters (one per retrieval system), one more than convex combination's single alpha
- RRF operates on rank, not score, discarding score-distribution information; a smoothed-rank variant (SRRF, sigmoid approximation of the indicator function with tunable Lipschitz constant beta) recovers some lost NDCG as beta decreases - direct evidence the RRF gap is a Lipschitz-continuity failure, not a normalization artifact

**Main findings**
- NDCG@1000 (alpha=0.8, eta=60), TM2C2 vs RRF, all differences significant at p<0.01: MS MARCO 0.454 vs 0.425, NQ 0.542 vs 0.514, Quora 0.901 vs 0.877, NFCorpus 0.327 vs 0.312 (@100), HotpotQA 0.699 vs 0.675, FEVER 0.744 vs 0.721, SciFact 0.753 vs 0.730 (@100), DBPedia 0.512 vs 0.489, FiQA 0.496 vs 0.464
- Recall@1000 favors TM2C2 on 6 of 9 datasets, ties on 2 (Quora, FEVER); RRF edges ahead only on HotpotQA (0.888 vs 0.884) and DBPedia (0.567 vs 0.564)
- Tuning RRF's eta_Lex/eta_Sem on in-domain data improves in-domain NDCG (MS MARCO rises to 0.451 with eta=(10,4)) but generalizes poorly out-of-domain: HotpotQA NDCG drops to 0.621 and FEVER to 0.649, both worse than the untuned eta=60 baseline
- TM2C2's alpha converges with under 5% of the training queries regardless of the magnitude of domain shift; RRF's tuned parameters remain sample-sensitive and never close the gap with TM2C2 even after tuning
- alpha in [0.6, 0.8] performs consistently well across all tested datasets without per-dataset tuning
- Oracle per-query alpha leaves substantial headroom over TM2C2 (e.g. MS MARCO oracle NDCG 0.547 vs TM2C2 0.454), so a fixed global alpha is not the ceiling

**Key takeaways**
- Score normalization choice (min-max, z-score, theoretical min-max) is provably rank-equivalent up to a re-parameterization of alpha - the "sensitive to normalization" claim in prior literature does not hold, freeing implementers to pick whichever normalization is convenient
- A single-alpha convex combination is markedly more sample-efficient to tune than parametric RRF - under 5% of training queries vs RRF, which stays parameter-sensitive and underperforms even after tuning
- RRF's information loss traces to discarding raw score magnitude in favor of rank alone, formalized here as a Lipschitz-continuity failure rather than a normalization issue
- Answers KGF's R47 finding directly (H508/H509): RRF-at-matched-budget lost against KGF's own hybrid retriever, the gap H53 left unaddressed. This paper supplies the fix - replace RRF with a normalization-agnostic convex combination alpha*dense + (1-alpha)*sparse, tuned on a small labeled sample or set to alpha in [0.6, 0.8] from domain knowledge with no training at all

**Tags**: #FusionFunctions #HybridRetrieval #RRF #ConvexCombination #ScoreNormalization #LipschitzContinuity

**Source**: https://arxiv.org/abs/2210.11934. Local: [paper] Fusion Functions for Hybrid Retrieval, 2023.pdf

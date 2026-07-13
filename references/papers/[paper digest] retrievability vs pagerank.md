**A Comparative Analysis of Retrievability and PageRank Measures**

Sinha et al. (2023) measure the correlation between document retrievability r(d) and link-based PageRank importance on two collections, finding only **weak positive correlation - Spearman's ρ = 0.07 (Kendall's τ = 0.04) on WT10g, rising to ρ = 0.22 (τ = 0.15) on the much larger Wikipedia collection**. The two metrics quantify discoverability through fundamentally different channels: retrievability via keyword/feature-based search, PageRank via link topology.

**Key mechanism**: Both measures are computed independently per document - r(d) by aggregating rank-weighted utility across a large sampled query set (as in Azzopardi & Vinay 2008), PageRank by the standard link-graph random-walk stationary distribution. Correlation is assessed with rank-based statistics (Kendall's τ, Spearman's ρ, Rank-Biased Overlap) rather than Pearson's, since the two scores are not commensurable in raw magnitude. Lorenz curves visualize inequality in both distributions.

**Main findings**:
- Correlation is consistently low, meaning a document's link-graph centrality is a poor predictor of whether keyword search can actually surface it
- Correlation strengthens with collection size and diversity (0.07→0.22 Spearman from WT10g to Wikipedia), suggesting larger, denser link structures let PageRank and retrievability partially converge, but the relationship remains weak even there
- The two measures capture genuinely distinct notions of document "importance" - neither substitutes for the other

**Key takeaways (relevance to KGF)**: Directly predicts and grounds H573 - a fact-carrier's global graph-centrality proxy (e.g. PPR-mass, node degree, community centrality) is not a reliable stand-in for whether anticipated questions actually surface it. Seed-rank / retrievability-style scoring, computed against the system's own retrieval mechanics, should be expected to beat generic PageRank-family centrality for predicting fact accessibility - this paper is the direct empirical precedent for that expectation, with the correlation numbers as the falsification bar.

**Tags**: retrievability, pagerank, correlation-analysis, retrieval-bias, arXiv-2023

**Source**: https://arxiv.org/abs/2311.10348

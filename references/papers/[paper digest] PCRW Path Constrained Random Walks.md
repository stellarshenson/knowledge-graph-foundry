**Relational Retrieval Using a Combination of Path-Constrained Random Walks (2010)**

Lao and Cohen replace the one-weight-per-edge-label parameterization of Random Walk with Restart (RWR) with the Path Ranking Algorithm (PRA): a linear model that learns **one weight per entire labeled relation-path** ("path expert"), so that e.g. "cited by a paper published in year y" and "published in year y" can be weighted completely differently even though both start with the same edge label. Across eight relational-retrieval tasks on two biological literature graphs (Yeast: 48K papers/164K nodes/2.8M edges; Fly: 127K papers/770K nodes/3.5M edges), the learned path-expert model beats trained RWR by **up to 23.8% relative MAP** on the headline reference-recommendation task (16.9 to 19.8 with the full model) and the paper's own abstract reports **up to 43% MAP improvement** over untrained RWR across the eight tasks combined.

**Key mechanism**
- A relation path P = R1...Rl is a type-correct sequence of graph relations (with type-consistent domain/range chaining); for a query entity set Eq, the path defines a probability distribution h(Eq,P) over reachable entities via iterated relation-following (a per-path random walk distribution, not a single mixed walk)
- Scoring function s(e;θ) = Σ_P h(Eq,P)(e)·θ_P is linear in the per-path weights θ; in matrix form s = Aθ where A is a sparse feature matrix of path-distribution values - all paths up to bounded length l are enumerated as a prefix tree and treated as features for a logistic-regression-style model trained with L-BFGS on binomial log-likelihood
- Two extensions reuse the same scoring machinery: query-independent experts add a synthetic "any-entity" query node so paths like e*→AnyPaper→Cite→paper approximate PageRank/recency signals computed once offline per year, independent of any real query; popular entity experts add per-entity and per-(query-entity, target-entity) bias terms, with an efficient induction strategy that adds only the top-J (J=20) highest-gradient bias parameters per training iteration, capped at 20 induction rounds, to avoid materializing all O(|E|²) possible bias terms
- Negative-sample selection for training uses stratified sampling weighted toward entities ranked highly by an untrained model, since a handful of positives face thousands to millions of negatives per query

**Main findings**
- Untrained-to-trained RWR alone already improves MAP substantially on 6 of 8 tasks (Table 2), e.g. Yeast reference recommendation 11.8 to 16.0 (+35.6%); gene recommendation shows no gain from training on either corpus
- Full PRA+qip+pop model vs. trained RWR (Table 5): Yeast reference recommendation 16.9→19.8 (+23.8%), Yeast expert finding 11.9→12.9 (+16.2%), Fly expert finding 7.6→8.5 (+18.1%); every task improves with both extensions, most improvements significant at p<0.05
- Query-independent and popular-entity experts each independently improve over base PRA on every task, and combine near-additively; popular-entity experts benefit the most from more training data since they carry the largest parameter count
- Path length trades quality for cost exponentially: both model complexity (number of features) and query execution time grow exponentially with max path length L, with practical L fixed at 3-4 across tasks; L2-regularization gives a small additional MAP boost
- Learned feature weights are directly inspectable (Tables 3-4): the model discovers that "papers cited by on-topic papers" (a 2-hop citation path) outweighs direct term overlap for reference recommendation, matching an independently-known effective heuristic from the TREC-CHEM Prior Art Search Task; query-independent citation-count paths get large positive weight (well-cited papers favored) while "any recent paper" paths get strongly negative weight (old papers favored, since publication volume grows yearly)

**Key takeaways**
- Weighting whole typed path sequences rather than individual edge labels is what lets the model separate genuinely different retrieval heuristics that happen to share a first edge label - single-parameter-per-edge RWR structurally cannot express this distinction
- Query-independent path experts are a cheap way to fold PageRank/recency-style global priors into the same linear scoring framework as query-dependent path features, computed once offline
- The top-J gradient-based feature induction strategy is the mechanism that keeps a per-entity bias term tractable despite a combinatorially large parameter space

**Relevance**
- PRA is the learned counterpart to PathSim (also in this batch): instead of hand-choosing a meta path, it learns per-typed-path weights against labeled relevance data - a direct template for a "meta-matching" scheme where KGF calibrates weights per traversal pattern rather than treating every hop type uniformly
- The query-independent expert construction (offline, type-scoped priors reused across queries) maps onto KGF's coverage/gap-ledger priors - a pattern for baking global graph statistics into a query-time score without recomputation
- The top-J feature-induction trick for the popular-entity bias term is a reusable bound if KGF ever moves toward learned per-entity or per-type weighting, avoiding the need to materialize weights for every entity up front

**Tags**
- #PathRankingAlgorithm
- #RandomWalk
- #RelationalRetrieval
- #LearnedPathWeights
- #TypedGraph

**Source**
- Download: https://link.springer.com/content/pdf/10.1007/s10994-010-5205-8.pdf
- Local: [paper] PCRW Path Constrained Random Walks, 2010.pdf

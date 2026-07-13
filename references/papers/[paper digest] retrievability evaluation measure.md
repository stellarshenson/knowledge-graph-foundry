**Retrievability: An Evaluation Measure for Higher Order Information Access Tasks**

Azzopardi and Vinay's CIKM 2008 paper introduces **retrievability**, r(d) - a per-document score counting how many queries (weighted by rank position, via a rank-based utility function such as inverse rank or a cutoff step function) retrieve document d from a collection under a given IR system. Validated on two TREC collections, it reframes evaluation away from pure relevance/effectiveness and toward what a system makes accessible at all.

**Key mechanism**: r(d) = sum over a query set Q of c(k_dq), where c() is a rank-based utility function (e.g. 1 if rank ≤ cutoff, 0 otherwise, or 1/rank) and k_dq is the rank of document d for query q. Because exhaustive querying is intractable, the paper samples a large query set (n-grams/terms drawn from the collection) as a proxy for the space of possible user queries; the resulting distribution of r(d) across all documents characterizes the system's bias.

**Main findings**:
- Retrievability distributions are highly skewed (Lorenz-curve/Gini-quantifiable inequality) - most documents are barely retrievable under any query, a small set dominates
- The shape of the r(d) distribution changes systematically with retrieval-model parameters (e.g. term weighting, smoothing), meaning system tuning directly reallocates which documents are accessible, independent of relevance-based effectiveness scores
- Retrievability bias correlates with retrieval effectiveness in some regimes, letting the measure double as an efficiency-free proxy for tuning

**Key takeaways (relevance to KGF)**: This is the founding instrument H571 ports from document-level to fact-carrier-level - r(d) becomes r(fact), the count/weight of anticipated questions that surface a given fact-carrying node or edge under the retrieval system in use. The core insight (retrieval precedes relevance; a system's own machinery pre-selects what can ever be judged relevant) applies directly to graph retrieval: a fact buried in a low-retrievability region of the graph is invisible to the QA layer regardless of its correctness.

**Tags**: retrievability, IR-evaluation, retrieval-bias, foundational, CIKM-2008

**Source**: https://doi.org/10.1145/1458082.1458157 (no open-access PDF found; ACM paywalled, no self-archived copy at Glasgow Enlighten/eprints, ResearchGate, or Semantic Scholar - abstract sourced from https://eprints.gla.ac.uk/34688/)

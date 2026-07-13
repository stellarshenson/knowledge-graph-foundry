**Retrievability and Retrieval Bias: A Comparison of Inequality Measures**

Wilkie and Azzopardi's ECIR 2015 short paper (LNCS vol. 9022, pp. 209-214) tests **8 inequality measures against the standard Gini coefficient across 3 retrieval models' parameter spaces**, asking whether Gini's single-number summary of retrievability-distribution bias is the right choice or whether alternatives reveal insights it misses.

**Key mechanism**: For each retrieval model (parameterized, e.g. by term weighting or smoothing), the retrievability distribution r(d) over the collection is computed, then reduced to a scalar bias score by each of the 9 inequality measures (Gini plus 8 others drawn from econometrics/inequality literature, including the Palma index and the 20:20 ratio). Measures are compared by whether they agree on which parameter settings minimize retrieval bias.

**Main findings**:
- Most of the 9 measures agree closely on which parameter settings minimize bias - Gini remains a reliable, representative single-number summary
- The Palma index and the 20:20 ratio diverge notably from Gini and from each other, meaning they emphasize different parts of the retrievability distribution (tail concentration vs. overall spread) and can surface different "optimal" settings
- No single alternative measure strictly dominates Gini, but the divergent measures offer a complementary lens on where in the distribution the bias actually concentrates

**Key takeaways (relevance to KGF)**: Establishes Gini-over-retrievability as the standard corpus-health scalar (H575's basis), while flagging that a single Gini number can mask tail-concentrated bias that Palma/20:20-style measures would catch. For KGF's fact-carrier retrievability, this argues for reporting Gini as the primary health metric but keeping a tail-sensitive secondary measure (e.g. Palma-style ratio) in reserve for diagnosing whether bias is broadly distributed or concentrated in a few catastrophically under-retrievable fact-carriers.

**Tags**: retrievability, retrieval-bias, gini-coefficient, inequality-measures, ECIR-2015

**Source**: https://doi.org/10.1007/978-3-319-16354-3_22 (no open-access PDF found; Springer paywalled, no self-archived copy at Strathprints, Strathclyde Pure portal, or ResearchGate (403); Semantic Scholar confirms openAccessPdf status CLOSED - abstract/findings sourced from Strathclyde Pure portal record)
